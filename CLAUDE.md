# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**WORLD SIMULATION** is a 2D multi-agent life simulation game built with **Pygame** and powered by **Ollama LLMs**. The simulator spawns AI characters ("almas") with personality traits, needs (hunger/energy/hygiene/social), and autonomous behaviors including wandering, eating, sleeping, showering, chatting, and thinking.

### Architecture Summary

```
WORLD_simulation/
├── main.py              # Main game loop: pygame event handling + update/draw cycle
│                        - Spawns characters via CharacterFactory
│                        - Handles keyboard (N, Space, +/- etc.) + mouse clicks
│                        - Manages loading screens and toast notifications
├── core/
│   ├── config.py        # Constants: screen size, decay rates, trait names/palettes, thresholds
│   ├── world.py         # WorldObject class for food/bed/shower/tree objects; generate_world() placement logic
│   ├── character_factory.py  # Generates batch of characters (6-50) via Ollama prompts or fallback stories
│   ├── ollama_client.py     # Async requests to localhost:11434, _clean_response(), ask_ollama_async() wrapper using threads
│   └── conv_logger.py    # Logs character conversations to "conversaciones/" directory with timestamps
├── ui/
│   └── panels.py        # Bottom panel (stats/bars), draw_toasts(), CreationModal dialog for new characters
└── conversaciones/      # Generated conversation logs (auto-created by conv_logger)

```

### Key Design Patterns & Concepts

**FSM State Machine (`core.character`):**
- States: `S_IDLE`, `S_WANDER`, `S_SEEK_FOOD/EAT/BED/SLEEP`, `S_SHOWER`, `S_CHAT/chatting_thinking` 
- State transitions driven by `_run_fsm()` evaluating needs vs. critical/low thresholds (CRITICAL=20, LOW=40)
- Each state has specific actions: movement toward target, resource consumption gains, timers

**Multi-turn Conversation Engine:**
- SpeechBubble displays temporary text with fade-out timing based on `len(words)/130*60` formula  
- ConversationEngine spawns parallel threads for alternating speaker/listener dialogue (max 8 turns)
- System prompt enforces: Spanish only, max ~25 words per turn, no markdown/asterisks

**Need Decay & Priority:**
```python
# Each second decay rates in config.py
HUNGER_DECAY = HUNGER_DECAY
ENERGY_DECAY = ENERGY_DECAY  
HYGIENE_DECAY  = HYGIENE_DECAY
SOCIAL_DECAY   = SOCIAL_DECAY
```

**Parallel Character Generation (character_factory):**
- Uses `threading.Semaphore(4)` to limit concurrent Ollama calls and avoid API saturation
- Falls back to pre-written `_FALLBACK_HISTORIAS` if Ollama unavailable  
- Progress callbacks update loading screen with percentage bar in main loop

## Commands for Development

### Running the Application

```bash
# Start simulation (requires Ollama running at localhost:11434)
python main.py

# If using conda/virtualenv environment first
conda activate world_sim_env  # or venv/venv depending on setup
python main.py
```

### Installing Dependencies

```bash
pip install pygame requests ollama>=0.2.8
ollama pull llama3:latest  # or gemma, mistral, phi - pick your model of choice
ollama serve               # Start Ollama in background (separate terminal)
```

## Code Structure Details

### core/character.py — Character Agent Core Logic

**Key properties & methods:**

- `_run_fsm(dt, world_objects, characters)` — Main state machine evaluating all conditions every frame  
- `_choose_action()` — FSM decision: if `most_urgent_need` < CRITICAL → seek; else wander or find chat candidate
- State-specific updates in the same method (e.g. S_EAT boosts hunger by 18*dt/sec)
- Personality trait modifiers applied directly to speed calculations and behavior probabilities

**Movement:** `_move_towards()` uses `math.hypot` distance checks, respects "perezoso" (-35%) or "energetico" (+30%) speed multipliers  

**Chatting Logic (`_start_conversation`, `_end_conversation`, `abort_conversation`):**
- Initiator stays put while partner moves to adjacent position  
- ConversationEngine auto-spawns and runs in daemon thread
- Other character joins with matching state, distance clamped by radii + 4px gap

### core/ollama_client.py — LLM Client Layer

**Thread-based async wrapper:**
```python
def ask_ollama_async(prompt: str, callback):
    def _worker(): # Runs in daemon thread
        requests.post(OLLAMA_URL, json=payload) → parse JSON response
        text = _clean_response(raw, max_chars=200)  # strip markdown/formatting
        callback(text or "...")  
```

### core/character_factory.py — Character Factory Logic

**Banco de Nombres:** Pre-populated list of ~56 Spanish names (Aria, Berto, Celia...) with fallback "Alma{i}" if exhausted

Generate_batch() flow:
1. If `count` not specified → random 6-50 characters  
2. Generate trait assignment via TRAITS array randomly shuffled
3. Ollama prompt per character for backstory (max 80 tokens, temperature=1)
4. Parallelize up to 4 threads with semaphore limiter

### main.py — Main Loop Architecture

```python
while running:  # Main game loop ~60 iterations/sec at normal speed
    dt_raw = clock.tick(FPS) / 1000.0  
    dt     = 0.0 if paused else min(dt_raw * sim_speed, 0.2)  

    for event in pygame.event.get():  # Process QUIT/KEYDOWN/MOUSEBUTTONDOWN events 
        - Handle modal open/close (creation dialog), pause/resume
        - Character creation via N key; delete character with DELETE
        - Regenerate world objects pressing R
    
    toasts = [t for t in toasts if t.alive()]  # Filter expired notifications  
    
    for c in characters:                         # Update all agents sequentially
        c.update(dt, world_objects, characters)

    # Draw phase (subsurface of screen to overlay on top half UI panel + bottom HUD text) 
```

## Controls Reference

| Key | Function                              |
|-----|---------------------------------------|
| N   | Create new character via modal dialog      |
| Space  | Pause / Resume simulation             |
| +/-    | Adjust speed (0.25x to 5.0x multiplier)|  
| T   | Request AI thought for selected character       |
|R   | Regenerate world objects                 |
| DELETE     | Delete selected character           |
| ESC      | Deselect current character         |
| L   | View conversation logs path             |

## World Objects & Personality Traits (Español)

**Object Types:** COMIDA (food), CAMA (bed/sleep location), DUCHA (shower spot), ÁRBOL (deco tree)  

**Trait Effects from config.py TRAITS list / TRAIT_DESC lookup table:**
- `amigable` — Seeks social interaction frequently  
- `timido`    — Avoids contact, prefers solitude (~25% chance to decline chat invites)  
- `curioso`   — Actively explores the world via wander state  
- `agresivo`  — Speaks with high energy in dialogue bursts  
- `perezoso`  — Moves at -35% speed multiplier  
- `energetico`— Moves +30% faster than base SPEED_NORMAL rate  
- `melancolico`— Reflective, sometimes solitary behavior patterns
- `optimista`   — Always good humor in speech bubbles  

## Common Development Tasks

### Running a Single Test (if pytest exists)
```bash
pytest test_module.py::test_character_state_transitions -v  # Adjust path to tests dir if different
```

### Regenerating Character Batch with Different Seed-like Behavior
Edit character_factory.NOMBRES or adjust random.seed() import from `random` module for reproducibility  

### Changing Ollama Model  
In core/config.py: change `OLLAMA_MODEL = "gemma4:e4b"` to `"mistral"`, `"phi3"`, etc. and restart main loop

## Conversation Logging System
- All dialogs logged as text files in `conversaciones/` directory (auto-created on first run)  
- Files named with timestamp + character names: `{YYYYMMDD}_{HHMMSS}_{name1}_y_{name2}.txt`
- Global session log also appended to `sesion_computa.txt` for review  

## Keyboard Navigation in Modal Dialogs

When creating characters (N key):
- TAB switches between fields: Nombre → Personalidad dropdown → Historia  
- Arrow keys navigate personality selector up/down the trait list  
- CLICK on personality field highlights it; hover dot indicator shows current selection position  

## UI Layout Breakdown (from panels.py)

**Bottom Panel Structure:** Left column = selected character details, Middle column = population dots summary, Right column = controls reference table + Ollama status LED

**Toast System:** Duration calculated per message type (~2-4 seconds), alpha fade-in/fade-out over ~0.6s at edges using `sin()` for smooth transitions

## Debugging Patterns

- If characters freeze → check if `_dist(self.target_obj.x, self.y)` < threshold triggers state transition
- Conversation hangups likely from Ollama timeout (check core.config.OLLAMA_TIMEOUT=80)  
- Memory leaks: daemon threads spawned per conversation but all set as `daemon=True` so safe on exit

## File Conventions

- All code in Spanish with English variable names for compatibility; strings render using pygame.font.SysFont
- Color palette from config.py uses RGB tuples (R,G,B); special alpha colors use 4-tuple format  
- State machine states: S_ prefix convention maintained throughout character module  
