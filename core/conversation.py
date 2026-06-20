# ─────────────────────────────────────────────
#  WORLD SIMULATION  –  Motor de Conversación
#
#  Maneja diálogos multi-turno entre dos personajes.
#  Cada turno:
#    1. Decide cuántos intercambios tendrá la conversación (2-5)
#    2. Llama a Ollama con el historial completo
#    3. Espera a que se muestre la burbuja antes del siguiente turno
#    4. Alterna entre los dos personajes
# ─────────────────────────────────────────────
import threading
import time
import random
from core.ollama_client import ask_ollama_async, _clean_response
from core.config import OLLAMA_MODEL, OLLAMA_URL, OLLAMA_TIMEOUT


# Número de intercambios según rasgos de personalidad
def _num_turns(trait_a: str, trait_b: str) -> int:
    """Cuántos turnos totales tendrá la conversación (mínimo 2, máximo 10)."""
    social_traits = {"amigable", "curioso", "optimista", "energetico"}
    quiet_traits  = {"timido", "melancolico", "perezoso"}

    score = 2  # base: 1 turno por cada personaje
    if trait_a in social_traits:
        score += random.randint(1, 3)
    if trait_b in social_traits:
        score += random.randint(1, 3)
    if trait_a in quiet_traits:
        score -= random.randint(0, 1)
    if trait_b in quiet_traits:
        score -= random.randint(0, 1)
    if trait_a == "agresivo" or trait_b == "agresivo":
        score += random.randint(0, 2)   # discusiones largas

    return max(2, min(10, score))


# Tiempo de lectura estimado: ~110 palabras/minuto → mínimo 3s
def _reading_time(text: str, extra: float = 1.5) -> float:
    words = len(text.split())
    return max(3.0, words / 110 * 60 + extra)


class Conversation:
    """
    Orquesta una conversación entre char_a (inicia) y char_b (responde).
    Se ejecuta completamente en un hilo de fondo para no bloquear el juego.
    """

    def __init__(self, char_a, char_b):
        self.char_a    = char_a
        self.char_b    = char_b
        self.active    = True
        self.history   = []           # lista de (nombre, texto)
        self.num_turns = _num_turns(char_a.trait, char_b.trait)
        self._thread   = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def _run(self):
        """Bucle principal de la conversación (hilo de fondo)."""
        # Contexto compartido del sistema
        system = (
            "Eres un personaje en una simulacion de vida. "
            "Responde SIEMPRE en español. "
            "Tus respuestas son conversacionales, naturales y breves (max 30 palabras). "
            "NO uses asteriscos, NO uses markdown, NO saltes de linea. "
            "Habla en primera persona. "
            "Mantén coherencia con el historial de la conversacion."
        )

        for turn in range(self.num_turns):
            if not self.active:
                break

            # Alternar quién habla
            speaker  = self.char_a if turn % 2 == 0 else self.char_b
            listener = self.char_b if turn % 2 == 0 else self.char_a

            # Construir historial legible
            history_txt = ""
            for name, msg in self.history[-6:]:   # máx 6 turnos de contexto
                history_txt += f"{name}: {msg}\n"

            if turn == 0:
                # Primer turno: saludo o inicio espontáneo
                prompt = (
                    f"Eres {speaker.name}, una persona {speaker.trait}. "
                    f"Historia: {speaker.backstory}. "
                    f"Te encuentras con {listener.name} ({listener.trait}). "
                    f"Inicia la conversacion con un saludo o comentario natural. "
                    f"Maximo 25 palabras, sin saludos formales exagerados."
                )
            else:
                # Turnos siguientes: respuesta al último mensaje
                last_name, last_msg = self.history[-1]
                prompt = (
                    f"Eres {speaker.name}, una persona {speaker.trait}. "
                    f"Historia: {speaker.backstory}. "
                    f"Estas hablando con {listener.name} ({listener.trait}). "
                    f"Historial reciente:\n{history_txt}"
                    f"{last_name} acaba de decir: \"{last_msg}\". "
                    f"Responde de forma natural y coherente. Maximo 30 palabras."
                )

            # Llamar a Ollama (bloqueante dentro del hilo)
            result = {"text": None}
            done   = threading.Event()

            def _cb(txt, r=result, e=done):
                r["text"] = txt
                e.set()

            ask_ollama_async(prompt, _cb, system=system,
                             max_chars=200, num_predict=150)

            # Esperar respuesta (máx 25 segundos)
            done.wait(timeout=25)
            text = result["text"] or "..."

            if not self.active:
                break

            # Registrar en historial
            self.history.append((speaker.name, text))

            # Mostrar burbuja al hablante
            from core.character import SpeechBubble
            speaker.bubble = SpeechBubble(text)

            # Esperar tiempo de lectura antes del siguiente turno
            read_t = _reading_time(text, extra=random.uniform(1.0, 2.5))
            time.sleep(read_t)

            if not self.active:
                break

        # Fin de conversación
        self.active = False
        # Notificar a ambos para que salgan del estado CHAT
        self.char_a._conv_finished = True
        self.char_b._conv_finished = True

    def stop(self):
        self.active = False
