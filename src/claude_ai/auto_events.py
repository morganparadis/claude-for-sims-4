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

from . import config, event_generator, storyteller, notifications

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


# ---------------------------------------------------------------------------
# Game state check
# ---------------------------------------------------------------------------

def _in_active_game():
    """Return True only if the player is in a live household, not on a menu or loading."""
    try:
        import services
        if services.current_zone() is None:
            return False
        if services.active_household() is None:
            return False
        # Don't fire during build/buy mode
        if services.current_zone().is_in_build_buy:
            return False
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Event dispatch
# ---------------------------------------------------------------------------

def _pick_and_fire():
    """Choose a random event type from the configured list and fire it."""
    types = get_event_types()
    if not types:
        return

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


# ---------------------------------------------------------------------------
# Background thread
# ---------------------------------------------------------------------------

def _worker():
    """Sleeps for the configured interval, then maybe fires an event."""
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

        # Sleep in small chunks so we can respond to stop() quickly
        elapsed = 0
        interval = get_interval_seconds()  # re-read each cycle in case config reloaded
        while _running and elapsed < interval:
            time.sleep(5)
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
