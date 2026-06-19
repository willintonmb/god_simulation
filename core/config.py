# ─────────────────────────────────────────────
#  GOD SIMULATION  –  Config & Constants
# ─────────────────────────────────────────────

# Window
SCREEN_W, SCREEN_H = 1820, 980
WORLD_W, WORLD_H   = 1820, 740          # top area for the world
UI_H               = SCREEN_H - WORLD_H  # bottom panel height
FPS = 30

# Ollama
OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen3.5:0.8b"   # change to any model you have pulled
OLLAMA_TIMEOUT = 30

# World grid
TILE = 32
COLS = WORLD_W // TILE
ROWS = WORLD_H // TILE

# Needs decay per second (0‒100 scale)
HUNGER_DECAY  = 0.8
ENERGY_DECAY  = 0.6
HYGIENE_DECAY = 0.4
SOCIAL_DECAY  = 0.3

# Need thresholds
CRITICAL = 20   # below → urgent action
LOW      = 40   # below → seek action

# Interaction distance (pixels)
TALK_DIST = 90
EAT_DIST  = 48

# Character speeds (pixels/sec)
SPEED_SLOW   = 55
SPEED_NORMAL = 90
SPEED_FAST   = 130

# Personality traits (affects behaviour weights)
TRAITS = ["friendly", "shy", "curious", "aggressive", "lazy", "energetic"]

# Palette
C_BG       = (15, 20, 30)
C_WORLD_BG = (28, 45, 28)
C_PANEL    = (18, 18, 28)
C_ACCENT   = (90, 200, 130)
C_WARN     = (220, 160, 40)
C_DANGER   = (210, 60, 60)
C_TEXT     = (220, 230, 220)
C_DIM      = (110, 120, 110)
C_BUBBLE   = (240, 240, 255)
C_BUBBLE_T = (20, 20, 40)
C_GRID     = (35, 55, 35)
C_WATER    = (40, 80, 140)
C_FOOD     = (180, 100, 40)
C_BED      = (80, 60, 120)
C_SHOWER   = (60, 120, 160)
C_TREE     = (30, 80, 30)
