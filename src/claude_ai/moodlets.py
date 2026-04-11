"""
Moodlet system — applies emotional buffs to your sim based on AI-generated content.

Uses add_buff_from_op (the same method S4CL uses) instead of debug_add_buff_by_type.
"""

# Confirmed buff IDs from S4CL (Alien Empathy Emotion buffs — work on all sims)
_MOOD_BUFF_IDS = {
    "happy":        103481,
    "sad":          103478,
    "angry":        103474,
    "confident":    103487,
    "flirty":       103483,
    "inspired":     103480,
    "focused":      103482,
    "energized":    103484,
    "playful":      103479,
    "uncomfortable":103476,
    "embarrassed":  103485,
    "bored":        103475,
    "dazed":        103486,
    "tense":        103477,
}


def apply_mood(sim_info, mood_tag):
    """
    Apply a moodlet buff to a sim based on a mood tag string.
    Returns True on success.
    """
    if not mood_tag:
        return False

    mood_key = mood_tag.strip().lower()
    buff_id = _MOOD_BUFF_IDS.get(mood_key)
    if not buff_id:
        return False

    try:
        import services
        import sims4.resources
        buff_manager = services.get_instance_manager(sims4.resources.Types.BUFF)
        if not buff_manager:
            return False
        buff_type = buff_manager.get(buff_id)
        if not buff_type:
            # ID didn't work — try searching by name
            target = mood_key
            for b in buff_manager.all_instances_gen():
                bn = type(b).__name__.lower()
                if target in bn and ("mood" in bn or "generic" in bn):
                    buff_type = b
                    break
        if not buff_type:
            return False
        sim_info.add_buff_from_op(buff_type, buff_reason=None)
        return True
    except BaseException:
        pass

    return False


def extract_mood_tag(text):
    """
    Extract a MOOD: tag from the end of generated text.
    Returns (clean_text, mood_tag) tuple.
    If no tag found, returns (original_text, None).
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
