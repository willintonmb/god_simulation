# ─────────────────────────────────────────────
#  GOD SIMULATION  –  Main Entry Point
#  Run with:  python main.py
#
#  Requirements:
#    pip install pygame requests
#    Ollama running locally (ollama serve)
#    At least one model pulled, e.g.: ollama pull llama3.2
# ─────────────────────────────────────────────
import sys, math, random, time
import pygame

from core.config import *
from core.world      import generate_world
from core.character  import Character, PALETTE
from core.ollama_client import check_ollama, list_models, ask_ollama_async
from ui.panels       import (draw_bottom_panel, draw_toasts,
                              CreationModal, Toast)


# ── Font helper ──────────────────────────────
def load_fonts():
    pygame.font.init()
    try:
        # Try system monospace
        sm = pygame.font.SysFont("DejaVu Sans Mono", 13)
        md = pygame.font.SysFont("DejaVu Sans Mono", 17)
        lg = pygame.font.SysFont("DejaVu Sans Mono", 22, bold=True)
    except Exception:
        sm = pygame.font.Font(None, 16)
        md = pygame.font.Font(None, 20)
        lg = pygame.font.Font(None, 26)
    return sm, md, lg


# ── World drawing ────────────────────────────
def draw_world(surf, world_objects, fonts):
    font_sm = fonts[0]
    # Background
    surf.fill(C_WORLD_BG)

    # Subtle grid
    for gx in range(0, WORLD_W, TILE * 2):
        pygame.draw.line(surf, C_GRID, (gx, 0), (gx, WORLD_H), 1)
    for gy in range(0, WORLD_H, TILE * 2):
        pygame.draw.line(surf, C_GRID, (0, gy), (WORLD_W, gy), 1)

    # World border
    pygame.draw.rect(surf, C_ACCENT, (0, 0, WORLD_W, WORLD_H), 2)

    # Objects
    for obj in world_objects:
        obj.draw(surf, font_sm)


# ── Default characters ────────────────────────
def make_defaults():
    defaults = [
        ("Aria",    "curious",    "A scientist fascinated by the unknown."),
        ("Rex",     "aggressive", "A warrior who acts first, thinks later."),
        ("Mila",    "friendly",   "A baker who loves sharing food."),
        ("Zeno",    "lazy",       "A philosopher who prefers thinking to moving."),
    ]
    chars = []
    for name, trait, backstory in defaults:
        x = random.uniform(80, WORLD_W - 80)
        y = random.uniform(80, WORLD_H - 80)
        c = Character(name, trait, backstory, x, y, random.choice(PALETTE))
        chars.append(c)
    return chars


# ── Main ────────────────────────────────────
def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("✦ God Simulation — Multi-Agent World")
    clock  = pygame.time.Clock()
    fonts  = load_fonts()
    font_sm, font_md, font_lg = fonts

    # Check Ollama
    ollama_ok = check_ollama()
    models    = list_models() if ollama_ok else []
    model_used = models[0] if models else OLLAMA_MODEL

    world_objects = generate_world()
    characters    = make_defaults()
    selected      = None
    toasts        = []
    sim_speed     = 1.0
    paused        = False
    modal         = CreationModal(fonts, TRAITS)

    def toast(msg):
        toasts.append(Toast(msg))
        # trim old
        while len(toasts) > 8:
            toasts.pop(0)

    if ollama_ok:
        toast(f"✓ Ollama connected — model: {model_used}")
    else:
        toast("⚠ Ollama offline — dialogues disabled")

    # ── Game loop ────────────────────────────
    running = True
    while running:
        dt_raw = clock.tick(FPS) / 1000.0
        dt     = 0.0 if paused else dt_raw * sim_speed

        # ── Events ───────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # Pass to modal first
            result = modal.handle_event(event)
            if result:
                if result[0] == "create":
                    _, name, trait, backstory = result
                    x = random.uniform(80, WORLD_W - 80)
                    y = random.uniform(80, WORLD_H - 80)
                    c = Character(name, trait, backstory, x, y, random.choice(PALETTE))
                    characters.append(c)
                    toast(f"✦ {name} has entered the world!")
                    selected = c
                    if ollama_ok:
                        ask_ollama_async(
                            f"You are {name}, a {trait} person. {backstory}. "
                            "You just appeared in a mysterious world. React in one short sentence.",
                            lambda txt, _c=c: setattr(_c, 'bubble',
                                __import__('core.character', fromlist=['SpeechBubble']).SpeechBubble(txt))
                        )
                continue
            if modal.active:
                continue

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    paused = not paused
                    toast("⏸ Paused" if paused else "▶ Resumed")

                elif event.key == pygame.K_EQUALS or event.key == pygame.K_PLUS:
                    sim_speed = min(5.0, sim_speed + 0.25)
                    toast(f"Speed: x{sim_speed:.2f}")

                elif event.key == pygame.K_MINUS:
                    sim_speed = max(0.25, sim_speed - 0.25)
                    toast(f"Speed: x{sim_speed:.2f}")

                elif event.key == pygame.K_n:
                    modal.open()

                elif event.key == pygame.K_t:
                    if selected and ollama_ok:
                        selected.ollama_thought()
                        toast(f"Asking {selected.name} what they think…")
                    elif not ollama_ok:
                        toast("⚠ Ollama offline")
                    else:
                        toast("Select a character first (click)")

                elif event.key == pygame.K_r:
                    world_objects = generate_world()
                    # release all targets
                    for c in characters:
                        c.target_obj = None
                        c.state = "idle"
                    toast("🗺 World regenerated!")

                elif event.key == pygame.K_ESCAPE:
                    if selected:
                        selected.selected = False
                        selected = None

                elif event.key == pygame.K_DELETE:
                    if selected:
                        characters.remove(selected)
                        toast(f"✦ {selected.name} has left the world.")
                        selected = None

            if event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                if my < WORLD_H:   # click in world
                    hit = None
                    for c in characters:
                        if math.hypot(mx - c.x, my - c.y) < c.radius + 4:
                            hit = c
                            break
                    if selected:
                        selected.selected = False
                    selected = hit
                    if selected:
                        selected.selected = True
                        selected.blink    = 0.3

        # ── Update ───────────────────────────
        toasts = [t for t in toasts if t.alive()]
        ollama_ok = check_ollama() if int(time.time()) % 10 == 0 else ollama_ok

        for c in characters:
            c.update(dt, world_objects, characters)

        # ── Draw ─────────────────────────────
        screen.fill(C_BG)

        # World surface (clipped)
        world_surf = screen.subsurface((0, 0, WORLD_W, WORLD_H))
        draw_world(world_surf, world_objects, fonts)

        # Characters
        for c in characters:
            c.draw(world_surf, fonts)

        # Bottom panel
        draw_bottom_panel(screen, fonts, characters, selected,
                          world_objects, sim_speed, paused, ollama_ok)

        # Toasts
        draw_toasts(screen, font_sm, toasts)

        # Modal
        modal.draw(screen)

        # HUD top-left
        hud = font_sm.render(
            f"✦ GOD SIMULATION  │  {len(characters)} souls  │  {clock.get_fps():.0f}fps",
            True, C_DIM
        )
        screen.blit(hud, (8, 4))

        # Title watermark top-right
        wm = font_sm.render("Powered by Ollama + Pygame", True, (40, 55, 40))
        screen.blit(wm, (SCREEN_W - wm.get_width() - 8, 4))

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
