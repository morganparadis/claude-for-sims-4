"""
Phone calls and texts -- generates AI-powered messages from relationship sims.
Uses the fast model for quick generation.
"""
import random

from . import api_client, sim_context, config, journal, notifications

_CALL_SYSTEM = """You are writing one side of a phone call in The Sims 4. You are writing \
what the CALLER says (the player's sim is listening). Write in {language}.

Rules:
- Write 3-5 short lines of dialogue (what the caller says)
- Match the caller's personality and relationship to the player's sim
- The call should have a reason: sharing news, asking for advice, inviting somewhere, \
  gossiping, complaining, celebrating, or just checking in
- Keep it natural and fun -- occasionally use Simlish words (Sul sul, Dag dag, Nooboo)
- Never use profanity or explicit content
- Write dialogue lines only, prefixed with the caller's first name"""

_TEXT_SYSTEM = """You are writing text messages from a Sim in The Sims 4. Write in {language}.

Rules:
- Write 1-3 short text messages (like real phone texts)
- Match the sender's personality and relationship to the recipient
- Texts can be casual, use abbreviations, and include emoji
- The text should have a purpose: making plans, sharing news/gossip, sending a meme description, \
  asking a question, or reacting to something that happened
- Keep it brief and authentic
- Occasionally use Simlish words naturally
- Never use profanity or explicit content"""


def _pick_random_relationship_sim():
    """Pick a random non-household sim from the protagonist's relationship network."""
    main_si = sim_context.get_main_sim_info()
    if main_si:
        _household_members, relationships = sim_context.get_main_sim_network(main_si)
        contacts = relationships  # only non-household sims
    else:
        active = sim_context.get_active_sim()
        if not active:
            return None
        rels = sim_context.get_sim_relationships(active.sim_info)
        contacts = [r for r in rels if not r.get("in_household")]

    if not contacts:
        return None

    # Weight toward stronger relationships (but everyone has a chance)
    weights = []
    for contact in contacts:
        score = abs(contact.get("friendship") or 0) + abs(contact.get("romance") or 0)
        weights.append(max(score, 10))

    return random.choices(contacts, weights=weights, k=1)[0]


def _describe_relationship(contact):
    """Build a short relationship description for the prompt."""
    parts = [f"Name: {contact['name']}"]
    if contact.get("status"):
        parts.append(f"Relationship: {contact['status']}")
    if contact.get("friendship") is not None:
        parts.append(f"Friendship level: {contact['friendship']}")
    if contact.get("romance") is not None:
        parts.append(f"Romance level: {contact['romance']}")
    if contact.get("in_household"):
        parts.append("Lives in the same household")

    si = contact.get("sim_info")
    if si:
        traits = sim_context.get_sim_traits(si, limit=4)
        if traits:
            parts.append(f"Traits: {', '.join(traits)}")
        mood = sim_context.get_sim_mood(si)
        parts.append(f"Current mood: {mood}")

    return "\n".join(parts)


def generate_call(callback=None, output=None):
    """Generate an incoming phone call from a relationship sim."""
    contact = _pick_random_relationship_sim()
    if not contact:
        msg = "No relationship sims found. Set a protagonist with claude.set_main or build some relationships first."
        if callback:
            callback(None, msg)
        elif output:
            notifications.show_error(msg, output=output)
        return

    main_si = sim_context.get_main_sim_info()
    main_name = main_si.first_name if main_si else "your Sim"

    language = config.get_language()
    system = _CALL_SYSTEM.format(language=language)
    rel_desc = _describe_relationship(contact)

    prompt = (
        f"Caller info:\n{rel_desc}\n\n"
        f"They are calling {main_name}.\n\n"
        f"Write what {contact['name']} says during this phone call. "
        f"Make the reason for calling feel natural given their relationship."
    )

    def _on_result(text, error):
        title = f"Incoming Call - {contact['name']}"
        if text:
            journal.add_entry("call", f"Call from {contact['name']}:\n{text}", sim_name=contact["name"])
            notifications.show(title, text, output=output)
        elif error:
            notifications.show_error(error, output=output)
        if callback:
            callback(text, error)

    return api_client.call_claude_async(
        [{"role": "user", "content": prompt}],
        system=system,
        use_fast_model=True,
        callback=_on_result,
    )


def generate_text(callback=None, output=None):
    """Generate a text message from a relationship sim."""
    contact = _pick_random_relationship_sim()
    if not contact:
        msg = "No relationship sims found. Set a protagonist with claude.set_main or build some relationships first."
        if callback:
            callback(None, msg)
        elif output:
            notifications.show_error(msg, output=output)
        return

    main_si = sim_context.get_main_sim_info()
    main_name = main_si.first_name if main_si else "your Sim"

    language = config.get_language()
    system = _TEXT_SYSTEM.format(language=language)
    rel_desc = _describe_relationship(contact)

    prompt = (
        f"Sender info:\n{rel_desc}\n\n"
        f"They are texting {main_name}.\n\n"
        f"Write 1-3 text messages from {contact['name']}. "
        f"Make the content feel natural given their relationship and current mood."
    )

    def _on_result(text, error):
        title = f"Text from {contact['name']}"
        if text:
            journal.add_entry("text", f"Text from {contact['name']}:\n{text}", sim_name=contact["name"])
            notifications.show(title, text, output=output)
        elif error:
            notifications.show_error(error, output=output)
        if callback:
            callback(text, error)

    return api_client.call_claude_async(
        [{"role": "user", "content": prompt}],
        system=system,
        use_fast_model=True,
        callback=_on_result,
    )
