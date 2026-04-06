"""
Phone calls and texts -- generates AI-powered messages from relationship sims.
Uses the fast model for quick generation.

Calls show as modal phone dialogs with the caller's portrait (ring).
Texts show as phone dialogs with buzz.
Players can reply with claude.reply <message> to continue the conversation.
"""
import random

from . import api_client, sim_context, config, journal, notifications

# Tracks the current conversation so the player can reply
# Format: {"contact": contact_dict, "history": [{"role": "them"|"you", "text": str}, ...]}
_active_conversation = None


def _show_phone_dialog(caller_sim_info, title, message, ring=True):
    """
    Show a phone dialog with the caller's portrait and Reply/Dismiss buttons.
    If the player clicks Reply, a hint is shown in the cheat console.
    """
    try:
        from sims4.localization import LocalizationHelperTuning
        from ui.ui_dialog import UiDialogOkCancel, PhoneRingType
        from distributor.shared_messages import IconInfoData
        import services

        client = services.client_manager().get_first_client()
        if not client or not client.active_sim_info:
            return False

        loc_text = LocalizationHelperTuning.get_raw_text(message)
        loc_title = LocalizationHelperTuning.get_raw_text(title)
        loc_reply = LocalizationHelperTuning.get_raw_text("Reply")
        loc_dismiss = LocalizationHelperTuning.get_raw_text("Dismiss")

        dialog = UiDialogOkCancel.TunableFactory().default(
            client.active_sim_info,
            text=lambda: loc_text,
            title=lambda: loc_title,
            text_ok=lambda: loc_reply,
            text_cancel=lambda: loc_dismiss,
        )
        dialog.phone_ring_type = PhoneRingType.RING if ring else PhoneRingType.BUZZ

        def _on_response(response_dialog):
            try:
                if response_dialog.accepted:
                    import sims4.commands
                    sims4.commands.output(
                        "[Claude AI] Open the cheat console and type your reply:", None
                    )
                    sims4.commands.output(
                        "[Claude AI]   claude.reply <your message>", None
                    )
            except Exception:
                pass

        dialog.add_listener(_on_response)
        dialog.show_dialog(icon_override=IconInfoData(obj_instance=caller_sim_info))
        return True
    except Exception:
        pass
    return False

_CALL_SYSTEM = """You are writing one side of a phone call in The Sims 4. You are writing \
what the CALLER says (the player's sim is listening). Write in {language}.

CRITICAL -- voice and personality:
- The caller's age, traits, mood, and relationship MUST shape how they talk.
- A Teen sounds completely different from an Elder. A Goofball sounds nothing like a Snob.
- Hot-Headed sims rant. Romantic sims flirt. Gloomy sims sigh. Loners keep it short.
- Geek sims make references. Evil sims are backhanded. Childish sims are excitable.
- Mean sims are blunt or rude. Good sims are warm. Self-Assured sims brag casually.
- Let traits CLASH in interesting ways -- a Romantic + Mean sim might be possessive.
- Age affects vocabulary, slang, energy level, and what they care about.
  Teens: slang, drama, school. Young Adults: ambition, nightlife, dating.
  Adults: career, family stress, nostalgia. Elders: wisdom, complaints, stories.

Rules:
- Write 3-5 short lines of dialogue (what the caller says)
- The call should have a reason: sharing news, asking for advice, inviting somewhere, \
  gossiping, complaining, celebrating, or just checking in
- Occasionally sprinkle in Simlish words naturally (Sul sul, Dag dag, Nooboo)
- Never use profanity or explicit content
- Write dialogue lines only, prefixed with the caller's first name"""

_TEXT_SYSTEM = """You are writing text messages from a Sim in The Sims 4. Write in {language}.

CRITICAL -- voice and personality:
- The sender's age, traits, mood, and relationship MUST shape how they text.
- Every sim texts differently. A Geek uses different emoji than a Bro.
- Teens: abbreviations, lots of emoji, dramatic, lowercase. "omggg no way 😭😭"
- Young Adults: mix of casual and articulate. "hey are you free tonight?"
- Adults: more complete sentences, less emoji. "Hi! Are you around this weekend?"
- Elders: formal, sometimes confused by texting. "Dear [name], I hope this message finds you."
- Hot-Headed: caps lock, exclamation marks. Gloomy: ellipses, sad emoji.
- Snob: proper grammar, condescending. Goofball: random, memes, lol.
- Romantic: hearts, flirty. Loner: terse, minimal. Evil: passive aggressive.
- Let the sim's personality make their texts unmistakably THEM.

Rules:
- Write 1-3 short text messages (like real phone texts)
- The text should have a purpose: making plans, sharing news/gossip, sending a meme description, \
  asking a question, or reacting to something
- Never use profanity or explicit content"""

_REPLY_SYSTEM = """You are writing text message replies from a Sim in The Sims 4. Write in {language}.

You are writing as {other_name}, replying to a message from {main_name}.
You will be given the conversation history so far.

CRITICAL -- voice and personality:
- Stay deeply in character as {other_name}. Their age, traits, and mood define their voice.
- A Teen replies totally differently from an Elder. A Goofball texts nothing like a Snob.
- Let their personality shine through word choice, punctuation, emoji use, and sentence length.
- React authentically to what {main_name} said -- don't be generic.

Rules:
- Write 1-3 short text messages as {other_name}'s reply
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


def _get_mutual_contacts(contact):
    """
    Find sims that both the protagonist and the contact have relationships with.
    Returns a list of short descriptions like "Bella Goth (your Friend, their Crush)".
    """
    mutuals = []
    try:
        main_si = sim_context.get_main_sim_info()
        other_si = contact.get("sim_info")
        if not main_si or not other_si:
            return mutuals

        # Get the protagonist's relationship targets
        main_rt = main_si.relationship_tracker
        main_targets = set(main_rt.target_sim_gen())
        main_targets.discard(other_si.sim_id)

        # Get the contact's relationship targets
        other_rt = other_si.relationship_tracker
        other_targets = set(other_rt.target_sim_gen())
        other_targets.discard(main_si.sim_id)

        # Find overlap
        shared_ids = main_targets & other_targets
        if not shared_ids:
            return mutuals

        import services
        sm = services.sim_info_manager()

        for sid in list(shared_ids)[:6]:  # cap at 6 to keep prompt reasonable
            try:
                si = sm.get(sid)
                if not si:
                    continue
                name = f"{si.first_name} {si.last_name}".strip()

                # Get relationship bits from protagonist's perspective
                main_bits = []
                try:
                    for bit in main_rt.get_all_bits(sid):
                        bn = sim_context._get_trait_name(bit)
                        for kw in ("Friend", "Enemy", "Romantic", "Married", "BFF",
                                   "Crush", "Family", "Sibling", "Parent", "Child"):
                            if kw in bn:
                                label = bn.replace("RelationshipBit_", "").replace("Romantic_", "").replace("_", " ").strip()
                                main_bits.append(label)
                                break
                except Exception:
                    pass

                # Get relationship bits from contact's perspective
                other_bits = []
                try:
                    for bit in other_rt.get_all_bits(sid):
                        bn = sim_context._get_trait_name(bit)
                        for kw in ("Friend", "Enemy", "Romantic", "Married", "BFF",
                                   "Crush", "Family", "Sibling", "Parent", "Child"):
                            if kw in bn:
                                label = bn.replace("RelationshipBit_", "").replace("Romantic_", "").replace("_", " ").strip()
                                other_bits.append(label)
                                break
                except Exception:
                    pass

                if main_bits or other_bits:
                    main_label = ", ".join(main_bits[:2]) if main_bits else "acquaintance"
                    other_label = ", ".join(other_bits[:2]) if other_bits else "acquaintance"
                    mutuals.append(f"{name} (your {main_label}, their {other_label})")
                else:
                    mutuals.append(f"{name} (mutual acquaintance)")
            except Exception:
                continue
    except Exception:
        pass
    return mutuals


def _describe_relationship(contact):
    """Build a detailed character description for the prompt."""
    parts = [f"Name: {contact['name']}"]

    si = contact.get("sim_info")
    if si:
        # Age — critical for voice
        try:
            age = str(getattr(si, "age", "")).replace("Age.", "")
            if age:
                parts.append(f"Age: {age}")
        except Exception:
            pass

        # Traits — the core of personality
        traits = sim_context.get_sim_traits(si, limit=6)
        if traits:
            parts.append(f"Traits: {', '.join(traits)}")

        # Mood — affects tone right now
        mood = sim_context.get_sim_mood(si)
        parts.append(f"Current mood: {mood}")

        # Career — gives them something to talk about
        career = sim_context.get_sim_career(si)
        if career:
            parts.append(f"Career: {career}")

        # Aspiration — what drives them
        aspiration = sim_context.get_sim_aspiration(si)
        if aspiration:
            parts.append(f"Aspiration: {aspiration}")

    if contact.get("status"):
        parts.append(f"Relationship to your sim: {contact['status']}")
    if contact.get("friendship") is not None:
        parts.append(f"Friendship level: {contact['friendship']}")
    if contact.get("romance") is not None:
        parts.append(f"Romance level: {contact['romance']}")
    if contact.get("in_household"):
        parts.append("Lives in the same household")

    return "\n".join(parts)


def _format_conversation_history(history, main_name, other_name):
    """Format conversation history into a prompt-readable string."""
    lines = []
    for msg in history:
        name = main_name if msg["role"] == "you" else other_name
        lines.append(f"{name}: {msg['text']}")
    return "\n".join(lines)


def _start_conversation(contact, first_message):
    """Start tracking a new conversation."""
    global _active_conversation
    _active_conversation = {
        "contact": contact,
        "history": [{"role": "them", "text": first_message}],
    }


def get_active_conversation():
    """Return the active conversation, or None."""
    return _active_conversation


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

    sim_history = journal.format_sim_history_for_prompt(contact["name"])
    history_block = f"\n\n{sim_history}" if sim_history else ""

    mutuals = _get_mutual_contacts(contact)
    mutual_block = ""
    if mutuals:
        mutual_block = "\n\nPeople you both know:\n" + "\n".join(f"  - {m}" for m in mutuals)
        mutual_block += "\nFeel free to gossip about, mention, or bring up any of these sims naturally."

    prompt = (
        f"Caller info:\n{rel_desc}{history_block}{mutual_block}\n\n"
        f"They are calling {main_name}.\n\n"
        f"Write what {contact['name']} says during this phone call. "
        f"If there is past interaction history, reference or build on it naturally. "
        f"Make the reason for calling feel natural given their relationship."
    )

    def _on_result(text, error):
        title = f"Call from {contact['name']}"
        if text:
            _start_conversation(contact, text)
            journal.add_entry("call", f"Call from {contact['name']}:\n{text}", sim_name=contact["name"])
            caller_si = contact.get("sim_info")
            shown = False
            if caller_si:
                shown = _show_phone_dialog(caller_si, title, text)
            if not shown:
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

    sim_history = journal.format_sim_history_for_prompt(contact["name"])
    history_block = f"\n\n{sim_history}" if sim_history else ""

    mutuals = _get_mutual_contacts(contact)
    mutual_block = ""
    if mutuals:
        mutual_block = "\n\nPeople you both know:\n" + "\n".join(f"  - {m}" for m in mutuals)
        mutual_block += "\nFeel free to gossip about, mention, or bring up any of these sims naturally."

    prompt = (
        f"Sender info:\n{rel_desc}{history_block}{mutual_block}\n\n"
        f"They are texting {main_name}.\n\n"
        f"Write 1-3 text messages from {contact['name']}. "
        f"If there is past interaction history, reference or build on it naturally. "
        f"Make the content feel natural given their relationship and current mood."
    )

    def _on_result(text, error):
        title = f"Text from {contact['name']}"
        if text:
            _start_conversation(contact, text)
            journal.add_entry("text", f"Text from {contact['name']}:\n{text}", sim_name=contact["name"])
            sender_si = contact.get("sim_info")
            shown = False
            if sender_si:
                shown = _show_phone_dialog(sender_si, title, text, ring=False)
            if not shown:
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


def generate_reply(player_message, callback=None, output=None):
    """
    Reply to the active conversation. The player's message is sent as their sim,
    and the other sim responds in character.
    """
    global _active_conversation
    if not _active_conversation:
        msg = "No active conversation. Use claude.call or claude.text first to start one."
        if callback:
            callback(None, msg)
        elif output:
            notifications.show_error(msg, output=output)
        return

    contact = _active_conversation["contact"]
    history = _active_conversation["history"]

    # Add the player's message to history
    history.append({"role": "you", "text": player_message})

    main_si = sim_context.get_main_sim_info()
    main_name = main_si.first_name if main_si else "your Sim"
    other_name = contact["name"]

    language = config.get_language()
    system = _REPLY_SYSTEM.format(
        language=language,
        other_name=other_name,
        main_name=main_name,
    )
    rel_desc = _describe_relationship(contact)
    convo_text = _format_conversation_history(history, main_name, other_name)
    sim_history = journal.format_sim_history_for_prompt(other_name)
    history_block = f"\n\n{sim_history}" if sim_history else ""

    mutuals = _get_mutual_contacts(contact)
    mutual_block = ""
    if mutuals:
        mutual_block = "\n\nPeople you both know:\n" + "\n".join(f"  - {m}" for m in mutuals)

    prompt = (
        f"Relationship info:\n{rel_desc}{history_block}{mutual_block}\n\n"
        f"Conversation so far:\n{convo_text}\n\n"
        f"Write {other_name}'s reply (1-3 short text messages)."
    )

    def _on_result(text, error):
        if text:
            history.append({"role": "them", "text": text})
            # Save the exchange to journal
            journal.add_entry(
                "text",
                f"Conversation with {other_name}:\n"
                f"{main_name}: {player_message}\n"
                f"{other_name}: {text}",
                sim_name=other_name,
            )
            title = f"Reply from {other_name}"
            sender_si = contact.get("sim_info")
            shown = False
            if sender_si:
                shown = _show_phone_dialog(sender_si, title, text, ring=False)
            if not shown:
                notifications.show(title, text, output=output)
        elif error:
            # Remove player message from history since the reply failed
            if history and history[-1]["role"] == "you":
                history.pop()
            notifications.show_error(error, output=output)
        if callback:
            callback(text, error)

    return api_client.call_claude_async(
        [{"role": "user", "content": prompt}],
        system=system,
        use_fast_model=True,
        callback=_on_result,
    )
