# ─────────────────────────────────────────────
#  GOD SIMULATION  –  Punto de entrada
#  Ejecutar:  python main.py
#
#  Requisitos:
#    pip install pygame requests
#    Ollama corriendo:  ollama serve
#    Modelo descargado: ollama pull llama3.2
# ─────────────────────────────────────────────
import sys, math, random, time
import pygame

from core.config import *
from core.world           import generate_world
from core.character       import Character, PALETTE, STATE_LABELS, SpeechBubble
from core.ollama_client   import check_ollama, list_models, ask_ollama_async
from ui.panels            import draw_bottom_panel, draw_toasts, CreationModal, Toast


# ── Fuentes ──────────────────────────────────
def load_fonts():
    pygame.font.init()
    candidates_mono = [
        "Consolas", "Courier New", "DejaVu Sans Mono",
        "Lucida Console", "Liberation Mono", "monospace"
    ]
    candidates_sans = [
        "Segoe UI", "Arial", "Helvetica", "DejaVu Sans", "sans-serif"
    ]

    def try_font(names, size, bold=False):
        for name in names:
            try:
                f = pygame.font.SysFont(name, size, bold=bold)
                # Verificar que renderiza ASCII normal
                f.render("Test ABC 123", True, (255,255,255))
                return f
            except Exception:
                continue
        return pygame.font.Font(None, size + 4)

    sm = try_font(candidates_mono, 13)
    md = try_font(candidates_sans, 16, bold=True)
    lg = try_font(candidates_sans, 21, bold=True)
    return sm, md, lg


# ── Dibujo del mundo ─────────────────────────
def draw_world(surf, world_objects, fonts):
    font_sm = fonts[0]
    surf.fill(C_WORLD_BG)

    # Cuadrícula sutil
    for gx in range(0, WORLD_W, TILE * 2):
        pygame.draw.line(surf, C_GRID, (gx, 0), (gx, WORLD_H), 1)
    for gy in range(0, WORLD_H, TILE * 2):
        pygame.draw.line(surf, C_GRID, (0, gy), (WORLD_W, gy), 1)

    # Borde del mundo
    pygame.draw.rect(surf, C_ACCENT, (0, 0, WORLD_W, WORLD_H), 2)

    # Objetos
    for obj in world_objects:
        obj.draw(surf, font_sm)


# ── Personajes por defecto ────────────────────
def make_defaults():
    defaults = [
        ("Aria",    "curioso",    "Una cientifica fascinada por lo desconocido."),
        ("Rex",     "agresivo",   "Un guerrero que actua antes de pensar."),
        ("Mila",    "amigable",   "Una panaderia que ama compartir su comida."),
        ("Zeno",    "perezoso",   "Un filosofo que prefiere pensar a moverse."),
    ]
    chars = []
    for name, trait, backstory in defaults:
        x = random.uniform(100, WORLD_W - 100)
        y = random.uniform(80, WORLD_H - 80)
        c = Character(name, trait, backstory, x, y, random.choice(PALETTE))
        chars.append(c)
    return chars


# ── Bucle principal ──────────────────────────
def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("God Simulation - Simulador Multi-Agente")
    clock  = pygame.time.Clock()
    fonts  = load_fonts()
    font_sm, font_md, font_lg = fonts

    # Verificar Ollama
    ollama_ok  = check_ollama()
    models     = list_models() if ollama_ok else []
    model_used = models[0] if models else OLLAMA_MODEL

    world_objects = generate_world()
    characters    = make_defaults()
    selected      = None
    toasts: list[Toast] = []
    sim_speed     = 1.0
    paused        = False
    modal         = CreationModal(fonts, TRAITS)
    ollama_check_timer = 0.0

    def toast(msg):
        toasts.append(Toast(msg))
        while len(toasts) > 10:
            toasts.pop(0)

    if ollama_ok:
        toast(f"Ollama conectado - modelo: {model_used}")
    else:
        toast("Ollama no disponible - dialogos desactivados")

    running = True
    while running:
        dt_raw = clock.tick(FPS) / 1000.0
        dt     = 0.0 if paused else min(dt_raw * sim_speed, 0.2)

        # ── Eventos ──────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # Modal primero
            result = modal.handle_event(event)
            if result:
                if result[0] == "create":
                    _, name, trait, backstory = result
                    x = random.uniform(100, WORLD_W - 100)
                    y = random.uniform(80,  WORLD_H - 80)
                    c = Character(name, trait, backstory, x, y, random.choice(PALETTE))
                    characters.append(c)
                    toast(f">> {name} ha entrado al mundo!")
                    if selected:
                        selected.selected = False
                    selected = c
                    c.selected = True
                    if ollama_ok:
                        def _intro_cb(txt, _c=c):
                            _c.bubble = SpeechBubble(txt)
                        ask_ollama_async(
                            f"Eres {name}, una persona {trait}. {backstory}. "
                            f"Acabas de aparecer en un mundo misterioso. "
                            f"Reacciona en español en una frase corta, maximo 18 palabras.",
                            _intro_cb
                        )
                continue
            if modal.active:
                continue

            # Teclas globales
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    paused = not paused
                    toast("Pausado" if paused else "Reanudado")

                elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    sim_speed = min(5.0, sim_speed + 0.25)
                    toast(f"Velocidad: x{sim_speed:.2f}")

                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    sim_speed = max(0.25, sim_speed - 0.25)
                    toast(f"Velocidad: x{sim_speed:.2f}")

                elif event.key == pygame.K_n:
                    modal.open()

                elif event.key == pygame.K_t:
                    if selected and ollama_ok:
                        selected.ollama_thought()
                        toast(f"Consultando el pensamiento de {selected.name}...")
                    elif not ollama_ok:
                        toast("Ollama no disponible")
                    else:
                        toast("Selecciona un personaje primero")

                elif event.key == pygame.K_r:
                    world_objects = generate_world()
                    for c in characters:
                        c._release_target()
                        c.state = "descanso"
                    toast("Mapa regenerado!")

                elif event.key == pygame.K_ESCAPE:
                    if selected:
                        selected.selected = False
                        selected = None

                elif event.key == pygame.K_DELETE:
                    if selected:
                        n = selected.name
                        selected._release_target()
                        characters.remove(selected)
                        selected = None
                        toast(f"{n} ha abandonado el mundo.")

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if my < WORLD_H and not modal.active:
                    hit = None
                    for c in characters:
                        if math.hypot(mx - c.x, my - c.y) < c.radius + 5:
                            hit = c
                            break
                    if selected:
                        selected.selected = False
                    selected = hit
                    if selected:
                        selected.selected = True
                        selected.blink    = 0.3

        # ── Actualización ─────────────────────
        toasts = [t for t in toasts if t.alive()]

        # Verificar Ollama cada 8 segundos
        ollama_check_timer -= dt_raw
        if ollama_check_timer <= 0:
            ollama_ok = check_ollama()
            ollama_check_timer = 8.0

        for c in characters:
            c.update(dt, world_objects, characters)

        # ── Dibujo ────────────────────────────
        screen.fill(C_BG)

        # Mundo (sub-superficie recortada)
        world_surf = screen.subsurface((0, 0, WORLD_W, WORLD_H))
        draw_world(world_surf, world_objects, fonts)

        # Personajes
        for c in characters:
            c.draw(world_surf, fonts)

        # Panel inferior
        draw_bottom_panel(screen, fonts, characters, selected,
                          world_objects, sim_speed, paused, ollama_ok)

        # Toasts
        draw_toasts(screen, font_sm, toasts)

        # Modal
        modal.draw(screen)

        # HUD superior
        fps_t = font_sm.render(
            f"GOD SIMULATION  |  {len(characters)} almas  |  {clock.get_fps():.0f} fps  |  "
            f"[N] Nuevo  [ESPACIO] Pausa  [T] Pensar",
            True, C_DIM
        )
        screen.blit(fps_t, (8, 4))

        # Marca de agua
        wm = font_sm.render("Pygame + Ollama", True, (35, 52, 35))
        screen.blit(wm, (SCREEN_W - wm.get_width() - 8, 4))

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
