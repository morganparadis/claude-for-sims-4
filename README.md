# Claude AI for The Sims 4

Brings AI-generated dialogue, storylines, random events, and challenges to your game using the Claude API.

---

## Installation

1. Run `python build.py` from this folder — it builds the mod and copies it to your Mods folder automatically.
2. Open `claude_config.cfg` in your Mods folder and replace `YOUR_API_KEY_HERE` with your API key.
   - Get a key at [console.anthropic.com](https://console.anthropic.com/) (free to sign up, pay per use)
3. In The Sims 4: **Game Options → Other → enable Custom Content and Script Mods**, then restart.
4. Open the cheat console (`Ctrl+Shift+C`) and type `claude.status` to confirm it's working.

---

## How does Claude know about your Sims?

Every time you run a command, the mod reads live data from the game and sends it to Claude as context. Claude doesn't remember previous sessions — it reads fresh each time.

**What it reads:**
| Data | Example |
|---|---|
| Active sim's name | Lily Feng |
| Age stage | Young Adult |
| Current mood | Confident |
| Traits (up to 6) | Bookworm, Ambitious, Loner |
| Career | Doctor |
| Aspiration | Renaissance Sim |
| Household name | The Feng Household |
| All household members | names, ages, moods, traits |
| Household funds | §42,800 |
| Current lot name | Oakenstead |

**What it does NOT know:**
- Relationship levels or friendship history
- Skill levels or career progress
- What happened in previous play sessions
- Events you haven't told it about

You can fill in gaps using `claude.chat`: for example, `claude.chat my sim just got fired and her husband doesn't know yet` gives Claude that context for richer responses.

---

## Commands

Open the cheat console with `Ctrl+Shift+C`, type a command, press Enter.

### Dialogue
| Command | What it does |
|---|---|
| `claude.dialogue` | 4–5 in-character lines for your active sim |
| `claude.dialogue_situation just got promoted` | Dialogue for a specific situation |
| `claude.backstory` | A backstory and personality reveal for the active sim |

### Storytelling
| Command | What it does |
|---|---|
| `claude.story` | 2–3 paragraph narrative update for the household |
| `claude.storyline` | Full 3-act storyline with gameplay goals |
| `claude.storyline_theme romance` | Storyline with a specific theme (try: rivalry, mystery, rags to riches, family drama, haunting) |
| `claude.drama` | Relationship drama arc between two household members |

### Events & Challenges
| Command | What it does |
|---|---|
| `claude.event` | A surprise random event to shake up your session |
| `claude.goals` | 5 session goals (mixed easy/hard, with a stretch goal) |
| `claude.challenge` | Medium difficulty gameplay challenge |
| `claude.challenge_easy` | Easy challenge |
| `claude.challenge_hard` | Hard challenge with strict rules |

### Protagonist
| Command | What it does |
|---|---|
| `claude.set_main Lily Feng` | Set Lily Feng as your protagonist sim |
| `claude.main` | Show your current protagonist and their relationship network |

Setting a protagonist focuses all story, event, and chat prompts on that sim and the sims they have relationships with — rather than every sim in the save file. This keeps the AI grounded in the story you're actually playing.

You can also set the protagonist in `claude_config.cfg` with `main_sim_name = Lily Feng`. The in-game command saves to `ClaudeAI_Settings.json` and persists across sessions.

If no protagonist is set, the mod falls back to your currently active sim.

### General
| Command | What it does |
|---|---|
| `claude.chat <message>` | Freeform — ask anything about your game |
| `claude.auto_events on` | Turn on random auto-events for this session |
| `claude.auto_events off` | Turn them off |
| `claude.status` | Show config, auto-event status, and all commands |
| `claude.reload` | Reload config file (after editing claude_config.cfg) |

---

## Auto-Events

Auto-events fire randomly while you play without you having to ask. They use **real-world time** — game speed doesn't affect them.

**How it works:**
- Every N real-world minutes, the mod rolls a random check
- If the roll succeeds (based on your configured chance %), it generates a random piece of content
- It only fires when you're in an active household (not during loading screens, CAS, or build mode)
- Silent failures — if there's a network error, nothing happens, no interruption

**Turn on in `claude_config.cfg`:**
```ini
auto_events_enabled = true
auto_event_interval_minutes = 20   ; check every 20 real minutes
auto_event_chance = 40             ; 40% chance each check fires something
auto_event_types = event, goals    ; what can fire: event, goals, story, drama
```

With the defaults (20 min interval, 40% chance), you get something roughly every 50 real minutes on average.

**Or toggle mid-session** without editing the config:
```
claude.auto_events on
claude.auto_events off
```

---

## Configuration (`claude_config.cfg`)

| Setting | Default | Description |
|---|---|---|
| `api_key` | *(required)* | Your Anthropic API key |
| `default_model` | `claude-opus-4-6` | Model for stories and storylines |
| `fast_model` | `claude-haiku-4-5` | Model for dialogue, events, goals |
| `max_tokens` | `512` | Max length of responses |
| `language` | `English` | Language for all generated content |
| `main_sim_name` | *(blank)* | Protagonist sim (FirstName LastName). Falls back to active sim. |
| `auto_events_enabled` | `false` | Turn on random auto-events |
| `auto_event_interval_minutes` | `20` | Real-world minutes between checks |
| `auto_event_chance` | `40` | Percent chance each check fires |
| `auto_event_types` | `event, goals` | Content types for auto-events |

After editing the config, type `claude.reload` in-game to apply changes without restarting.

---

## API Cost

Everything is very cheap. Rough estimates per command:

| Type | Model | Estimated cost |
|---|---|---|
| Dialogue, events, goals | Haiku | ~$0.001 |
| Story, storyline, drama | Opus | ~$0.01–0.02 |
| Chat | Opus | ~$0.005–0.01 |

A heavy play session with 30+ commands + auto-events would cost around $0.20–0.50.

**To reduce cost further**, set `default_model = claude-haiku-4-5` in the config. The quality drops a bit for long-form stories but is still good for events and dialogue.

---

## Development

The source is in `src/claude_ai/`. After making changes, run `python build.py` to rebuild and reinstall.

```
src/claude_ai/
  __init__.py        mod entry point, starts auto-events
  config.py          reads claude_config.cfg
  api_client.py      HTTP calls to Claude API (urllib, background thread)
  sim_context.py     reads sim data from the game
  dialogue.py        dialogue, conversation, backstory generation
  storyteller.py     story updates, storylines, relationship drama
  event_generator.py random events, challenges, weekly goals
  auto_events.py     background thread for random auto-events
  notifications.py   in-game popup + cheat console output
  commands.py        all claude.* cheat commands
```
