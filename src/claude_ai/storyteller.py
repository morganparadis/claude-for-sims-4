"""
Storyteller — generates narrative updates, storylines, and dramatic arcs for households.
Uses the default (Opus) model for richer, more complex output.
"""
from . import api_client, sim_context, config, journal

_SYSTEM = """You are a dramatic, witty storyteller for The Sims 4. You narrate the lives of \
Sim families like a soap opera writer who also loves cozy life simulation games.

Your voice:
- Warm, clever, and occasionally over-the-top dramatic
- Reference real Sims 4 mechanics naturally (needs bars, skills, careers, aspirations, \
  relationships, whims, moodlets, death types, occults)
- Mix humor with genuine emotional stakes
- Create character dynamics that feel personal and specific to these Sims
- Always family-friendly
- Write in {language}"""


def generate_story_update(callback=None):
    """
    Generate a 2–3 paragraph narrative update for the current household —
    like a chapter from a Sims let's play story.
    """
    household = sim_context.get_household_context()
    context = sim_context.build_context_string_with_journal()
    language = config.get_language()
    system = _SYSTEM.format(language=language)

    prompt = (
        f"{context}\n\n"
        "Write a SHORT story update for this household (1 short paragraph, max 4-5 sentences). "
        "Must fit in a small popup window. "
        "If there is journal history above, continue from where it left off. "
        "Vivid and fun — what's happening now and what drama might unfold next."
    )

    def _callback_with_journal(text, error):
        if text:
            household_name = household.get("household_name", "")
            journal.add_entry("story", text, sim_name=household_name)
        if callback:
            callback(text, error)

    return api_client.call_claude_async(
        [{"role": "user", "content": prompt}],
        system=system,
        callback=_callback_with_journal,
    )


def generate_relationship_drama(sim1_name=None, sim2_name=None, callback=None):
    """
    Generate a relationship-focused dramatic arc between two household members.
    """
    household = sim_context.get_household_context()
    language = config.get_language()
    system = _SYSTEM.format(language=language)

    members = household.get("members", [])
    if not members:
        if callback:
            callback(None, "No household members found.")
        return None

    names = [m["name"] for m in members]
    name1 = sim1_name or (names[0] if len(names) > 0 else "Sim A")
    name2 = sim2_name or (names[1] if len(names) > 1 else "Sim B")

    context = sim_context.build_context_string_with_journal()

    prompt = (
        f"{context}\n\n"
        f"Write a short dramatic arc between {name1} and {name2}. "
        "If there is journal history above, build on past events.\n\n"
        "Keep it SHORT — must fit in a small popup window. Max 6 lines.\n\n"
        "Format:\n"
        "DRAMA: [Catchy title]\n"
        "[2-3 sentences: the situation, the conflict, what might happen next]\n"
        "PLAY IT: [1-2 specific gameplay actions]"
    )

    def _callback_with_journal(text, error):
        if text:
            journal.add_entry("drama", text, sim_name=f"{name1} & {name2}")
        if callback:
            callback(text, error)

    return api_client.call_claude_async(
        [{"role": "user", "content": prompt}],
        system=system,
        callback=_callback_with_journal,
    )


def generate_storyline(theme=None, callback=None):
    """
    Generate a full 3-act storyline for the household to play out,
    with specific gameplay goals.

    Args:
        theme:    optional string (e.g. "rivalry", "romance", "rags to riches")
        callback: function(text, error)
    """
    context = sim_context.build_context_string_with_journal()
    language = config.get_language()
    system = _SYSTEM.format(language=language)

    theme_line = f"Requested theme: {theme}\n\n" if theme else ""

    prompt = (
        f"{context}\n\n"
        f"{theme_line}"
        "Create a 3-act storyline for this household to play out over multiple play sessions.\n\n"
        "Format exactly as:\n"
        "ACT 1 — [Title]: [Inciting incident and opening situation, 2–3 sentences]\n\n"
        "ACT 2 — [Title]: [Rising action, complications, character development, 2–3 sentences]\n\n"
        "ACT 3 — [Title]: [Climax and resolution, 2–3 sentences]\n\n"
        "GAMEPLAY GOALS:\n"
        "• [Specific in-game action 1]\n"
        "• [Specific in-game action 2]\n"
        "• [Specific in-game action 3]\n"
        "• [Specific in-game action 4]\n"
        "• [Specific in-game action 5]\n\n"
        "Make the goals concrete and achievable in Sims 4 (raise a skill, achieve a career level, "
        "build a relationship, complete an aspiration milestone, etc.)."
    )

    def _callback_with_journal(text, error):
        if text:
            journal.add_entry("storyline", text)
        if callback:
            callback(text, error)

    return api_client.call_claude_async(
        [{"role": "user", "content": prompt}],
        system=system,
        callback=_callback_with_journal,
    )


