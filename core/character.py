# ─────────────────────────────────────────────
#  WORLD SIMULATION  –  Agente Personaje
# ─────────────────────────────────────────────
import math, random, time, threading
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
    S_IDLE:        "Descansando",   S_WANDER:      "Explorando",
    S_SEEK_FOOD:   "->Comida",      S_EAT:         "Comiendo",
    S_SEEK_BED:    "->Cama",        S_SLEEP:       "Durmiendo",
    S_SEEK_SHOWER: "->Ducha",       S_SHOWER:      "Duchando",
    S_SEEK_CHAT:   "->Charla",      S_CHAT:        "Charlando",
}
STATE_ICONS = {
    S_IDLE:"[..]", S_WANDER:"[>>]", S_SEEK_FOOD:"[>F]", S_EAT:"[F!]",
    S_SEEK_BED:"[>Z]", S_SLEEP:"[ZZ]", S_SEEK_SHOWER:"[>W]", S_SHOWER:"[W!]",
    S_SEEK_CHAT:"[>C]", S_CHAT:"[CC]",
}

PALETTE = [
    (220,100,80),(80,160,220),(160,220,80),(220,180,60),(160,80,220),(80,220,200),
    (220,120,160),(140,200,140),(200,140,100),(100,200,220),(220,160,100),(180,220,100),
    (240,130,60),(60,200,160),(200,80,160),(120,180,240),(240,200,80),(80,240,120),
]

_next_id = 0
def _new_id():
    global _next_id; _next_id += 1; return _next_id

def _reading_secs(text: str, extra: float = 1.2) -> float:
    return max(3.5, max(1, len(text.split())) / 130 * 60 + extra)

def _num_turns(trait_a: str, trait_b: str) -> int:
    social = {"amigable","curioso","optimista","energetico","agresivo"}
    quiet  = {"timido","melancolico","perezoso"}
    score  = 2
    for t in (trait_a, trait_b):
        if t in social: score += random.randint(1, 3)
        if t in quiet:  score -= random.randint(0, 1)
    return max(2, min(8, score))


# ── Burbuja de diálogo ───────────────────────
class SpeechBubble:
    def __init__(self, text: str):
        self.text     = text.strip() if text else ""
        self.duration = _reading_secs(self.text, extra=1.5)
        self.born     = time.time()

    def alive(self):  return time.time() - self.born < self.duration
    def age(self):    return time.time() - self.born
    def alpha(self):
        elapsed = self.age()
        fade_start = self.duration - 1.5
        if elapsed < fade_start: return 255
        return max(0, int(255 * (self.duration - elapsed) / 1.5))


# ── Motor de conversación multi-turno ─────────
class ConversationEngine:
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
        self.history: list[tuple[str,str]] = []
        self.num_turns = _num_turns(char_a.trait, char_b.trait)
        self._t        = threading.Thread(target=self._run, daemon=True)

    def start(self):  self._t.start()
    def stop(self):   self.active = False

    def _run(self):
        for turn in range(self.num_turns):
            if not self.active:
                break

            speaker  = self.char_a if turn % 2 == 0 else self.char_b
            listener = self.char_b if turn % 2 == 0 else self.char_a

            hist_txt = "".join(f"{n}: {m}\n" for n, m in self.history[-6:])

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

            result = {"text": None}
            done   = threading.Event()
            def _cb(txt, r=result, e=done): r["text"] = txt; e.set()
            ask_ollama_async(prompt, _cb, system=self.SYSTEM,
                             max_chars=220, num_predict=160)
            done.wait(timeout=80)

            if not self.active:
                break

            text = (result["text"] or "...").strip()
            self.history.append((speaker.name, text))
            speaker.bubble = SpeechBubble(text)

            wait = _reading_secs(text, extra=random.uniform(0.8, 2.0))
            deadline = time.time() + wait
            while time.time() < deadline and self.active:
                time.sleep(0.1)

        # Guardar log y notificar fin
        self.active = False
        self._save_log()
        self.char_a._conv_done = True
        self.char_b._conv_done = True

    def _save_log(self):
        if not self.history:
            return
        try:
            from core.conv_logger import log_conversation
            log_conversation(
                self.char_a.name, self.char_b.name,
                self.char_a.trait, self.char_b.trait,
                self.history,
            )
        except Exception as e:
            print(f"[Logger] Error al guardar: {e}")


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

        self.hunger  = random.uniform(55, 95)
        self.energy  = random.uniform(55, 95)
        self.hygiene = random.uniform(55, 95)
        self.social  = random.uniform(55, 95)

        self.state        = S_IDLE
        self.target_obj   = None
        self.target_char: "Character | None" = None
        self.dest_x       = self.x
        self.dest_y       = self.y
        self.action_timer = 0.0
        self.idle_timer   = random.uniform(1, 3)

        self.bubble: SpeechBubble | None = None
        self._chat_cooldown = 0.0
        self._conv: ConversationEngine | None = None
        self._conv_done    = False
        self._is_initiator = False

        self.radius   = 16
        self.zz_phase = 0.0
        self.selected = False
        self.blink    = 0.0
        self._thinking = False

    @property
    def most_urgent_need(self):
        d = {"hunger":self.hunger,"energy":self.energy,
             "hygiene":self.hygiene,"social":self.social}
        return min(d, key=d.get)

    def need_value(self, key): return getattr(self, key)

    # ── Update ────────────────────────────────
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
        if self.state == S_IDLE:
            self.idle_timer -= dt
            if self.idle_timer <= 0:
                self._choose_action(world_objects, characters)

        elif self.state == S_WANDER:
            self._move_towards(self.dest_x, self.dest_y, dt, SPEED_SLOW)
            if self._at_dest(): self._transition_idle()

        elif self.state == S_SEEK_FOOD:
            if self.target_obj is None: self._transition_idle(); return
            self._move_towards(self.target_obj.x, self.target_obj.y, dt, SPEED_NORMAL)
            if self._dist(self.target_obj.x, self.target_obj.y) < EAT_DIST:
                self.state = S_EAT
                self.action_timer = random.uniform(4, 7)
                self._say("Mmm, necesito comer algo...")

        elif self.state == S_EAT:
            self.action_timer -= dt
            self.hunger = min(100, self.hunger + 18 * dt)
            if self.action_timer <= 0 or self.hunger >= 99:
                self._release_target(); self._transition_idle()

        elif self.state == S_SEEK_BED:
            if self.target_obj is None: self._transition_idle(); return
            self._move_towards(self.target_obj.x, self.target_obj.y, dt, SPEED_SLOW)
            if self._dist(self.target_obj.x, self.target_obj.y) < EAT_DIST:
                self.state = S_SLEEP
                self.action_timer = random.uniform(8, 14)
                self._say("Que sueno tengo... a descansar.")

        elif self.state == S_SLEEP:
            self.action_timer -= dt
            self.energy = min(100, self.energy + 10 * dt)
            self.zz_phase += dt * 2
            if self.action_timer <= 0 or self.energy >= 99:
                self._release_target(); self._transition_idle()

        elif self.state == S_SEEK_SHOWER:
            if self.target_obj is None: self._transition_idle(); return
            self._move_towards(self.target_obj.x, self.target_obj.y, dt, SPEED_NORMAL)
            if self._dist(self.target_obj.x, self.target_obj.y) < EAT_DIST:
                self.state = S_SHOWER
                self.action_timer = random.uniform(4, 6)
                self._say("Una ducha me vendra de maravilla.")

        elif self.state == S_SHOWER:
            self.action_timer -= dt
            self.hygiene = min(100, self.hygiene + 20 * dt)
            if self.action_timer <= 0 or self.hygiene >= 99:
                self._release_target(); self._transition_idle()

        elif self.state == S_SEEK_CHAT:
            other = self.target_char
            if other is None or other.state == S_SLEEP:
                self._transition_idle(); return
            self._move_towards(other.x, other.y, dt, SPEED_NORMAL)
            # Distancia de parada: que los bordes se toquen (radio + radio + 4px gap)
            stop_dist = self.radius + other.radius + 4
            if self._dist(other.x, other.y) <= stop_dist + 2:
                self._start_conversation(other)

        elif self.state == S_CHAT:
            # ── Mantenerse pegados (bordes tocándose) ──
            if self.target_char:
                other   = self.target_char
                dist    = self._dist(other.x, other.y)
                desired = self.radius + other.radius + 4   # borde a borde
                if dist > desired + 6:
                    # acercarse suavemente hasta la distancia justa
                    self._move_towards(other.x, other.y, dt, SPEED_SLOW * 0.5)
                elif dist < desired - 4:
                    # alejarse ligeramente si quedaron encima
                    dx = self.x - other.x
                    dy = self.y - other.y
                    length = math.hypot(dx, dy) or 1
                    push = (desired - dist) * 0.5
                    self.x += (dx / length) * push * dt * 10
                    self.y += (dy / length) * push * dt * 10
                    self.x = max(self.radius, min(WORLD_W - self.radius, self.x))
                    self.y = max(self.radius, min(WORLD_H - self.radius, self.y))

            self.social = min(100, self.social + 4 * dt)
            if self._conv_done:
                self._end_conversation()

    # ── Decisiones ────────────────────────────
    def _choose_action(self, world_objects, characters):
        urgent = self.most_urgent_need
        val    = self.need_value(urgent)
        if val < CRITICAL:
            self._seek_for(urgent, world_objects, characters); return
        if val < LOW and random.random() < 0.7:
            self._seek_for(urgent, world_objects, characters); return

        if self.social < LOW and self._chat_cooldown <= 0:
            candidates = [c for c in characters
                          if c.id != self.id
                          and c.state not in (S_SLEEP, S_SEEK_CHAT, S_CHAT)]
            if candidates:
                chance = 0.20 if self.trait == "timido" else 0.70
                if random.random() < chance:
                    self.target_char   = random.choice(candidates)
                    self.state         = S_SEEK_CHAT
                    self._is_initiator = True
                    return

        self.state  = S_WANDER
        self.dest_x = random.uniform(60, WORLD_W - 60)
        self.dest_y = random.uniform(60, WORLD_H - 60)

    def _seek_for(self, need, world_objects, characters):
        kind_map  = {"hunger":"comida","energy":"cama","hygiene":"ducha"}
        state_map = {"comida":S_SEEK_FOOD,"cama":S_SEEK_BED,"ducha":S_SEEK_SHOWER}
        kind = kind_map.get(need)
        if not kind: return
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
        if not self._is_initiator: return

        # ── Posicionarse lado a lado ──────────
        # El iniciador (self) se queda donde está.
        # El otro se coloca a exactamente (r_a + r_b + 4) píxeles de distancia,
        # en la dirección que ya tiene respecto al iniciador.
        dist    = self._dist(other.x, other.y)
        desired = self.radius + other.radius + 4
        if dist > 0:
            dx = (other.x - self.x) / dist
            dy = (other.y - self.y) / dist
        else:
            dx, dy = 1.0, 0.0
        other.x = self.x + dx * desired
        other.y = self.y + dy * desired
        other.x = max(other.radius, min(WORLD_W - other.radius, other.x))
        other.y = max(other.radius, min(WORLD_H - other.radius, other.y))

        self.state  = S_CHAT
        other.state = S_CHAT
        other.target_char   = self
        other._is_initiator = False

        self._conv_done  = False
        other._conv_done = False
        engine = ConversationEngine(self, other)
        self._conv  = engine
        other._conv = engine
        engine.start()

    def _end_conversation(self):
        self._conv_done    = False
        self._is_initiator = False
        self._conv         = None
        self._chat_cooldown = random.uniform(25, 50)
        self.target_char   = None
        self._transition_idle()

    def abort_conversation(self):
        if self._conv: self._conv.stop(); self._conv = None
        self._conv_done    = True
        self._is_initiator = False

    def _release_target(self):
        if self.target_obj:
            self.target_obj.release()
            self.target_obj = None

    def _transition_idle(self):
        self.state = S_IDLE
        self.idle_timer = random.uniform(1.5, 4)

    # ── Movimiento ────────────────────────────
    def _move_towards(self, tx, ty, dt, speed):
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        if dist < 2: return
        spd = speed * dt
        if self.trait == "perezoso":   spd *= 0.65
        elif self.trait == "energetico": spd *= 1.3
        ratio = min(1.0, spd / dist)
        self.x = max(self.radius, min(WORLD_W - self.radius, self.x + dx * ratio))
        self.y = max(self.radius, min(WORLD_H - self.radius, self.y + dy * ratio))

    def _dist(self, tx, ty): return math.hypot(tx - self.x, ty - self.y)
    def _at_dest(self):      return self._dist(self.dest_x, self.dest_y) < 6
    def _say(self, text):    self.bubble = SpeechBubble(text)

    def ollama_thought(self):
        if self._thinking: return
        self._thinking = True
        need_es = {"hunger":"hambre","energy":"energia",
                   "hygiene":"higiene","social":"vida social"}
        urgent = self.most_urgent_need
        val    = self.need_value(urgent)
        prompt = (
            f"Eres {self.name}, una persona {self.trait}. "
            f"Historia: {self.backstory}. "
            f"Tu nivel de {need_es.get(urgent,urgent)} es {val:.0f}/100. "
            f"Estado: {STATE_LABELS.get(self.state,self.state)}. "
            f"Expresa en espanol lo que estas pensando ahora mismo. "
            f"Una sola frase, maximo 20 palabras, en primera persona. Sin asteriscos."
        )
        def _cb(txt):
            self.bubble = SpeechBubble(txt)
            self._thinking = False
        ask_ollama_async(prompt, _cb, max_chars=200, num_predict=100)

    # ── Dibujo ────────────────────────────────
    def draw(self, surf, fonts):
        font_sm, font_md, font_lg = fonts
        cx, cy = int(self.x), int(self.y)
        r = self.radius

        # Sombra
        shadow = pygame.Surface((r*2+4, 8), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0,0,0,55), shadow.get_rect())
        surf.blit(shadow, (cx-r-2, cy+r-4))

        # Cuerpo
        col = self.color
        if self.state == S_SLEEP:
            col = tuple(max(0, c-65) for c in col)
        pygame.draw.circle(surf, col, (cx, cy), r)
        pygame.draw.circle(surf, (255,255,255), (cx, cy), r, 2)

        # Línea de conversación pulsante
        if self.state == S_CHAT and self.target_char and self._is_initiator:
            tc = self.target_char
            pulse = int(abs(math.sin(time.time() * 4)) * 80 + 80)
            pygame.draw.line(surf, (pulse, 220, pulse),
                             (cx, cy), (int(tc.x), int(tc.y)), 2)

        # Anillo selección
        if self.selected:
            pulse = int(abs(math.sin(time.time() * 3)) * 80)
            pygame.draw.circle(surf, (255,255,100+pulse), (cx,cy), r+5, 2)

        # Cara
        if self.state != S_SLEEP:
            pygame.draw.circle(surf, (255,255,255), (cx-5,cy-4), 4)
            pygame.draw.circle(surf, (255,255,255), (cx+5,cy-4), 4)
            pygame.draw.circle(surf, (30,30,30),    (cx-5,cy-4), 2)
            pygame.draw.circle(surf, (30,30,30),    (cx+5,cy-4), 2)
            if self.hunger < CRITICAL or self.energy < CRITICAL or self.hygiene < CRITICAL:
                pygame.draw.arc(surf,(180,60,60),(cx-6,cy+2,12,8),math.pi,2*math.pi,2)
            else:
                pygame.draw.arc(surf,(80,200,80),(cx-6,cy+1,12,8),0,math.pi,2)
        else:
            self.zz_phase += 0.05
            off = int(math.sin(self.zz_phase)*3)
            pygame.draw.line(surf,(200,180,240),(cx-7,cy-4+off),(cx-2,cy-4+off),2)
            pygame.draw.line(surf,(200,180,240),(cx+2,cy-4+off),(cx+7,cy-4+off),2)
            zt = font_sm.render("zzz", True, (200,180,240))
            surf.blit(zt, (cx+r+2, cy-r-2))

        # Nombre
        nt = font_sm.render(self.name, True, C_TEXT)
        surf.blit(nt, (cx - nt.get_width()//2, cy+r+3))

        # Icono estado
        icon = STATE_ICONS.get(self.state,"")
        if icon:
            it = font_sm.render(icon, True, C_DIM)
            surf.blit(it, (cx - it.get_width()//2, cy-r-18))

        # Burbuja
        if self.bubble and self.bubble.alive():
            self._draw_bubble(surf, font_sm, cx, cy-r-20)

    def _draw_bubble(self, surf, font, cx, top):
        MAX_W = 260
        text  = self.bubble.text if self.bubble else ""
        if not text: return

        words = text.split()
        if not words: return

        lines, current = [], []
        for word in words:
            probe = " ".join(current + [word])
            if font.size(probe)[0] > MAX_W - 16 and current:
                lines.append(" ".join(current)); current = [word]
            else: current.append(word)
        if current: lines.append(" ".join(current))
        if not lines: return

        lh = font.get_height() + 4
        bw = max(font.size(ln)[0] for ln in lines) + 20
        bw = max(bw, 50)
        bh = len(lines) * lh + 16

        bx = cx - bw // 2
        by = top - bh - 10
        bx = max(4, min(WORLD_W - bw - 4, bx))
        by = max(4, by)

        alpha = self.bubble.alpha()
        bubble = pygame.Surface((bw, bh), pygame.SRCALPHA)
        pygame.draw.rect(bubble, (*C_BUBBLE, alpha),     (0,0,bw,bh), border_radius=9)
        pygame.draw.rect(bubble, (150,155,200,alpha),    (0,0,bw,bh), 1, border_radius=9)

        for i, line_text in enumerate(lines):
            rendered = font.render(line_text, True, C_BUBBLE_T)
            tmp = pygame.Surface(rendered.get_size(), pygame.SRCALPHA)
            tmp.blit(rendered, (0,0)); tmp.set_alpha(alpha)
            bubble.blit(tmp, (10, 8 + i*lh))
        surf.blit(bubble, (bx, by))

        # Cola
        tail_x = max(bx+12, min(bx+bw-12, cx))
        pts = [(tail_x, top-3), (tail_x-7, by+bh), (tail_x+7, by+bh)]
        ts  = pygame.Surface((WORLD_W, WORLD_H), pygame.SRCALPHA)
        pygame.draw.polygon(ts, (*C_BUBBLE, alpha), pts)
        surf.blit(ts, (0,0))
