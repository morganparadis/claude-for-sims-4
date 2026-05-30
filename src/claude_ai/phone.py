"""
Phone calls and texts -- generates AI-powered messages from relationship sims.
Uses the fast model for quick generation.

Calls show as modal phone dialogs with the caller's portrait (ring).
Texts show as phone dialogs with buzz.
Players can reply with claude.reply <message> to continue the conversation.
"""
import random

from . import api_client, sim_context, config, journal, notifications, moodlets

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
        if not client:
            return False

        # Anchor the phone dialog to the protagonist (who actually has a phone),
        # falling back to active sim if no protagonist is set.
        # This prevents toddlers/kids/pets from "receiving" calls and texts.
        anchor_sim = sim_context.get_main_sim_info()
        if not anchor_sim:
            anchor_sim = client.active_sim_info
        if not anchor_sim:
            return False

        loc_text = LocalizationHelperTuning.get_raw_text(message)
        loc_title = LocalizationHelperTuning.get_raw_text(title)
        loc_reply = LocalizationHelperTuning.get_raw_text("Reply")
        loc_dismiss = LocalizationHelperTuning.get_raw_text("Dismiss")

        dialog = UiDialogOkCancel.TunableFactory().default(
            anchor_sim,
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

_CALL_SYSTEM = """You write one side of a Sims 4 phone call — what the caller says to the \
player's sim. Stay in character as the caller. Write in {language}.

# Whose data is whose
The context describes the CALLER. Career, traits, mood, aspiration, world, interests — \
all theirs, not the player's. Never confuse them.

CRITICAL: You know almost NOTHING about the player's sim beyond the relationship facts \
listed. Do NOT invent the player's career, hobbies, interests, activities, or past. \
Do NOT ask "are you still into X" or "how's your job going at Y" unless X or Y appears \
in the relationship facts. The caller can talk about THEIR OWN career and interests — \
they cannot assume the player shares them.

# Voice
The caller's family role to the player, age stage, and traits define how they speak.

Family roles (when listed) lock the voice — a Father speaks like a dad, a Sibling teases, \
a Spouse is intimate, a Grandparent dotes. Modify warmth by friendship score: high = warm, \
low = stilted, negative = hostile.

Age:
- Teen: dramatic, slang
- Young Adult: casual but articulate
- Adult: measured sentences, no youth slang ("yo", "bro", "dude")
- Elder: nostalgic, formal, long-winded

Traits add flavor on top (Hot-Headed rants, Goofball jokes, Snob condescends, Loner is terse).

# What to write
2-3 SHORT lines of dialogue, prefixed with the caller's first name. One topic. \
Your FIRST line must contain a specific, concrete piece of information or question — \
NEVER a vague observation about feelings, distance, time, or the relationship's vibe.

The topic should usually be about the CALLER'S OWN LIFE — their day, a recent thought, \
something they did/saw/want, a question for the player. INVENT concrete specifics: \
locations they went, objects they bought, food they ate, jobs they screwed up, \
dreams they had, opinions, weird encounters with strangers, conspiracy theories, \
emergencies, regrets, ambitions, bad ideas, good ideas, hot takes. \
Be specific (a llama, a §10,000 mistake, a weird painting in the basement, \
a coworker named Brad — generic role names for non-mutuals are fine).

Topic variety guide (rotate, don't keep picking the same kind):
1. Their own life right now (most common)
2. A specific question or favor they need
3. A confession or admission
4. A reaction to something that happened to them
5. An invitation or plan (respect the geography rule)
6. A wild idea, opinion, or hot take
7. Gossip about a mutual (USE SPARINGLY — only ~1 in 5 calls, not the default)
Occasional Simlish (Sul sul, Dag dag, Nooboo) is fine.

# Geography rule (STRICT)
Look at the caller's world vs the player's world (both listed in the context).
- SAME world: in-person plans are fine ("come over", "let's grab drinks", "I ran into X").
- DIFFERENT worlds: NEVER suggest casual in-person meetups ("come over", "stop by", \
  "let's hang out", "let's grab drinks"). NEVER claim to have "run into" or "bumped into" \
  the player. Long-distance is the default — frame everything as a phone call, text, video \
  chat, or a PLANNED future visit ("when I come visit next month"). Same rule applies to \
  mentions of mutual contacts: only "ran into X" if X lives in the CALLER's world.

# Hard rules
- The caller and player are on GOOD TERMS unless friendship is negative or the journal \
  shows actual conflict. Never invent past conflict. BANNED phrases (and any variants): \
  "things got weird between us", "things have been weird", "things are weird between us", \
  "after what happened", "we left things off badly", "I know it's been weird", \
  "been meaning to catch up", "we should catch up properly", "we need to catch up", \
  "do a video call sometime", "let's catch up sometime". \
  If you find yourself reaching for any of these, you're writing filler — start over with \
  a concrete topic instead.
- Family relationships are NEVER romantic, regardless of romance score.
- No profanity or explicit content.
- Only name sims listed in the mutual contacts block. For others, use a role like \
  "my coworker", "a friend of mine".
- Only reference sims in age-appropriate contexts (teens at school, adults at work, etc.).
- Adults don't treat children/toddlers as peers — only as kids in their own/family/friends' lives.
- Sims with the same last name are NOT automatically related or in the same household.
- Stay in character. Never acknowledge being an AI or claim missing information. Improvise.

# Output format (STRICT)
PLAIN TEXT ONLY. No markdown. No `**bold**`, no `*italics*`, no `_emphasis_`, no headings, \
no `---` separators, no labels like "Message 1:" or "Reply:". Just the spoken lines.

Format your response as:
<line 1>
<line 2>
<line 3, optional>
MOOD: <emotion>

The MOOD line is the LAST line, on its own, no formatting. Emotion is one of: \
happy, confident, flirty, inspired, focused, energized, playful, sad, angry, tense, \
embarrassed, bored, uncomfortable, dazed."""

_TEXT_SYSTEM = """You write text messages from a Sim in The Sims 4 to the player's sim. \
Stay in character as the sender. Write in {language}.

# Whose data is whose
The context describes the SENDER. Career, traits, mood, aspiration, world, interests — \
all theirs, not the player's. Never confuse them.

CRITICAL: You know almost NOTHING about the player's sim beyond the relationship facts \
listed. Do NOT invent the player's career, hobbies, interests, activities, or past. \
Do NOT ask "are you still into X" or "how's your job going at Y" unless X or Y appears \
in the relationship facts. The sender can talk about THEIR OWN career and interests — \
they cannot assume the player shares them.

# Voice
The sender's family role to the player, age stage, and traits define how they text.

Family roles (when listed) lock the voice — a Father texts like a dad, a Sibling teases, \
a Spouse is intimate, a Grandparent dotes. Modify warmth by friendship score: high = warm, \
low = stilted, negative = hostile.

Age:
- Teen: lowercase, abbreviations, lots of emoji. "omggg no way 😭"
- Young Adult: casual but articulate. "hey are you free tonight?"
- Adult: complete sentences, minimal emoji, no youth slang. "Hi! Are you free this weekend?"
- Elder: formal, warm, sometimes long-winded. "Hello dear, I hope you're well."

Traits add flavor on top (Hot-Headed = caps, Gloomy = ellipses, Snob = condescending grammar, \
Goofball = playful, Romantic = hearts, Loner = terse, Evil = passive aggressive).

# What to write
1-2 SHORT messages, max 2 sentences each. One topic. Your FIRST message must contain a \
specific, concrete piece of information or question — NEVER a vague observation about \
feelings, distance, time, or the relationship's vibe.

The topic should usually be about the SENDER'S OWN LIFE — their day, a recent thought, \
something they did/saw/want, a question for the player. INVENT concrete specifics: \
locations they went, objects they bought, food they ate, jobs they screwed up, \
dreams they had, opinions, weird encounters with strangers, conspiracy theories, \
emergencies, regrets, ambitions, bad ideas, hot takes. \
Be specific (a llama, a §10,000 mistake, a weird painting in the basement, \
a coworker named Brad — generic role names for non-mutuals are fine).

Topic variety guide (rotate, don't keep picking the same kind):
1. Their own life right now (most common)
2. A specific question or favor they need
3. A confession or admission
4. A reaction to something that happened to them
5. An invitation or plan (respect the geography rule)
6. A wild idea, opinion, or hot take
7. Gossip about a mutual (USE SPARINGLY — only ~1 in 5 messages, not the default)

# Geography rule (STRICT)
Look at the sender's world vs the player's world (both listed in the context).
- SAME world: in-person plans are fine ("come over", "let's grab coffee", "I saw X").
- DIFFERENT worlds: NEVER suggest casual in-person meetups ("come over", "stop by", \
  "let's hang out"). NEVER claim to have "run into" the player. Frame everything as long- \
  distance — texts, video chats, social media, or a PLANNED future visit. Same rule for \
  mentions of mutuals: only "ran into X" if X lives in the SENDER's world.

# Hard rules
- The sender and player are on GOOD TERMS unless friendship is negative or the journal \
  shows actual conflict. Never invent past conflict. BANNED phrases (and any variants): \
  "things got weird between us", "things have been weird", "things are weird between us", \
  "after what happened", "we left things off badly", "I know it's been weird", \
  "been meaning to catch up", "we should catch up properly", "we need to catch up", \
  "do a video call sometime", "let's catch up sometime". \
  If you find yourself reaching for any of these, start over with a concrete topic.
- Family relationships are NEVER romantic, regardless of romance score.
- No profanity or explicit content.
- Only name sims listed in the mutual contacts block. For others, use a role like \
  "my coworker", "a friend of mine".
- Only reference sims in age-appropriate contexts (teens at school, adults at work, etc.).
- Adults don't treat children/toddlers as peers — only as kids in their own/family/friends' lives.
- Sims with the same last name are NOT automatically related or in the same household.
- Stay in character. Never acknowledge being an AI or claim missing information. Improvise.

# Output format (STRICT)
PLAIN TEXT ONLY. No markdown. No `**bold**`, no `*italics*`, no `_emphasis_`, no headings, \
no `---` separators, no labels like "Message 1:" or "Text 2:". Just the messages.

Format your response as:
<message 1 text>
<message 2 text, optional, on its own line>
MOOD: <emotion>

The MOOD line is the LAST line, on its own, no formatting. Emotion is one of: \
happy, confident, flirty, inspired, focused, energized, playful, sad, angry, tense, \
embarrassed, bored, uncomfortable, dazed."""

_REPLY_SYSTEM = """You write a Sim's reply to a text from the player's sim in The Sims 4. \
Stay in character as {other_name} replying to {main_name}. Write in {language}.

# Voice
{other_name}'s family role to {main_name}, age stage, and traits define how they reply.

Family role locks the voice (Father = dad voice, Sibling = teasing, Spouse = intimate). \
Warmth scales by friendship score: high = warm, low = stilted, negative = hostile. \
Adults use full sentences and proper punctuation, no youth slang. Teens use lowercase \
and emoji. Elders are formal and warm.

# What to write
1-2 SHORT messages, max 2 sentences each. React authentically to what {main_name} said — \
no generic responses. If they mention someone or something not in the context, react in \
character (curious, confused, gossipy) — never refuse or ask for details.

# Hard rules
- Family relationships are NEVER romantic, regardless of romance score.
- No profanity or explicit content.
- Don't assume same last name = related or in same household.
- Stay in character. Never acknowledge being an AI or claim missing information.

# Output format (STRICT)
PLAIN TEXT ONLY. No markdown, no `**bold**`, no `---` separators, no "Message 1:" labels.

Format your response as:
<message 1 text>
<message 2 text, optional>
MOOD: <emotion>

Emotion is one of: happy, confident, flirty, inspired, focused, energized, playful, sad, \
angry, tense, embarrassed, bored, uncomfortable, dazed. This is the emotion {main_name} feels."""


def _apply_mood_from_text(text, reason=None):
    """Extract MOOD tag from text, apply the moodlet to protagonist, return cleaned text."""
    clean_text, mood_tag = moodlets.extract_mood_tag(text)
    if mood_tag:
        main_si = sim_context.get_main_sim_info()
        if not main_si:
            active = sim_context.get_active_sim()
            if active:
                main_si = active.sim_info
        if main_si:
            moodlets.apply_mood(main_si, mood_tag, reason=reason)
    return clean_text


def _get_sims_on_active_lot():
    """Return a set of sim_ids currently on the active lot."""
    sim_ids = set()
    try:
        import services
        zone = services.current_zone()
        if not zone:
            return sim_ids
        # Iterate through all sims currently instantiated on the lot
        sm = services.sim_info_manager()
        if sm:
            for si in sm.values():
                try:
                    sim = si.get_sim_instance()
                    if sim is not None and sim.zone_id == zone.id:
                        sim_ids.add(si.sim_id)
                except Exception:
                    continue
    except Exception:
        pass
    return sim_ids


def _is_ghost(sim_info):
    """Check if a sim is dead/ghost. Tries multiple methods for compatibility."""
    if sim_info is None:
        return False

    # Method 1: is_ghost can be a method OR a property in different game versions
    try:
        ig = getattr(sim_info, "is_ghost", None)
        if ig is not None:
            val = ig() if callable(ig) else ig
            if val:
                return True
    except Exception:
        pass

    # Method 2: is_dead attribute
    try:
        if getattr(sim_info, "is_dead", False):
            return True
    except Exception:
        pass

    # Method 3: death_type — None or NONE means alive
    try:
        death_type = getattr(sim_info, "death_type", None)
        if death_type is not None:
            dt_str = str(death_type)
            if dt_str and "NONE" not in dt_str.upper():
                return True
    except Exception:
        pass

    # Method 4: check for ghost traits on the sim
    try:
        traits = sim_context.get_sim_traits(sim_info, limit=20)
        for t in traits:
            if "ghost" in t.lower():
                return True
    except Exception:
        pass

    return False


def find_contact_by_name(full_name):
    """Find a specific sim by name from the protagonist's relationship network or sim manager."""
    name_lower = full_name.lower()

    # First check relationship network
    main_si = sim_context.get_main_sim_info()
    if main_si:
        hh_members, relationships = sim_context.get_main_sim_network(main_si)
        for contact in hh_members + relationships:
            if contact["name"].lower() == name_lower:
                return contact

    # Fallback: search the sim manager directly and build a contact dict
    try:
        import services
        parts = full_name.strip().split(None, 1)
        first = parts[0].lower()
        last = parts[1].lower() if len(parts) > 1 else ""

        for si in services.sim_info_manager().values():
            if si.first_name.lower() != first:
                continue
            if last and si.last_name.lower() != last:
                continue
            return {
                "sim_info": si,
                "sim_id": si.sim_id,
                "name": f"{si.first_name} {si.last_name}".strip(),
                "status": "",
                "friendship": None,
                "romance": None,
                "in_household": False,
            }
    except Exception:
        pass
    return None


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

    # Filter out ghosts unless config allows them
    allow_ghosts = config.get_config().getboolean("claude_ai", "phone_allow_ghosts", fallback=True)
    if not allow_ghosts:
        contacts = [c for c in contacts if not _is_ghost(c.get("sim_info"))]

    # Filter out sims currently on the same lot (no point texting/calling someone who's right there)
    on_lot = _get_sims_on_active_lot()
    if on_lot:
        contacts = [c for c in contacts if c.get("sim_id") not in on_lot]

    if not contacts:
        return None

    # Weight toward stronger relationships (but everyone has a chance)
    weights = []
    for contact in contacts:
        score = abs(contact.get("friendship") or 0) + abs(contact.get("romance") or 0)
        weights.append(max(score, 10))

    return random.choices(contacts, weights=weights, k=1)[0]


# Bits that signal a relationship is platonic (no longer romantic).
# Sims 4 adds these when a romance ends — they override any lingering romantic bits.
_PLATONIC_BIT_KEYWORDS = ("justfriends", "justgoodfriends", "platonic")
# Bits that indicate ACTIVE romance (vs historical romantic bits)
_ACTIVE_ROMANCE_BIT_KEYWORDS = (
    "married", "spouse", "engaged", "fiance",
    "soulmate", "significant_other", "significantother",
    "boyfriend", "girlfriend", "partner",
)


def _has_platonic_bit(bits):
    """Return True if any bit indicates the relationship is now platonic."""
    if not bits:
        return False
    for bit in bits:
        try:
            bn = sim_context._get_trait_name(bit).lower().replace("_", "")
            if any(kw in bn for kw in _PLATONIC_BIT_KEYWORDS):
                return True
        except Exception:
            pass
    return False


def _has_active_romance_bit(bits):
    """Return True if any bit indicates an active romantic relationship."""
    if not bits:
        return False
    for bit in bits:
        try:
            bn = sim_context._get_trait_name(bit).lower().replace("_", "")
            if any(kw in bn for kw in _ACTIVE_ROMANCE_BIT_KEYWORDS):
                return True
        except Exception:
            pass
    return False


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

        # Cap mutual contacts at 4 — more than that and Claude over-relies on the list
        for sid in list(shared_ids)[:4]:
            try:
                si = sm.get(sid)
                if not si:
                    continue
                name = f"{si.first_name} {si.last_name}".strip()

                # Get relationship bits from protagonist's perspective
                main_bits = []
                try:
                    raw_main_bits = list(main_rt.get_all_bits(sid))
                    main_is_platonic = _has_platonic_bit(raw_main_bits)
                    for bit in raw_main_bits:
                        bn = sim_context._get_trait_name(bit)
                        bn_low = bn.lower().replace("_", "")
                        # Skip historical romantic bits when relationship is now platonic
                        is_romantic = any(kw in bn_low for kw in ("romantic", "crush", "lover"))
                        if is_romantic and main_is_platonic:
                            continue
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
                    raw_other_bits = list(other_rt.get_all_bits(sid))
                    other_is_platonic = _has_platonic_bit(raw_other_bits)
                    for bit in raw_other_bits:
                        bn = sim_context._get_trait_name(bit)
                        bn_low = bn.lower().replace("_", "")
                        is_romantic = any(kw in bn_low for kw in ("romantic", "crush", "lover"))
                        if is_romantic and other_is_platonic:
                            continue
                        for kw in ("Friend", "Enemy", "Romantic", "Married", "BFF",
                                   "Crush", "Family", "Sibling", "Parent", "Child"):
                            if kw in bn:
                                label = bn.replace("RelationshipBit_", "").replace("Romantic_", "").replace("_", " ").strip()
                                other_bits.append(label)
                                break
                except Exception:
                    pass

                # Include their age and world so Claude knows context
                world = _get_sim_home_world(si)
                age = ""
                try:
                    age_str = str(getattr(si, "age", "")).replace("Age.", "")
                    if age_str:
                        age = f", {age_str}"
                except Exception:
                    pass
                world_part = f", lives in {world}" if world else ""

                if main_bits or other_bits:
                    main_label = ", ".join(main_bits[:2]) if main_bits else "acquaintance"
                    other_label = ", ".join(other_bits[:2]) if other_bits else "acquaintance"
                    mutuals.append(f"{name} (your {main_label}, their {other_label}{age}{world_part})")
                else:
                    mutuals.append(f"{name} (mutual acquaintance{age}{world_part})")
            except Exception:
                continue
    except Exception:
        pass
    return mutuals


# Map internal region names (and pack codes) to friendly world names.
# Sims 4 worlds are usually identified by EP/GP/SP pack codes.
_WORLD_NAMES = {
    # Base game
    "willowcreek": "Willow Creek",
    "oasissprings": "Oasis Springs",
    "newcrest": "Newcrest",
    # EP01 Get to Work
    "magnoliapromenade": "Magnolia Promenade",
    "ep01": "Magnolia Promenade",
    # EP02 Get Together
    "windenburg": "Windenburg",
    "ep02": "Windenburg",
    # EP03 City Living
    "sanmyshuno": "San Myshuno",
    "ep03": "San Myshuno",
    # EP04 Cats & Dogs
    "brindletonbay": "Brindleton Bay",
    "ep04": "Brindleton Bay",
    # EP05 Seasons (no new world)
    # EP06 Get Famous
    "delsolvalley": "Del Sol Valley",
    "ep06": "Del Sol Valley",
    # EP07 Island Living
    "sulani": "Sulani",
    "ep07": "Sulani",
    # EP08 Discover University
    "britechester": "Britechester",
    "ep08": "Britechester",
    # EP09 Eco Lifestyle
    "evergreenharbor": "Evergreen Harbor",
    "ep09": "Evergreen Harbor",
    # EP10 Snowy Escape
    "mtkomorebi": "Mt. Komorebi",
    "ep10": "Mt. Komorebi",
    # EP11 Cottage Living
    "henfordonbagley": "Henford-on-Bagley",
    "henford": "Henford-on-Bagley",
    "ep11": "Henford-on-Bagley",
    # EP12 High School Years
    "copperdale": "Copperdale",
    "ep12": "Copperdale",
    # EP13 Growing Together
    "sansequoia": "San Sequoia",
    "ep13": "San Sequoia",
    # EP14 Horse Ranch
    "chestnutridge": "Chestnut Ridge",
    "ep14": "Chestnut Ridge",
    # EP15 For Rent
    "tomarang": "Tomarang",
    "ep15": "Tomarang",
    # EP16 Life & Death
    "ravenwood": "Ravenwood",
    "ep16": "Ravenwood",
    # EP17 Lovestruck
    "ciudadenamorada": "Ciudad Enamorada",
    "ep17": "Ciudad Enamorada",
    # EP18 Businesses & Hobbies
    "nordhaven": "Nordhaven",
    "ep18": "Nordhaven",
    # GP packs with worlds
    "granitefalls": "Granite Falls",
    "outdoorretreat": "Granite Falls",
    "gp01": "Granite Falls",
    "forgottenhollow": "Forgotten Hollow",
    "gp04": "Forgotten Hollow",
    "selvadorada": "Selvadorada",
    "gp06": "Selvadorada",
    "strangerville": "StrangerVille",
    "gp07": "StrangerVille",
    "glimmerbrook": "Glimmerbrook",
    "magicvenue": "Glimmerbrook",
    "gp08": "Glimmerbrook",
    "batuu": "Batuu",
    "gp09": "Batuu",
    "tartosa": "Tartosa",
    "weddingworld": "Tartosa",
    "gp11": "Tartosa",
    "moonwoodmill": "Moonwood Mill",
    "gp12": "Moonwood Mill",
    "innisgreen": "Innisgreen",
    "gp14": "Innisgreen",
    # Hidden worlds
    "alienworld": "Sixam",
    "sixam": "Sixam",
    "forgottengrotto": "Forgotten Grotto",
    "sylvanglade": "Sylvan Glade",
}


def _friendly_world_name(raw):
    """Convert internal region name to friendly name. Returns None for unknowns."""
    if not raw:
        return None
    import re
    full_key = raw.lower().replace(" ", "").replace("_", "")
    if not full_key:
        return None

    # 1. Try exact match on the full normalized key
    name = _WORLD_NAMES.get(full_key)
    if name:
        return name

    # 2. Try matching by pack code prefix (ep18, gp12, etc.)
    m = re.match(r'(ep|gp|sp|fp)(\d+)', full_key)
    if m:
        pack_code = m.group(1) + m.group(2)
        name = _WORLD_NAMES.get(pack_code)
        if name:
            return name

    # 3. Try after stripping the pack prefix
    stripped = re.sub(r'^(ep|gp|sp|fp)\d+', '', full_key)
    if stripped:
        name = _WORLD_NAMES.get(stripped)
        if name:
            return name

    # 4. Try partial matches
    for k, v in _WORLD_NAMES.items():
        if len(k) >= 4 and (k in full_key or k in stripped):
            return v

    return None


def _get_sim_home_world(sim_info):
    """Get the world/neighborhood name where a sim lives."""
    try:
        household = sim_info.household
        if household:
            home_zone_id = household.home_zone_id
            if home_zone_id:
                try:
                    from world.region import get_region_instance_from_zone_id
                    region = get_region_instance_from_zone_id(home_zone_id)
                    if region:
                        name = getattr(region, "__name__", "") or str(region)
                        cleaned = (name
                            .replace("Region_", "")
                            .replace("region_", "")
                            .replace("_", " ")
                            .strip())
                        if cleaned:
                            return _friendly_world_name(cleaned)
                except Exception:
                    pass
    except Exception:
        pass
    return None


def _location_context(main_si, contact):
    """Build a short string describing where each sim lives, if known."""
    main_home = _get_sim_home_world(main_si) if main_si else None
    other_si = contact.get("sim_info")
    other_home = _get_sim_home_world(other_si) if other_si else None

    if main_home and other_home:
        if main_home.lower() == other_home.lower():
            return f"\n[GEOGRAPHY: Both live in {main_home} — SAME world, in-person plans OK]"
        return (
            f"\n[GEOGRAPHY: {main_si.first_name} lives in {main_home}, "
            f"{contact['name']} lives in {other_home} — DIFFERENT worlds, "
            f"NO casual in-person meetups, long-distance only]"
        )
    elif main_home:
        return f"\n[GEOGRAPHY: {main_si.first_name} lives in {main_home}]"
    elif other_home:
        return f"\n[GEOGRAPHY: {contact['name']} lives in {other_home}]"
    return ""


def _get_family_relationship(other_si, contact):
    """
    Try to determine the precise family relationship between the protagonist
    and the other sim using genealogy tracker and relationship bits.
    Returns a string like "Father", "Daughter", "Sibling" or None.
    """
    main_si = sim_context.get_main_sim_info()
    if not main_si or not other_si:
        return None

    # Try genealogy tracker first — most precise
    try:
        from sims.genealogy_tracker import FamilyRelationshipIndex
        gen = main_si.genealogy
        if gen:
            # Check if other_si is a parent
            for parent_idx in (FamilyRelationshipIndex.MOTHER, FamilyRelationshipIndex.FATHER):
                try:
                    parent_id = gen.get_family_relationship(parent_idx)
                    if parent_id == other_si.sim_id:
                        gender = str(getattr(other_si, "gender", "")).replace("Gender.", "")
                        return "Father" if gender == "MALE" else "Mother"
                except Exception:
                    pass

        # Check if protagonist is a parent of other_si
        other_gen = other_si.genealogy
        if other_gen:
            for parent_idx in (FamilyRelationshipIndex.MOTHER, FamilyRelationshipIndex.FATHER):
                try:
                    parent_id = other_gen.get_family_relationship(parent_idx)
                    if parent_id == main_si.sim_id:
                        gender = str(getattr(other_si, "gender", "")).replace("Gender.", "")
                        return "Son" if gender == "MALE" else "Daughter"
                except Exception:
                    pass

        # Check for siblings (share a parent)
        if gen and other_gen:
            try:
                for idx in (FamilyRelationshipIndex.MOTHER, FamilyRelationshipIndex.FATHER):
                    my_parent = gen.get_family_relationship(idx)
                    their_parent = other_gen.get_family_relationship(idx)
                    if my_parent and my_parent == their_parent:
                        gender = str(getattr(other_si, "gender", "")).replace("Gender.", "")
                        return "Brother" if gender == "MALE" else "Sister"
            except Exception:
                pass
    except Exception:
        pass

    # Fallback: check relationship bits for family keywords
    try:
        rt = main_si.relationship_tracker
        bits = rt.get_all_bits(other_si.sim_id)
        if bits:
            for bit in bits:
                bn = sim_context._get_trait_name(bit)
                bn_lower = bn.lower()
                if "parent" in bn_lower:
                    gender = str(getattr(other_si, "gender", "")).replace("Gender.", "")
                    return "Father" if gender == "MALE" else "Mother"
                if "child" in bn_lower or "offspring" in bn_lower:
                    gender = str(getattr(other_si, "gender", "")).replace("Gender.", "")
                    return "Son" if gender == "MALE" else "Daughter"
                if "sibling" in bn_lower:
                    gender = str(getattr(other_si, "gender", "")).replace("Gender.", "")
                    return "Brother" if gender == "MALE" else "Sister"
                if "grandparent" in bn_lower:
                    gender = str(getattr(other_si, "gender", "")).replace("Gender.", "")
                    return "Grandfather" if gender == "MALE" else "Grandmother"
                if "grandchild" in bn_lower:
                    gender = str(getattr(other_si, "gender", "")).replace("Gender.", "")
                    return "Grandson" if gender == "MALE" else "Granddaughter"
                if "spouse" in bn_lower or "married" in bn_lower:
                    gender = str(getattr(other_si, "gender", "")).replace("Gender.", "")
                    return "Husband" if gender == "MALE" else "Wife"
                if "uncle" in bn_lower or "aunt" in bn_lower:
                    gender = str(getattr(other_si, "gender", "")).replace("Gender.", "")
                    return "Uncle" if gender == "MALE" else "Aunt"
                if "cousin" in bn_lower:
                    return "Cousin"
                if "niece" in bn_lower or "nephew" in bn_lower:
                    gender = str(getattr(other_si, "gender", "")).replace("Gender.", "")
                    return "Nephew" if gender == "MALE" else "Niece"
    except Exception:
        pass

    return None


def _get_protagonist_relationships():
    """
    Build an unambiguous summary of the protagonist's key relationships.
    Uses explicit "X is married to Y" phrasing to avoid confusion.
    """
    main_si = sim_context.get_main_sim_info()
    if not main_si:
        return ""

    main_name = main_si.first_name + " " + main_si.last_name
    facts = []

    try:
        rt = main_si.relationship_tracker
        import services
        sm = services.sim_info_manager()

        for target_id in rt.target_sim_gen():
            other_si = sm.get(target_id)
            if not other_si:
                continue
            other_name = other_si.first_name + " " + other_si.last_name

            try:
                bits = list(rt.get_all_bits(target_id))
                if not bits:
                    continue
                # Pre-scan: is this relationship now platonic, or actively romantic?
                is_platonic = _has_platonic_bit(bits)
                has_active_romance = _has_active_romance_bit(bits)
                # Build the lowercased bit name list once
                bit_names = []
                for bit in bits:
                    try:
                        bit_names.append(sim_context._get_trait_name(bit).lower())
                    except Exception:
                        pass

                # Priority: spouse > parent/child/sibling > active romance > nothing
                # Historical romantic bits are IGNORED when there's a platonic bit
                # or when the relationship has no active-romance signal.
                added = False
                for bn in bit_names:
                    if "spouse" in bn or "married" in bn:
                        facts.append(main_name + " is married to " + other_name)
                        added = True
                        break
                    elif "parent" in bn:
                        facts.append(main_name + " is " + other_name + "'s parent")
                        added = True
                        break
                    elif "child" in bn or "offspring" in bn:
                        facts.append(main_name + " is " + other_name + "'s child")
                        added = True
                        break
                    elif "sibling" in bn:
                        facts.append(main_name + " and " + other_name + " are siblings")
                        added = True
                        break

                if not added and has_active_romance and not is_platonic:
                    facts.append(main_name + " is in a romantic relationship with " + other_name)
            except Exception:
                pass

            if len(facts) >= 6:
                break
    except Exception:
        pass

    if not facts:
        return ""

    return "IMPORTANT — the player's sim's relationships (these are FACTS, do not contradict them):\n" + "\n".join("- " + f for f in facts)


def _describe_relationship(contact):
    """Build a detailed character description for the prompt.
    All facts are explicitly labeled as belonging to the contact, not the player,
    to prevent attribute bleed in the AI's response."""
    name = contact['name']
    parts = [f"=== Character: {name} (THE CALLER/SENDER, NOT the player) ==="]

    si = contact.get("sim_info")
    if si:
        try:
            age = str(getattr(si, "age", "")).replace("Age.", "")
            if age:
                parts.append(f"{name}'s age: {age}")
        except Exception:
            pass

        try:
            gender = str(getattr(si, "gender", "")).replace("Gender.", "")
            if gender:
                parts.append(f"{name}'s gender: {gender}")
        except Exception:
            pass

        traits = sim_context.get_sim_traits(si, limit=6)
        if traits:
            parts.append(f"{name}'s traits: {', '.join(traits)}")

        mood = sim_context.get_sim_mood(si)
        parts.append(f"{name}'s current mood: {mood}")

        career = sim_context.get_sim_career(si)
        if career:
            parts.append(f"{name}'s career: {career}")

        aspiration = sim_context.get_sim_aspiration(si)
        if aspiration:
            parts.append(f"{name}'s aspiration: {aspiration}")

        home = _get_sim_home_world(si)
        if home:
            parts.append(f"{name} lives in: {home}")

    family_label = _get_family_relationship(si, contact) if si else None
    if family_label:
        parts.append(f"{name} is the player's {family_label}")

    if contact.get("status"):
        status = contact['status']
        if not family_label:
            parts.append(f"{name}'s relationship to the player: {status}")
        elif status and not any(kw in status for kw in ("Family", "Parent", "Child", "Sibling")):
            parts.append(f"{name} is also: {status}")
    if contact.get("friendship") is not None:
        parts.append(f"Friendship between {name} and the player: {contact['friendship']}")
    romance = contact.get("romance")
    if romance is not None and romance != 0 and not family_label:
        parts.append(f"Romance between {name} and the player: {romance}")
    if contact.get("in_household") is True:
        parts.append("Lives in the same household as the player")

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
    """Generate an incoming phone call from a random relationship sim."""
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
        mutual_block = "\n\nPeople BOTH of you know (these are the ONLY mutual sims you can reference by name):\n" + "\n".join(f"  - {m}" for m in mutuals)
        mutual_block += "\nFeel free to gossip about, mention, or bring up any of these sims naturally. \
DO NOT invent any other sim names — if you need to reference someone not on this list, \
use a generic reference like 'a coworker', 'my neighbor', 'this friend of mine' instead."

    protag_rels = _get_protagonist_relationships()
    protag_block = f"\n\n{protag_rels}" if protag_rels else ""

    prompt = (
        f"Caller info:\n{rel_desc}{history_block}{mutual_block}{protag_block}\n\n"
        f"They are calling {main_name}{_location_context(main_si, contact)}.\n\n"
        f"Write what {contact['name']} says during this phone call. "
        f"If there is past interaction history, reference or build on it naturally. "
        f"If they live in different worlds, acknowledge the distance naturally "
        f"(e.g. ask how things are there, suggest visiting, reference their world). "
        f"When referring to other sims, use correct relationship labels "
        f"(e.g. say 'your wife' not 'Vivian's spouse' if the player IS Vivian's spouse). "
        f"Make the reason for calling feel natural given their relationship."
    )

    def _on_result(text, error):
        title = f"Call from {contact['name']}"
        if text:
            text = _apply_mood_from_text(text, reason="Call from " + contact["name"])
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
        mutual_block = "\n\nPeople BOTH of you know (these are the ONLY mutual sims you can reference by name):\n" + "\n".join(f"  - {m}" for m in mutuals)
        mutual_block += "\nFeel free to gossip about, mention, or bring up any of these sims naturally. \
DO NOT invent any other sim names — if you need to reference someone not on this list, \
use a generic reference like 'a coworker', 'my neighbor', 'this friend of mine' instead."

    protag_rels = _get_protagonist_relationships()
    protag_block = f"\n\n{protag_rels}" if protag_rels else ""

    prompt = (
        f"Sender info:\n{rel_desc}{history_block}{mutual_block}{protag_block}\n\n"
        f"They are texting {main_name}{_location_context(main_si, contact)}.\n\n"
        f"Write 1-3 text messages from {contact['name']}. "
        f"If there is past interaction history, reference or build on it naturally. "
        f"If they live in different worlds, acknowledge the distance naturally. "
        f"When referring to other sims, use correct relationship labels "
        f"(e.g. say 'your wife' not 'Vivian's spouse' if the player IS Vivian's spouse). "
        f"Make the content feel natural given their relationship and current mood."
    )

    def _on_result(text, error):
        title = f"Text from {contact['name']}"
        if text:
            text = _apply_mood_from_text(text, reason="Text from " + contact["name"])
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
        mutual_block = "\n\nPeople BOTH of you know (the ONLY mutual sims you can name):\n" + "\n".join(f"  - {m}" for m in mutuals)
        mutual_block += "\nDO NOT invent other sim names — use generic references like 'a coworker' if needed."

    protag_rels = _get_protagonist_relationships()
    protag_block = f"\n\n{protag_rels}" if protag_rels else ""

    prompt = (
        f"Relationship info:\n{rel_desc}{history_block}{mutual_block}{protag_block}\n\n"
        f"Conversation so far:\n{convo_text}\n\n"
        f"Write {other_name}'s reply (1-3 short text messages)."
    )

    def _on_result(text, error):
        if text:
            text = _apply_mood_from_text(text, reason="Reply from " + other_name)
            history.append({"role": "them", "text": text})
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


def send_text(contact, player_message, callback=None, output=None):
    """
    Send a text TO a specific sim. The player writes the message,
    and the sim responds in character.
    """
    main_si = sim_context.get_main_sim_info()
    main_name = main_si.first_name if main_si else "your Sim"
    other_name = contact["name"]

    _start_conversation(contact, "")
    _active_conversation["history"] = [{"role": "you", "text": player_message}]

    language = config.get_language()
    system = _REPLY_SYSTEM.format(
        language=language,
        other_name=other_name,
        main_name=main_name,
    )
    rel_desc = _describe_relationship(contact)
    sim_history = journal.format_sim_history_for_prompt(other_name)
    history_block = f"\n\n{sim_history}" if sim_history else ""
    mutuals = _get_mutual_contacts(contact)
    mutual_block = ""
    if mutuals:
        mutual_block = "\n\nPeople BOTH of you know (the ONLY mutual sims you can name):\n" + "\n".join(f"  - {m}" for m in mutuals)
        mutual_block += "\nDO NOT invent other sim names — use generic references like 'a coworker' if needed."

    protag_rels = _get_protagonist_relationships()
    protag_block = f"\n\n{protag_rels}" if protag_rels else ""

    prompt = (
        f"Relationship info:\n{rel_desc}{history_block}{mutual_block}{protag_block}\n\n"
        f"{main_name} just texted {other_name}: \"{player_message}\"\n\n"
        f"Write {other_name}'s reply (1-3 short text messages). "
        f"If {main_name} mentions people or events you don't have details about, "
        f"improvise naturally as {other_name} would — react in character, never refuse."
    )

    def _on_send_text_result(text, error):
        if text:
            text = _apply_mood_from_text(text, reason="Text from " + other_name)
            _active_conversation["history"].append({"role": "them", "text": text})
            journal.add_entry(
                "text",
                f"Text conversation with {other_name}:\n"
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
            notifications.show_error(error, output=output)
        if callback:
            callback(text, error)

    return api_client.call_claude_async(
        [{"role": "user", "content": prompt}],
        system=system,
        use_fast_model=True,
        callback=_on_send_text_result,
    )


def send_call(contact, player_topic, callback=None, output=None):
    """
    Call a specific sim about a topic. The player describes what they want
    to talk about, and the sim responds in character.
    """
    main_si = sim_context.get_main_sim_info()
    main_name = main_si.first_name if main_si else "your Sim"
    other_name = contact["name"]

    _start_conversation(contact, "")
    _active_conversation["history"] = [{"role": "you", "text": player_topic}]

    language = config.get_language()
    system = _CALL_SYSTEM.format(language=language)
    rel_desc = _describe_relationship(contact)
    sim_history = journal.format_sim_history_for_prompt(other_name)
    history_block = f"\n\n{sim_history}" if sim_history else ""
    mutuals = _get_mutual_contacts(contact)
    mutual_block = ""
    if mutuals:
        mutual_block = "\n\nPeople BOTH of you know (the ONLY mutual sims you can name):\n" + "\n".join(f"  - {m}" for m in mutuals)
        mutual_block += "\nDO NOT invent other sim names — use generic references like 'a coworker' if needed."

    protag_rels = _get_protagonist_relationships()
    protag_block = f"\n\n{protag_rels}" if protag_rels else ""

    prompt = (
        f"Person being called:\n{rel_desc}{history_block}{mutual_block}{protag_block}\n\n"
        f"{main_name} is calling {other_name}. {main_name} says: \"{player_topic}\"\n\n"
        f"Write what {other_name} says in response (3-5 lines of dialogue). "
        f"They should react naturally to what {main_name} said."
    )

    def _on_send_call_result(text, error):
        if text:
            text = _apply_mood_from_text(text, reason="Call with " + other_name)
            _active_conversation["history"].append({"role": "them", "text": text})
            journal.add_entry(
                "call",
                f"Call with {other_name}:\n"
                f"{main_name}: {player_topic}\n"
                f"{other_name}: {text}",
                sim_name=other_name,
            )
            title = f"Call with {other_name}"
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
        callback=_on_send_call_result,
    )
