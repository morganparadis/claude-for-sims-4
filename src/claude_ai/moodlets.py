"""
Moodlet system — applies emotional buffs to the recipient sim based on the
mood tag the LLM appended to its response.

Every step logs to ClaudeAI_Log.txt with a [moodlets] prefix so silent failures
are visible. Lookup strategy: try the configured buff ID first (fast path),
then fall back to fuzzy name search through the buff manager (handles cases
where buff IDs differ across Sims 4 versions or expansion packs).
"""

import os
import datetime


def _log(message):
    try:
        path = os.path.join(os.path.expanduser("~"), "Documents", "ClaudeAI_Log.txt")
        with open(path, "a", encoding="utf-8") as f:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{ts}] [moodlets] {message}\n")
    except Exception:
        pass


# Base-game buff tuning IDs. These are the "generic" social/emotional buffs
# that ship with every Sims 4 install. If a lookup fails the code falls back
# to a fuzzy name search, so wrong IDs aren't fatal -- just slower.
_MOOD_BUFF_IDS = {
    "happy":         27738,
    "confident":     27131,
    "flirty":        27468,
    "inspired":      27503,
    "focused":       27453,
    "energized":     27400,
    "playful":       27954,
    "sad":           28173,
    "angry":         26818,
    "tense":         28356,
    "embarrassed":   27363,
    "bored":         27049,
    "uncomfortable": 28395,
    "dazed":         27167,
}


# Tokens that mean "this buff has NARRATIVE CONTENT" (a specific gameplay
# event reason for the mood -- new baby, finished workout, got engaged, etc.).
# These buffs DO produce visible moodlets, but the moodlet text reads as if
# that thing actually happened. We must NEVER pick these -- the player will
# see "New Baby!" on their sim despite not having one, and the LLM downstream
# will hallucinate around the false context.
#
# Also includes sentiment/relationship tokens (invisible buffs) and any
# expansion-pack-specific gameplay events that would mislead the player.
_NON_MOOD_BUFF_TOKENS = (
    # Sentiment buffs (invisible relationship trackers)
    "sentiment", "crush", "bonded", "hurt", "guilty", "enamored",
    "sympathetic", "burned", "motivating", "adoring", "smitten",
    "lousy", "rooting", "spiteful", "furious_with", "supported_by",
    # Pregnancy / family life events
    "baby", "newborn", "infant", "toddler", "pregnant", "pregnancy",
    "expecting", "labor", "birthing", "midwife", "fatherhood", "motherhood",
    "adoption", "adopted",
    # Romance / marriage events
    "wedding", "engaged", "engagement", "married", "marriage", "honeymoon",
    "anniversary", "divorced", "divorce", "broke_up", "breakup", "proposal",
    "first_kiss", "firstkiss", "woohoo", "rejected",
    # Career / work events
    "career", "job", "promotion", "promoted", "fired", "demoted", "boss",
    "coworker", "interview", "raise_", "_raise",
    # Death / ghost
    "death", "dying", "deceased", "ghost", "haunt", "grim", "urn",
    "mortified", "lost_loved", "lostloved", "grief", "mourning",
    "funeral",
    # Food / drink / consumption
    "food", "meal", "hungry", "starving", "ate_", "eaten", "drink",
    "drunk", "alcohol", "caffeine", "coffee", "potion", "elixir",
    "ambrosia", "nausea", "nauseated",
    # Sickness / injury
    "sick", "ill_", "_ill", "disease", "virus", "infection", "fever",
    "injured", "burnt", "burned", "shocked", "electrocuted", "poison",
    # Workout / fitness / activity-specific
    "workout", "exercise", "gym_", "_gym", "athletic", "sweat", "sore",
    "running", "yoga", "martial_arts", "treadmill",
    # School / education
    "school", "university", "homework", "exam", "studied", "studying",
    "graduate", "graduation", "honor_roll",
    # Holidays / parties / events
    "holiday", "christmas", "birthday", "party", "wedding", "festival",
    "thanksgiving", "halloween", "love_day", "winterfest",
    # Occults
    "vampire", "werewolf", "witch", "spellcaster", "mermaid", "alien",
    "fairy", "plantsim", "skeleton", "servo",
    # Pets
    "pet_", "_pet", "dog_", "cat_", "puppy", "kitten",
    # Weather / supernatural ambient
    "hauntings", "spooky", "creepy",
    # Specific aspirations / lifestyles
    "midlife", "crisis",
    # Misc gameplay
    "trespassing", "arrested", "burglar", "fire_", "burglary", "robbed",
    "abducted", "abduction", "kidnapped",
)


def _is_excluded_buff(class_name_lower):
    return any(tok in class_name_lower for tok in _NON_MOOD_BUFF_TOKENS)


# Tokens that strongly suggest a "pure emotional carryover" buff -- these
# are the safest because they're applied by the game as generic mood boosts
# without a specific narrative event behind them.
_PURE_MOOD_HINT_TOKENS = (
    "carryover", "highmood", "mood_default", "default_mood", "_generic",
    "highenergy", "highfun", "highrecharge", "highhygiene",
)


def _is_pure_mood_buff(class_name_lower):
    return any(tok in class_name_lower for tok in _PURE_MOOD_HINT_TOKENS)


def _find_mood_type(mood_key):
    """Find the Sims 4 Mood resource (Mood_Happy, Mood_Sad, etc.) for an
    emotion key. Returns None if not found."""
    try:
        import services
        import sims4.resources
        mood_manager = services.get_instance_manager(sims4.resources.Types.MOOD)
        if not mood_manager:
            return None
        target = mood_key.lower()
        for mood_type in mood_manager.types.values():
            try:
                name = mood_type.__name__.lower()
                # Expected pattern: "mood_happy", "mood_sad", etc.
                if name == f"mood_{target}":
                    return mood_type
            except Exception:
                continue
        # Looser match (e.g. "Mood_Happy_Extended")
        for mood_type in mood_manager.types.values():
            try:
                name = mood_type.__name__.lower()
                if name.startswith("mood_") and target in name:
                    return mood_type
            except Exception:
                continue
    except Exception as e:
        _log(f"_find_mood_type({mood_key}) failed: {type(e).__name__}: {e}")
    return None


def _find_buff_by_mood_type(buff_manager, mood_key):
    """Find a buff whose mood_type attribute points to the Mood resource
    for this emotion. This is the most reliable strategy -- it skips
    sentiment/crush/etc buffs because they don't carry a mood_type."""
    target_mood = _find_mood_type(mood_key)
    if not target_mood:
        _log(f"could not find Mood resource for '{mood_key}'")
        return None

    pure_candidates = []
    fallback_candidates = []
    try:
        for buff_type in buff_manager.types.values():
            try:
                bt_mood = getattr(buff_type, "mood_type", None)
                if bt_mood is None:
                    continue
                if bt_mood is not target_mood:
                    continue
                class_name = buff_type.__name__.lower()
                if _is_excluded_buff(class_name):
                    continue
                # Two-tier ranking: prefer buffs that look like pure mood
                # carryovers (no narrative reason), only fall back to other
                # mood-typed buffs if there's no pure one.
                if _is_pure_mood_buff(class_name):
                    pure_candidates.append(buff_type)
                else:
                    fallback_candidates.append(buff_type)
            except Exception:
                continue
    except Exception as e:
        _log(f"mood_type buff scan failed: {type(e).__name__}: {e}")
        return None

    if pure_candidates:
        pure_candidates.sort(key=lambda b: len(b.__name__))
        _log(f"mood_type search for '{mood_key}': {len(pure_candidates)} pure candidate(s); chose {pure_candidates[0].__name__}")
        return pure_candidates[0]

    if fallback_candidates:
        # No carryover/generic buff exists for this mood. Rather than apply a
        # random narrative buff (which would mislead the player), skip and let
        # the caller log "no clean buff found". The user has been seeing
        # "New Baby" and "Workout" moodlets because we picked these blindly.
        _log(
            f"mood_type search for '{mood_key}' found {len(fallback_candidates)} "
            f"narrative-laden candidates (e.g. {fallback_candidates[0].__name__}) "
            f"but no pure-mood buff -- skipping rather than applying a misleading moodlet."
        )
        return None

    return None


def _find_buff_by_name(buff_manager, mood_key):
    """Last-resort fuzzy name match. Tries known naming patterns, then a
    looser search excluding sentiment-style buffs."""
    try:
        all_types = buff_manager.types
    except Exception as e:
        _log(f"buff_manager.types access failed: {type(e).__name__}: {e}")
        return None

    target = mood_key.lower()
    target_cap = mood_key.capitalize()

    # Try common exact naming patterns first
    exact_patterns = [
        f"Buff_{target_cap}",
        f"Buff_Mood_{target_cap}",
        f"Buff_{target_cap}_Generic",
        f"buff_{target}_generic",
    ]
    try:
        for buff_type in all_types.values():
            try:
                if buff_type.__name__ in exact_patterns:
                    return buff_type
            except Exception:
                continue
    except Exception:
        pass

    # Loose match -- only consider buffs that match pure-mood hint tokens,
    # AND aren't narrative-laden. If neither tier matches, return None.
    pure = []
    try:
        for buff_type in all_types.values():
            try:
                class_name = buff_type.__name__.lower()
                if target not in class_name:
                    continue
                if _is_excluded_buff(class_name):
                    continue
                if _is_pure_mood_buff(class_name):
                    pure.append(buff_type)
            except Exception:
                continue
    except Exception as e:
        _log(f"buff iteration failed: {type(e).__name__}: {e}")
        return None

    if not pure:
        return None
    pure.sort(key=lambda b: len(b.__name__))
    return pure[0]


def apply_mood(sim_info, mood_tag, reason=None):
    """
    Apply a moodlet buff to a sim based on a mood tag string.
    Returns True on success, False on any failure. Logs the outcome either way.
    """
    if not sim_info:
        _log("apply_mood called with no sim_info")
        return False
    if not mood_tag:
        _log("apply_mood called with no mood_tag")
        return False

    mood_key = mood_tag.strip().lower()
    if mood_key not in _MOOD_BUFF_IDS:
        _log(f"unknown mood '{mood_key}' -- not in mood table")
        return False

    sim_name = "?"
    try:
        sim_name = f"{sim_info.first_name} {sim_info.last_name}".strip()
    except Exception:
        pass

    try:
        import services
        import sims4.resources
    except Exception as e:
        _log(f"failed to import services/sims4.resources: {type(e).__name__}: {e}")
        return False

    try:
        buff_manager = services.get_instance_manager(sims4.resources.Types.BUFF)
    except Exception as e:
        _log(f"get_instance_manager(BUFF) failed: {type(e).__name__}: {e}")
        return False
    if not buff_manager:
        _log("buff_manager is None")
        return False

    # Lookup strategy (most reliable first):
    #   1. Direct buff ID (fast path, but our IDs are often wrong)
    #   2. mood_type attribute matching — finds real emotion buffs and skips
    #      sentiment/crush/etc. by design (sentiment buffs don't carry mood_type)
    #   3. Fuzzy name match with sentiment exclusion (last resort)
    buff_id = _MOOD_BUFF_IDS[mood_key]
    buff_type = None
    try:
        buff_type = buff_manager.get(buff_id)
        if buff_type:
            class_name = buff_type.__name__.lower()
            if _is_excluded_buff(class_name):
                _log(f"buff_id {buff_id} resolved to excluded buff {buff_type.__name__} -- discarding")
                buff_type = None
    except Exception as e:
        _log(f"buff_manager.get({buff_id}) raised {type(e).__name__}: {e}")

    if not buff_type:
        buff_type = _find_buff_by_mood_type(buff_manager, mood_key)

    if not buff_type:
        _log(f"mood_type search failed for '{mood_key}'; falling back to name search")
        buff_type = _find_buff_by_name(buff_manager, mood_key)
        if buff_type:
            _log(f"name search found: {buff_type.__name__}")

    if not buff_type:
        _log(f"no buff found for '{mood_key}' via ID, mood_type, or name -- giving up")
        return False

    # add_buff_from_op is the standard application method used by S4CL and
    # most working mods. It accepts the buff CLASS (not an instance).
    try:
        sim_info.add_buff_from_op(buff_type, buff_reason=None)
        _log(f"applied '{mood_key}' ({buff_type.__name__}) to {sim_name} -- reason: {reason}")
        return True
    except Exception as e:
        _log(f"add_buff_from_op failed for {sim_name}: {type(e).__name__}: {e}")

    # Last-resort fallback: try the simpler add_buff method
    try:
        sim_info.add_buff(buff_type, buff_reason=None)
        _log(f"applied via add_buff fallback: '{mood_key}' ({buff_type.__name__}) to {sim_name}")
        return True
    except Exception as e:
        _log(f"add_buff fallback also failed for {sim_name}: {type(e).__name__}: {e}")

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
