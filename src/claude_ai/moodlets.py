"""
Moodlet system — applies emotional buffs to your sim based on AI-generated content.

After Claude generates a call, text, or event, it tags the emotional tone.
This module maps that tone to a base-game buff and applies it.
"""

# Base game buff tuning IDs for each mood.
# These are the generic "social" or "phone" themed buffs where available.
_MOOD_BUFFS = {
    "happy":      27738,   # Buff_Happy_Generic
    "confident":  27131,   # Buff_Confident_Generic
    "flirty":     27468,   # Buff_Flirty_Generic
    "inspired":   27503,   # Buff_Inspired_Generic
    "focused":    27453,   # Buff_Focused_Generic
    "energized":  27400,   # Buff_Energized_Generic
    "playful":    27954,   # Buff_Playful_Generic
    "sad":        28173,   # Buff_Sad_Generic
    "angry":      26818,   # Buff_Angry_Generic
    "tense":      28356,   # Buff_Tense_Generic
    "embarrassed": 27363,  # Buff_Embarrassed_Generic
    "bored":      27049,   # Buff_Bored_Generic
    "uncomfortable": 28395,# Buff_Uncomfortable_Generic
    "dazed":      27167,   # Buff_Dazed_Generic
}


def apply_mood(sim_info, mood_tag):
    """
    Apply a moodlet buff to a sim based on a mood tag string.
    Returns True on success, False if the mood is unknown or buff fails.
    """
    if not mood_tag:
        return False

    mood_key = mood_tag.strip().lower()
    buff_id = _MOOD_BUFFS.get(mood_key)
    if not buff_id:
        return False

    try:
        import services
        import sims4.resources
        buff_manager = services.get_instance_manager(sims4.resources.Types.BUFF)
        buff_type = buff_manager.get(buff_id)
        if not buff_type:
            return False
        sim_info.debug_add_buff_by_type(buff_type)
        return True
    except Exception:
        return False


def extract_mood_tag(text):
    """
    Extract a MOOD: tag from the end of generated text.
    Returns (clean_text, mood_tag) tuple.
    If no tag found, returns (original_text, None).
    """
    if not text:
        return text, None

    # Look for MOOD: tag on the last line
    lines = text.rstrip().split("\n")
    last_line = lines[-1].strip()

    if last_line.upper().startswith("MOOD:"):
        mood = last_line.split(":", 1)[1].strip().lower()
        clean_text = "\n".join(lines[:-1]).rstrip()
        return clean_text, mood

    return text, None
