# ─────────────────────────────────────────────
#  WORLD SIMULATION  –  Cliente Ollama
# ─────────────────────────────────────────────
import threading
import requests
from core.config import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT


def _clean_response(text: str, max_chars: int = 180) -> str:
    """
    Limpia la respuesta de Ollama:
    - Elimina saltos de línea (los reemplaza por espacio)
    - Elimina asteriscos de énfasis (*texto*)
    - Elimina comillas envolventes innecesarias
    - Trunca en un punto de corte natural sin romper palabras
    """
    if not text:
        return ""

    # 1) Normalizar saltos de línea → espacio
    text = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")

    # 2) Quitar asteriscos de markdown (*negrita* / _cursiva_)
    import re
    text = re.sub(r"[*_]{1,2}([^*_]+)[*_]{1,2}", r"\1", text)

    # 3) Quitar comillas envolventes si el modelo las añade
    text = text.strip('"').strip("'").strip()

    # 4) Colapsar espacios múltiples
    text = re.sub(r" {2,}", " ", text).strip()

    if len(text) <= max_chars:
        return text

    # 5) Truncar en el último punto/signo de puntuación antes del límite
    cut = text[:max_chars]
    for sep in (".", "!", "?", ";", ","):
        idx = cut.rfind(sep)
        if idx > max_chars // 2:           # al menos la mitad del texto
            return cut[: idx + 1].strip()

    # Si no hay puntuación, cortar en la última palabra completa
    idx = cut.rfind(" ")
    return (cut[:idx] if idx > 0 else cut).strip()


def ask_ollama_async(prompt: str, callback,
                     system: str = "",
                     max_chars: int = 180,
                     num_predict: int = 120):
    """
    Llamada asíncrona a Ollama.
    `callback(text: str)` se llama desde el hilo worker cuando termina.
    """
    def _worker():
        try:
            payload = {
                "model":   OLLAMA_MODEL,
                "prompt":  prompt,
                "stream":  False,
                "think": False,
                "options": {
                    "temperature": 0.9,
                    "num_predict": num_predict,
                    "stop": [],          # sin stop tokens; dejamos que el modelo fluya
                },
            }
            if system:
                payload["system"] = system

            r = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            raw  = data.get("response", "").strip()
            text = _clean_response(raw, max_chars=max_chars)
            callback(text if text else "...")
        except Exception as e:
            callback(f"[Error: {e}]")

    threading.Thread(target=_worker, daemon=True).start()


def check_ollama() -> bool:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def list_models() -> list[str]:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []
