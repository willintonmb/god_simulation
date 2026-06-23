# ─────────────────────────────────────────────
#  WORLD SIMULATION  –  Configuración
# ─────────────────────────────────────────────

# Ventana
SCREEN_W, SCREEN_H = 1820, 980
WORLD_W,  WORLD_H  = 1820, 740
UI_H               = SCREEN_H - WORLD_H
FPS = 30

# Ollama
OLLAMA_URL     = "http://localhost:11434/api/generate"
OLLAMA_MODEL   = "gemma4:e4b"
OLLAMA_TIMEOUT = 80

# Cuadrícula
TILE = 32
COLS = WORLD_W // TILE
ROWS = WORLD_H // TILE

# Decaimiento de necesidades por segundo (escala 0-100)
HUNGER_DECAY  = 0.8
ENERGY_DECAY  = 0.6
HYGIENE_DECAY = 0.4
SOCIAL_DECAY  = 0.3

# Umbrales de necesidades
CRITICAL = 20
LOW      = 40

# Distancias
TALK_DIST = 90
EAT_DIST  = 48

# Velocidades (píxeles/seg)
SPEED_SLOW   = 55
SPEED_NORMAL = 90
SPEED_FAST   = 130

# Rasgos de personalidad en español
TRAITS = [
    "amigable",
    "timido",
    "curioso",
    "agresivo",
    "perezoso",
    "energetico",
    "melancolico",
    "optimista",
]

# Descripciones de rasgos para mostrar en UI
TRAIT_DESC = {
    "amigable":   "Busca interaccion social con frecuencia",
    "timido":     "Evita el contacto, prefiere la soledad",
    "curioso":    "Explora activamente el mundo",
    "agresivo":   "Directo, habla con mucha energia",
    "perezoso":   "Se mueve mas lento de lo normal",
    "energetico": "Se mueve 30% mas rapido",
    "melancolico":"Reflexivo, solitario a veces",
    "optimista":  "Siempre de buen humor",
}

# Paleta de colores
C_BG        = (12, 18, 28)
C_WORLD_BG  = (22, 40, 22)
C_PANEL     = (16, 18, 28)
C_ACCENT    = (80, 200, 120)
C_ACCENT2   = (60, 160, 220)
C_WARN      = (220, 160, 40)
C_DANGER    = (210, 60, 60)
C_TEXT      = (215, 228, 215)
C_DIM       = (100, 115, 100)
C_BUBBLE    = (240, 245, 255)
C_BUBBLE_T  = (20, 25, 45)
C_GRID      = (28, 50, 28)
C_WATER     = (40, 80, 140)
C_FOOD      = (160, 85, 30)
C_BED       = (70, 50, 110)
C_SHOWER    = (50, 110, 150)
C_TREE      = (25, 75, 25)
