# ─────────────────────────────────────────────
#  WORLD SIMULATION  –  Generador aleatorio de personajes
#  Usa Ollama para generar la historia de cada uno.
# ─────────────────────────────────────────────
import random
import threading
import time
import requests
from core.config import TRAITS, OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT
from core.ollama_client import _clean_response

# Banco de nombres variados
NOMBRES = [
    "Aria","Berto","Celia","Diego","Elena","Fausto","Gloria","Hector",
    "Iris","Jano","Kira","Leon","Mila","Nora","Omar","Pilar","Quino",
    "Rosa","Santi","Talia","Ulises","Vera","Waldo","Xena","Yael","Zara",
    "Alba","Bruno","Carmen","Dante","Ema","Felix","Gael","Hana","Ivan",
    "Julia","Kai","Lena","Marco","Nina","Oto","Paz","Remi","Sara","Teo",
    "Ula","Vito","Wren","Xabi","Yuna","Zeno",
]

# Historias de respaldo (si Ollama no está disponible)
_FALLBACK_HISTORIAS = [
    "Un viajero que ha recorrido tierras lejanas buscando su lugar en el mundo.",
    "Una artista que plasma sus emociones en coloridos murales callejeros.",
    "Un ex-soldado que busca redención tras años de conflictos.",
    "Una botanica obsesionada con plantas extintas que intenta revivir.",
    "Un cocinero que convierte ingredientes simples en platos extraordinarios.",
    "Una escritora de cartas anónimas que cambian la vida de los destinatarios.",
    "Un astronomo aficionado que busca patrones en las estrellas que nadie más ve.",
    "Una médica rural que sacrificó la ciudad por ayudar a comunidades pequeñas.",
    "Un inventor excéntrico cuyas creaciones siempre funcionan... a su manera.",
    "Una maestra que colecciona historias de sus alumnos en un diario secreto.",
    "Un músico callejero que solo toca las canciones que la gente necesita escuchar.",
    "Una detective retirada que aún resuelve misterios por pura curiosidad.",
    "Un jardinero que habla con sus plantas y asegura que ellas responden.",
    "Una arquitecta que diseña casas adaptadas a las emociones de sus dueños.",
    "Un chef que perdió el olfato y desarrolló un sexto sentido para el sabor.",
]


def _generate_backstory_sync(name: str, trait: str, timeout: int = 15) -> str:
    """
    Genera una historia breve para el personaje usando Ollama (síncrono).
    Retorna historia de respaldo si falla o tarda demasiado.
    """
    prompt = (
        f"Crea una historia de origen breve (maximo 25 palabras, una sola frase) "
        f"para un personaje llamado {name} con personalidad {trait}. "
        f"Responde SOLO con la historia, sin introduccion, sin comillas, en español. "
        f"Usa primera o tercera persona. Sin asteriscos ni saltos de linea."
    )
    try:
        payload = {
            "model":   OLLAMA_MODEL,
            "prompt":  prompt,
            "stream":  False,
            "options": {"temperature": 1.0, "num_predict": 80},
        }
        r = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
        r.raise_for_status()
        raw  = r.json().get("response", "").strip()
        text = _clean_response(raw, max_chars=200)
        return text if len(text) > 10 else random.choice(_FALLBACK_HISTORIAS)
    except Exception:
        return random.choice(_FALLBACK_HISTORIAS)


class CharacterFactory:
    """
    Genera un conjunto aleatorio de personajes (6-50) con historias
    generadas por Ollama en paralelo.
    """

    def __init__(self, ollama_ok: bool = True):
        self.ollama_ok = ollama_ok

    def generate_batch(self,
                       count: int | None = None,
                       on_progress=None) -> list[dict]:
        """
        Genera `count` personajes (aleatorio entre 6-50 si no se especifica).
        `on_progress(done, total)` se llama tras cada historia generada.
        Retorna lista de dicts con keys: name, trait, backstory.
        """
        if count is None:
            count = random.randint(6, 50)

        # Asegurar nombres únicos
        pool = NOMBRES.copy()
        random.shuffle(pool)
        names = pool[:count] if count <= len(pool) else \
                pool + [f"Alma{i}" for i in range(1, count - len(pool) + 1)]

        traits = [random.choice(TRAITS) for _ in range(count)]

        results   = [None] * count
        done_lock = threading.Lock()
        done_cnt  = [0]

        def _gen(i, name, trait):
            if self.ollama_ok:
                story = _generate_backstory_sync(name, trait)
            else:
                story = random.choice(_FALLBACK_HISTORIAS)
            results[i] = {"name": name, "trait": trait, "backstory": story}
            with done_lock:
                done_cnt[0] += 1
                if on_progress:
                    on_progress(done_cnt[0], count)

        # Hasta 6 hilos en paralelo para no saturar Ollama
        MAX_THREADS = 4
        sem = threading.Semaphore(MAX_THREADS)

        def _worker(i, name, trait):
            with sem:
                _gen(i, name, trait)

        threads = []
        for i in range(count):
            t = threading.Thread(target=_worker, args=(i, names[i], traits[i]), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=60)

        # Rellenar huecos (si algún hilo falló)
        for i, r in enumerate(results):
            if r is None:
                results[i] = {
                    "name":      names[i],
                    "trait":     traits[i],
                    "backstory": random.choice(_FALLBACK_HISTORIAS),
                }

        return results
