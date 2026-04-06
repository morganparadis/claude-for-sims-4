"""
Claude AI for The Sims 4
Brings AI-powered dialogue, storytelling, and dynamic events to your game.

Commands (open cheat console with Ctrl+Shift+C):
  claude.status     -- check setup and see all commands
  claude.dialogue   -- generate sim dialogue
  claude.story      -- household narrative update
  claude.storyline  -- 3-act storyline
  claude.event      -- surprise random event
  claude.challenge  -- gameplay challenge
  claude.call       -- incoming call from a relationship sim
  claude.text       -- text message from a relationship sim
  claude.chat <msg> -- chat about your game
"""

MOD_NAME = "Claude AI for The Sims 4"
MOD_VERSION = "1.1.0"


def _log(message):
    """Write to a log file in Documents -- the only reliable way to surface errors."""
    import os, datetime
    try:
        path = os.path.join(os.path.expanduser("~"), "Documents", "ClaudeAI_Log.txt")
        with open(path, "a", encoding="utf-8") as f:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{ts}] {message}\n")
    except Exception:
        pass


try:
    _log("Starting mod load...")

    import sims4.commands
    import threading
    from . import commands   # noqa: F401 -- registers all claude.* cheat commands
    from . import auto_events

    auto_events.start()  # starts only if auto_events_enabled = true in config

    _log("All modules imported, commands registered.")

    # Console output fires immediately as a fallback
    sims4.commands.output(
        f"[{MOD_NAME}] v{MOD_VERSION} loaded -- type 'claude.status' to get started.",
        None,
    )

    # Deferred in-game notification -- waits for the game client to be ready
    def _deferred_startup_notification():
        import time
        for attempt in range(30):  # up to ~60 seconds
            time.sleep(2)
            try:
                import services
                client = services.client_manager().get_first_client()
                if client and client.active_sim:
                    from . import notifications, config
                    _log(f"Game client ready (attempt {attempt + 1}), showing startup notification.")
                    if config.is_configured():
                        body = (
                            f"v{MOD_VERSION} ready!\n"
                            f"Model: {config.get_default_model()}\n"
                            f"Type 'claude.status' in the cheat console for all commands."
                        )
                        notifications.show(MOD_NAME, body)
                    else:
                        body = (
                            f"v{MOD_VERSION} loaded but NOT configured.\n"
                            f"Edit claude_config.cfg and add your API key,\n"
                            f"then type 'claude.reload' in the cheat console."
                        )
                        notifications.show(MOD_NAME, body)
                    return
            except Exception as inner:
                _log(f"Startup notification attempt {attempt + 1} failed: {type(inner).__name__}: {inner}")
        _log("Startup notification gave up after 60 seconds -- no active sim found.")

    threading.Thread(
        target=_deferred_startup_notification,
        daemon=True,
        name="ClaudeAI-Startup",
    ).start()

except Exception as e:
    _log(f"FAILED TO LOAD: {type(e).__name__}: {e}")
    try:
        import sims4.commands
        sims4.commands.output(f"[{MOD_NAME}] FAILED TO LOAD: {type(e).__name__}: {e}", None)
    except Exception:
        pass
