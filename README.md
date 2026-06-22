# WORLD Simulation — Simulador Multi-Agente
### Pygame + Ollama  |  Español

## Instalación rápida

```bash
pip install pygame requests
ollama pull llama3.2        # o: mistral, phi3, gemma
ollama serve                # iniciar Ollama (si no está corriendo)
python main.py
```
<img width="1821" height="1011" alt="image" src="https://github.com/user-attachments/assets/2b0bccea-f42b-4e9e-8907-981f84b774ad" />

## Controles

| Tecla         | Acción                              |
|---------------|-------------------------------------|
| N             | Crear nuevo personaje               |
| ESPACIO       | Pausar / Reanudar                   |
| + / -         | Aumentar / reducir velocidad        |
| T             | Pedir pensamiento (requiere Ollama) |
| R             | Regenerar mapa del mundo            |
| SUPR / DELETE | Eliminar personaje seleccionado     |
| ESC           | Deseleccionar personaje             |
| Click         | Seleccionar personaje               |

## Objetos del mundo

| Objeto | Satisface |
|--------|-----------|
| COMIDA | Hambre    |
| CAMA   | Energía   |
| DUCHA  | Higiene   |
| ARBOL  | Decorativo|

## Personalidades

| Rasgo       | Efecto                             |
|-------------|-------------------------------------|
| amigable    | Busca interacción social activamente|
| timido      | Evita el contacto (25% de chance)  |
| curioso     | Explora más el mundo               |
| agresivo    | Habla con mucha energía            |
| perezoso    | 35% más lento                      |
| energetico  | 30% más rápido                     |
| melancolico | Reflexivo, solitario               |
| optimista   | Siempre de buen humor              |

## Estructura del proyecto

```
WORLD_simulation/
├── main.py              ← Bucle principal
├── core/
│   ├── config.py        ← Constantes y paleta
│   ├── world.py         ← Objetos del mundo
│   ├── character.py     ← Agente IA + FSM + necesidades
│   └── ollama_client.py ← Cliente async Ollama
└── ui/
    └── panels.py        ← Panel UI, modal, notificaciones
```

## Cambiar modelo de Ollama

Edita `core/config.py`:
```python
OLLAMA_MODEL = "llama3.2"   # cambiar a: mistral, phi3, gemma, etc.
```
