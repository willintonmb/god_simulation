# ─────────────────────────────────────────────
#  WORLD SIMULATION  –  Componentes de UI
# ─────────────────────────────────────────────
import math, time
import pygame
from core.config import *


def _bar(surf, x, y, w, h, val, col_full, col_bg=(35, 38, 55)):
    pygame.draw.rect(surf, col_bg, (x, y, w, h), border_radius=3)
    fill = int(w * max(0, min(100, val)) / 100)
    if fill > 0:
        pygame.draw.rect(surf, col_full, (x, y, fill, h), border_radius=3)
    pygame.draw.rect(surf, (70, 75, 100), (x, y, w, h), 1, border_radius=3)


# ── Panel inferior principal ─────────────────
def draw_bottom_panel(surf, fonts, characters, selected, world_objects,
                      sim_speed, paused, ollama_ok):
    font_sm, font_md, font_lg = fonts
    px, py = 0, WORLD_H
    pw, ph = SCREEN_W, UI_H

    pygame.draw.rect(surf, C_PANEL, (px, py, pw, ph))
    pygame.draw.line(surf, C_ACCENT, (px, py), (px + pw, py), 2)

    # ── Columna izquierda: personaje seleccionado ──
    if selected:
        c = selected
        nt = font_md.render(f">> {c.name}", True, c.color)
        surf.blit(nt, (px + 12, py + 8))

        trait_desc = TRAIT_DESC.get(c.trait, "")
        tt = font_sm.render(f"[{c.trait}]  {trait_desc}", True, C_DIM)
        surf.blit(tt, (px + 12, py + 32))

        bs = c.backstory if len(c.backstory) <= 58 else c.backstory[:55] + "..."
        bt = font_sm.render(bs, True, (160, 170, 160))
        surf.blit(bt, (px + 12, py + 48))

        from core.character import STATE_LABELS
        estado = STATE_LABELS.get(c.state, c.state)
        st = font_sm.render(f"Estado: {estado}", True, C_TEXT)
        surf.blit(st, (px + 12, py + 65))

        needs = [
            ("Hambre",  c.hunger,  (210, 140, 55)),
            ("Energia", c.energy,  (80,  155, 230)),
            ("Higiene", c.hygiene, (65,  195, 165)),
            ("Social",  c.social,  (195, 95,  195)),
        ]
        bx = px + 12
        for i, (label, val, col) in enumerate(needs):
            lbl = font_sm.render(label, True, C_DIM)
            surf.blit(lbl, (bx, py + 86 + i * 26))
            _bar(surf, bx + 60, py + 89 + i*26, 110, 11, val, col)
            # Color del valor según urgencia
            vcol = C_DANGER if val < CRITICAL else (C_WARN if val < LOW else C_TEXT)
            vt = font_sm.render(f"{val:.0f}", True, vcol)
            surf.blit(vt, (bx + 175, py + 86 + i*26))
    else:
        hint1 = font_md.render("Haz clic en un personaje", True, C_DIM)
        hint2 = font_sm.render("para ver sus estadisticas", True, (70, 85, 70))
        surf.blit(hint1, (px + 20, py + ph//2 - 20))
        surf.blit(hint2, (px + 20, py + ph//2 + 4))

    # ── Columna central: lista de población ──────
    mx = 500
    head = font_sm.render("POBLACION", True, C_ACCENT)
    surf.blit(head, (px + mx, py + 8))

    from core.character import STATE_LABELS
    max_visible = min(len(characters), 9)
    for i, c in enumerate(characters[:max_visible]):
        is_sel = selected and selected.id == c.id
        col    = (255, 255, 100) if is_sel else c.color
        pygame.draw.circle(surf, col, (px + mx + 7, py + 30 + i*18), 5)
        estado_corto = STATE_LABELS.get(c.state, c.state)[:10]
        nt = font_sm.render(f"{c.name}  - {estado_corto}", True, col)
        surf.blit(nt, (px + mx + 18, py + 23 + i*18))

    if len(characters) > 9:
        mt = font_sm.render(f"+ {len(characters)-9} mas...", True, C_DIM)
        surf.blit(mt, (px + mx + 8, py + 30 + 9*18))

    # ── Columna derecha: controles ───────────────
    rx = SCREEN_W - 270

    speed_txt = "PAUSADO" if paused else f"x{sim_speed:.2f}"
    spd_col   = C_WARN if paused else C_ACCENT
    st = font_sm.render(f"Velocidad: {speed_txt}", True, spd_col)
    surf.blit(st, (px + rx, py + 8))

    controles = [
        ("ESPACIO",  "Pausar / Reanudar"),
        ("+  /  -",  "Velocidad"),
        ("N",        "Nuevo personaje"),
        ("T",        "Pedir pensamiento"),
        ("R",        "Regenerar mapa"),
        ("SUPR",     "Eliminar seleccionado"),
        ("ESC",      "Deseleccionar"),
    ]
    for i, (k, desc) in enumerate(controles):
        kt = font_sm.render(f"[{k}]", True, C_ACCENT)
        dt = font_sm.render(desc, True, C_DIM)
        surf.blit(kt, (px + rx, py + 28 + i*21))
        surf.blit(dt, (px + rx + 70, py + 28 + i*21))

    # Estado Ollama
    ok_col = C_ACCENT if ollama_ok else C_DANGER
    ok_txt = "CONECTADO" if ollama_ok else "DESCONECTADO"
    ok_t   = font_sm.render(f"[*] Ollama: {ok_txt}", True, ok_col)
    surf.blit(ok_t, (px + rx, py + ph - 22))

    # Líneas separadoras verticales
    pygame.draw.line(surf, (40, 50, 55), (px + mx - 12, py + 4), (px + mx - 12, py + ph - 4), 1)
    pygame.draw.line(surf, (40, 50, 55), (px + rx - 12, py + 4), (px + rx - 12, py + ph - 4), 1)


# ── Toast / notificaciones ───────────────────
class Toast:
    def __init__(self, text, duration=3.5):
        self.text     = text
        self.born     = time.time()
        self.duration = duration

    def alive(self):
        return time.time() - self.born < self.duration

    def alpha(self):
        age = time.time() - self.born
        if age < self.duration - 0.6:
            return 210
        return max(0, int(210 * (self.duration - age) / 0.6))


def draw_toasts(surf, font, toasts):
    y = WORLD_H - 12
    for t in reversed(toasts):
        if not t.alive():
            continue
        a  = t.alpha()
        tw = font.size(t.text)[0] + 22
        ts = pygame.Surface((tw, 28), pygame.SRCALPHA)
        pygame.draw.rect(ts, (18, 20, 38, a), ts.get_rect(), border_radius=6)
        pygame.draw.rect(ts, (80, 200, 120, a), ts.get_rect(), 1, border_radius=6)
        tt = font.render(t.text, True, (215, 228, 215))
        ts.blit(tt, (11, 6))
        y -= 32
        surf.blit(ts, (SCREEN_W // 2 - tw // 2, y))


# ── Modal de creación de personaje ──────────
class CreationModal:
    FIELDS = ["Nombre", "Personalidad", "Historia"]

    def __init__(self, fonts, traits):
        self.fonts     = fonts
        self.traits    = traits
        self.active    = False
        self.values    = ["", traits[0] if traits else "", ""]
        self.focused   = 0
        self.trait_idx = 0
        self.error     = ""

        self.rect = pygame.Rect(
            SCREEN_W//2 - 310, SCREEN_H//2 - 220,
            620, 440
        )

    def open(self):
        self.active    = True
        self.values    = ["", self.traits[0] if self.traits else "", ""]
        self.trait_idx = 0
        self.focused   = 0
        self.error     = ""

    def close(self):
        self.active = False

    def handle_event(self, event):
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
            elif self.focused == 1:
                # Selección de personalidad con flechas
                if event.key in (pygame.K_LEFT, pygame.K_UP):
                    self.trait_idx = (self.trait_idx - 1) % len(self.traits)
                    self.values[1] = self.traits[self.trait_idx]
                elif event.key in (pygame.K_RIGHT, pygame.K_DOWN):
                    self.trait_idx = (self.trait_idx + 1) % len(self.traits)
                    self.values[1] = self.traits[self.trait_idx]
            else:
                fi = self.focused
                if fi != 1:
                    if event.key == pygame.K_BACKSPACE:
                        self.values[fi] = self.values[fi][:-1]
                    elif event.unicode and len(self.values[fi]) < 100:
                        self.values[fi] += event.unicode

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            # Click en campos
            for i in range(len(self.FIELDS)):
                fr = self._field_rect(i)
                if fr.collidepoint(mx, my):
                    self.focused = i

            # Click en flechas de personalidad
            arr_l, arr_r = self._trait_arrows()
            if arr_l.collidepoint(mx, my):
                self.trait_idx = (self.trait_idx - 1) % len(self.traits)
                self.values[1] = self.traits[self.trait_idx]
            elif arr_r.collidepoint(mx, my):
                self.trait_idx = (self.trait_idx + 1) % len(self.traits)
                self.values[1] = self.traits[self.trait_idx]

            # Botón Crear
            ok_r = self._btn_ok_rect()
            cn_r = self._btn_cancel_rect()
            if ok_r.collidepoint(mx, my):
                return self._submit()
            if cn_r.collidepoint(mx, my):
                self.close()
                return ("cancel",)

        return None

    def _submit(self):
        name      = self.values[0].strip()
        trait     = self.values[1].strip()
        backstory = self.values[2].strip()
        if not name:
            self.error = "El nombre no puede estar vacio."
            return None
        if not trait:
            trait = self.traits[0]
        if not backstory:
            backstory = f"Un alma {trait} que deambula por este mundo."
        self.close()
        return ("create", name, trait, backstory)

    def _field_rect(self, i):
        # Campo 1 (personalidad) es más alto para el selector
        y_offsets = [115, 185, 285]
        h_sizes   = [36,  60,  36]
        return pygame.Rect(
            self.rect.x + 30,
            self.rect.y + y_offsets[i],
            self.rect.w - 60,
            h_sizes[i]
        )

    def _trait_arrows(self):
        fr = self._field_rect(1)
        btn_size = 32
        arr_l = pygame.Rect(fr.x, fr.y + (fr.h - btn_size)//2, btn_size, btn_size)
        arr_r = pygame.Rect(fr.right - btn_size, fr.y + (fr.h - btn_size)//2, btn_size, btn_size)
        return arr_l, arr_r

    def _btn_ok_rect(self):
        return pygame.Rect(self.rect.right - 150, self.rect.bottom - 55, 120, 38)

    def _btn_cancel_rect(self):
        return pygame.Rect(self.rect.right - 290, self.rect.bottom - 55, 120, 38)

    def draw(self, surf):
        if not self.active:
            return
        font_sm, font_md, font_lg = self.fonts

        # Overlay oscuro
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 170))
        surf.blit(ov, (0, 0))

        # Caja del modal
        pygame.draw.rect(surf, (20, 22, 36), self.rect, border_radius=14)
        pygame.draw.rect(surf, C_ACCENT, self.rect, 2, border_radius=14)

        # Título
        title = font_lg.render(">> Crear Personaje", True, C_ACCENT)
        surf.blit(title, (self.rect.x + 30, self.rect.y + 18))
        pygame.draw.line(surf, (40, 60, 50),
                         (self.rect.x + 20, self.rect.y + 52),
                         (self.rect.right - 20, self.rect.y + 52), 1)

        labels   = ["Nombre", "Personalidad", "Historia (opcional)"]
        fr_rects = [self._field_rect(i) for i in range(3)]

        for i, (label, fr) in enumerate(zip(labels, fr_rects)):
            lbl = font_sm.render(label, True, C_DIM)
            surf.blit(lbl, (fr.x, fr.y - 18))

            is_focused = (self.focused == i)
            col_border = C_ACCENT if is_focused else (50, 60, 80)
            pygame.draw.rect(surf, (24, 28, 46), fr, border_radius=7)
            pygame.draw.rect(surf, col_border, fr, 1, border_radius=7)

            if i == 1:
                # Selector de personalidad con flechas clickeables
                arr_l, arr_r = self._trait_arrows()

                # Flecha izquierda
                lc = C_ACCENT if is_focused else (80, 100, 80)
                pygame.draw.rect(surf, (28, 34, 52), arr_l, border_radius=5)
                pygame.draw.rect(surf, lc, arr_l, 1, border_radius=5)
                lt = font_md.render("<", True, lc)
                surf.blit(lt, lt.get_rect(center=arr_l.center))

                # Flecha derecha
                pygame.draw.rect(surf, (28, 34, 52), arr_r, border_radius=5)
                pygame.draw.rect(surf, lc, arr_r, 1, border_radius=5)
                rt = font_md.render(">", True, lc)
                surf.blit(rt, rt.get_rect(center=arr_r.center))

                # Nombre del trait centrado
                trait_name = self.values[1]
                tn = font_md.render(trait_name, True, C_TEXT)
                surf.blit(tn, tn.get_rect(center=fr.center))

                # Indicadores de posición
                total = len(self.traits)
                idx   = self.trait_idx
                dot_y = fr.bottom - 12
                dot_start = fr.centerx - (total * 10) // 2
                for d in range(total):
                    dc = C_ACCENT if d == idx else (50, 65, 60)
                    pygame.draw.circle(surf, dc, (dot_start + d*10, dot_y), 3)

                # Descripción del trait
                desc = TRAIT_DESC.get(trait_name, "")
                if desc:
                    dt = font_sm.render(desc, True, (100, 140, 100))
                    surf.blit(dt, (fr.x + 40, fr.y + fr.h - 18))

                # Instrucción si no está enfocado
                if not is_focused:
                    hint = font_sm.render("  Haz clic aqui o usa TAB  ", True, (60, 80, 70))
                    surf.blit(hint, (fr.centerx - hint.get_width()//2, fr.y + 5))

            else:
                cursor = "|" if is_focused and int(time.time() * 2) % 2 == 0 else ""
                val    = self.values[i]
                vt     = font_sm.render(val + cursor, True, C_TEXT)
                # Truncar si es muy largo
                max_w = fr.w - 16
                if vt.get_width() > max_w:
                    # mostrar solo el final del texto
                    chars = list(val)
                    while chars and font_sm.size("".join(chars) + cursor)[0] > max_w:
                        chars.pop(0)
                    vt = font_sm.render("".join(chars) + cursor, True, C_TEXT)
                surf.blit(vt, (fr.x + 8, fr.y + (fr.h - vt.get_height())//2))

        # Error
        if self.error:
            et = font_sm.render(self.error, True, C_DANGER)
            surf.blit(et, (self.rect.x + 30, self.rect.bottom - 70))

        # Botones
        ok_r = self._btn_ok_rect()
        cn_r = self._btn_cancel_rect()

        pygame.draw.rect(surf, C_ACCENT, ok_r, border_radius=8)
        pygame.draw.rect(surf, (45, 55, 75), cn_r, border_radius=8)
        pygame.draw.rect(surf, (80, 95, 115), cn_r, 1, border_radius=8)

        ok_t = font_sm.render("Crear  [ENTER]", True, (10, 15, 10))
        cn_t = font_sm.render("Cancelar  [ESC]", True, C_TEXT)
        surf.blit(ok_t, ok_t.get_rect(center=ok_r.center))
        surf.blit(cn_t, cn_t.get_rect(center=cn_r.center))

        # Ayuda de teclado
        help_t = font_sm.render("TAB = siguiente campo   |   flechas = cambiar personalidad", True, (55, 70, 65))
        surf.blit(help_t, (self.rect.x + 30, self.rect.bottom - 18))
