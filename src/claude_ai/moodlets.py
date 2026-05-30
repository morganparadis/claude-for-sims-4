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
    Also strips trailing separator lines (---, ===, ***) and markdown labels.
    """
    if not text:
        return text, None

    lines = text.rstrip().split("\n")
    mood = None

    # Walk backwards looking for the MOOD line and strip trailing junk along the way
    while lines:
        last = lines[-1].strip()
        if not last:
            lines.pop()
            continue
        if last.upper().startswith("MOOD:"):
            mood = last.split(":", 1)[1].strip().lower()
            lines.pop()
            continue
        # Strip trailing separators like ---, ===, ***
        stripped_chars = set(last)
        if stripped_chars and stripped_chars.issubset(set("-=*_~ ")):
            lines.pop()
            continue
        break

    # Strip markdown formatting from remaining lines
    import re
    cleaned_lines = []
    for line in lines:
        # Remove **bold**, *italic*, __bold__, _italic_
        line = re.sub(r'\*\*(.+?)\*\*', r'\1', line)
        line = re.sub(r'__(.+?)__', r'\1', line)
        # Remove "Message 1:", "Message 2:" labels at line starts
        line = re.sub(r'^\s*\*?\*?Message\s*\d+\s*:?\*?\*?\s*', '', line, flags=re.IGNORECASE)
        cleaned_lines.append(line)

    clean_text = "\n".join(cleaned_lines).rstrip()
    return clean_text, mood
