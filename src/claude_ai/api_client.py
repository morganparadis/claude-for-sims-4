"""
Claude API HTTP client.
Uses urllib (Python stdlib) since pip packages aren't available in Sims 4's Python runtime.
All calls are made on a background thread to avoid freezing the game.
"""
import json
import threading
import urllib.request
import urllib.error

from . import config

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"


def _extract_text(response_data):
    try:
        return response_data["content"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return ""


def call_claude_async(messages, system=None, use_fast_model=False, callback=None):
    """
    Make an async call to the Claude API on a background thread.

    Args:
        messages: list of {"role": "user"|"assistant", "content": str}
        system:   optional system prompt string
        use_fast_model: if True, uses fast_model from config (Haiku) instead of default
        callback: function(text: str | None, error: str | None) called when done

    Returns the background Thread object.
    """
    def _request():
        api_key = config.get_api_key()
        if not config.is_configured():
            if callback:
                callback(None, "No API key configured. Edit claude_config.cfg in your Mods folder.")
            return

        model = config.get_fast_model() if use_fast_model else config.get_default_model()
        max_tokens = config.get_max_tokens()

        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": _API_VERSION,
        }
        body = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            body["system"] = system

        req = urllib.request.Request(
            _API_URL,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = _extract_text(data)
                if callback:
                    callback(text, None)

        except urllib.error.HTTPError as e:
            try:
                err_body = json.loads(e.read().decode("utf-8"))
                msg = err_body.get("error", {}).get("message", str(e))
            except Exception:
                msg = str(e)
            if callback:
                callback(None, f"API error {e.code}: {msg}")

        except urllib.error.URLError as e:
            if callback:
                callback(None, f"Network error: {e.reason}")

        except Exception as e:
            if callback:
                callback(None, f"Unexpected error: {type(e).__name__}: {e}")

    thread = threading.Thread(target=_request, daemon=True, name="ClaudeAI-Request")
    thread.start()
    return thread
