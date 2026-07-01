"""
In-game interaction log.

Hooks `relationships.relationship_objects.relationship.Relationship.add_relationship_bit`
so we know when sims add social bits to each other (Just Chatted, Just
Flirted, Just Argued, Just Kissed, etc). For pairs where at least one
participant is in the active household, we record the timestamp + bit
name. One entry per (sim_a, sim_b) pair, key sorted so it's symmetric;
each new interaction OVERWRITES the previous entry. File stays bounded
no matter how much the household socializes.

Prompt builders ask `most_recent_for_pair(sim_a, sim_b)` -- if the
returned timestamp is newer than the last journal entry between those
sims, surface "they just X'd in person" in the prompt.

Storage: <save folder>/Interactions.json -- per-save, alongside the
journal and milestones files. Atomic .tmp + os.replace writes match the
journal hardening pattern.

Verified hook signature in simulation.zip/relationships/relationship_-
objects/relationship.pyc:
  add_relationship_bit(self, actor_sim_id, target_sim_id, bit_to_add,
                       notify_client, pending_bits, force_add,
                       from_load, send_rel_change_event)
sim ids come in as positional args, NOT attributes on self.
"""

import datetime
import json
import os
import re
import threading

from . import save_id as _save_id

_FILENAME = "Interactions.json"

# Match bits that signal a recent social interaction. Patterns derived
# from real-game diagnostic logs -- the engine doesn't use a single
# naming convention so we match a set of known interaction-indicator
# words/phrases. Substring (not prefix) match: Sims 4 prefixes bit names
# with "Special Bits", "relbit", category names, etc., and CC mods like
# WickedWhims prepend their own tags. Patterns checked case-insensitively
# against the cleaned bit name.
#
# Tested signals seen in logs:
#   "Special Bits  Greeted"                  -> first contact in a convo
#   "relbit  Social Context  Casual"         -> active conversation state
#   "T U R B O D R I V E R: ...  Recently Had Social Interaction"
#                                            -> WickedWhims STC tag
# Excluded (don't match):
#   "multi unit neighbor", "neighbor"        -> permanent state
#   "rel Bit  Attraction ..."                -> internal calc
#   "relationshipbit  Compatibility  Bad"    -> compat calc result
#   "romantic-  Significant  Other"          -> family/partner state
_INTERACTION_BIT_PATTERN = re.compile(
    r"\b(Just|Recently|Made|Greeted|Social\s*Context)\b",
    re.IGNORECASE,
)


# Map cleaned bit names to a natural English phrase for the prompt.
# "You {phrase} in person recently." -- so the phrase reads as a verb
# clause without "just" repeating. Falls back to a generic phrasing
# when an unknown bit slips through the filter.
def _humanize_kind(cleaned):
    lower = (cleaned or "").lower()
    if "kissed" in lower or "made out" in lower:
        return "kissed"
    if "flirt" in lower:
        return "flirted"
    if "fight" in lower or "argued" in lower or "argument" in lower:
        return "had an argument"
    if "woohoo" in lower:
        return "had an intimate moment"
    if "chat" in lower:
        return "chatted"
    if "greeted" in lower:
        return "saw each other"
    if "romantic" in lower and "context" in lower:
        return "shared a romantic moment"
    if "social context" in lower or "had social" in lower:
        return "had a conversation"
    if "recently" in lower:
        return "spent time together"
    if "just" in lower:
        # Generic "Just X" -- pull out the X and prepend "just"
        tail = lower.split("just", 1)[1].strip()
        if tail:
            return "just " + tail
    return "spent time together"

# How old an entry can get before cleanup_old will trim it. Sized so
# even a long-running save's file stays small and a stale entry doesn't
# misleadingly surface "they interacted recently" days later.
_RETENTION_DAYS = 30


# In-memory cache + the save id it was loaded for. Same pattern as journal.py.
_cache = None
_cached_for_save_id = None
_lock = threading.RLock()

# True after install_hook patches Relationship.add_relationship_bit.
_hook_installed = False


def _log(message):
    """Best-effort log line into the main Llamafone_Log.txt."""
    try:
        path = os.path.join(os.path.expanduser("~"), "Documents", "Llamafone_Log.txt")
        with open(path, "a", encoding="utf-8") as f:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{ts}] [interactions] {message}\n")
    except Exception:
        pass


def _path():
    """Per-save Interactions.json path; None when no save is loaded."""
    return _save_id.data_path(_FILENAME)


def _pair_key(sim_a_id, sim_b_id):
    """Sorted-pair key so lookups are symmetric. Returns 'min:max' as a
    string so it survives JSON serialization without losing precision on
    64-bit sim ids."""
    a, b = int(sim_a_id), int(sim_b_id)
    if a > b:
        a, b = b, a
    return f"{a}:{b}"


def _clean_bit_name(bit_to_add):
    """Turn the bit class reference into a human-readable string for
    pattern matching and humanization. Sims 4's bit class names are
    like `RelationshipBit_Friendship_JustChatted` or
    `Special_Bits_Greeted`; CC mods prepend their own tags. We strip
    well-known prefixes, split CamelCase, and collapse runs of
    whitespace so the result is loosely-natural English."""
    raw = getattr(bit_to_add, "__name__", "") or str(bit_to_add)
    raw = re.sub(r"^(RelationshipBit_|Relationship_Bit_)", "", raw)
    raw = re.sub(r"^(Friendship|Romance|Family|Conflict|Romantic)_", "", raw)
    # Insert a space before each interior uppercase letter (CamelCase split)
    spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", raw).replace("_", " ")
    # Collapse multi-space runs to single spaces, then strip ends.
    spaced = re.sub(r"\s+", " ", spaced).strip()
    return spaced


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
            return  # no save loaded
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


def record(sim_a_id, sim_b_id, kind):
    """Record (or overwrite) the most-recent interaction between two
    sims. Keyed by sorted pair, so direction doesn't matter."""
    if sim_a_id is None or sim_b_id is None or sim_a_id == sim_b_id:
        return
    with _lock:
        data = _load()
        data[_pair_key(sim_a_id, sim_b_id)] = {
            "timestamp": datetime.datetime.now().isoformat(),
            "kind": str(kind) if kind else "",
        }
        _save(data)


def most_recent_for_pair(sim_a_id, sim_b_id):
    """Return {'timestamp': iso8601, 'kind': str} for the last logged
    interaction between this pair, or None if no entry."""
    if sim_a_id is None or sim_b_id is None:
        return None
    return _load().get(_pair_key(sim_a_id, sim_b_id))


def cleanup_old(days=_RETENTION_DAYS):
    """Drop entries older than `days` days from the on-disk file.
    Idempotent; safe to call on every save load."""
    with _lock:
        data = _load()
        if not data:
            return
        cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
        cutoff_iso = cutoff.isoformat()
        before = len(data)
        keep = {k: v for k, v in data.items()
                if isinstance(v, dict) and v.get("timestamp", "") >= cutoff_iso}
        if len(keep) < before:
            _save(keep)
            _log(f"cleanup_old: trimmed {before - len(keep)} entries older than {days} days")


# ---------------------------------------------------------------------------
# Live hook
# ---------------------------------------------------------------------------

def _is_in_active_household(sim_id):
    """True if `sim_id` belongs to a sim in the currently-active household
    (the one the player is controlling)."""
    if sim_id is None:
        return False
    try:
        import services
        hh = services.active_household()
        if hh is None:
            return False
        for si in hh.sim_info_gen():
            if getattr(si, "sim_id", None) == sim_id:
                return True
    except Exception:
        pass
    return False


def install_hook():
    """Monkey-patch Relationship.add_relationship_bit so every bit add
    also fires our recorder. Idempotent. Returns True on success or if
    already patched, False if the Relationship class can't be imported.

    Verified against the game class on this patch (2026-06-17):
      relationships.relationship_objects.relationship.Relationship
      .add_relationship_bit(self, actor_sim_id, target_sim_id,
                            bit_to_add, ...)
    The sim ids come in as positional args; we don't read self for them.
    """
    global _hook_installed
    if _hook_installed:
        return True
    try:
        from relationships.relationship_objects.relationship import Relationship
    except Exception as e:
        _log(f"install_hook: cannot import Relationship: {type(e).__name__}: {e}")
        return False
    if getattr(Relationship, "_llamafone_interactions_hooked", False):
        _hook_installed = True
        return True
    original = Relationship.add_relationship_bit

    def _patched(self, actor_sim_id, target_sim_id, bit_to_add, *args, **kwargs):
        result = original(self, actor_sim_id, target_sim_id, bit_to_add, *args, **kwargs)
        try:
            # Skip sim<->object relationships (e.g. sim's relationship
            # with their gravestone). We only care about sim<->sim.
            if getattr(self, "is_object_rel", False):
                return result
            # Filter: at least one participant must be in the active
            # household. Avoids logging NPC-on-NPC interactions the
            # player will never see in a prompt.
            if not (_is_in_active_household(actor_sim_id)
                    or _is_in_active_household(target_sim_id)):
                return result
            cleaned = _clean_bit_name(bit_to_add)
            # Only "Just X'd" / "Recently Y'd" / "Greeted" / "Social
            # Context X" style bits -- see _INTERACTION_BIT_PATTERN for
            # the verified set. Permanent state bits (Spouse, Neighbor,
            # Attraction) don't indicate a fresh interaction.
            if not _INTERACTION_BIT_PATTERN.search(cleaned):
                return result
            record(actor_sim_id, target_sim_id, cleaned)
        except Exception as e:
            _log(f"hook handler failed: {type(e).__name__}: {e}")
        return result

    Relationship.add_relationship_bit = _patched
    Relationship._llamafone_interactions_hooked = True
    _hook_installed = True
    _log("installed Relationship.add_relationship_bit hook")
    return True


# ---------------------------------------------------------------------------
# Prompt-helper
# ---------------------------------------------------------------------------

def format_for_prompt(sim_a_id, sim_b_id, last_conv_iso=None):
    """Return a single bracket-tagged line for inclusion in a phone prompt,
    or empty string if no relevant entry exists.

    If `last_conv_iso` (the timestamp of the most-recent journal entry
    for this pair) is provided, only surface the entry if the recorded
    interaction is NEWER than that conversation -- otherwise the AI
    would just be told what it already wrote about in the last text.
    """
    entry = most_recent_for_pair(sim_a_id, sim_b_id)
    if not entry:
        return ""
    ts = entry.get("timestamp", "")
    if last_conv_iso and ts <= last_conv_iso:
        return ""
    phrase = _humanize_kind(entry.get("kind", ""))
    return f"\n[RECENT CONTACT: You {phrase} in person recently.]"
