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


def _build_household_block(household):
    """Format household context into a prompt-friendly string."""
    if not household:
        return "Unknown household with no information available."

    lines = [
        f"Household: {household.get('household_name', 'Unknown')}",
        f"Funds: §{household.get('funds', '?')}",
        "Members:",
    ]
    for m in household.get("members", []):
        line = f"  - {m['name']} ({m.get('age', '?')}, {m.get('mood', '?')} mood)"
        if m.get("traits"):
            line += f" | Traits: {', '.join(m['traits'])}"
        if m.get("career"):
            line += f" | Career: {m['career']}"
        lines.append(line)
    return "\n".join(lines)


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
        "Write a 2–3 paragraph story update for this household. "
        "If there is journal history above, continue the story naturally from where it left off. "
        "Describe what's probably happening in their lives right now, highlight interesting "
        "character dynamics or tensions, and hint at what drama might unfold next. "
        "Write it like a chapter entry in a Sims story blog — personal, vivid, and fun."
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
        f"Write a dramatic relationship story arc between {name1} and {name2}. "
        "This could be romantic tension, a long-simmering rivalry, a family betrayal, "
        "or a budding friendship with complications. "
        "If there is journal history above, make this arc feel continuous with past events.\n\n"
        "Include:\n"
        "THE SITUATION: [What's going on between them right now]\n"
        "THE CONFLICT: [What's driving them apart or creating tension]\n"
        "THE TURNING POINT: [A dramatic moment that changes everything]\n"
        "POSSIBLE ENDINGS: [Two different ways this could resolve — one happy, one bittersweet]\n"
        "HOW TO PLAY IT: [2–3 specific gameplay actions to enact this drama]"
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

    # Pick first two members if names not supplied
    names = [m["name"] for m in members]
    name1 = sim1_name or (names[0] if len(names) > 0 else "Sim A")
    name2 = sim2_name or (names[1] if len(names) > 1 else "Sim B")

    context = _build_household_block(household)

    prompt = (
        f"{context}\n\n"
        f"Write a dramatic relationship story arc between {name1} and {name2}. "
        "This could be romantic tension, a long-simmering rivalry, a family betrayal, "
        "or a budding friendship with complications.\n\n"
        "Include:\n"
        "THE SITUATION: [What's going on between them right now]\n"
        "THE CONFLICT: [What's driving them apart or creating tension]\n"
        "THE TURNING POINT: [A dramatic moment that changes everything]\n"
        "POSSIBLE ENDINGS: [Two different ways this could resolve — one happy, one bittersweet]\n"
        "HOW TO PLAY IT: [2–3 specific gameplay actions to enact this drama]"
    )

    return api_client.call_claude_async(
        [{"role": "user", "content": prompt}],
        system=system,
        callback=callback,
    )
