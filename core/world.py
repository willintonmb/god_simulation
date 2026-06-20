# ─────────────────────────────────────────────
#  WORLD SIMULATION  –  Objetos del Mundo
# ─────────────────────────────────────────────
import random
import pygame
from core.config import *


class WorldObject:
    def __init__(self, x, y, kind):
        self.x, self.y = x, y
        self.kind      = kind        # "comida" | "cama" | "ducha" | "arbol"
        self.in_use_by = None
        self.rect = pygame.Rect(x - TILE//2, y - TILE//2, TILE, TILE)

    def is_free(self):
        return self.in_use_by is None

    def reserve(self, char_id):
        self.in_use_by = char_id

    def release(self):
        self.in_use_by = None

    def draw(self, surf, font_small):
        r = self.rect

        if self.kind == "comida":
            pygame.draw.rect(surf, C_FOOD, r, border_radius=5)
            pygame.draw.rect(surf, (240, 160, 70), r, 2, border_radius=5)
            # Icono dibujado con formas (sin emoji)
            # Plato: círculo
            cx, cy = r.centerx, r.centery
            pygame.draw.circle(surf, (240, 200, 100), (cx, cy), 9)
            pygame.draw.circle(surf, (200, 140, 50), (cx, cy), 9, 2)
            # Tenedor/cuchillo: dos líneas verticales
            pygame.draw.line(surf, (160, 90, 30), (cx-4, cy-7), (cx-4, cy+7), 2)
            pygame.draw.line(surf, (160, 90, 30), (cx+4, cy-7), (cx+4, cy+7), 2)
            label = font_small.render("COMIDA", True, (255, 220, 150))

        elif self.kind == "cama":
            pygame.draw.rect(surf, C_BED, r, border_radius=6)
            pygame.draw.rect(surf, (140, 100, 200), r, 2, border_radius=6)
            cx, cy = r.centerx, r.centery
            # Cama: rectángulo con almohada
            pygame.draw.rect(surf, (100, 80, 160), (r.x+4, r.y+8, r.w-8, r.h-12), border_radius=3)
            pygame.draw.rect(surf, (200, 180, 240), (r.x+4, r.y+8, 10, r.h-16), border_radius=2)
            label = font_small.render("CAMA", True, (200, 180, 255))

        elif self.kind == "ducha":
            pygame.draw.rect(surf, C_SHOWER, r, border_radius=5)
            pygame.draw.rect(surf, (100, 180, 220), r, 2, border_radius=5)
            cx, cy = r.centerx, r.centery
            # Ducha: cabezal + gotas
            pygame.draw.circle(surf, (180, 230, 255), (cx, cy-5), 6)
            pygame.draw.circle(surf, (60, 140, 180), (cx, cy-5), 6, 2)
            for gx, gy in [(-4,3),(0,5),(4,3),(-2,8),(2,8)]:
                pygame.draw.circle(surf, (180, 230, 255), (cx+gx, cy+gy), 2)
            label = font_small.render("DUCHA", True, (180, 230, 255))

        else:  # arbol
            cx, cy = r.centerx, r.centery
            # Tronco
            pygame.draw.rect(surf, (100, 60, 20), (cx-4, cy+2, 8, 12))
            # Copa
            pygame.draw.circle(surf, C_TREE, (cx, cy-2), 12)
            pygame.draw.circle(surf, (20, 100, 20), (cx, cy-2), 12, 2)
            label = font_small.render("ARBOL", True, (100, 200, 100))

        # Etiqueta
        surf.blit(label, (r.centerx - label.get_width()//2, r.bottom + 1))

        # Indicador de uso
        if self.in_use_by is not None:
            pygame.draw.circle(surf, (255, 60, 60), (r.right - 5, r.top + 5), 4)


def generate_world(num_food=7, num_beds=5, num_showers=4, num_trees=9):
    """Genera objetos del mundo distribuidos aleatoriamente."""
    objects = []
    margin  = TILE * 2

    def place(kind, count):
        placed, attempts = 0, 0
        while placed < count and attempts < 600:
            attempts += 1
            x = random.randint(margin, WORLD_W - margin)
            y = random.randint(margin, WORLD_H - margin)
            ok = all(abs(x - o.x) + abs(y - o.y) > TILE * 2.2 for o in objects)
            if ok:
                objects.append(WorldObject(x, y, kind))
                placed += 1

    place("comida",  num_food)
    place("cama",    num_beds)
    place("ducha",   num_showers)
    place("arbol",   num_trees)
    return objects
