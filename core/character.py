# ─────────────────────────────────────────────
#  GOD SIMULATION  –  Agente Personaje
# ─────────────────────────────────────────────
import math
import random
import time
import pygame
from core.config import *
from core.ollama_client import ask_ollama_async


# ── Estados de la máquina de estados ─────────
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

# Etiquetas en español para mostrar en UI
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

# Iconos en texto ASCII (sin emoji) para compatibilidad Windows
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


class SpeechBubble:
    DURATION = 7.0

    def __init__(self, text: str):
        self.text = text.strip()
        self.born = time.time()

    def alive(self):
        return time.time() - self.born < self.DURATION

    def alpha(self):
        age = time.time() - self.born
        if age < self.DURATION - 1.5:
            return 255
        return max(0, int(255 * (self.DURATION - age) / 1.5))


class Character:
    def __init__(self, name: str, trait: str, backstory: str,
                 x: float, y: float, color=None):
        self.id        = _new_id()
        self.name      = name
        self.trait     = trait
        self.backstory = backstory

        self.x, self.y = float(x), float(y)
        self.color = color or random.choice(PALETTE)

        # Necesidades (0=crítico, 100=satisfecho)
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

        # Diálogo
        self.bubble: SpeechBubble | None = None
        self._waiting_reply = False
        self._chat_cooldown = 0.0

        # Visual
        self.radius   = 16
        self.zz_phase = 0.0
        self.selected = False
        self.blink    = 0.0

    # ── Necesidad más urgente ─────────────────
    @property
    def most_urgent_need(self):
        return min(
            {"hunger": self.hunger, "energy": self.energy,
             "hygiene": self.hygiene, "social": self.social},
            key=lambda k: {"hunger": self.hunger, "energy": self.energy,
                           "hygiene": self.hygiene, "social": self.social}[k]
        )

    def need_value(self, key):
        return getattr(self, key)

    # ── Actualización principal ───────────────
    def update(self, dt: float, world_objects: list, characters: list):
        self.hunger  = max(0, self.hunger  - HUNGER_DECAY  * dt)
        self.energy  = max(0, self.energy  - ENERGY_DECAY  * dt)
        self.hygiene = max(0, self.hygiene - HYGIENE_DECAY * dt)
        self.social  = max(0, self.social  - SOCIAL_DECAY  * dt)

        self._chat_cooldown = max(0, self._chat_cooldown - dt)
        self.blink = max(0, self.blink - dt)

        self._run_fsm(dt, world_objects, characters)

    def _run_fsm(self, dt, world_objects, characters):
        if self.state == S_IDLE:
            self.idle_timer -= dt
            if self.idle_timer <= 0:
                self._choose_action(world_objects, characters)

        elif self.state == S_WANDER:
            self._move_towards(self.dest_x, self.dest_y, dt, SPEED_SLOW)
            if self._at_dest():
                self.state = S_IDLE
                self.idle_timer = random.uniform(1, 3)
                self._choose_action(world_objects, characters)

        elif self.state == S_SEEK_FOOD:
            if self.target_obj is None:
                self._transition_idle(); return
            self._move_towards(self.target_obj.x, self.target_obj.y, dt, SPEED_NORMAL)
            if self._dist(self.target_obj.x, self.target_obj.y) < EAT_DIST:
                self.state = S_EAT
                self.action_timer = random.uniform(4, 7)
                self._say_auto("Mmm, necesito comer algo...")

        elif self.state == S_EAT:
            self.action_timer -= dt
            self.hunger = min(100, self.hunger + 18 * dt)
            if self.action_timer <= 0 or self.hunger >= 99:
                self._release_target(); self._transition_idle()

        elif self.state == S_SEEK_BED:
            if self.target_obj is None:
                self._transition_idle(); return
            self._move_towards(self.target_obj.x, self.target_obj.y, dt, SPEED_SLOW)
            if self._dist(self.target_obj.x, self.target_obj.y) < EAT_DIST:
                self.state = S_SLEEP
                self.action_timer = random.uniform(8, 14)
                self._say_auto("Que sueno tengo... necesito descansar.")

        elif self.state == S_SLEEP:
            self.action_timer -= dt
            self.energy = min(100, self.energy + 10 * dt)
            self.zz_phase += dt * 2
            if self.action_timer <= 0 or self.energy >= 99:
                self._release_target(); self._transition_idle()

        elif self.state == S_SEEK_SHOWER:
            if self.target_obj is None:
                self._transition_idle(); return
            self._move_towards(self.target_obj.x, self.target_obj.y, dt, SPEED_NORMAL)
            if self._dist(self.target_obj.x, self.target_obj.y) < EAT_DIST:
                self.state = S_SHOWER
                self.action_timer = random.uniform(4, 6)
                self._say_auto("Una ducha me vendra de maravilla.")

        elif self.state == S_SHOWER:
            self.action_timer -= dt
            self.hygiene = min(100, self.hygiene + 20 * dt)
            if self.action_timer <= 0 or self.hygiene >= 99:
                self._release_target(); self._transition_idle()

        elif self.state == S_SEEK_CHAT:
            if self.target_char is None or self.target_char.state == S_SLEEP:
                self._transition_idle(); return
            self._move_towards(self.target_char.x, self.target_char.y, dt, SPEED_NORMAL)
            if self._dist(self.target_char.x, self.target_char.y) < TALK_DIST:
                self.state = S_CHAT
                self.action_timer = 5.0
                self._trigger_chat(self.target_char)

        elif self.state == S_CHAT:
            self.action_timer -= dt
            self.social = min(100, self.social + 5 * dt)
            if self.action_timer <= 0:
                self._chat_cooldown = random.uniform(20, 40)
                self.target_char = None
                self._transition_idle()

    # ── Toma de decisiones ────────────────────
    def _choose_action(self, world_objects, characters):
        urgent = self.most_urgent_need
        val    = self.need_value(urgent)

        if val < CRITICAL:
            self._seek_for(urgent, world_objects, characters)
            return
        if val < LOW:
            if random.random() < 0.7:
                self._seek_for(urgent, world_objects, characters)
                return

        # Interacción social
        if self.social < LOW and self._chat_cooldown <= 0:
            candidates = [c for c in characters
                          if c.id != self.id
                          and c.state not in (S_SLEEP, S_SEEK_CHAT, S_CHAT)]
            if candidates:
                chance = 0.25 if self.trait == "timido" else 0.75
                if random.random() < chance:
                    self._start_seek_chat(random.choice(candidates))
                    return

        # Deambular
        self.state  = S_WANDER
        self.dest_x = random.uniform(50, WORLD_W - 50)
        self.dest_y = random.uniform(50, WORLD_H - 50)

    def _seek_for(self, need, world_objects, characters):
        kind_map = {"hunger": "comida", "energy": "cama", "hygiene": "ducha"}
        kind = kind_map.get(need)
        if kind is None:
            return

        objs = [o for o in world_objects if o.kind == kind and o.is_free()]
        if not objs:
            self.state  = S_WANDER
            self.dest_x = random.uniform(50, WORLD_W - 50)
            self.dest_y = random.uniform(50, WORLD_H - 50)
            return

        obj = min(objs, key=lambda o: self._dist(o.x, o.y))
        obj.reserve(self.id)
        self.target_obj = obj
        state_map = {"comida": S_SEEK_FOOD, "cama": S_SEEK_BED, "ducha": S_SEEK_SHOWER}
        self.state = state_map[kind]

    def _start_seek_chat(self, target):
        self.target_char = target
        self.state       = S_SEEK_CHAT

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
        self.x += dx * ratio
        self.y += dy * ratio
        self.x = max(self.radius, min(WORLD_W - self.radius, self.x))
        self.y = max(self.radius, min(WORLD_H - self.radius, self.y))

    def _dist(self, tx, ty):
        return math.hypot(tx - self.x, ty - self.y)

    def _at_dest(self):
        return self._dist(self.dest_x, self.dest_y) < 6

    # ── Diálogo ───────────────────────────────
    def _say_auto(self, text: str):
        self.bubble = SpeechBubble(text)

    def _trigger_chat(self, other: "Character"):
        if self._waiting_reply:
            return
        self._waiting_reply = True
        prompt = (
            f"Eres {self.name}, una persona {self.trait}. "
            f"Historia: {self.backstory}. "
            f"Acabas de encontrarte con {other.name} ({other.trait}). "
            f"Di un saludo o comentario corto en espanol, maximo 20 palabras, en primera persona."
        )
        def _cb(txt):
            self.bubble = SpeechBubble(txt)
            self._waiting_reply = False
            self._schedule_reply(other, txt)
        ask_ollama_async(prompt, _cb)

    def _schedule_reply(self, other: "Character", original: str):
        import threading, time as _time
        def _delayed():
            _time.sleep(2.5)
            if other.state == S_SLEEP:
                return
            prompt = (
                f"Eres {other.name}, una persona {other.trait}. "
                f"Historia: {other.backstory}. "
                f"{self.name} te dijo: \"{original}\". "
                f"Responde brevemente en espanol, maximo 20 palabras, en primera persona."
            )
            def _cb2(txt):
                other.bubble = SpeechBubble(txt)
            ask_ollama_async(prompt, _cb2)
        threading.Thread(target=_delayed, daemon=True).start()

    def ollama_thought(self):
        if self._waiting_reply:
            return
        self._waiting_reply = True
        urgent = self.most_urgent_need
        val    = self.need_value(urgent)
        need_es = {"hunger": "hambre", "energy": "energia",
                   "hygiene": "higiene", "social": "vida social"}
        prompt = (
            f"Eres {self.name}, una persona {self.trait}. "
            f"Historia: {self.backstory}. "
            f"Tu nivel de {need_es.get(urgent, urgent)} es {val:.0f}/100. "
            f"Estado actual: {STATE_LABELS.get(self.state, self.state)}. "
            f"Expresa en espanol lo que estas pensando ahora mismo, "
            f"una sola frase corta, maximo 18 palabras, en primera persona."
        )
        def _cb(txt):
            self.bubble = SpeechBubble(txt)
            self._waiting_reply = False
        ask_ollama_async(prompt, _cb)

    # ── Dibujo ────────────────────────────────
    def draw(self, surf, fonts):
        font_sm, font_md, font_lg = fonts
        cx, cy = int(self.x), int(self.y)
        r = self.radius

        # Sombra
        shadow = pygame.Surface((r*2+4, 8), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 60), shadow.get_rect())
        surf.blit(shadow, (cx - r - 2, cy + r - 4))

        # Cuerpo
        col = self.color
        if self.state == S_SLEEP:
            col = tuple(max(0, c - 60) for c in col)
        pygame.draw.circle(surf, col, (cx, cy), r)
        pygame.draw.circle(surf, (255, 255, 255), (cx, cy), r, 2)

        # Anillo de selección pulsante
        if self.selected:
            pulse = int(abs(math.sin(time.time() * 3)) * 80)
            pygame.draw.circle(surf, (255, 255, 100 + pulse), (cx, cy), r + 5, 2)

        # Cara
        if self.state != S_SLEEP:
            pygame.draw.circle(surf, (255, 255, 255), (cx-5, cy-4), 4)
            pygame.draw.circle(surf, (255, 255, 255), (cx+5, cy-4), 4)
            pygame.draw.circle(surf, (30, 30, 30),    (cx-5, cy-4), 2)
            pygame.draw.circle(surf, (30, 30, 30),    (cx+5, cy-4), 2)
            if self.hunger < CRITICAL or self.energy < CRITICAL or self.hygiene < CRITICAL:
                pygame.draw.arc(surf, (180, 60, 60),
                                (cx-6, cy+2, 12, 8), math.pi, 2*math.pi, 2)
            else:
                pygame.draw.arc(surf, (80, 200, 80),
                                (cx-6, cy+1, 12, 8), 0, math.pi, 2)
        else:
            # Animación ZZZ con líneas
            self.zz_phase += 0.05
            off = int(math.sin(self.zz_phase) * 3)
            pygame.draw.line(surf, (200,180,240), (cx-7, cy-4+off), (cx-2, cy-4+off), 2)
            pygame.draw.line(surf, (200,180,240), (cx+2, cy-4+off), (cx+7, cy-4+off), 2)
            zt = font_sm.render("zzz", True, (200, 180, 240))
            surf.blit(zt, (cx + r + 2, cy - r - 2))

        # Nombre
        nt = font_sm.render(self.name, True, C_TEXT)
        surf.blit(nt, (cx - nt.get_width()//2, cy + r + 3))

        # Icono de estado (texto ASCII, sin emoji)
        icon = STATE_ICONS.get(self.state, "")
        if icon:
            it = font_sm.render(icon, True, C_DIM)
            surf.blit(it, (cx - it.get_width()//2, cy - r - 18))

        # Burbuja de diálogo
        if self.bubble and self.bubble.alive():
            self._draw_bubble(surf, font_sm, cx, cy - r - 20)

    def _draw_bubble(self, surf, font, cx, top):
        MAX_W = 210
        text = self.bubble.text
        if not text:
            return

        # Word-wrap manual
        words = text.split()
        if not words:
            return

        lines = []
        current = []
        for word in words:
            test = " ".join(current + [word])
            if font.size(test)[0] > MAX_W - 14 and current:
                lines.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        if current:
            lines.append(" ".join(current))

        if not lines:
            return

        lh = font.get_height() + 3
        bw = max((font.size(ln)[0] for ln in lines), default=40) + 18
        bw = max(bw, 40)
        bh = len(lines) * lh + 14

        bx = cx - bw // 2
        by = top - bh - 10

        # Clamp dentro del mundo
        bx = max(4, min(WORLD_W - bw - 4, bx))
        by = max(4, by)

        alpha = self.bubble.alpha()

        bubble_surf = pygame.Surface((bw, bh), pygame.SRCALPHA)
        pygame.draw.rect(bubble_surf, (*C_BUBBLE, alpha), (0, 0, bw, bh), border_radius=8)
        pygame.draw.rect(bubble_surf, (160, 160, 200, alpha), (0, 0, bw, bh), 1, border_radius=8)

        for i, line_text in enumerate(lines):
            rendered = font.render(line_text, True, C_BUBBLE_T)
            # Crear superficie con alpha para el texto
            txt_surf = pygame.Surface(rendered.get_size(), pygame.SRCALPHA)
            txt_surf.blit(rendered, (0, 0))
            txt_surf.set_alpha(alpha)
            bubble_surf.blit(txt_surf, (8, 7 + i * lh))

        surf.blit(bubble_surf, (bx, by))

        # Cola de la burbuja
        tail_x = max(bx + 10, min(bx + bw - 10, cx))
        tail_pts = [
            (tail_x,     top - 2),
            (tail_x - 6, by + bh),
            (tail_x + 6, by + bh),
        ]
        ts = pygame.Surface((WORLD_W, WORLD_H), pygame.SRCALPHA)
        pygame.draw.polygon(ts, (*C_BUBBLE, alpha), tail_pts)
        surf.blit(ts, (0, 0))
