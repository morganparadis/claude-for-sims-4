"""
Event & challenge generator — creates surprising in-game events and gameplay challenges.
Uses the fast model for quick response times.
"""
from . import api_client, sim_context, config, journal, moodlets

_SYSTEM = """You are a mischievous game master for The Sims 4. You create fun, surprising events \
and challenges that shake up the player's game.

Your events and challenges must:
- Reference actual Sims 4 gameplay mechanics (specific skills, career tracks, relationship types, \
  lot traits, world names, object types, need bars, moodlets, aspirations, life events)
- Be immediately actionable — the player should know exactly what to do
- Range from silly to dramatic
- Be completable without mods or cheats (unless obviously implied)
- Write in {language}

IMPORTANT: On the very last line of your response, write MOOD: followed by the emotional \
impact this event would have on the player's sim. Pick exactly one: \
happy, confident, flirty, inspired, focused, energized, playful, sad, angry, tense, \
embarrassed, bored, uncomfortable, dazed"""


def _get_context_block():
    """Build a short context string for event prompts."""
    lines = []
    active = sim_context.get_active_sim()
    if active:
        info = sim_context.get_sim_info_dict(active)
        lines.append(f"Active Sim: {info['name']} ({info.get('mood', '?')} mood)")
        if info.get("traits"):
            lines.append(f"Traits: {', '.join(info['traits'])}")

    household = sim_context.get_household_context()
    if household:
        names = [m["name"] for m in household.get("members", [])]
        lines.append(f"Household: {household.get('household_name', '?')} — {', '.join(names)}")
        lines.append(f"Funds: §{household.get('funds', '?')}")

    lot = sim_context.get_current_lot_name()
    if lot:
        lines.append(f"Location: {lot}")

    return "\n".join(lines) if lines else "Generic Sims 4 household."


def generate_random_event(callback=None):
    """
    Generate a single surprise event to shake up the current play session.
    """
    context = sim_context.build_context_string_with_journal()
    language = config.get_language()
    system = _SYSTEM.format(language=language)

    prompt = (
        f"{context}\n\n"
        "Generate ONE surprising random event for this household right now. "
        "If there is journal history above, make this event feel connected to past events "
        "rather than completely out of nowhere.\n\n"
        "Format exactly as:\n"
        "EVENT: [Catchy name]\n"
        "WHAT HAPPENED: [2–3 sentences describing the event]\n"
        "IMMEDIATE ACTION: [Exactly what the player should do right now]\n"
        "TWIST: [An optional complication or surprise that could follow]\n\n"
        "Event ideas to draw from (pick something creative, don't use these verbatim):\n"
        "unexpected visitor, secret inheritance, neighborhood drama, skill breakthrough, "
        "career crisis, relationship revelation, mysterious object, strange dream, "
        "neighborhood feud, surprise party, hidden talent discovered, old flame returns"
    )

    def _callback_with_journal(text, error):
        if text:
            text, mood_tag = moodlets.extract_mood_tag(text)
            if mood_tag:
                try:
                    import services
                    main_si = None
                    try:
                        from . import sim_context as _sc
                        main_si = _sc.get_main_sim_info()
                    except Exception:
                        pass
                    if not main_si:
                        client = services.client_manager().get_first_client()
                        if client:
                            main_si = client.active_sim_info
                    if main_si:
                        moodlets.apply_mood(main_si, mood_tag)
                except Exception:
                    pass
            journal.add_entry("event", text)
        if callback:
            callback(text, error)

    return api_client.call_claude_async(
        [{"role": "user", "content": prompt}],
        system=system,
        use_fast_model=True,
        callback=_callback_with_journal,
    )


def generate_challenge(difficulty="medium", callback=None):
    """
    Generate a gameplay challenge with rules and win conditions.

    Args:
        difficulty: "easy", "medium", or "hard"
        callback:   function(text, error)
    """
    context = _get_context_block()
    language = config.get_language()
    system = _SYSTEM.format(language=language)

    difficulty_notes = {
        "easy": "Simple and achievable in one or two play sessions. Good for beginners.",
        "medium": "Requires some planning across multiple sessions. Has real restrictions.",
        "hard": "Punishing and demanding. Strict rules that genuinely constrain the player.",
    }
    note = difficulty_notes.get(difficulty, difficulty_notes["medium"])

    prompt = (
        f"{context}\n\n"
        f"Create a {difficulty.upper()} difficulty gameplay challenge. {note}\n\n"
        "Format exactly as:\n"
        f"CHALLENGE: [Name] ({difficulty.title()} Difficulty)\n"
        "OBJECTIVE: [The main goal in 1–2 sentences]\n"
        "RULES:\n"
        "• [Rule 1]\n"
        "• [Rule 2]\n"
        "• [Rule 3]\n"
        "WIN CONDITION: [How to officially complete the challenge]\n"
        "BONUS GOAL: [An optional harder objective for extra bragging rights]"
    )

    return api_client.call_claude_async(
        [{"role": "user", "content": prompt}],
        system=system,
        use_fast_model=True,
        callback=callback,
    )


def generate_weekly_goals(callback=None):
    """
    Generate a set of 5 goals for the player to accomplish this play session.
    """
    context = _get_context_block()
    language = config.get_language()
    system = _SYSTEM.format(language=language)

    prompt = (
        f"{context}\n\n"
        "Generate 5 fun weekly goals for this household's current play session. "
        "Mix easy, medium, and one stretch goal.\n\n"
        "Format as:\n"
        "THIS WEEK'S GOALS:\n"
        "1. [Easy goal]\n"
        "2. [Easy/medium goal]\n"
        "3. [Medium goal]\n"
        "4. [Medium/hard goal]\n"
        "5. ⭐ STRETCH: [Ambitious goal]\n\n"
        "Each goal should reference specific Sims 4 mechanics and be completable in one session."
    )

    return api_client.call_claude_async(
        [{"role": "user", "content": prompt}],
        system=system,
        use_fast_model=True,
        callback=callback,
    )
