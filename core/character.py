# ─────────────────────────────────────────────
#  WORLD SIMULATION  –  Agente Personaje
# ─────────────────────────────────────────────
import math
import random
import time
import pygame
from core.config import *
from core.ollama_client import ask_ollama_async

# ── Estados FSM ───────────────────────────────
S_IDLE        = "descanso"
S_WANDER      = "explorando"
S_SEEK_FOOD   = "busca_comida"
S_EAT         = "comiendo"
S_SEEK_BED    = "busca_cama"
S_SLEEP       = "durmiendo"
S_SEEK_SHOWER = "busca_ducha"
S_SHOWER      = "duchando"
S_SEEK_CHAT   = "busca_chat"
S_CHAT        = "charlando"

STATE_LABELS = {
    S_IDLE:        "Descansando",
    S_WANDER:      "Explorando",
    S_SEEK_FOOD:   "->Comida",
    S_EAT:         "Comiendo",
    S_SEEK_BED:    "->Cama",
    S_SLEEP:       "Durmiendo",
    S_SEEK_SHOWER: "->Ducha",
    S_SHOWER:      "Duchando",
    S_SEEK_CHAT:   "->Charla",
    S_CHAT:        "Charlando",
}

STATE_ICONS = {
    S_IDLE:        "[..]",
    S_WANDER:      "[>>]",
    S_SEEK_FOOD:   "[>F]",
    S_EAT:         "[F!]",
    S_SEEK_BED:    "[>Z]",
    S_SLEEP:       "[ZZ]",
    S_SEEK_SHOWER: "[>W]",
    S_SHOWER:      "[W!]",
    S_SEEK_CHAT:   "[>C]",
    S_CHAT:        "[CC]",
}

PALETTE = [
    (220, 100, 80),  (80, 160, 220),  (160, 220, 80),
    (220, 180, 60),  (160, 80, 220),  (80, 220, 200),
    (220, 120, 160), (140, 200, 140), (200, 140, 100),
    (100, 200, 220), (220, 160, 100), (180, 220, 100),
]

_next_id = 0
def _new_id():
    global _next_id
    _next_id += 1
    return _next_id

# ── Tiempo de lectura estimado ────────────────
def _reading_secs(text: str, extra: float = 1.2) -> float:
    """~130 palabras por minuto + pausa base."""
    words = max(1, len(text.split()))
    return max(3.5, words / 130 * 60 + extra)

# ── Turnos según personalidades ───────────────
def _num_turns(trait_a: str, trait_b: str) -> int:
    social  = {"amigable", "curioso", "optimista", "energetico", "agresivo"}
    quiet   = {"timido", "melancolico", "perezoso"}
    score = 2
    for t in (trait_a, trait_b):
        if t in social:
            score += random.randint(1, 3)
        if t in quiet:
            score -= random.randint(0, 1)
    return max(2, min(8, score))


# ── Burbuja de diálogo ───────────────────────
class SpeechBubble:
    """La duración se calcula al crear, basada en la longitud del texto."""

    def __init__(self, text: str):
        self.text = text.strip() if text else ""
        # Duración = tiempo de lectura + 1.5 s de fade
        self.duration = _reading_secs(self.text, extra=1.5)
        self.born     = time.time()

    def alive(self):
        return time.time() - self.born < self.duration

    def age(self):
        return time.time() - self.born

    def alpha(self):
        elapsed = self.age()
        fade_start = self.duration - 1.5
        if elapsed < fade_start:
            return 255
        return max(0, int(255 * (self.duration - elapsed) / 1.5))


# ── Motor de conversación multi-turno ─────────
import threading

class ConversationEngine:
    """
    Orquesta un diálogo multi-turno entre char_a y char_b en un hilo de fondo.
    Los personajes permanecen quietos mientras conversan.
    """

    SYSTEM = (
        "Eres un personaje en una simulacion de vida 2D. "
        "Responde SIEMPRE en espanol. "
        "Tus respuestas son cortas, naturales y conversacionales (maximo 28 palabras). "
        "NO uses asteriscos ni markdown. NO incluyas saltos de linea. "
        "Habla en primera persona. "
        "Mantén coherencia con el historial de la conversacion."
    )

    def __init__(self, char_a: "Character", char_b: "Character"):
        self.char_a    = char_a
        self.char_b    = char_b
        self.active    = True
        self.history   = []   # [(nombre, texto), ...]
        self.num_turns = _num_turns(char_a.trait, char_b.trait)
        self._t        = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._t.start()

    def stop(self):
        self.active = False

    def _run(self):
        for turn in range(self.num_turns):
            if not self.active:
                break

            speaker  = self.char_a if turn % 2 == 0 else self.char_b
            listener = self.char_b if turn % 2 == 0 else self.char_a

            # Construir historial para el prompt (últimos 6 turnos)
            hist_txt = ""
            for name, msg in self.history[-6:]:
                hist_txt += f"{name}: {msg}\n"

            if turn == 0:
                prompt = (
                    f"Eres {speaker.name}, una persona {speaker.trait}. "
                    f"Historia personal: {speaker.backstory}. "
                    f"Acabas de encontrarte con {listener.name}, que es {listener.trait}. "
                    f"Inicia la conversacion de forma natural. Maximo 25 palabras."
                )
            else:
                last_name, last_msg = self.history[-1]
                prompt = (
                    f"Eres {speaker.name}, una persona {speaker.trait}. "
                    f"Historia personal: {speaker.backstory}. "
                    f"Estas hablando con {listener.name} ({listener.trait}). "
                    f"Historial:\n{hist_txt}"
                    f"{last_name} dijo: \"{last_msg}\". "
                    f"Responde de forma natural y coherente. Maximo 28 palabras."
                )

            # Llamada bloqueante a Ollama dentro del hilo
            result = {"text": None}
            done   = threading.Event()

            def _cb(txt, r=result, e=done):
                r["text"] = txt
                e.set()

            ask_ollama_async(prompt, _cb, system=self.SYSTEM,
                             max_chars=220, num_predict=160)
            done.wait(timeout=30)

            if not self.active:
                break

            text = (result["text"] or "...").strip()
            self.history.append((speaker.name, text))

            # Mostrar burbuja al hablante
            speaker.bubble = SpeechBubble(text)

            # Esperar a que se lea el mensaje antes del siguiente turno
            wait = _reading_secs(text, extra=random.uniform(0.8, 2.0))
            deadline = time.time() + wait
            while time.time() < deadline and self.active:
                time.sleep(0.1)

        # Fin: notificar a ambos
        self.active = False
        self.char_a._conv_done = True
        self.char_b._conv_done = True


# ── Clase Character ───────────────────────────
class Character:
    def __init__(self, name: str, trait: str, backstory: str,
                 x: float, y: float, color=None):
        self.id        = _new_id()
        self.name      = name
        self.trait     = trait
        self.backstory = backstory

        self.x, self.y = float(x), float(y)
        self.color      = color or random.choice(PALETTE)

        # Necesidades
        self.hunger  = random.uniform(55, 95)
        self.energy  = random.uniform(55, 95)
        self.hygiene = random.uniform(55, 95)
        self.social  = random.uniform(55, 95)

        # FSM
        self.state        = S_IDLE
        self.target_obj   = None
        self.target_char  = None
        self.dest_x       = self.x
        self.dest_y       = self.y
        self.action_timer = 0.0
        self.idle_timer   = random.uniform(1, 3)

        # Conversación
        self.bubble: SpeechBubble | None = None
        self._chat_cooldown = 0.0
        self._conv: ConversationEngine | None = None
        self._conv_done     = False   # flag que el motor pone en True al terminar
        self._is_initiator  = False   # True = quien inició la conv

        # Visual
        self.radius   = 16
        self.zz_phase = 0.0
        self.selected = False
        self.blink    = 0.0

        # Pensamiento Ollama (tecla T)
        self._thinking = False

    # ── Necesidad más urgente ─────────────────
    @property
    def most_urgent_need(self):
        needs = {"hunger": self.hunger, "energy": self.energy,
                 "hygiene": self.hygiene, "social": self.social}
        return min(needs, key=needs.get)

    def need_value(self, key):
        return getattr(self, key)

    # ── Update principal ──────────────────────
    def update(self, dt: float, world_objects: list, characters: list):
        self.hunger  = max(0, self.hunger  - HUNGER_DECAY  * dt)
        self.energy  = max(0, self.energy  - ENERGY_DECAY  * dt)
        self.hygiene = max(0, self.hygiene - HYGIENE_DECAY * dt)
        self.social  = max(0, self.social  - SOCIAL_DECAY  * dt)

        self._chat_cooldown = max(0, self._chat_cooldown - dt)
        self.blink = max(0, self.blink - dt)

        self._run_fsm(dt, world_objects, characters)

    # ── FSM ───────────────────────────────────
    def _run_fsm(self, dt, world_objects, characters):

        # ── IDLE ─────────────────────────────
        if self.state == S_IDLE:
            self.idle_timer -= dt
            if self.idle_timer <= 0:
                self._choose_action(world_objects, characters)

        # ── WANDER ───────────────────────────
        elif self.state == S_WANDER:
            self._move_towards(self.dest_x, self.dest_y, dt, SPEED_SLOW)
            if self._at_dest():
                self._transition_idle()

        # ── SEEK FOOD ────────────────────────
        elif self.state == S_SEEK_FOOD:
            if self.target_obj is None:
                self._transition_idle(); return
            self._move_towards(self.target_obj.x, self.target_obj.y, dt, SPEED_NORMAL)
            if self._dist(self.target_obj.x, self.target_obj.y) < EAT_DIST:
                self.state = S_EAT
                self.action_timer = random.uniform(4, 7)
                self._say("Mmm, necesito comer algo...")

        # ── EAT ──────────────────────────────
        elif self.state == S_EAT:
            self.action_timer -= dt
            self.hunger = min(100, self.hunger + 18 * dt)
            if self.action_timer <= 0 or self.hunger >= 99:
                self._release_target(); self._transition_idle()

        # ── SEEK BED ─────────────────────────
        elif self.state == S_SEEK_BED:
            if self.target_obj is None:
                self._transition_idle(); return
            self._move_towards(self.target_obj.x, self.target_obj.y, dt, SPEED_SLOW)
            if self._dist(self.target_obj.x, self.target_obj.y) < EAT_DIST:
                self.state = S_SLEEP
                self.action_timer = random.uniform(8, 14)
                self._say("Que sueno tengo... a descansar.")

        # ── SLEEP ────────────────────────────
        elif self.state == S_SLEEP:
            self.action_timer -= dt
            self.energy = min(100, self.energy + 10 * dt)
            self.zz_phase += dt * 2
            if self.action_timer <= 0 or self.energy >= 99:
                self._release_target(); self._transition_idle()

        # ── SEEK SHOWER ──────────────────────
        elif self.state == S_SEEK_SHOWER:
            if self.target_obj is None:
                self._transition_idle(); return
            self._move_towards(self.target_obj.x, self.target_obj.y, dt, SPEED_NORMAL)
            if self._dist(self.target_obj.x, self.target_obj.y) < EAT_DIST:
                self.state = S_SHOWER
                self.action_timer = random.uniform(4, 6)
                self._say("Una ducha me vendra de maravilla.")

        # ── SHOWER ───────────────────────────
        elif self.state == S_SHOWER:
            self.action_timer -= dt
            self.hygiene = min(100, self.hygiene + 20 * dt)
            if self.action_timer <= 0 or self.hygiene >= 99:
                self._release_target(); self._transition_idle()

        # ── SEEK CHAT ────────────────────────
        elif self.state == S_SEEK_CHAT:
            other = self.target_char
            if other is None or other.state == S_SLEEP:
                self._transition_idle(); return
            # Acercarse al otro
            self._move_towards(other.x, other.y, dt, SPEED_NORMAL)
            if self._dist(other.x, other.y) < TALK_DIST:
                self._start_conversation(other)

        # ── CHAT ─────────────────────────────
        elif self.state == S_CHAT:
            # Mantenerse ligeramente cerca del interlocutor (sin moverse mucho)
            if self.target_char:
                self._move_towards(
                    self.target_char.x + random.uniform(-20, 20),
                    self.target_char.y + random.uniform(-20, 20),
                    dt, SPEED_SLOW * 0.3   # casi quieto
                )

            # Ganar social gradualmente
            self.social = min(100, self.social + 4 * dt)

            # Comprobar si el motor de conversación terminó
            if self._conv_done:
                self._end_conversation()

    # ── Decisiones ────────────────────────────
    def _choose_action(self, world_objects, characters):
        urgent = self.most_urgent_need
        val    = self.need_value(urgent)

        if val < CRITICAL:
            self._seek_for(urgent, world_objects, characters)
            return
        if val < LOW and random.random() < 0.7:
            self._seek_for(urgent, world_objects, characters)
            return

        # Social
        if self.social < LOW and self._chat_cooldown <= 0:
            candidates = [c for c in characters
                          if c.id != self.id
                          and c.state not in (S_SLEEP, S_SEEK_CHAT, S_CHAT)]
            if candidates:
                chance = 0.20 if self.trait == "timido" else 0.70
                if random.random() < chance:
                    self.target_char = random.choice(candidates)
                    self.state       = S_SEEK_CHAT
                    self._is_initiator = True
                    return

        # Deambular
        self.state  = S_WANDER
        self.dest_x = random.uniform(60, WORLD_W - 60)
        self.dest_y = random.uniform(60, WORLD_H - 60)

    def _seek_for(self, need, world_objects, characters):
        kind_map  = {"hunger": "comida", "energy": "cama", "hygiene": "ducha"}
        state_map = {"comida": S_SEEK_FOOD, "cama": S_SEEK_BED, "ducha": S_SEEK_SHOWER}
        kind = kind_map.get(need)
        if not kind:
            return
        objs = [o for o in world_objects if o.kind == kind and o.is_free()]
        if not objs:
            self.state  = S_WANDER
            self.dest_x = random.uniform(60, WORLD_W - 60)
            self.dest_y = random.uniform(60, WORLD_H - 60)
            return
        obj = min(objs, key=lambda o: self._dist(o.x, o.y))
        obj.reserve(self.id)
        self.target_obj = obj
        self.state = state_map[kind]

    # ── Conversación ──────────────────────────
    def _start_conversation(self, other: "Character"):
        """Inicia el motor multi-turno. Solo el iniciador crea el engine."""
        if not self._is_initiator:
            return

        # Poner ambos en estado CHAT detenidos
        self.state  = S_CHAT
        other.state = S_CHAT
        other.target_char = self
        other._is_initiator = False

        # Crear y arrancar motor
        self._conv_done       = False
        other._conv_done      = False
        engine = ConversationEngine(self, other)
        self._conv  = engine
        other._conv = engine
        engine.start()

    def _end_conversation(self):
        """Limpia el estado al terminar la conversación."""
        self._conv_done     = False
        self._is_initiator  = False
        self._conv          = None
        self._chat_cooldown = random.uniform(25, 50)
        self.target_char    = None
        self._transition_idle()

    def abort_conversation(self):
        """Interrumpe una conversación en curso (p.ej. si una necesidad es crítica)."""
        if self._conv:
            self._conv.stop()
            self._conv = None
        self._conv_done    = True
        self._is_initiator = False

    def _release_target(self):
        if self.target_obj:
            self.target_obj.release()
            self.target_obj = None

    def _transition_idle(self):
        self.state      = S_IDLE
        self.idle_timer = random.uniform(1.5, 4)

    # ── Movimiento ────────────────────────────
    def _move_towards(self, tx, ty, dt, speed):
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        if dist < 2:
            return
        spd = speed * dt
        if self.trait == "perezoso":
            spd *= 0.65
        elif self.trait == "energetico":
            spd *= 1.3
        ratio = min(1.0, spd / dist)
        self.x = max(self.radius, min(WORLD_W - self.radius, self.x + dx * ratio))
        self.y = max(self.radius, min(WORLD_H - self.radius, self.y + dy * ratio))

    def _dist(self, tx, ty):
        return math.hypot(tx - self.x, ty - self.y)

    def _at_dest(self):
        return self._dist(self.dest_x, self.dest_y) < 6

    # ── Diálogo utilitarios ───────────────────
    def _say(self, text: str):
        self.bubble = SpeechBubble(text)

    def ollama_thought(self):
        """Pide a Ollama un pensamiento introspectivo (tecla T)."""
        if self._thinking:
            return
        self._thinking = True
        need_es = {"hunger": "hambre", "energy": "energia",
                   "hygiene": "higiene", "social": "vida social"}
        urgent = self.most_urgent_need
        val    = self.need_value(urgent)
        prompt = (
            f"Eres {self.name}, una persona {self.trait}. "
            f"Historia: {self.backstory}. "
            f"Tu nivel de {need_es.get(urgent, urgent)} es {val:.0f}/100. "
            f"Estado: {STATE_LABELS.get(self.state, self.state)}. "
            f"Expresa en espanol lo que estas pensando ahora mismo. "
            f"Una sola frase, maximo 20 palabras, en primera persona. Sin asteriscos."
        )
        def _cb(txt):
            self.bubble    = SpeechBubble(txt)
            self._thinking = False
        ask_ollama_async(prompt, _cb, max_chars=200, num_predict=100)

    # ── Dibujo ────────────────────────────────
    def draw(self, surf, fonts):
        font_sm, font_md, font_lg = fonts
        cx, cy = int(self.x), int(self.y)
        r = self.radius

        # Sombra elíptica
        shadow = pygame.Surface((r*2+4, 8), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 55), shadow.get_rect())
        surf.blit(shadow, (cx - r - 2, cy + r - 4))

        # Cuerpo
        col = self.color
        if self.state == S_SLEEP:
            col = tuple(max(0, c - 65) for c in col)
        pygame.draw.circle(surf, col, (cx, cy), r)
        pygame.draw.circle(surf, (255, 255, 255), (cx, cy), r, 2)

        # Línea de conexión durante conversación
        if self.state == S_CHAT and self.target_char:
            tc = self.target_char
            mid_x = (cx + int(tc.x)) // 2
            mid_y = (cy + int(tc.y)) // 2
            pulse = int(abs(math.sin(time.time() * 4)) * 60 + 60)
            pygame.draw.line(surf, (pulse, 200, pulse),
                             (cx, cy), (int(tc.x), int(tc.y)), 1)

        # Anillo de selección pulsante
        if self.selected:
            pulse = int(abs(math.sin(time.time() * 3)) * 80)
            pygame.draw.circle(surf, (255, 255, 100 + pulse), (cx, cy), r + 5, 2)

        # Cara
        if self.state != S_SLEEP:
            pygame.draw.circle(surf, (255, 255, 255), (cx-5, cy-4), 4)
            pygame.draw.circle(surf, (255, 255, 255), (cx+5, cy-4), 4)
            pygame.draw.circle(surf, (30,  30,  30),  (cx-5, cy-4), 2)
            pygame.draw.circle(surf, (30,  30,  30),  (cx+5, cy-4), 2)
            if self.hunger < CRITICAL or self.energy < CRITICAL or self.hygiene < CRITICAL:
                pygame.draw.arc(surf, (180, 60, 60),
                                (cx-6, cy+2, 12, 8), math.pi, 2*math.pi, 2)
            else:
                pygame.draw.arc(surf, (80, 200, 80),
                                (cx-6, cy+1, 12, 8), 0, math.pi, 2)
        else:
            self.zz_phase += 0.05
            off = int(math.sin(self.zz_phase) * 3)
            pygame.draw.line(surf, (200, 180, 240), (cx-7, cy-4+off), (cx-2, cy-4+off), 2)
            pygame.draw.line(surf, (200, 180, 240), (cx+2, cy-4+off), (cx+7, cy-4+off), 2)
            zt = font_sm.render("zzz", True, (200, 180, 240))
            surf.blit(zt, (cx + r + 2, cy - r - 2))

        # Nombre
        nt = font_sm.render(self.name, True, C_TEXT)
        surf.blit(nt, (cx - nt.get_width()//2, cy + r + 3))

        # Icono de estado ASCII
        icon = STATE_ICONS.get(self.state, "")
        if icon:
            it = font_sm.render(icon, True, C_DIM)
            surf.blit(it, (cx - it.get_width()//2, cy - r - 18))

        # Burbuja de diálogo
        if self.bubble and self.bubble.alive():
            self._draw_bubble(surf, font_sm, cx, cy - r - 20)

    def _draw_bubble(self, surf, font, cx, top):
        """Dibuja burbuja de diálogo con word-wrap correcto."""
        MAX_W = 240   # ancho máximo de la burbuja en píxeles

        text = self.bubble.text if self.bubble else ""
        if not text:
            return

        # ── Word-wrap ────────────────────────
        words = text.split()
        if not words:
            return

        lines   = []
        current = []
        for word in words:
            probe = " ".join(current + [word])
            if font.size(probe)[0] > MAX_W - 16 and current:
                lines.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        if current:
            lines.append(" ".join(current))

        if not lines:
            return

        lh = font.get_height() + 4
        bw = max(font.size(ln)[0] for ln in lines) + 20
        bw = max(bw, 50)
        bh = len(lines) * lh + 16

        # Posición: encima del personaje
        bx = cx - bw // 2
        by = top - bh - 10

        # Clamp dentro del mundo
        bx = max(4, min(WORLD_W - bw - 4, bx))
        by = max(4, by)

        alpha = self.bubble.alpha()

        # Fondo de la burbuja
        bubble = pygame.Surface((bw, bh), pygame.SRCALPHA)
        pygame.draw.rect(bubble, (*C_BUBBLE, alpha),     (0, 0, bw, bh), border_radius=9)
        pygame.draw.rect(bubble, (150, 155, 200, alpha), (0, 0, bw, bh), 1, border_radius=9)

        # Texto línea a línea
        for i, line_text in enumerate(lines):
            # Renderizar con antialias y color sólido, luego modular alpha
            rendered = font.render(line_text, True, C_BUBBLE_T)
            tmp = pygame.Surface(rendered.get_size(), pygame.SRCALPHA)
            tmp.blit(rendered, (0, 0))
            tmp.set_alpha(alpha)
            bubble.blit(tmp, (10, 8 + i * lh))

        surf.blit(bubble, (bx, by))

        # ── Cola triangular ──────────────────
        # Apunta hacia el personaje desde la base de la burbuja
        tail_x = max(bx + 12, min(bx + bw - 12, cx))
        pts = [
            (tail_x,      top - 3),
            (tail_x - 7,  by + bh),
            (tail_x + 7,  by + bh),
        ]
        tail_surf = pygame.Surface((WORLD_W, WORLD_H), pygame.SRCALPHA)
        pygame.draw.polygon(tail_surf, (*C_BUBBLE, alpha), pts)
        surf.blit(tail_surf, (0, 0))
