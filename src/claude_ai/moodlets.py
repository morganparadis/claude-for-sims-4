"""
Response cleaner -- strips markdown noise and trailing separators from LLM
output before showing it to the player.

(Historically this module also applied Sims 4 buff moodlets based on a MOOD:
tag the LLM emitted. That feature was removed -- Sims 4 buffs all carry
narrative content that misled the player about what their sim had actually
done in-game. The prompts no longer ask for a MOOD line.)
"""

import re


def clean_response(text):
    """
    Strip trailing separator lines (---, ===, ***), legacy MOOD/MOOD_TOPIC
    lines that may still appear if a prompt drifts, and inline markdown
    formatting from LLM output. Returns the cleaned text.
    """
    if not text:
        return text

    lines = text.rstrip().split("\n")

    # Walk backwards stripping trailing junk
    while lines:
        last = lines[-1].strip()
        if not last:
            lines.pop()
            continue
        upper = last.upper()
        # Drop any stray MOOD: / MOOD_TOPIC: lines if the LLM emits them.
        if upper.startswith("MOOD:") or upper.startswith("MOOD_TOPIC:") or upper.startswith("MOOD TOPIC:"):
            lines.pop()
            continue
        # Drop trailing separators like ---, ===, ***
        stripped_chars = set(last)
        if stripped_chars and stripped_chars.issubset(set("-=*_~ ")):
            lines.pop()
            continue
        break

    # Strip inline markdown formatting
    cleaned_lines = []
    for line in lines:
        line = re.sub(r'\*\*(.+?)\*\*', r'\1', line)
        line = re.sub(r'__(.+?)__', r'\1', line)
        line = re.sub(r'^\s*\*?\*?Message\s*\d+\s*:?\*?\*?\s*', '', line, flags=re.IGNORECASE)
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).rstrip()
