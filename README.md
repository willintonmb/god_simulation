# ✦ God Simulation
### Un simulador multi-agente con IA — Pygame + Ollama

---

## Descripción

Un "God Game" 2D donde creates personajes con personalidad propia que:

- **Satisfacen necesidades automáticamente**: hambre, energía, higiene y socialización.
- **Interactúan entre ellos** con diálogos generados en tiempo real por Ollama.
- **Tienen personalidad**: el rasgo (`trait`) afecta velocidad, socialización y decisiones.
- **Razonan sobre su estado**: pídeles un pensamiento con la tecla `T`.

---

## Instalación

```bash
# 1. Dependencias Python
pip install pygame requests

# 2. Instalar Ollama  (https://ollama.com)
#    En Windows/Mac: descargar el instalador
#    En Linux:
curl -fsSL https://ollama.com/install.sh | sh

# 3. Bajar un modelo (elige uno)
ollama pull llama3.2        # recomendado (~2 GB)
ollama pull mistral         # alternativa
ollama pull phi3            # ligero

# 4. Iniciar Ollama (si no está corriendo)
ollama serve

# 5. Ejecutar el juego
cd god_simulation
python main.py
```

---

## Controles

| Tecla      | Acción                              |
|------------|-------------------------------------|
| `N`        | Crear nuevo personaje (modal)       |
| `SPACE`    | Pausar / Reanudar simulación        |
| `+` / `-`  | Aumentar / reducir velocidad (x0.25 a x5) |
| `T`        | Pedir pensamiento al personaje seleccionado |
| `R`        | Regenerar el mapa del mundo         |
| `DELETE`   | Eliminar personaje seleccionado     |
| `ESC`      | Deseleccionar personaje             |
| Click      | Seleccionar personaje               |

---

## Objetos del Mundo

| Icono | Objeto  | Satisface  |
|-------|---------|------------|
| 🍖    | Comida  | Hambre     |
| 🛏    | Cama    | Energía    |
| 🚿    | Ducha   | Higiene    |
| 🌲    | Árbol   | Decorativo |

---

## Personalidades (Traits)

| Trait       | Efecto                                          |
|-------------|------------------------------------------------|
| `friendly`  | Busca interacciones sociales con frecuencia    |
| `shy`       | Evita el chat (25% de probabilidad)            |
| `curious`   | Explora más el mundo                            |
| `aggressive`| Responde con energía en los diálogos           |
| `lazy`      | Se mueve 35% más lento                         |
| `energetic` | Se mueve 30% más rápido                        |

---

## Arquitectura

```
god_simulation/
├── main.py                  # Game loop principal
├── core/
│   ├── config.py            # Constantes y paleta
│   ├── world.py             # Objetos del mundo
│   ├── character.py         # Agente + FSM + necesidades
│   └── ollama_client.py     # Cliente async para Ollama
└── ui/
    └── panels.py            # Panel inferior, modal, toasts
```

### Sistema de Necesidades

Cada necesidad decae por segundo:

```
Hambre:   -0.8 / seg   →  busca 🍖 comida
Energía:  -0.6 / seg   →  busca 🛏 cama
Higiene:  -0.4 / seg   →  busca 🚿 ducha
Social:   -0.3 / seg   →  busca otro personaje para chatear
```

### FSM (Finite State Machine)

```
IDLE → WANDER
     → SEEK_FOOD → EAT → IDLE
     → SEEK_BED  → SLEEP → IDLE
     → SEEK_SHOWER → SHOWER → IDLE
     → SEEK_CHAT → CHAT → IDLE
```

---

## Configuración

Edita `core/config.py` para ajustar:

- `OLLAMA_MODEL` — modelo a usar ("llama3.2", "mistral", etc.)
- `OLLAMA_URL`   — URL de Ollama si no es localhost
- `HUNGER_DECAY`, `ENERGY_DECAY`, etc. — velocidad de degradación de necesidades
- `SCREEN_W/H`  — tamaño de ventana

---

## Requisitos

- Python 3.10+
- pygame 2.x
- requests
- Ollama corriendo localmente (opcional pero recomendado para diálogos)
