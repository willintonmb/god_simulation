# ─────────────────────────────────────────────
#  GOD SIMULATION  –  UI Components
# ─────────────────────────────────────────────
import math, time
import pygame
from core.config import *


# ── Colours & helpers ────────────────────────
def _bar(surf, x, y, w, h, val, col_full, col_bg=(40,40,60)):
    pygame.draw.rect(surf, col_bg, (x, y, w, h), border_radius=3)
    fill = int(w * val / 100)
    if fill > 0:
        pygame.draw.rect(surf, col_full, (x, y, fill, h), border_radius=3)
    pygame.draw.rect(surf, (80,80,100), (x, y, w, h), 1, border_radius=3)


# ── Bottom Info Panel ────────────────────────
def draw_bottom_panel(surf, fonts, characters, selected, world_objects,
                      sim_speed, paused, ollama_ok):
    font_sm, font_md, font_lg = fonts
    px, py = 0, WORLD_H
    pw, ph = SCREEN_W, UI_H

    # Background
    pygame.draw.rect(surf, C_PANEL, (px, py, pw, ph))
    pygame.draw.line(surf, C_ACCENT, (px, py), (px + pw, py), 2)

    # === Left: selected character details ===
    if selected:
        c = selected
        # Name + trait
        nt = font_md.render(f"✦ {c.name}", True, c.color)
        surf.blit(nt, (px + 12, py + 10))
        tt = font_sm.render(f"[{c.trait}]  {c.backstory[:55]}…" if len(c.backstory)>55
                             else f"[{c.trait}]  {c.backstory}", True, C_DIM)
        surf.blit(tt, (px + 12, py + 36))

        # State
        st = font_sm.render(f"State: {c.state}", True, C_TEXT)
        surf.blit(st, (px + 12, py + 55))

        # Need bars
        needs = [
            ("Hunger",  c.hunger,  (200, 140, 60)),
            ("Energy",  c.energy,  (90,  160, 230)),
            ("Hygiene", c.hygiene, (70,  200, 170)),
            ("Social",  c.social,  (200, 100, 200)),
        ]
        bx = px + 12
        for i, (label, val, col) in enumerate(needs):
            lbl = font_sm.render(label, True, C_DIM)
            surf.blit(lbl, (bx, py + 80 + i * 28))
            _bar(surf, bx + 55, py + 83 + i*28, 100, 12, val, col)
            vt = font_sm.render(f"{val:.0f}", True, C_TEXT)
            surf.blit(vt, (bx + 160, py + 80 + i*28))

    else:
        hint = font_md.render("Click a character to inspect", True, C_DIM)
        surf.blit(hint, (px + 20, py + ph//2 - hint.get_height()//2))

    # === Middle: population list ===
    mx = 340
    head = font_sm.render("POPULATION", True, C_ACCENT)
    surf.blit(head, (px + mx, py + 10))
    visible = characters[:8]
    for i, c in enumerate(visible):
        col = c.color if not selected or selected.id != c.id else (255,255,100)
        dot = pygame.draw.circle(surf, col, (px + mx + 6, py + 33 + i*18), 5)
        nt  = font_sm.render(f"{c.name}  [{c.state[:8]}]", True, col)
        surf.blit(nt, (px + mx + 16, py + 26 + i*18))
    if len(characters) > 8:
        mt = font_sm.render(f"+ {len(characters)-8} more", True, C_DIM)
        surf.blit(mt, (px + mx + 6, py + 33 + 8*18))

    # === Right: controls & status ===
    rx = SCREEN_W - 260
    # Sim speed
    spd_col = C_ACCENT if not paused else C_WARN
    st = font_sm.render(f"Speed: {'PAUSED' if paused else f'x{sim_speed:.1f}'}", True, spd_col)
    surf.blit(st, (px + rx, py + 10))

    keys = [
        ("SPACE",  "Pause/Resume"),
        ("+/-",    "Speed"),
        ("N",      "New Character"),
        ("T",      "Ask Thought"),
        ("R",      "Regenerate World"),
        ("ESC",    "Deselect"),
    ]
    for i, (k, desc) in enumerate(keys):
        kt = font_sm.render(f"[{k}]", True, C_ACCENT)
        dt = font_sm.render(desc, True, C_DIM)
        surf.blit(kt, (px + rx, py + 32 + i*22))
        surf.blit(dt, (px + rx + 44, py + 32 + i*22))

    # Ollama status
    ok_col = C_ACCENT if ollama_ok else C_DANGER
    ok_t   = font_sm.render(f"● Ollama: {'OK' if ollama_ok else 'OFFLINE'}", True, ok_col)
    surf.blit(ok_t, (px + rx, py + ph - 24))


# ── Notification Toast ───────────────────────
class Toast:
    def __init__(self, text, duration=3.0):
        self.text     = text
        self.born     = time.time()
        self.duration = duration

    def alive(self):
        return time.time() - self.born < self.duration

    def alpha(self):
        age = time.time() - self.born
        if age < self.duration - 0.5:
            return 200
        return int(200 * (self.duration - age) / 0.5)


def draw_toasts(surf, font, toasts):
    y = WORLD_H - 10
    for t in reversed(toasts):
        if not t.alive():
            continue
        a  = t.alpha()
        tw = font.size(t.text)[0] + 20
        ts = pygame.Surface((tw, 28), pygame.SRCALPHA)
        pygame.draw.rect(ts, (20, 20, 40, a), ts.get_rect(), border_radius=6)
        pygame.draw.rect(ts, (90, 200, 130, a), ts.get_rect(), 1, border_radius=6)
        tt = font.render(t.text, True, (220, 230, 220))
        ts.blit(tt, (10, 5))
        y -= 32
        surf.blit(ts, (SCREEN_W // 2 - tw // 2, y))


# ── Creation Modal ────────────────────────────
class CreationModal:
    """Simple text-input modal to create a new character."""

    FIELDS = ["Name", "Trait", "Backstory"]

    def __init__(self, fonts, traits):
        self.fonts    = fonts
        self.traits   = traits
        self.active   = False
        self.values   = ["", "friendly", ""]
        self.focused  = 0
        self.trait_idx = 0
        self.error    = ""

        self.rect = pygame.Rect(
            SCREEN_W//2 - 300, SCREEN_H//2 - 200,
            600, 400
        )

    def open(self):
        self.active   = True
        self.values   = ["", self.traits[0], ""]
        self.trait_idx = 0
        self.focused  = 0
        self.error    = ""

    def close(self):
        self.active = False

    def handle_event(self, event):
        """Returns ('create', name, trait, backstory) | ('cancel',) | None"""
        if not self.active:
            return None

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.close()
                return ("cancel",)
            elif event.key == pygame.K_TAB:
                self.focused = (self.focused + 1) % len(self.FIELDS)
            elif event.key == pygame.K_RETURN:
                return self._submit()
            elif self.focused == 1:   # trait: arrow keys
                if event.key in (pygame.K_LEFT, pygame.K_UP):
                    self.trait_idx = (self.trait_idx - 1) % len(self.traits)
                    self.values[1] = self.traits[self.trait_idx]
                elif event.key in (pygame.K_RIGHT, pygame.K_DOWN):
                    self.trait_idx = (self.trait_idx + 1) % len(self.traits)
                    self.values[1] = self.traits[self.trait_idx]
            else:
                fi = self.focused
                if fi != 1:   # editable text fields
                    if event.key == pygame.K_BACKSPACE:
                        self.values[fi] = self.values[fi][:-1]
                    elif event.unicode and len(self.values[fi]) < 80:
                        self.values[fi] += event.unicode

        if event.type == pygame.MOUSEBUTTONDOWN:
            for i in range(len(self.FIELDS)):
                fr = self._field_rect(i)
                if fr.collidepoint(event.pos):
                    self.focused = i

        return None

    def _submit(self):
        name = self.values[0].strip()
        trait = self.values[1].strip()
        backstory = self.values[2].strip()
        if not name:
            self.error = "Name cannot be empty."
            return None
        if not backstory:
            backstory = f"A {trait} soul wandering this world."
        self.close()
        return ("create", name, trait, backstory)

    def _field_rect(self, i):
        return pygame.Rect(self.rect.x + 30, self.rect.y + 120 + i * 80, 540, 36)

    def draw(self, surf):
        if not self.active:
            return
        font_sm, font_md, font_lg = self.fonts

        # Overlay
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 160))
        surf.blit(ov, (0, 0))

        # Box
        pygame.draw.rect(surf, (22, 24, 38), self.rect, border_radius=12)
        pygame.draw.rect(surf, C_ACCENT, self.rect, 2, border_radius=12)

        # Title
        title = font_lg.render("✦ Create Character", True, C_ACCENT)
        surf.blit(title, (self.rect.x + 30, self.rect.y + 18))

        labels = ["Name", "Trait  (←→)", "Backstory"]
        for i, label in enumerate(labels):
            fr = self._field_rect(i)
            lbl = font_sm.render(label, True, C_DIM)
            surf.blit(lbl, (fr.x, fr.y - 18))

            col_border = C_ACCENT if self.focused == i else (60, 70, 90)
            pygame.draw.rect(surf, (28, 32, 50), fr, border_radius=6)
            pygame.draw.rect(surf, col_border, fr, 1, border_radius=6)

            val = self.values[i]
            if i == 1:
                # Trait selector with arrows
                lt = font_sm.render(f"◀  {val}  ▶", True, C_TEXT)
            else:
                cursor = "|" if self.focused == i and int(time.time() * 2) % 2 == 0 else ""
                lt = font_sm.render(val + cursor, True, C_TEXT)
            surf.blit(lt, (fr.x + 8, fr.y + 8))

        # Error
        if self.error:
            et = font_sm.render(self.error, True, C_DANGER)
            surf.blit(et, (self.rect.x + 30, self.rect.y + 360))

        # Buttons
        ok_r = pygame.Rect(self.rect.right - 140, self.rect.bottom - 50, 110, 36)
        cn_r = pygame.Rect(self.rect.right - 270, self.rect.bottom - 50, 110, 36)
        pygame.draw.rect(surf, C_ACCENT, ok_r, border_radius=8)
        pygame.draw.rect(surf, (60,70,90), cn_r, border_radius=8)
        ok_t = font_sm.render("Create  ↵", True, (10,10,10))
        cn_t = font_sm.render("Cancel  ESC", True, C_TEXT)
        surf.blit(ok_t, ok_t.get_rect(center=ok_r.center))
        surf.blit(cn_t, cn_t.get_rect(center=cn_r.center))
