# ─────────────────────────────────────────────
#  GOD SIMULATION  –  Character Agent
# ─────────────────────────────────────────────
import math
import random
import time
import pygame
from core.config import *
from core.ollama_client import ask_ollama_async


# ── State machine states ──────────────────────
S_IDLE      = "idle"
S_WANDER    = "wander"
S_SEEK_FOOD = "seek_food"
S_EAT       = "eat"
S_SEEK_BED  = "seek_bed"
S_SLEEP     = "sleep"
S_SEEK_SHOWER = "seek_shower"
S_SHOWER    = "shower"
S_SEEK_CHAT = "seek_chat"
S_CHAT      = "chat"


PALETTE = [
    (220, 100, 80), (80, 160, 220), (160, 220, 80),
    (220, 180, 60), (160, 80, 220), (80, 220, 200),
    (220, 120, 160),(140, 200, 140),(200, 140, 100),
]

_next_id = 0

def _new_id():
    global _next_id
    _next_id += 1
    return _next_id


class SpeechBubble:
    DURATION = 6.0   # seconds

    def __init__(self, text: str):
        self.text  = text
        self.born  = time.time()

    def alive(self):
        return time.time() - self.born < self.DURATION

    def alpha(self):
        age = time.time() - self.born
        if age < self.DURATION - 1.5:
            return 255
        return int(255 * (self.DURATION - age) / 1.5)


class Character:
    def __init__(self, name: str, trait: str, backstory: str,
                 x: float, y: float, color=None):
        self.id       = _new_id()
        self.name     = name
        self.trait    = trait        # personality trait
        self.backstory = backstory

        self.x, self.y = float(x), float(y)
        self.color    = color or random.choice(PALETTE)

        # Needs (0 = critical, 100 = full)
        self.hunger  = random.uniform(50, 95)
        self.energy  = random.uniform(50, 95)
        self.hygiene = random.uniform(50, 95)
        self.social  = random.uniform(50, 95)

        # State machine
        self.state       = S_IDLE
        self.target_obj  = None   # WorldObject being used
        self.target_char = None   # Character for social
        self.dest_x = self.x
        self.dest_y = self.y
        self.action_timer = 0.0   # countdown for action completion

        # Idle / wander timer
        self.idle_timer = random.uniform(1, 3)

        # Speech
        self.bubble: SpeechBubble | None = None
        self._waiting_reply = False
        self._chat_cooldown = 0.0

        # Visual
        self.radius  = 16
        self.zz_anim = 0.0        # sleep animation phase
        self.selected = False
        self.blink    = 0.0

    # ── Properties ───────────────────────────────
    @property
    def most_urgent_need(self):
        needs = {
            "hunger":  self.hunger,
            "energy":  self.energy,
            "hygiene": self.hygiene,
            "social":  self.social,
        }
        return min(needs, key=needs.get)

    def need_value(self, key):
        return getattr(self, key)

    # ── Core Update ───────────────────────────────
    def update(self, dt: float, world_objects: list, characters: list):
        # Decay needs
        self.hunger  = max(0, self.hunger  - HUNGER_DECAY  * dt)
        self.energy  = max(0, self.energy  - ENERGY_DECAY  * dt)
        self.hygiene = max(0, self.hygiene - HYGIENE_DECAY * dt)
        self.social  = max(0, self.social  - SOCIAL_DECAY  * dt)

        self._chat_cooldown = max(0, self._chat_cooldown - dt)
        self.blink = max(0, self.blink - dt)

        self._run_fsm(dt, world_objects, characters)

    def _run_fsm(self, dt, world_objects, characters):
        # ── IDLE ─────────────────────────────────
        if self.state == S_IDLE:
            self.idle_timer -= dt
            if self.idle_timer <= 0:
                self._choose_action(world_objects, characters)

        # ── WANDER ───────────────────────────────
        elif self.state == S_WANDER:
            self._move_towards(self.dest_x, self.dest_y, dt, SPEED_SLOW)
            if self._at_dest():
                self.state = S_IDLE
                self.idle_timer = random.uniform(1, 3)
                self._choose_action(world_objects, characters)

        # ── SEEK FOOD ────────────────────────────
        elif self.state == S_SEEK_FOOD:
            if self.target_obj is None:
                self._transition_idle()
                return
            self._move_towards(self.target_obj.x, self.target_obj.y, dt, SPEED_NORMAL)
            if self._dist(self.target_obj.x, self.target_obj.y) < EAT_DIST:
                self.state = S_EAT
                self.action_timer = random.uniform(4, 7)
                self._say_auto(f"Hmm, let me eat something...")

        # ── EAT ──────────────────────────────────
        elif self.state == S_EAT:
            self.action_timer -= dt
            self.hunger = min(100, self.hunger + 18 * dt)
            if self.action_timer <= 0 or self.hunger >= 99:
                self._release_target()
                self._transition_idle()

        # ── SEEK BED ─────────────────────────────
        elif self.state == S_SEEK_BED:
            if self.target_obj is None:
                self._transition_idle()
                return
            self._move_towards(self.target_obj.x, self.target_obj.y, dt, SPEED_SLOW)
            if self._dist(self.target_obj.x, self.target_obj.y) < EAT_DIST:
                self.state = S_SLEEP
                self.action_timer = random.uniform(8, 14)
                self._say_auto("So tired… need to rest.")

        # ── SLEEP ────────────────────────────────
        elif self.state == S_SLEEP:
            self.action_timer -= dt
            self.energy = min(100, self.energy + 10 * dt)
            self.zz_anim += dt * 2
            if self.action_timer <= 0 or self.energy >= 99:
                self._release_target()
                self._transition_idle()

        # ── SEEK SHOWER ──────────────────────────
        elif self.state == S_SEEK_SHOWER:
            if self.target_obj is None:
                self._transition_idle()
                return
            self._move_towards(self.target_obj.x, self.target_obj.y, dt, SPEED_NORMAL)
            if self._dist(self.target_obj.x, self.target_obj.y) < EAT_DIST:
                self.state = S_SHOWER
                self.action_timer = random.uniform(4, 6)
                self._say_auto("A shower will do me good.")

        # ── SHOWER ───────────────────────────────
        elif self.state == S_SHOWER:
            self.action_timer -= dt
            self.hygiene = min(100, self.hygiene + 20 * dt)
            if self.action_timer <= 0 or self.hygiene >= 99:
                self._release_target()
                self._transition_idle()

        # ── SEEK CHAT ────────────────────────────
        elif self.state == S_SEEK_CHAT:
            if self.target_char is None or self.target_char.state == S_SLEEP:
                self._transition_idle()
                return
            self._move_towards(self.target_char.x, self.target_char.y, dt, SPEED_NORMAL)
            if self._dist(self.target_char.x, self.target_char.y) < TALK_DIST:
                self.state = S_CHAT
                self.action_timer = 5.0
                self._trigger_chat(self.target_char)

        # ── CHAT ─────────────────────────────────
        elif self.state == S_CHAT:
            self.action_timer -= dt
            self.social = min(100, self.social + 5 * dt)
            if self.action_timer <= 0:
                self._chat_cooldown = random.uniform(20, 40)
                self.target_char = None
                self._transition_idle()

    # ── Decision Making ──────────────────────────
    def _choose_action(self, world_objects, characters):
        # Priority: critical needs first
        urgent = self.most_urgent_need
        val    = self.need_value(urgent)

        if val < CRITICAL:
            self._seek_for(urgent, world_objects, characters)
            return
        if val < LOW:
            if random.random() < 0.7:
                self._seek_for(urgent, world_objects, characters)
                return

        # Social interaction with another character
        if self.social < LOW and self._chat_cooldown <= 0:
            candidates = [c for c in characters
                          if c.id != self.id and c.state not in (S_SLEEP, S_SEEK_CHAT, S_CHAT)]
            if candidates:
                if self.trait == "shy":
                    if random.random() < 0.25:
                        self._start_seek_chat(random.choice(candidates))
                        return
                else:
                    self._start_seek_chat(random.choice(candidates))
                    return

        # Wander
        self.state  = S_WANDER
        margin = 50
        self.dest_x = random.uniform(margin, WORLD_W - margin)
        self.dest_y = random.uniform(margin, WORLD_H - margin)

    def _seek_for(self, need, world_objects, characters):
        kind_map = {"hunger": "food", "energy": "bed", "hygiene": "shower"}
        kind = kind_map.get(need)
        if kind is None:
            # social handled elsewhere
            return

        objs = [o for o in world_objects if o.kind == kind and o.is_free()]
        if not objs:
            # all occupied → wander
            self.state = S_WANDER
            self.dest_x = random.uniform(50, WORLD_W - 50)
            self.dest_y = random.uniform(50, WORLD_H - 50)
            return

        # Closest
        obj = min(objs, key=lambda o: self._dist(o.x, o.y))
        obj.reserve(self.id)
        self.target_obj = obj
        state_map = {"food": S_SEEK_FOOD, "bed": S_SEEK_BED, "shower": S_SEEK_SHOWER}
        self.state = state_map[kind]

    def _start_seek_chat(self, target):
        self.target_char = target
        self.state       = S_SEEK_CHAT

    def _release_target(self):
        if self.target_obj:
            self.target_obj.release()
            self.target_obj = None

    def _transition_idle(self):
        self.state = S_IDLE
        self.idle_timer = random.uniform(1.5, 4)

    # ── Movement ─────────────────────────────────
    def _move_towards(self, tx, ty, dt, speed):
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        if dist < 2:
            return
        spd = speed * dt
        if self.trait == "lazy":
            spd *= 0.65
        elif self.trait == "energetic":
            spd *= 1.3
        ratio = min(1.0, spd / dist)
        self.x += dx * ratio
        self.y += dy * ratio
        # Clamp
        self.x = max(self.radius, min(WORLD_W - self.radius, self.x))
        self.y = max(self.radius, min(WORLD_H - self.radius, self.y))

    def _dist(self, tx, ty):
        return math.hypot(tx - self.x, ty - self.y)

    def _at_dest(self):
        return self._dist(self.dest_x, self.dest_y) < 6

    # ── Speech & Ollama ──────────────────────────
    def _say_auto(self, text: str):
        self.bubble = SpeechBubble(text)

    def _trigger_chat(self, other: "Character"):
        if self._waiting_reply:
            return
        self._waiting_reply = True
        prompt = (
            f"You are {self.name}, a {self.trait} person. "
            f"Background: {self.backstory}. "
            f"You just met {other.name} ({other.trait}). "
            f"Say one short, in-character greeting or comment (max 20 words)."
        )
        def _cb(txt):
            self.bubble = SpeechBubble(txt)
            self._waiting_reply = False
            # trigger reply from other after short delay
            self._schedule_reply(other, txt)

        ask_ollama_async(prompt, _cb)

    def _schedule_reply(self, other: "Character", original: str):
        import threading, time
        def _delayed():
            time.sleep(2.5)
            if other.state in (S_SLEEP,):
                return
            prompt = (
                f"You are {other.name}, a {other.trait} person. "
                f"Background: {other.backstory}. "
                f"{self.name} just said: \"{original}\". "
                f"Reply briefly in character (max 20 words)."
            )
            def _cb2(txt):
                other.bubble = SpeechBubble(txt)
            ask_ollama_async(prompt, _cb2)

        t = threading.Thread(target=_delayed, daemon=True)
        t.start()

    def ollama_thought(self):
        """Ask Ollama what this character is thinking right now."""
        if self._waiting_reply:
            return
        self._waiting_reply = True
        urgent = self.most_urgent_need
        val    = self.need_value(urgent)
        prompt = (
            f"You are {self.name}, a {self.trait} character. "
            f"Background: {self.backstory}. "
            f"Your {urgent} is at {val:.0f}/100. Current action: {self.state}. "
            f"Express what you are thinking right now in one short sentence (max 18 words)."
        )
        def _cb(txt):
            self.bubble = SpeechBubble(txt)
            self._waiting_reply = False
        ask_ollama_async(prompt, _cb)

    # ── Drawing ──────────────────────────────────
    def draw(self, surf, fonts):
        font_sm, font_md, font_lg = fonts
        cx, cy = int(self.x), int(self.y)

        # Shadow
        shadow = pygame.Surface((self.radius*2+4, 8), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0,0,0,60), shadow.get_rect())
        surf.blit(shadow, (cx - self.radius - 2, cy + self.radius - 4))

        # Body circle
        r = self.radius
        col = self.color
        if self.state == S_SLEEP:
            col = tuple(max(0, c - 60) for c in col)
        pygame.draw.circle(surf, col, (cx, cy), r)
        pygame.draw.circle(surf, (255,255,255), (cx, cy), r, 2)

        # Selected ring
        if self.selected:
            t = time.time()
            pulse = int(abs(math.sin(t * 3)) * 80)
            pygame.draw.circle(surf, (255, 255, 100 + pulse), (cx, cy), r + 5, 2)

        # Face
        if self.state != S_SLEEP:
            # Eyes
            pygame.draw.circle(surf, (255,255,255), (cx-5, cy-4), 4)
            pygame.draw.circle(surf, (255,255,255), (cx+5, cy-4), 4)
            pygame.draw.circle(surf, (30,30,30),    (cx-5, cy-4), 2)
            pygame.draw.circle(surf, (30,30,30),    (cx+5, cy-4), 2)
            # Mouth
            if self.hunger < CRITICAL or self.energy < CRITICAL or self.hygiene < CRITICAL:
                # sad
                pygame.draw.arc(surf, (180,60,60),
                                (cx-6, cy+2, 12, 8), math.pi, 2*math.pi, 2)
            else:
                # happy
                pygame.draw.arc(surf, (80,200,80),
                                (cx-6, cy+1, 12, 8), 0, math.pi, 2)
        else:
            # ZZZ eyes
            self.zz_anim += 0.05
            offset = int(math.sin(self.zz_anim) * 3)
            pygame.draw.line(surf, (200,180,240), (cx-7, cy-4+offset), (cx-2, cy-4+offset), 2)
            pygame.draw.line(surf, (200,180,240), (cx+2, cy-4+offset), (cx+7, cy-4+offset), 2)
            # ZZZ text
            zt = font_sm.render("zzz", True, (200,180,240))
            surf.blit(zt, (cx + r, cy - r - 4))

        # Name tag
        nt = font_sm.render(self.name, True, C_TEXT)
        surf.blit(nt, (cx - nt.get_width()//2, cy + r + 3))

        # State icon
        icon_map = {
            S_SLEEP: "😴", S_EAT: "🍖", S_SHOWER: "🚿",
            S_CHAT: "💬", S_WANDER: "🚶", S_SEEK_FOOD: "→🍖",
            S_SEEK_BED: "→🛏", S_SEEK_SHOWER: "→🚿",
            S_SEEK_CHAT: "→💬", S_IDLE: "💭",
        }
        icon = icon_map.get(self.state, "")
        if icon:
            it = font_sm.render(icon, True, C_DIM)
            surf.blit(it, (cx - it.get_width()//2, cy - r - 20))

        # Speech bubble
        if self.bubble and self.bubble.alive():
            self._draw_bubble(surf, font_sm, cx, cy - r - 18)

    def _draw_bubble(self, surf, font, cx, top):
        MAX_W = 200
        words = self.bubble.text.split()
        lines, line = [], []
        for w in words:
            test = " ".join(line + [w])
            if font.size(test)[0] > MAX_W - 12:
                if line:
                    lines.append(" ".join(line))
                line = [w]
            else:
                line.append(w)
        if line:
            lines.append(" ".join(line))

        lh   = font.get_height() + 2
        bw   = max(font.size(l)[0] for l in lines) + 16
        bh   = len(lines) * lh + 12
        bx   = cx - bw // 2
        by   = top - bh - 8

        # Clamp to world
        bx = max(4, min(WORLD_W - bw - 4, bx))
        by = max(4, by)

        alpha = self.bubble.alpha()
        bubble_surf = pygame.Surface((bw, bh), pygame.SRCALPHA)
        pygame.draw.rect(bubble_surf, (*C_BUBBLE, alpha), (0,0,bw,bh), border_radius=8)
        pygame.draw.rect(bubble_surf, (160,160,200, alpha), (0,0,bw,bh), 1, border_radius=8)
        for i, line_text in enumerate(lines):
            lt = font.render(line_text, True, (*C_BUBBLE_T, alpha))
            bubble_surf.blit(lt, (8, 6 + i * lh))
        surf.blit(bubble_surf, (bx, by))
        # Tail
        tail_pts = [(cx, top - 4), (cx - 5, by + bh), (cx + 5, by + bh)]
        ts = pygame.Surface((WORLD_W, WORLD_H), pygame.SRCALPHA)
        pygame.draw.polygon(ts, (*C_BUBBLE, alpha), tail_pts)
        surf.blit(ts, (0, 0))
