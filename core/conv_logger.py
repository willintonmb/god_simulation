# ─────────────────────────────────────────────
#  WORLD SIMULATION  –  Logger de conversaciones
# ─────────────────────────────────────────────
import os
import threading
from datetime import datetime

LOG_DIR  = "conversaciones"
_lock    = threading.Lock()


def _ensure_dir():
    os.makedirs(LOG_DIR, exist_ok=True)


def log_conversation(char_a_name: str, char_b_name: str,
                     trait_a: str, trait_b: str,
                     history: list[tuple[str, str]]):
    """
    Guarda la conversación completa en un archivo TXT.
    history: [(nombre, texto), ...]
    """
    if not history:
        return

    _ensure_dir()
    ts        = datetime.now()
    ts_str    = ts.strftime("%Y-%m-%d %H:%M:%S")
    filename  = ts.strftime("%Y%m%d_%H%M%S") + f"_{char_a_name}_y_{char_b_name}.txt"
    filepath  = os.path.join(LOG_DIR, filename)

    sep_doble = "=" * 60
    sep_turno = "-" * 40

    lines = [
        sep_doble,
        f"  CONVERSACION",
        f"  {char_a_name} ({trait_a})  <-->  {char_b_name} ({trait_b})",
        f"  Fecha y hora: {ts_str}",
        f"  Turnos registrados: {len(history)}",
        sep_doble,
        "",
    ]

    for i, (nombre, texto) in enumerate(history, 1):
        lines.append(f"[Turno {i}]  {nombre}:")
        lines.append(f"  \"{texto}\"")
        lines.append(sep_turno)

    lines += ["", f"  Fin de la conversacion entre {char_a_name} y {char_b_name}.", sep_doble, ""]

    with _lock:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    # También append al log global de sesión
    global_log = os.path.join(LOG_DIR, "sesion_completa.txt")
    with _lock:
        with open(global_log, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))

    return filepath
