"""
Moodlet system — placeholder for future buff application.
Currently only extracts mood tags from generated text.
"""


def apply_mood(sim_info, mood_tag, reason=None):
    """Placeholder — buff application not yet implemented."""
    return False


def extract_mood_tag(text):
    """
    Extract a MOOD: tag from the end of generated text.
    Returns (clean_text, mood_tag) tuple.
    """
    if not text:
        return text, None

    lines = text.rstrip().split("\n")
    last_line = lines[-1].strip()

    if last_line.upper().startswith("MOOD:"):
        mood = last_line.split(":", 1)[1].strip().lower()
        clean_text = "\n".join(lines[:-1]).rstrip()
        return clean_text, mood

    return text, None
