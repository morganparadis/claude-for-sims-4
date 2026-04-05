"""
Collects information about the current game state to give Claude rich context.
All Sims 4 API calls are wrapped in try/except to handle version differences gracefully.
"""

# Mapping from sims4.common.Pack enum attribute name → friendly pack name.
# Each entry is tried individually so unknown/future packs don't crash anything.
_PACK_MAP = {
    # Expansion Packs
    "EP01": "Get to Work",
    "EP02": "Get Together",
    "EP03": "City Living",
    "EP04": "Cats & Dogs",
    "EP05": "Seasons",
    "EP06": "Get Famous",
    "EP07": "Island Living",
    "EP08": "Discover University",
    "EP09": "Eco Lifestyle",
    "EP10": "Snowy Escape",
    "EP11": "Cottage Living",
    "EP12": "High School Years",
    "EP13": "Growing Together",
    "EP14": "Horse Ranch",
    "EP15": "For Rent",
    "EP16": "Life & Death",
    # Game Packs
    "GP01": "Outdoor Retreat",
    "GP02": "Spa Day",
    "GP03": "Dine Out",
    "GP04": "Vampires",
    "GP05": "Parenthood",
    "GP06": "Jungle Adventure",
    "GP07": "StrangerVille",
    "GP08": "Realm of Magic",
    "GP09": "Star Wars: Journey to Batuu",
    "GP10": "Dream Home Decorator",
    "GP11": "My Wedding Stories",
    "GP12": "Werewolves",
    "GP13": "Lovestruck",
    "GP14": "Businesses & Hobbies",
}

# Cache so we only scan once per session
_installed_packs_cache = None


def get_installed_packs():
    """
    Return a list of friendly pack names the player has installed.
    Results are cached after the first call.
    """
    global _installed_packs_cache
    if _installed_packs_cache is not None:
        return _installed_packs_cache

    installed = []
    try:
        import sims4.common
        for attr, name in _PACK_MAP.items():
            try:
                pack = getattr(sims4.common.Pack, attr, None)
                if pack is not None and sims4.common.is_available_pack(pack):
                    installed.append(name)
            except Exception:
                continue
    except Exception:
        pass

    _installed_packs_cache = installed
    return installed


def _safe(obj, attr, default=None):
    try:
        return getattr(obj, attr, default)
    except Exception:
        return default


def get_active_sim():
    """Return the currently controlled Sim, or None."""
    try:
        import services
        client = services.client_manager().get_first_client()
        if client and client.active_sim:
            return client.active_sim
    except Exception:
        pass
    return None


def get_sim_traits(sim_info, limit=6):
    """Return a list of cleaned trait names for a sim."""
    try:
        raw = list(sim_info.trait_tracker.traits)
        names = []
        for t in raw:
            name = t.__name__
            # Skip internal/occult traits that aren't player-visible
            if any(name.startswith(p) for p in ("trait_occult", "trait_hidden", "trait_gender")):
                continue
            cleaned = name.replace("trait_", "").replace("_", " ").title()
            names.append(cleaned)
            if len(names) >= limit:
                break
        return names
    except Exception:
        return []


def get_sim_mood(sim_info):
    """Return the sim's current mood as a readable string."""
    try:
        mood = sim_info.get_mood()
        if mood:
            return mood.__name__.replace("Mood_", "").replace("_", " ")
    except Exception:
        pass
    return "Neutral"


def get_sim_skills(sim_info, min_level=1, limit=12):
    """
    Return a dict of {skill_name: level} for skills the sim has learned.
    Only includes skills at or above min_level. Sorted highest first.
    """
    skills = {}
    try:
        tracker = sim_info.skill_tracker
        if not tracker:
            return skills
        for stat_inst in tracker._statistics.values():
            try:
                level = int(stat_inst.get_value())
                if level < min_level:
                    continue
                name = stat_inst.__class__.__name__
                cleaned = (name
                    .replace("Skill_Adult_", "")
                    .replace("Skill_Child_", "")
                    .replace("Skill_Toddler_", "")
                    .replace("Skill_Teen_", "")
                    .replace("Skill_", "")
                    .replace("_", " ")
                    .title())
                skills[cleaned] = level
            except Exception:
                continue
    except Exception:
        pass
    # Sort by level descending, take top N
    sorted_skills = dict(sorted(skills.items(), key=lambda x: -x[1])[:limit])
    return sorted_skills


def get_sim_relationships(sim_info, limit=8):
    """
    Return a list of relationship dicts for this sim's notable relationships.
    Each dict has: name, status (relationship bit labels), and optionally scores.
    """
    relationships = []
    try:
        import services
        rel_tracker = sim_info.relationship_tracker
        sim_manager = services.sim_info_manager()
        my_id = sim_info.sim_id

        for rel in rel_tracker.relationships.values():
            try:
                other_id = rel.sim_id_b if rel.sim_id_a == my_id else rel.sim_id_a
                other_si = sim_manager.get(other_id)
                if not other_si:
                    continue

                name = f"{other_si.first_name} {other_si.last_name}".strip()

                # Relationship bit labels (Friend, Enemy, Married, etc.)
                bit_labels = []
                try:
                    for bit in rel.relationship_bit_tracker.relationship_bits:
                        bit_name = bit.__name__
                        _visible_keywords = (
                            "Friend", "Enemy", "Romantic", "Married", "Divorced",
                            "BFF", "Acquaintance", "Hate", "Despise", "Crush",
                            "Partner", "Engaged", "FamilyRelationship",
                        )
                        if any(kw in bit_name for kw in _visible_keywords):
                            label = (bit_name
                                .replace("RelationshipBit_", "")
                                .replace("Romantic_", "")
                                .replace("_", " ")
                                .strip())
                            bit_labels.append(label)
                except Exception:
                    pass

                # Try to get numeric friendship/romance scores
                friendship = None
                romance = None
                try:
                    for track_stat in rel._relationship_tracks.values():
                        track_name = track_stat.__class__.__name__.lower()
                        val = int(track_stat.get_value())
                        if "romance" in track_name:
                            romance = val
                        elif "friend" in track_name or "acquaint" in track_name:
                            friendship = val
                except Exception:
                    pass

                entry = {"name": name}
                if bit_labels:
                    entry["status"] = ", ".join(bit_labels[:3])
                if friendship is not None:
                    entry["friendship"] = friendship
                if romance is not None and romance != 0:
                    entry["romance"] = romance

                # Only include relationships with some substance
                if bit_labels or (friendship is not None and abs(friendship) > 10):
                    relationships.append(entry)
                    if len(relationships) >= limit:
                        break
            except Exception:
                continue
    except Exception:
        pass
    return relationships


def get_sim_career(sim_info):
    """Return the sim's career name if employed."""
    try:
        career_tracker = sim_info.career_tracker
        if career_tracker:
            for career in career_tracker.careers.values():
                return career.__class__.__name__.replace("_", " ").title()
    except Exception:
        pass
    return None


def get_sim_aspiration(sim_info):
    """Return the sim's current aspiration name."""
    try:
        asp = sim_info.primary_aspiration
        if asp:
            return asp.__name__.replace("aspiration_", "").replace("_", " ").title()
    except Exception:
        pass
    return None


def get_sim_info_dict(sim):
    """Build a context dict for a single sim."""
    info = {"name": "Unknown Sim"}
    try:
        si = sim.sim_info
        first = _safe(si, "first_name", "")
        last = _safe(si, "last_name", "")
        info["name"] = f"{first} {last}".strip() or "Unknown Sim"
        info["age"] = str(_safe(si, "age", "Unknown")).replace("Age.", "")
        info["gender"] = str(_safe(si, "gender", "Unknown")).replace("Gender.", "")
        info["mood"] = get_sim_mood(si)
        info["traits"] = get_sim_traits(si)

        career = get_sim_career(si)
        if career:
            info["career"] = career

        aspiration = get_sim_aspiration(si)
        if aspiration:
            info["aspiration"] = aspiration

        info["skills"] = get_sim_skills(si)
        info["relationships"] = get_sim_relationships(si)

    except Exception:
        pass
    return info


def get_household_context():
    """Build a context dict for the active household."""
    try:
        import services
        household = services.active_household()
        if not household:
            return {}

        members = []
        for si in household.sim_info_gen():
            try:
                first = _safe(si, "first_name", "")
                last = _safe(si, "last_name", "")
                name = f"{first} {last}".strip() or "Unknown"
                age = str(_safe(si, "age", "")).replace("Age.", "")
                mood = get_sim_mood(si)
                traits = get_sim_traits(si, limit=4)
                career = get_sim_career(si)
                entry = {"name": name, "age": age, "mood": mood, "traits": traits}
                if career:
                    entry["career"] = career
                members.append(entry)
            except Exception:
                continue

        funds = "unknown"
        try:
            funds = str(household.funds.money)
        except Exception:
            pass

        return {
            "household_name": str(_safe(household, "name", "Unknown Household")),
            "members": members,
            "funds": funds,
        }
    except Exception:
        return {}


def get_current_lot_name():
    """Return the name of the current lot/venue."""
    try:
        import services
        zone = services.current_zone()
        if zone:
            lot = zone.lot
            if lot:
                return str(_safe(lot, "lot_name", "Unknown Lot"))
    except Exception:
        pass
    return None


def build_context_string(sim=None):
    """
    Build a human-readable context string to include in prompts.
    Includes active sim info and household overview.
    """
    lines = []

    target_sim = sim or get_active_sim()
    if target_sim:
        info = get_sim_info_dict(target_sim)
        lines.append(f"Active Sim: {info['name']}")
        if info.get("age"):
            lines.append(f"  Age: {info['age']}")
        if info.get("gender"):
            lines.append(f"  Gender: {info['gender']}")
        lines.append(f"  Mood: {info.get('mood', 'Unknown')}")
        if info.get("traits"):
            lines.append(f"  Traits: {', '.join(info['traits'])}")
        if info.get("career"):
            lines.append(f"  Career: {info['career']}")
        if info.get("aspiration"):
            lines.append(f"  Aspiration: {info['aspiration']}")
        if info.get("skills"):
            skill_str = ", ".join(f"{k} {v}" for k, v in info["skills"].items())
            lines.append(f"  Skills: {skill_str}")
        if info.get("relationships"):
            lines.append("  Relationships:")
            for r in info["relationships"]:
                rel_line = f"    - {r['name']}"
                if r.get("status"):
                    rel_line += f" ({r['status']})"
                if r.get("friendship") is not None:
                    rel_line += f" [friendship: {r['friendship']}]"
                if r.get("romance") is not None:
                    rel_line += f" [romance: {r['romance']}]"
                lines.append(rel_line)

    lot = get_current_lot_name()
    if lot:
        lines.append(f"Current Location: {lot}")

    household = get_household_context()
    if household:
        lines.append(f"\nHousehold: {household.get('household_name', 'Unknown')}")
        lines.append(f"  Funds: §{household.get('funds', '?')}")
        members = household.get("members", [])
        if members:
            lines.append("  Members:")
            for m in members:
                member_line = f"    - {m['name']} ({m.get('age', '?')}, {m.get('mood', '?')} mood)"
                if m.get("traits"):
                    member_line += f", traits: {', '.join(m['traits'])}"
                if m.get("career"):
                    member_line += f", career: {m['career']}"
                lines.append(member_line)

    packs = get_installed_packs()
    if packs:
        lines.append(f"\nInstalled Packs: {', '.join(packs)}")
    else:
        lines.append("\nInstalled Packs: base game only (or could not detect)")

    return "\n".join(lines) if lines else "No game context available (not in an active save)."


def build_context_string_with_journal(sim=None):
    """
    Full context string including recent journal history.
    Use this for story, event, and chat prompts where past events matter.
    Skip it for quick dialogue prompts where latency is more important.
    """
    from . import journal  # local import to avoid circular dependency
    ctx = build_context_string(sim=sim)
    history = journal.format_for_prompt()
    if history:
        return f"{ctx}\n\n{history}"
    return ctx
