"""
Past-event memory for shared calendar events.

Sims 4's CalendarService removes one-off social events (funerals, weddings,
parties, dinners) from `_event_data_map` once they end -- so by the time
the AI generates dialogue the next day, the calendar can't tell us "what
funeral did we both just attend." Holidays repeat yearly and stay, but
social events vanish.

This module keeps a side-file per save (`PastEvents.json`) of events the
mod observed via drama-node lifecycle hooks, so we can surface "you both
attended X recently" for a few in-game days after the event ends.

Hook strategy:

  Monkey-patch `BaseDramaNode._setup` so EVERY drama node instance
  registers our recorder via `self.add_callback_on_complete_func`. The
  engine then calls our recorder when the node completes, regardless of
  the specific drama-node subclass (dinner parties, weddings, funerals,
  player-planned events, holidays — all flow through BaseDramaNode).

  The previous attempt patched `PlayerPlannedDramaNode._run` and
  `.cleanup` -- these are internal lifecycle methods that didn't fire
  for dinner parties. Verified the right approach against the game's
  drama_node.pyc on 2026-06-17:
    add_callback_on_complete_func(fn) ==> self._callbacks_on_complete.append(fn)
  i.e. the canonical public registration point.

Storage: `<save folder>/PastEvents.json`, atomic .tmp + os.replace writes,
RLock-guarded against concurrent record/read.
"""

import datetime
import json
import os
import threading

from . import save_id as _save_id


_FILENAME = "PastEvents.json"

# Retention window for old entries. In-game days, not real-world. After
# this many in-game days past the event start, the entry gets dropped on
# the next cleanup pass.
_RETENTION_IN_GAME_DAYS = 30

# How far back to surface events as "recent" when building a prompt.
# In-game days.
_RECENT_WINDOW_IN_GAME_DAYS = 5

# Ticks per minute in Sims 4's DateAndTime math. Documented in the
# game's date_and_time module; the conversion ratio is stable.
_TICKS_PER_MINUTE = 100


_cache = None
_cached_for_save_id = None
_lock = threading.RLock()
_hook_installed = False


def _log(message):
    """Best-effort log line into the main Llamafone_Log.txt."""
    try:
        path = os.path.join(os.path.expanduser("~"), "Documents", "Llamafone_Log.txt")
        with open(path, "a", encoding="utf-8") as f:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{ts}] [past_events] {message}\n")
    except Exception:
        pass


def _path():
    """Per-save PastEvents.json path; None when no save is loaded."""
    return _save_id.data_path(_FILENAME)


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def _load():
    with _lock:
        global _cache, _cached_for_save_id
        current = _save_id.get_current_save_id()
        if _cache is not None and _cached_for_save_id == current:
            return _cache
        _cached_for_save_id = current
        path = _path()
        if path is None or not os.path.exists(path):
            _cache = {}
            return _cache
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            _cache = data if isinstance(data, dict) else {}
        except Exception as e:
            _log(f"_load: parse failed ({type(e).__name__}: {e}); starting fresh")
            _cache = {}
        return _cache


def _save(data):
    with _lock:
        global _cache, _cached_for_save_id
        _cache = data
        _cached_for_save_id = _save_id.get_current_save_id()
        path = _path()
        if path is None:
            return
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except Exception:
                    pass
            os.replace(tmp, path)
        except Exception as e:
            _log(f"_save failed: {type(e).__name__}: {e}")
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# DateAndTime helpers
# ---------------------------------------------------------------------------

def _ticks_of(start_time):
    """Pull a numeric tick value out of a Sims 4 DateAndTime object so we
    can persist and compare across sessions. Different versions expose
    the same number through slightly different attrs."""
    if start_time is None:
        return None
    for attr in ("absolute_ticks", "value", "ticks"):
        fn = getattr(start_time, attr, None)
        if callable(fn):
            try:
                return int(fn())
            except Exception:
                continue
        if fn is not None:
            try:
                return int(fn)
            except Exception:
                continue
    # Last-ditch: many DateAndTime reprs look like "DateAndTime(123456)"
    try:
        raw = str(start_time)
        if "(" in raw and raw.endswith(")"):
            return int(raw.split("(")[-1][:-1])
    except Exception:
        pass
    return None


def _now_ticks():
    try:
        import services
        ts = services.time_service()
        now = getattr(ts, "sim_now", None) if ts else None
        return _ticks_of(now)
    except Exception:
        return None


def _ticks_to_minutes(ticks):
    if ticks is None:
        return None
    try:
        return ticks // _TICKS_PER_MINUTE
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def record_seen(event_id, name, start_time, attendee_ids, honored=None, is_holiday=False):
    """Record/update a single event. Keyed by event_id so repeated calls
    for the same event just refresh the snapshot (newer attendee list etc.)"""
    if event_id is None or not name:
        return
    start_ticks = _ticks_of(start_time)
    if start_ticks is None:
        return
    try:
        with _lock:
            cache = _load()
            cache[str(event_id)] = {
                "event_id": str(event_id),
                "name": name,
                "start_ticks": start_ticks,
                "attendees": list(attendee_ids or []),
                "honored": list(honored or []),
                "is_holiday": bool(is_holiday),
                "logged_at": datetime.datetime.now().isoformat(),
            }
            _save(cache)
    except Exception as e:
        _log(f"record_seen failed: {type(e).__name__}: {e}")


def get_recent_for(sim_a_id, sim_b_id, max_days=_RECENT_WINDOW_IN_GAME_DAYS):
    """Return events where (a) start_ticks is in the past, (b) start is
    within max_days in-game days of now, and (c) BOTH sims appear in
    the attendees list. Newest first."""
    if sim_a_id is None or sim_b_id is None:
        return []
    cache = _load()
    if not cache:
        return []
    now_ticks = _now_ticks()
    if now_ticks is None:
        return []
    cutoff_minutes = max_days * 24 * 60
    matches = []
    for entry in cache.values():
        try:
            start_ticks = entry.get("start_ticks")
            if start_ticks is None or start_ticks >= now_ticks:
                continue
            mins_ago = _ticks_to_minutes(now_ticks - start_ticks)
            if mins_ago is None or mins_ago > cutoff_minutes:
                continue
            attendees = entry.get("attendees") or []
            if sim_a_id not in attendees or sim_b_id not in attendees:
                continue
            entry_copy = dict(entry)
            entry_copy["_mins_ago"] = mins_ago
            matches.append(entry_copy)
        except Exception:
            continue
    matches.sort(key=lambda e: e.get("start_ticks", 0), reverse=True)
    return matches


def cleanup_old(max_days=_RETENTION_IN_GAME_DAYS):
    """Drop entries with start_ticks older than max_days in-game days."""
    try:
        with _lock:
            cache = _load()
            if not cache:
                return 0
            now_ticks = _now_ticks()
            if now_ticks is None:
                return 0
            cutoff_minutes = max_days * 24 * 60
            before = len(cache)
            keep = {}
            for key, entry in cache.items():
                try:
                    start_ticks = entry.get("start_ticks")
                    if start_ticks is None:
                        keep[key] = entry
                        continue
                    if start_ticks >= now_ticks:
                        keep[key] = entry
                        continue
                    mins_ago = _ticks_to_minutes(now_ticks - start_ticks)
                    if mins_ago is None or mins_ago <= cutoff_minutes:
                        keep[key] = entry
                except Exception:
                    keep[key] = entry
            dropped = before - len(keep)
            if dropped:
                _save(keep)
                _log(f"cleanup_old: dropped {dropped}, kept {len(keep)}")
            return dropped
    except Exception as e:
        _log(f"cleanup_old failed: {type(e).__name__}: {e}")
        return 0


# ---------------------------------------------------------------------------
# Prompt-helper
# ---------------------------------------------------------------------------

def format_for_prompt(sim_a_id, sim_b_id):
    """Return a multi-line block listing recent events both sims attended,
    or empty string if none. Used by the phone prompt builders."""
    events = get_recent_for(sim_a_id, sim_b_id)
    if not events:
        return ""
    lines = ["Recent events you both attended:"]
    for e in events[:4]:  # cap at 4 most-recent so the prompt doesn't bloat
        name = e.get("name") or "Event"
        mins_ago = e.get("_mins_ago", 0)
        days_ago = mins_ago // (24 * 60)
        if days_ago == 0:
            when = "today"
        elif days_ago == 1:
            when = "yesterday"
        else:
            when = f"{days_ago} sim days ago"
        honored = e.get("honored") or []
        honor_str = f" (in memory of {', '.join(honored)})" if honored else ""
        lines.append(f"  - {name}{honor_str} -- {when}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Hook installation
# ---------------------------------------------------------------------------

def _record_from_drama_node(node):
    """Pull metadata off a completed drama node and write it to disk."""
    try:
        from . import events as _events
    except Exception as e:
        _log(f"events module import failed: {type(e).__name__}: {e}")
        return
    try:
        event_id = getattr(node, "uid", None)
        if not event_id:
            return
        try:
            start = node.get_calendar_start_time()
        except Exception:
            return
        if start is None:
            return
        name = _events._resolve_event_name(node)
        if not name:
            return
        attendees = set()
        try:
            sims = node.get_calendar_sims() or ()
            attendees = {_events._sim_id(si) for si in sims if si is not None}
        except Exception:
            pass
        if not attendees:
            return
        honored = []
        try:
            honored = _events._get_honored_sims(node, event_name_for_log=name)
        except Exception:
            pass
        record_seen(
            event_id=event_id,
            name=name,
            start_time=start,
            attendee_ids=list(attendees),
            honored=honored,
            is_holiday=False,
        )
    except Exception as e:
        _log(f"_record_from_drama_node failed: {type(e).__name__}: {e}")


def install_hook():
    """Monkey-patch BaseDramaNode._setup so every drama node instance
    registers our recorder via `add_callback_on_complete_func`. The
    engine then fires the recorder when the node completes, no matter
    which subclass (PlayerPlannedDramaNode, CalendarEventDramaNode,
    etc) was actually instantiated. Idempotent.

    Verified hook against simulation.zip/drama_scheduler/drama_node.pyc
    on 2026-06-17:
      `add_callback_on_complete_func(fn)` appends to `_callbacks_on_complete`,
      which the engine invokes on node completion.
    """
    global _hook_installed
    if _hook_installed:
        return True
    try:
        from drama_scheduler.drama_node import BaseDramaNode
    except Exception as e:
        _log(f"install_hook: BaseDramaNode not importable: {type(e).__name__}: {e}")
        return False
    if getattr(BaseDramaNode, "_llamafone_past_events_hooked", False):
        _hook_installed = True
        return True

    original_setup = BaseDramaNode._setup

    def _patched_setup(self, *args, **kwargs):
        result = original_setup(self, *args, **kwargs)
        try:
            # Register our recorder so the engine calls it when this
            # specific drama-node instance completes. _callbacks_on_complete
            # is initialized by the engine before _setup runs.
            register = getattr(self, "add_callback_on_complete_func", None)
            if register is not None:
                register(_record_from_drama_node)
        except Exception as e:
            _log(f"register failed on {type(self).__name__}: {type(e).__name__}: {e}")
        return result

    BaseDramaNode._setup = _patched_setup
    BaseDramaNode._llamafone_past_events_hooked = True
    _hook_installed = True
    _log("installed BaseDramaNode._setup hook")
    return True
