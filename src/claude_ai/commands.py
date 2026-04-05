"""
Cheat console commands for the Claude AI mod.
Open the cheat console with Ctrl+Shift+C, then type a command.

COMMANDS:
  claude.status                     Check config and list all commands
  claude.dialogue                   Generate dialogue for the active sim
  claude.dialogue_situation <text>  Generate dialogue for a specific situation
  claude.backstory                  Generate a backstory for the active sim
  claude.story                      Narrative update for your household
  claude.storyline                  Generate a 3-act storyline
  claude.storyline_theme <theme>    Generate a storyline with a specific theme
  claude.drama                      Generate relationship drama arc
  claude.event                      Generate a surprise random event
  claude.challenge                  Generate a medium challenge
  claude.challenge_easy             Generate an easy challenge
  claude.challenge_hard             Generate a hard challenge
  claude.goals                      Generate weekly goals for this session
  claude.chat <message>             Chat with Claude about your game
  claude.reload                     Reload config (after editing claude_config.cfg)
  claude.auto_events on|off         Enable/disable random auto-events mid-session
"""

try:
    import sims4.commands
    from . import config, sim_context, dialogue, storyteller, event_generator, notifications, api_client, auto_events

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _require_config(output):
        if not config.is_configured():
            output("[Claude AI] Not configured. Edit claude_config.cfg and add your API key.")
            output("[Claude AI] Then run: claude.reload")
            return False
        return True

    def _on_result(feature_name, output):
        """Returns a callback that displays the result via notifications."""
        def callback(text, error):
            if error:
                notifications.show_error(error, output=output)
            else:
                notifications.show_result(feature_name, text, output=output)
        return callback

    # -------------------------------------------------------------------------
    # Status / config
    # -------------------------------------------------------------------------

    @sims4.commands.Command("claude.status", command_type=sims4.commands.CommandType.Live)
    def cmd_status(_connection=None):
        output = sims4.commands.CheatOutput(_connection)
        if config.is_configured():
            output(f"[Claude AI] ✓ Configured")
            output(f"[Claude AI]   Default model : {config.get_default_model()}")
            output(f"[Claude AI]   Fast model    : {config.get_fast_model()}")
            output(f"[Claude AI]   Max tokens    : {config.get_max_tokens()}")
            output(f"[Claude AI]   Language      : {config.get_language()}")
        else:
            output("[Claude AI] ✗ NOT configured — edit claude_config.cfg and add your API key")

        output(f"[Claude AI] {auto_events.status()}")
        output("")
        output("[Claude AI] Available commands:")
        output("  claude.dialogue             — active sim's dialogue")
        output("  claude.dialogue_situation   — dialogue for a specific situation")
        output("  claude.backstory            — active sim's backstory")
        output("  claude.story                — household narrative update")
        output("  claude.storyline            — 3-act storyline")
        output("  claude.storyline_theme X    — storyline with theme X")
        output("  claude.drama                — relationship drama arc")
        output("  claude.event                — surprise random event")
        output("  claude.challenge            — medium gameplay challenge")
        output("  claude.challenge_easy       — easy challenge")
        output("  claude.challenge_hard       — hard challenge")
        output("  claude.goals                — weekly session goals")
        output("  claude.chat <message>       — chat about your game")
        output("  claude.reload               — reload config file")

    @sims4.commands.Command("claude.reload", command_type=sims4.commands.CommandType.Live)
    def cmd_reload(_connection=None):
        output = sims4.commands.CheatOutput(_connection)
        config.reload_config()
        auto_events.restart()  # pick up any changes to auto-event settings
        if config.is_configured():
            output("[Claude AI] Config reloaded. API key found — you're good to go!")
        else:
            output("[Claude AI] Config reloaded. Still no API key found.")
            output("[Claude AI] Make sure claude_config.cfg is in your Mods folder.")

    @sims4.commands.Command("claude.auto_events", command_type=sims4.commands.CommandType.Live)
    def cmd_auto_events(toggle: str = None, _connection=None):
        output = sims4.commands.CheatOutput(_connection)
        if toggle is None:
            output(f"[Claude AI] {auto_events.status()}")
            output("[Claude AI] Usage: claude.auto_events on  OR  claude.auto_events off")
            return
        if toggle.lower() in ("on", "true", "1", "yes"):
            auto_events.stop()
            # Temporarily force-enable regardless of config
            config.get_config().set("claude_ai", "auto_events_enabled", "true")
            auto_events.start()
            output(f"[Claude AI] Auto-events turned ON for this session.")
            output(f"[Claude AI] {auto_events.status()}")
            output("[Claude AI] To make this permanent, set auto_events_enabled = true in claude_config.cfg")
        elif toggle.lower() in ("off", "false", "0", "no"):
            auto_events.stop()
            output("[Claude AI] Auto-events turned OFF for this session.")

    # -------------------------------------------------------------------------
    # Dialogue
    # -------------------------------------------------------------------------

    @sims4.commands.Command("claude.dialogue", command_type=sims4.commands.CommandType.Live)
    def cmd_dialogue(_connection=None):
        output = sims4.commands.CheatOutput(_connection)
        if not _require_config(output):
            return
        sim = sim_context.get_active_sim()
        if not sim:
            output("[Claude AI] No active sim found.")
            return
        name = sim.sim_info.first_name
        output(f"[Claude AI] Generating dialogue for {name}…")
        dialogue.generate_sim_dialogue(sim=sim, callback=_on_result(f"{name}'s Dialogue", output))

    @sims4.commands.Command("claude.dialogue_situation", command_type=sims4.commands.CommandType.Live)
    def cmd_dialogue_situation(situation: str = None, _connection=None):
        output = sims4.commands.CheatOutput(_connection)
        if not _require_config(output):
            return
        if not situation:
            output("[Claude AI] Usage: claude.dialogue_situation <situation description>")
            output("[Claude AI] Example: claude.dialogue_situation just got promoted")
            return
        sim = sim_context.get_active_sim()
        name = sim.sim_info.first_name if sim else "Your Sim"
        output(f"[Claude AI] Generating dialogue for: {situation}…")
        dialogue.generate_sim_dialogue(
            sim=sim,
            situation=situation,
            callback=_on_result(f"{name}'s Dialogue", output),
        )

    @sims4.commands.Command("claude.backstory", command_type=sims4.commands.CommandType.Live)
    def cmd_backstory(_connection=None):
        output = sims4.commands.CheatOutput(_connection)
        if not _require_config(output):
            return
        sim = sim_context.get_active_sim()
        name = sim.sim_info.first_name if sim else "Sim"
        output(f"[Claude AI] Generating backstory for {name}…")
        dialogue.generate_npc_backstory(sim=sim, callback=_on_result(f"{name}'s Backstory", output))

    # -------------------------------------------------------------------------
    # Storytelling
    # -------------------------------------------------------------------------

    @sims4.commands.Command("claude.story", command_type=sims4.commands.CommandType.Live)
    def cmd_story(_connection=None):
        output = sims4.commands.CheatOutput(_connection)
        if not _require_config(output):
            return
        output("[Claude AI] Generating household story update…")
        storyteller.generate_story_update(callback=_on_result("Household Story", output))

    @sims4.commands.Command("claude.storyline", command_type=sims4.commands.CommandType.Live)
    def cmd_storyline(_connection=None):
        output = sims4.commands.CheatOutput(_connection)
        if not _require_config(output):
            return
        output("[Claude AI] Generating 3-act storyline…")
        storyteller.generate_storyline(callback=_on_result("Storyline", output))

    @sims4.commands.Command("claude.storyline_theme", command_type=sims4.commands.CommandType.Live)
    def cmd_storyline_theme(theme: str = None, _connection=None):
        output = sims4.commands.CheatOutput(_connection)
        if not _require_config(output):
            return
        if not theme:
            output("[Claude AI] Usage: claude.storyline_theme <theme>")
            output("[Claude AI] Examples: romance  |  rivalry  |  rags to riches  |  ghost mystery")
            return
        output(f"[Claude AI] Generating storyline with theme: {theme}…")
        storyteller.generate_storyline(theme=theme, callback=_on_result("Storyline", output))

    @sims4.commands.Command("claude.drama", command_type=sims4.commands.CommandType.Live)
    def cmd_drama(_connection=None):
        output = sims4.commands.CheatOutput(_connection)
        if not _require_config(output):
            return
        output("[Claude AI] Generating relationship drama arc…")
        storyteller.generate_relationship_drama(callback=_on_result("Relationship Drama", output))

    # -------------------------------------------------------------------------
    # Events & challenges
    # -------------------------------------------------------------------------

    @sims4.commands.Command("claude.event", command_type=sims4.commands.CommandType.Live)
    def cmd_event(_connection=None):
        output = sims4.commands.CheatOutput(_connection)
        if not _require_config(output):
            return
        output("[Claude AI] Rolling a random event…")
        event_generator.generate_random_event(callback=_on_result("Random Event!", output))

    @sims4.commands.Command("claude.challenge", command_type=sims4.commands.CommandType.Live)
    def cmd_challenge(_connection=None):
        output = sims4.commands.CheatOutput(_connection)
        if not _require_config(output):
            return
        output("[Claude AI] Generating medium challenge…")
        event_generator.generate_challenge(difficulty="medium", callback=_on_result("Challenge", output))

    @sims4.commands.Command("claude.challenge_easy", command_type=sims4.commands.CommandType.Live)
    def cmd_challenge_easy(_connection=None):
        output = sims4.commands.CheatOutput(_connection)
        if not _require_config(output):
            return
        output("[Claude AI] Generating easy challenge…")
        event_generator.generate_challenge(difficulty="easy", callback=_on_result("Easy Challenge", output))

    @sims4.commands.Command("claude.challenge_hard", command_type=sims4.commands.CommandType.Live)
    def cmd_challenge_hard(_connection=None):
        output = sims4.commands.CheatOutput(_connection)
        if not _require_config(output):
            return
        output("[Claude AI] Generating hard challenge…")
        event_generator.generate_challenge(difficulty="hard", callback=_on_result("Hard Challenge", output))

    @sims4.commands.Command("claude.goals", command_type=sims4.commands.CommandType.Live)
    def cmd_goals(_connection=None):
        output = sims4.commands.CheatOutput(_connection)
        if not _require_config(output):
            return
        output("[Claude AI] Generating weekly goals…")
        event_generator.generate_weekly_goals(callback=_on_result("Weekly Goals", output))

    # -------------------------------------------------------------------------
    # Freeform chat
    # -------------------------------------------------------------------------

    @sims4.commands.Command("claude.chat", command_type=sims4.commands.CommandType.Live)
    def cmd_chat(message: str = None, _connection=None):
        output = sims4.commands.CheatOutput(_connection)
        if not _require_config(output):
            return
        if not message:
            output("[Claude AI] Usage: claude.chat <your message>")
            output("[Claude AI] Example: claude.chat what career should my sim pursue?")
            return

        context = sim_context.build_context_string()
        language = config.get_language()

        system = (
            f"You are a helpful, enthusiastic Sims 4 advisor and storyteller. "
            f"The player is asking about their game. Respond in {language}. "
            f"Be helpful, creative, and reference Sims 4 gameplay naturally. "
            f"Keep your response focused and under 300 words."
        )
        prompt = f"Current game state:\n{context}\n\nPlayer: {message}"

        output(f"[Claude AI] Thinking…")
        api_client.call_claude_async(
            [{"role": "user", "content": prompt}],
            system=system,
            callback=_on_result("Claude AI", output),
        )

except ImportError:
    # Running outside the Sims 4 game environment (e.g., during development)
    pass
