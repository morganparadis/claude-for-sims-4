"""
Displays text to the player via Sims 4 UI notifications.
Falls back to cheat console output if the UI isn't available.

Note: Sims 4 notifications have a character limit, so long text gets truncated.
The full text is always echoed to the cheat console as a fallback.
"""

# Max chars to show in a notification popup before it looks bad
_NOTIFICATION_MAX_CHARS = 800


def _truncate(text, max_chars=_NOTIFICATION_MAX_CHARS):
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "…\n[See cheat console for full text]"


def _show_game_notification(title, message):
    """
    Attempt to show an in-game notification popup.
    Returns True on success, False if unavailable.
    """
    try:
        import sims4.localization
        import ui.ui_dialog_notification
        import services

        client = services.client_manager().get_first_client()
        if client is None:
            return False

        display_text = _truncate(message)

        notification = ui.ui_dialog_notification.UiDialogNotification.TunableFactory().default_factory(
            client.active_sim,
            text=lambda **_: sims4.localization.LocalizationHelperTuning.get_raw_text(display_text),
            title=lambda **_: sims4.localization.LocalizationHelperTuning.get_raw_text(title),
        )
        notification.show_dialog()
        return True
    except Exception:
        return False


def _console_output(text, connection=None):
    """Write to cheat console if possible."""
    try:
        import sims4.commands
        sims4.commands.output(text, connection)
    except Exception:
        pass


def show(title, message, output=None):
    """
    Show a message to the player.

    Tries the in-game notification popup first.
    Always also echoes to the cheat console (via output or fallback).

    Args:
        title:   Short heading string
        message: Body text
        output:  sims4.commands.CheatOutput instance (optional but recommended)
    """
    _show_game_notification(title, message)

    # Always echo full text to console so nothing is lost to truncation
    full_text = f"[Claude AI — {title}]\n{message}"
    if output:
        output(full_text)
    else:
        _console_output(full_text)


def show_error(message, output=None):
    show("Error", message, output=output)


def show_result(feature_name, text, output=None):
    show(feature_name, text, output=output)
