# ─────────────────────────────────────────────
#  GOD SIMULATION  –  Ollama Client
# ─────────────────────────────────────────────
import threading
import requests
import json
from core.config import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT


def ask_ollama_async(prompt: str, callback, system: str = ""):
    """
    Fire-and-forget call to Ollama.
    `callback(text: str)` is called from the worker thread when done.
    """
    def _worker():
        try:
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.85, "num_predict": 80},
            }
            if system:
                payload["system"] = system
            r = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            text = data.get("response", "").strip()
            print(text)
            # Truncate to first sentence or 120 chars
            for sep in [".", "!", "?", "\n"]:
                idx = text.find(sep)
                if 0 < idx < 120:
                    text = text[: idx + 1]
                    break
            text = text[:130]
            callback(text)
        except Exception as e:
            callback(f"[{e}]")

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def check_ollama() -> bool:
    """Return True if Ollama is reachable."""
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def list_models() -> list[str]:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        data = r.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []
