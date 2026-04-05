"""
Claude AI for The Sims 4
Brings AI-powered dialogue, storytelling, and dynamic events to your game.

Commands (open cheat console with Ctrl+Shift+C):
  claude.status     — check setup and see all commands
  claude.dialogue   — generate sim dialogue
  claude.story      — household narrative update
  claude.storyline  — 3-act storyline
  claude.event      — surprise random event
  claude.challenge  — gameplay challenge
  claude.chat <msg> — chat about your game
"""

MOD_NAME = "Claude AI for The Sims 4"
MOD_VERSION = "1.0.0"

try:
    import sims4.commands
    from . import commands   # noqa: F401 — registers all claude.* cheat commands
    from . import auto_events

    auto_events.start()  # starts only if auto_events_enabled = true in config

    sims4.commands.output(
        f"[{MOD_NAME}] v{MOD_VERSION} loaded — type 'claude.status' to get started.",
        None,
    )
except ImportError:
    pass
