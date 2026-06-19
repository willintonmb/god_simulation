# ─────────────────────────────────────────────
#  GOD SIMULATION  –  World Objects
# ─────────────────────────────────────────────
import random
import pygame
from core.config import *


class WorldObject:
    def __init__(self, x, y, kind):
        self.x, self.y = x, y
        self.kind  = kind        # "food" | "bed" | "shower" | "tree"
        self.in_use_by = None    # character id using it
        self.rect  = pygame.Rect(x - TILE//2, y - TILE//2, TILE, TILE)

    def is_free(self):
        return self.in_use_by is None

    def reserve(self, char_id):
        self.in_use_by = char_id

    def release(self):
        self.in_use_by = None

    def draw(self, surf, font_small):
        r = self.rect
        if self.kind == "food":
            pygame.draw.rect(surf, C_FOOD, r, border_radius=4)
            pygame.draw.rect(surf, (220, 140, 60), r, 2, border_radius=4)
            t = font_small.render("🍖", True, (255,255,255))
        elif self.kind == "bed":
            pygame.draw.rect(surf, C_BED, r, border_radius=6)
            pygame.draw.rect(surf, (120, 90, 180), r, 2, border_radius=6)
            t = font_small.render("🛏", True, (255,255,255))
        elif self.kind == "shower":
            pygame.draw.rect(surf, C_SHOWER, r, border_radius=5)
            pygame.draw.rect(surf, (90, 160, 200), r, 2, border_radius=5)
            t = font_small.render("🚿", True, (255,255,255))
        else:  # tree
            pygame.draw.circle(surf, C_TREE, r.center, TILE//2 - 2)
            pygame.draw.circle(surf, (20, 60, 20), r.center, TILE//2 - 2, 2)
            t = font_small.render("🌲", True, (255,255,255))

        surf.blit(t, (r.centerx - t.get_width()//2,
                      r.centery - t.get_height()//2))

        if self.in_use_by is not None:
            dot = pygame.Surface((8, 8), pygame.SRCALPHA)
            pygame.draw.circle(dot, (255, 80, 80, 200), (4, 4), 4)
            surf.blit(dot, (r.right - 10, r.top + 2))


def generate_world(num_food=6, num_beds=4, num_showers=3, num_trees=8):
    """Return a list of WorldObjects spread across the world."""
    objects = []
    margin = TILE * 2

    def place(kind, count):
        placed = 0
        attempts = 0
        while placed < count and attempts < 500:
            attempts += 1
            x = random.randint(margin, WORLD_W - margin)
            y = random.randint(margin, WORLD_H - margin)
            # avoid overlap
            ok = all(abs(x - o.x) + abs(y - o.y) > TILE * 2 for o in objects)
            if ok:
                objects.append(WorldObject(x, y, kind))
                placed += 1

    place("food",   num_food)
    place("bed",    num_beds)
    place("shower", num_showers)
    place("tree",   num_trees)
    return objects
