"""
Configuration loader for Claude AI mod.
Reads from claude_config.cfg in the Mods folder.
"""
import os
import configparser

_config = None
_CONFIG_FILENAME = "claude_config.cfg"


def _find_config_file():
    """Search for config file relative to this script, walking up directories."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    search_dirs = [
        script_dir,
        os.path.join(script_dir, ".."),
        os.path.join(script_dir, "..", ".."),
        os.path.join(script_dir, "..", "..", ".."),
    ]
    for d in search_dirs:
        path = os.path.join(d, _CONFIG_FILENAME)
        if os.path.isfile(path):
            return os.path.abspath(path)
    return None


def get_config():
    global _config
    if _config is None:
        _config = configparser.ConfigParser()
        path = _find_config_file()
        if path:
            _config.read(path)
    return _config


def reload_config():
    global _config
    _config = None
    return get_config()


def get_api_key():
    return get_config().get("claude_ai", "api_key", fallback="")


def get_default_model():
    return get_config().get("claude_ai", "default_model", fallback="claude-opus-4-6")


def get_fast_model():
    return get_config().get("claude_ai", "fast_model", fallback="claude-haiku-4-5")


def get_max_tokens():
    return get_config().getint("claude_ai", "max_tokens", fallback=512)


def get_language():
    return get_config().get("claude_ai", "language", fallback="English")


def is_configured():
    key = get_api_key()
    return bool(key and key != "YOUR_API_KEY_HERE")
