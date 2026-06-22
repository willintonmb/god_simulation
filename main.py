# ─────────────────────────────────────────────
#  WORLD SIMULATION  –  Punto de entrada
#  Ejecutar:  python main.py
# ─────────────────────────────────────────────
import sys, math, random, time, os
import pygame

from core.config import *
from core.world           import generate_world
from core.character       import Character, PALETTE, STATE_LABELS, SpeechBubble
from core.ollama_client   import check_ollama, list_models, ask_ollama_async
from core.character_factory import CharacterFactory
from ui.panels            import draw_bottom_panel, draw_toasts, CreationModal, Toast


# ── Fuentes ──────────────────────────────────
def load_fonts():
    pygame.font.init()
    mono = ["Consolas","Courier New","DejaVu Sans Mono","Lucida Console","monospace"]
    sans = ["Segoe UI","Arial","Helvetica","DejaVu Sans","sans-serif"]
    def try_f(names, size, bold=False):
        for n in names:
            try:
                f = pygame.font.SysFont(n, size, bold=bold)
                f.render("Test ABC 123", True, (255,255,255))
                return f
            except Exception: continue
        return pygame.font.Font(None, size+4)
    return try_f(mono,13), try_f(sans,16,True), try_f(sans,21,True)


# ── Pantalla de carga ─────────────────────────
def loading_screen(screen, fonts, message: str, progress: float = -1):
    """Dibuja una pantalla de carga elegante."""
    font_sm, font_md, font_lg = fonts
    screen.fill(C_BG)

    # Título
    t = font_lg.render("WORLD SIMULATION", True, C_ACCENT)
    screen.blit(t, (SCREEN_W//2 - t.get_width()//2, SCREEN_H//2 - 80))

    # Mensaje
    m = font_md.render(message, True, C_TEXT)
    screen.blit(m, (SCREEN_W//2 - m.get_width()//2, SCREEN_H//2 - 20))

    # Barra de progreso (si progress >= 0)
    if progress >= 0:
        bw, bh = 400, 14
        bx = SCREEN_W//2 - bw//2
        by = SCREEN_H//2 + 20
        pygame.draw.rect(screen, (30,40,35), (bx, by, bw, bh), border_radius=7)
        fill = int(bw * min(1.0, progress))
        if fill > 0:
            pygame.draw.rect(screen, C_ACCENT, (bx, by, fill, bh), border_radius=7)
        pygame.draw.rect(screen, C_DIM, (bx, by, bw, bh), 1, border_radius=7)
        pct = font_sm.render(f"{int(progress*100)}%", True, C_DIM)
        screen.blit(pct, (SCREEN_W//2 - pct.get_width()//2, by+18))

    # Puntos animados
    dots = "." * (int(time.time() * 2) % 4)
    dt_t = font_sm.render(dots, True, C_DIM)
    screen.blit(dt_t, (SCREEN_W//2 + m.get_width()//2 + 4, SCREEN_H//2 - 18))

    pygame.display.flip()


# ── Dibujo del mundo ─────────────────────────
def draw_world(surf, world_objects, fonts):
    font_sm = fonts[0]
    surf.fill(C_WORLD_BG)
    for gx in range(0, WORLD_W, TILE*2):
        pygame.draw.line(surf, C_GRID, (gx,0), (gx,WORLD_H), 1)
    for gy in range(0, WORLD_H, TILE*2):
        pygame.draw.line(surf, C_GRID, (0,gy), (WORLD_W,gy), 1)
    pygame.draw.rect(surf, C_ACCENT, (0,0,WORLD_W,WORLD_H), 2)
    for obj in world_objects:
        obj.draw(surf, font_sm)


# ── Generación inicial aleatoria ─────────────
def generate_initial_characters(screen, fonts, ollama_ok: bool) -> list[Character]:
    count   = random.randint(6, 50)
    factory = CharacterFactory(ollama_ok=ollama_ok)
    results = []
    done_so_far = [0]

    def on_progress(done, total):
        done_so_far[0] = done
        loading_screen(screen, fonts,
                       f"Generando personaje {done}/{total}...",
                       progress=done/total)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()

    loading_screen(screen, fonts, f"Creando {count} almas para el mundo...", 0.0)
    pygame.display.flip()

    batch = factory.generate_batch(count=count, on_progress=on_progress)

    # Convertir a Character con posiciones aleatorias sin solapamiento
    chars = []
    margin = 60
    for data in batch:
        for _ in range(100):
            x = random.uniform(margin, WORLD_W - margin)
            y = random.uniform(margin, WORLD_H - margin)
            overlap = any(math.hypot(x-c.x, y-c.y) < 40 for c in chars)
            if not overlap:
                break
        col = random.choice(PALETTE)
        c   = Character(data["name"], data["trait"], data["backstory"], x, y, col)
        chars.append(c)

    return chars


# ── Bucle principal ──────────────────────────
def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("WORLD Simulation - Simulador Multi-Agente")
    clock  = pygame.time.Clock()
    fonts  = load_fonts()
    font_sm, font_md, font_lg = fonts

    # Verificar Ollama
    loading_screen(screen, fonts, "Conectando con Ollama...")
    pygame.display.flip()
    ollama_ok  = check_ollama()
    models     = list_models() if ollama_ok else []
    model_used = models[0] if models else OLLAMA_MODEL

    # Generar mundo y personajes
    world_objects = generate_world()
    characters    = generate_initial_characters(screen, fonts, ollama_ok)

    selected: Character | None = None
    toasts: list[Toast]        = []
    sim_speed     = 1.0
    paused        = False
    modal         = CreationModal(fonts, TRAITS)
    ollama_check_timer = 0.0

    # Directorio de logs
    os.makedirs("conversaciones", exist_ok=True)

    def toast(msg):
        toasts.append(Toast(msg))
        while len(toasts) > 10: toasts.pop(0)

    if ollama_ok:
        toast(f"Ollama OK - modelo: {model_used}")
        toast(f"{len(characters)} almas generadas. Logs en carpeta 'conversaciones/'")
    else:
        toast("Ollama no disponible - dialogos desactivados")
        toast(f"{len(characters)} almas generadas (historias predefinidas)")

    # ── Game loop ────────────────────────────
    running = True
    while running:
        dt_raw = clock.tick(FPS) / 1000.0
        dt     = 0.0 if paused else min(dt_raw * sim_speed, 0.2)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            result = modal.handle_event(event)
            if result:
                if result[0] == "create":
                    _, name, trait, backstory = result
                    x = random.uniform(100, WORLD_W-100)
                    y = random.uniform(80,  WORLD_H-80)
                    c = Character(name, trait, backstory, x, y, random.choice(PALETTE))
                    characters.append(c)
                    toast(f">> {name} ha entrado al mundo!")
                    if selected: selected.selected = False
                    selected = c; c.selected = True
                    if ollama_ok:
                        def _intro(txt, _c=c):
                            _c.bubble = SpeechBubble(txt)
                        ask_ollama_async(
                            f"Eres {name}, una persona {trait}. {backstory}. "
                            f"Acabas de aparecer en un mundo misterioso. "
                            f"Reacciona en espanol, maximo 18 palabras, sin asteriscos.",
                            _intro)
                continue
            if modal.active: continue

            if event.type == pygame.KEYDOWN:
                k = event.key
                if k == pygame.K_SPACE:
                    paused = not paused
                    toast("Pausado" if paused else "Reanudado")

                elif k in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    sim_speed = min(5.0, sim_speed + 0.25)
                    toast(f"Velocidad: x{sim_speed:.2f}")

                elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    sim_speed = max(0.25, sim_speed - 0.25)
                    toast(f"Velocidad: x{sim_speed:.2f}")

                elif k == pygame.K_n:
                    modal.open()

                elif k == pygame.K_t:
                    if selected and ollama_ok:
                        selected.ollama_thought()
                        toast(f"Consultando el pensamiento de {selected.name}...")
                    elif not ollama_ok: toast("Ollama no disponible")
                    else: toast("Selecciona un personaje primero")

                elif k == pygame.K_r:
                    world_objects = generate_world()
                    for c in characters:
                        c._release_target(); c.state = S_IDLE
                    toast("Mapa regenerado!")

                elif k == pygame.K_g:
                    # Re-generar todo el mundo con nuevos personajes
                    for c in characters:
                        if c._conv: c._conv.stop()
                    loading_screen(screen, fonts, "Regenerando mundo completo...", 0.0)
                    pygame.display.flip()
                    world_objects = generate_world()
                    characters    = generate_initial_characters(screen, fonts, ollama_ok)
                    selected      = None
                    toast(f"Mundo regenerado con {len(characters)} nuevas almas!")

                elif k == pygame.K_l:
                    path = os.path.abspath("conversaciones")
                    toast(f"Logs en: {path}")

                elif k == pygame.K_ESCAPE:
                    if selected: selected.selected = False; selected = None

                elif k == pygame.K_DELETE:
                    if selected:
                        n = selected.name
                        selected._release_target()
                        if selected._conv: selected._conv.stop()
                        characters.remove(selected)
                        selected = None
                        toast(f"{n} ha abandonado el mundo.")

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if my < WORLD_H and not modal.active:
                    hit = None
                    for c in characters:
                        if math.hypot(mx-c.x, my-c.y) < c.radius+5:
                            hit = c; break
                    if selected: selected.selected = False
                    selected = hit
                    if selected: selected.selected = True; selected.blink = 0.3

        # ── Update ───────────────────────────
        toasts = [t for t in toasts if t.alive()]
        ollama_check_timer -= dt_raw
        if ollama_check_timer <= 0:
            ollama_ok = check_ollama()
            ollama_check_timer = 8.0

        for c in characters:
            c.update(dt, world_objects, characters)

        # ── Draw ─────────────────────────────
        screen.fill(C_BG)
        world_surf = screen.subsurface((0,0,WORLD_W,WORLD_H))
        draw_world(world_surf, world_objects, fonts)
        for c in characters:
            c.draw(world_surf, fonts)

        draw_bottom_panel(screen, fonts, characters, selected,
                          world_objects, sim_speed, paused, ollama_ok)
        draw_toasts(screen, font_sm, toasts)
        modal.draw(screen)

        # HUD
        hud = font_sm.render(
            f"WORLD SIMULATION  |  {len(characters)} almas  |  {clock.get_fps():.0f} fps  |  "
            f"[N] Nuevo  [G] Regenerar mundo  [ESPACIO] Pausa  [T] Pensar  [L] Ver ruta logs",
            True, C_DIM)
        screen.blit(hud, (8, 4))
        wm = font_sm.render("Pygame + Ollama", True, (35,52,35))
        screen.blit(wm, (SCREEN_W - wm.get_width()-8, 4))

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
