"""
Collects information about the current game state to give Claude rich context.
All Sims 4 API calls are wrapped in try/except to handle version differences gracefully.
"""


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

    return "\n".join(lines) if lines else "No game context available (not in an active save)."
