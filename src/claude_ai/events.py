"""
Read upcoming household calendar events that two sims are both attending.

The Sims 4 calendar is exposed via `services.calendar_service()`. Each entry
is a drama-node-derived object stored in `_event_data_map`. Useful fields:

  event.uid                      -- unique event id
  event.get_calendar_start_time()  -- TimeStamp (sim time)
  event.get_calendar_end_time()    -- TimeStamp or None
  event.get_calendar_sims()        -- iterable of SimInfo
  event.ui_display_data.name       -- LocalizedString (the player-facing label)

We use that to find events that BOTH the contact and the recipient are
invited to, so phone prompts can include lines like "I'll see you at the
funeral later." We never invent events that aren't actually on the calendar.
"""
from . import sim_context


def _get_calendar_service():
    try:
        import services
        return services.calendar_service()
    except Exception:
        return None


def _get_now():
    try:
        import services
        ts = services.time_service()
        if ts is None:
            return None
        return ts.sim_now
    except Exception:
        return None


def _sim_id(sim_info):
    try:
        return sim_info.id
    except Exception:
        try:
            return sim_info.sim_id
        except Exception:
            return None


def _resolve_event_name(event):
    """Best-effort plain-string name for a calendar event. Falls back to
    a tidy class name if the localized display data isn't available."""
    try:
        ud = getattr(event, "ui_display_data", None)
        if ud is not None:
            raw = getattr(ud, "name", None)
            if raw is not None:
                resolved = sim_context._resolve_localized_string(raw)
                if resolved:
                    return resolved
    except Exception:
        pass
    # Fallback: class name (e.g. "PlayerPlannedDramaNode" -> "Planned event")
    try:
        cls_name = type(event).__name__
        if cls_name.endswith("DramaNode"):
            cls_name = cls_name[:-len("DramaNode")]
        cls_name = cls_name.replace("_", " ").strip()
        return cls_name or "Event"
    except Exception:
        return "Event"


def _format_time_until(start_time, now):
    """Return a short human-readable 'in X hours' / 'tomorrow' string.
    Returns None if the time math fails or the event is in the past."""
    try:
        delta = start_time - now
        # date_and_time.TimeSpan -- get total minutes
        if hasattr(delta, "in_minutes"):
            mins = int(delta.in_minutes())
        elif hasattr(delta, "in_hours"):
            mins = int(delta.in_hours() * 60)
        else:
            return None
        if mins <= 0:
            return "happening now"
        if mins < 60:
            return f"in {mins} minutes"
        hours = mins // 60
        if hours < 24:
            return f"in {hours} hours" if hours > 1 else "in about an hour"
        days = hours // 24
        if days == 1:
            return "tomorrow"
        if days < 7:
            return f"in {days} days"
        return f"in about {days // 7} week" + ("s" if days // 7 != 1 else "")
    except Exception:
        return None


def get_shared_upcoming_events(recipient_sim_info, contact_sim_info, max_events=3):
    """Return a list of upcoming calendar events that both sims are
    invited to. Each item is a dict with name + when_string.

    Quietly returns [] if the calendar service isn't ready, either sim
    is missing, or no shared events exist. The caller drops the result
    into the prompt only when non-empty.
    """
    if recipient_sim_info is None or contact_sim_info is None:
        return []
    recipient_id = _sim_id(recipient_sim_info)
    contact_id = _sim_id(contact_sim_info)
    if recipient_id is None or contact_id is None:
        return []

    cal = _get_calendar_service()
    if cal is None:
        return []
    now = _get_now()
    if now is None:
        return []

    data_map = getattr(cal, "_event_data_map", None)
    if not data_map:
        return []

    results = []
    try:
        for event_ref in data_map.values():
            try:
                event = event_ref() if callable(event_ref) else event_ref
            except Exception:
                continue
            if event is None:
                continue
            try:
                start = event.get_calendar_start_time()
            except Exception:
                continue
            if start is None:
                continue
            # Past events are irrelevant
            try:
                if start < now:
                    continue
            except Exception:
                pass

            try:
                sims = event.get_calendar_sims() or ()
                attendee_ids = {_sim_id(si) for si in sims if si is not None}
            except Exception:
                continue
            if recipient_id not in attendee_ids or contact_id not in attendee_ids:
                continue

            name = _resolve_event_name(event)
            when = _format_time_until(start, now) or "soon"
            results.append({"name": name, "when": when, "start": start})
    except Exception:
        return results

    # Sort by soonest first and cap
    try:
        results.sort(key=lambda r: r["start"])
    except Exception:
        pass
    return results[:max_events]


def format_shared_events_for_prompt(recipient_sim_info, contact_sim_info):
    """Build a small prompt block listing upcoming events both sims are
    invited to, or "" if there aren't any. The model can use this to
    naturally reference shared upcoming plans ('see you at the funeral
    later') without inventing events that aren't actually scheduled."""
    events = get_shared_upcoming_events(recipient_sim_info, contact_sim_info)
    if not events:
        return ""
    lines = [
        "Upcoming events you are BOTH attending (feel free to reference these "
        "naturally; do not invent events not listed here):"
    ]
    for ev in events:
        lines.append(f"  - {ev['name']} ({ev['when']})")
    return "\n".join(lines)
