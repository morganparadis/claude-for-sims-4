"""
Claude API HTTP client.
Uses curl via subprocess since the Sims 4's embedded Python 3.7 lacks SSL support.
All calls are made on a background thread to avoid freezing the game.
"""
import json
import subprocess
import threading

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

        body = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            body["system"] = system

        body_json = json.dumps(body)

        try:
            # Hide the terminal window on Windows
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0

            result = subprocess.run(
                [
                    "curl", "-s",
                    "-X", "POST",
                    "-H", "Content-Type: application/json",
                    "-H", "x-api-key: " + api_key,
                    "-H", "anthropic-version: " + _API_VERSION,
                    "-d", body_json,
                    _API_URL,
                ],
                capture_output=True,
                text=True,
                timeout=60,
                startupinfo=startupinfo,
            )

            if result.returncode != 0:
                err = result.stderr.strip() or f"curl exited with code {result.returncode}"
                if callback:
                    callback(None, f"Network error: {err}")
                return

            data = json.loads(result.stdout)

            # Check for API error response
            if "error" in data:
                msg = data["error"].get("message", str(data["error"]))
                if callback:
                    callback(None, f"API error: {msg}")
                return

            text = _extract_text(data)
            if callback:
                callback(text, None)

        except subprocess.TimeoutExpired:
            if callback:
                callback(None, "Request timed out after 60 seconds.")

        except json.JSONDecodeError:
            if callback:
                callback(None, f"Invalid response from API: {result.stdout[:200]}")

        except FileNotFoundError:
            if callback:
                callback(None, "curl not found. This mod requires Windows 10 or later.")

        except Exception as e:
            if callback:
                callback(None, f"Unexpected error: {type(e).__name__}: {e}")

    thread = threading.Thread(target=_request, daemon=True, name="ClaudeAI-Request")
    thread.start()
    return thread
