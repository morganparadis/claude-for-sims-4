"""
Auto-events — randomly fires event/story prompts while you play without you having to ask.

Uses a real-time background thread (not Sims game-time) so "every 20 minutes" means
20 real-world minutes of having the game open, regardless of game speed.

The thread checks whether you're actually in an active household before firing anything,
so it won't trigger during loading screens, CAS, or build mode.

Config options (in claude_config.cfg):
  auto_events_enabled        = true / false
  auto_event_interval_minutes = 20        (real-world minutes between checks)
  auto_event_chance           = 40        (percent chance each check fires something)
  auto_event_types            = event,goals  (comma-separated: event, goals, story, drama)
"""

import random
import threading
import time

from . import config, event_generator, storyteller, notifications, phone

_thread = None
_running = False
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def is_enabled():
    return config.get_config().getboolean("claude_ai", "auto_events_enabled", fallback=False)

def get_interval_seconds():
    minutes = config.get_config().getfloat("claude_ai", "auto_event_interval_minutes", fallback=20.0)
    return max(5.0, minutes) * 60  # minimum 5 minutes

def get_chance():
    return config.get_config().getint("claude_ai", "auto_event_chance", fallback=40)

def get_event_types():
    raw = config.get_config().get("claude_ai", "auto_event_types", fallback="event,goals")
    return [t.strip().lower() for t in raw.split(",") if t.strip()]

def get_event_weights():
    """
    Read per-type weights from config. Format: event:30, call:40, text:20, goals:10
    If no weights are configured, all types get equal weight.
    """
    raw = config.get_config().get("claude_ai", "auto_event_weights", fallback="")
    weights = {}
    if raw.strip():
        for part in raw.split(","):
            part = part.strip()
            if ":" in part:
                name, val = part.split(":", 1)
                try:
                    weights[name.strip().lower()] = int(val.strip())
                except ValueError:
                    pass
    return weights


# ---------------------------------------------------------------------------
# Game state check
# ---------------------------------------------------------------------------

def _is_game_paused():
    """Return True if the game clock is paused."""
    try:
        import services
        from clock import ClockSpeedMode
        clock = services.game_clock_service()
        if clock and clock.clock_speed == ClockSpeedMode.PAUSED:
            return True
    except Exception:
        pass
    return False


def _in_active_game():
    """Return True only if the player is in a live, unpaused household."""
    try:
        import services
        if services.current_zone() is None:
            return False
        if services.active_household() is None:
            return False
        if services.current_zone().is_in_build_buy:
            return False
        if _is_game_paused():
            return False
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Event dispatch
# ---------------------------------------------------------------------------

def _pick_and_fire():
    """Choose a random event type using configured weights and fire it."""
    types = get_event_types()
    if not types:
        return

    weights_map = get_event_weights()
    if weights_map:
        # Use configured weights (types not in weights_map get weight 0 and are skipped)
        weighted_types = [t for t in types if weights_map.get(t, 0) > 0]
        if not weighted_types:
            weighted_types = types  # fallback if all weights are 0
        w = [weights_map.get(t, 1) for t in weighted_types]
        chosen = random.choices(weighted_types, weights=w, k=1)[0]
    else:
        # No weights configured — equal chance
        chosen = random.choice(types)

    def on_result(text, error):
        if error:
            # Silent failure for auto-events — don't interrupt the player with errors
            return
        label = {
            "event": "Random Event!",
            "goals": "Today's Goals",
            "story": "Story Update",
            "drama": "Household Drama",
        }.get(chosen, "Claude AI")
        notifications.show_result(label, text)

    if chosen == "event":
        event_generator.generate_random_event(callback=on_result)
    elif chosen == "goals":
        event_generator.generate_weekly_goals(callback=on_result)
    elif chosen == "story":
        storyteller.generate_story_update(callback=on_result)
    elif chosen == "drama":
        storyteller.generate_relationship_drama(callback=on_result)
    elif chosen == "call":
        phone.generate_call()  # phone module handles its own notifications
    elif chosen == "text":
        phone.generate_text()  # phone module handles its own notifications


# ---------------------------------------------------------------------------
# Background thread
# ---------------------------------------------------------------------------

def _worker():
    """Sleeps for the configured interval, then maybe fires an event.
    Timer only ticks while the game is actively running (not paused)."""
    interval = get_interval_seconds()
    # Stagger the first fire so it doesn't happen immediately on load
    time.sleep(min(interval, 120))

    while _running:
        if _in_active_game() and config.is_configured():
            chance = get_chance()
            if random.randint(1, 100) <= chance:
                try:
                    _pick_and_fire()
                except Exception:
                    pass

        # Sleep in small chunks; only count time when game is unpaused
        elapsed = 0
        interval = get_interval_seconds()
        while _running and elapsed < interval:
            time.sleep(5)
            if not _is_game_paused():
                elapsed += 5


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start():
    """Start the auto-event background thread if enabled in config."""
    global _thread, _running
    with _lock:
        if not is_enabled():
            return
        if _thread and _thread.is_alive():
            return  # already running
        _running = True
        _thread = threading.Thread(target=_worker, daemon=True, name="ClaudeAI-AutoEvents")
        _thread.start()


def stop():
    """Stop the auto-event background thread."""
    global _running
    _running = False


def restart():
    """Stop and restart — call this after reloading config."""
    stop()
    time.sleep(0.1)
    start()


def status():
    """Return a status string for claude.status output."""
    if not is_enabled():
        return "Auto-events: OFF  (set auto_events_enabled = true to turn on)"
    active = _thread is not None and _thread.is_alive()
    interval = get_interval_seconds() / 60
    types = ", ".join(get_event_types()) or "none"
    chance = get_chance()
    state = "running" if active else "stopped"
    return (
        f"Auto-events: ON ({state}) — "
        f"every ~{interval:.0f} min, {chance}% chance, types: {types}"
    )
