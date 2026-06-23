# ═══════════════════════════════════════════════════════════════
#  WORLD SIMULATION  –  Research Data Logger
#
#  Captura datos multi-nivel para análisis con ML/NN:
#
#  NIVEL 0 – Sesión
#    data/sessions.json           metadata de cada ejecución
#
#  NIVEL 1 – Agente
#    data/agents.csv              registro maestro de agentes
#    data/needs_timeseries.csv    snapshot de necesidades c/N seg
#    data/state_events.csv        cada transición de estado FSM
#
#  NIVEL 2 – Conversación
#    data/conversations.csv       métricas por conversación
#    data/social_edges.csv        grafo de interacciones acumulado
#
#  NIVEL 3 – Turno de diálogo
#    data/utterances.csv          cada turno con features extraídas
#    data/utterances.jsonl        idem en JSON con texto completo
# ═══════════════════════════════════════════════════════════════

import os, csv, json, math, re, time, threading, uuid
from datetime import datetime
from collections import defaultdict

DATA_DIR = "data"

# ── Léxico de sentimiento en español ────────────
_LEX_POS = {
    "bien","alegr","feliz","genial","maravill","contento","contenta","amor",
    "gusto","gracias","perfecto","perfeccto","excelente","fantástico","fantastico",
    "encanta","felicidad","dichoso","dichosa","bonito","bonita","precioso","linda",
    "lindo","hermoso","hermosa","tranquil","paz","calma","fresco","fresca",
    "animad","divertid","emocionad","esperanza","orgull","satisfech","ilusión",
    "ilusion","bienvenid","sorprendido","increíble","increible","energético"
}
_LEX_NEG = {
    "mal","triste","enojad","solo","sola","cansad","hambre","sucio","sucia",
    "molest","aburrido","aburrida","miedo","dolor","ansios","preocupad",
    "horrible","terrible","fatal","pésimo","pesimo","odio","detesto","asco",
    "furioso","furiosa","deprimid","desesperado","desesperada","soledad",
    "confundid","perdid","agotado","agotada","frustrad","desanimad","oscuro"
}
_LEX_AGR = {
    "nunca","jamás","jamas","siempre","imposible","idiot","estúpid","estupid",
    "basta","cállate","callate","lárgate","largate","pelea","discutir","mentir",
    "mentira","trampa","traición","traicion","insulto","grito","gritar"
}
_LEX_CUR = {
    "por qué","porque","cómo","como","qué","que","cuándo","cuando","dónde",
    "donde","quién","quien","cuál","cual","explica","cuéntame","cuéntame",
    "hablame","háblame","interesante","curioso","curiosa","descubrir","saber",
    "aprender","investigar","pregunta","pregunto"
}

def _sentiment_score(text: str) -> dict:
    """
    Análisis léxico de sentimiento en español.
    Retorna dict con scores normalizados [-1, 1] y conteos.
    """
    t = text.lower()
    words = re.findall(r'\w+', t)
    n = max(len(words), 1)

    pos = sum(1 for w in words if any(w.startswith(p) for p in _LEX_POS))
    neg = sum(1 for w in words if any(w.startswith(p) for p in _LEX_NEG))
    agr = sum(1 for w in words if any(w.startswith(p) for p in _LEX_AGR))
    cur = sum(1 for w in words if any(p in t for p in _LEX_CUR))

    # Preguntas y exclamaciones
    questions    = text.count("?") + text.count("¿")
    exclamations = text.count("!") + text.count("¡")

    polarity   = (pos - neg) / n          # [-1, 1] aprox
    aggression = agr / n
    curiosity  = (cur + questions * 0.5) / n

    return {
        "polarity":        round(polarity,   4),
        "aggression":      round(aggression, 4),
        "curiosity":       round(curiosity,  4),
        "positive_words":  pos,
        "negative_words":  neg,
        "aggressive_words":agr,
        "curious_words":   cur,
        "word_count":      len(words),
        "char_count":      len(text),
        "questions":       questions,
        "exclamations":    exclamations,
    }

def _text_features(text: str) -> dict:
    """Features lingüísticas adicionales."""
    words   = re.findall(r'\w+', text.lower())
    sents   = re.split(r'[.!?]+', text)
    sents   = [s.strip() for s in sents if s.strip()]
    avg_wl  = sum(len(w) for w in words) / max(len(words), 1)
    return {
        "avg_word_length": round(avg_wl, 2),
        "sentence_count":  len(sents),
        "unique_words":    len(set(words)),
        "lexical_richness": round(len(set(words)) / max(len(words), 1), 4),
    }


# ── ResearchLogger ───────────────────────────
class ResearchLogger:
    """
    Singleton-like logger. Instanciar una vez en main() y pasar a los módulos.
    Thread-safe mediante locks por archivo.
    """

    # Intervalo de snapshot de necesidades (segundos de simulación)
    NEEDS_INTERVAL = 5.0

    def __init__(self, session_label: str = ""):
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
        self.label      = session_label or self.session_id
        self.start_ts   = time.time()

        os.makedirs(DATA_DIR, exist_ok=True)
        self._locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
        self._headers_written: set = set()

        # Contadores en memoria
        self._conv_counter    = 0
        self._edge_counts:    dict[tuple, int] = defaultdict(int)   # (a,b)->n
        self._edge_last:      dict[tuple, float] = {}               # (a,b)->last_ts
        self._needs_timer:    dict[int, float] = {}                  # char_id->next_snap
        self._agent_written:  set = set()                            # ids ya en agents.csv

        # Acumular para session summary
        self._total_utterances = 0
        self._total_convs      = 0

        self._log_session_start()

    # ── paths ─────────────────────────────────
    def _p(self, name): return os.path.join(DATA_DIR, name)

    # ── CSV writer helper ─────────────────────
    def _write_csv(self, filename: str, row: dict, fieldnames: list[str]):
        path = self._p(filename)
        with self._locks[filename]:
            new_file = filename not in self._headers_written
            with open(path, "a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                if new_file and not os.path.exists(path) or os.path.getsize(path) == 0:
                    w.writeheader()
                elif new_file:
                    # file exists from prior session – no header needed
                    pass
                else:
                    if filename not in self._headers_written:
                        if os.path.getsize(path) == 0:
                            w.writeheader()
                w.writerow(row)
            self._headers_written.add(filename)

    def _write_csv_safe(self, filename: str, row: dict, fieldnames: list[str]):
        """Write CSV ensuring header is written exactly once per file (across sessions)."""
        path = self._p(filename)
        with self._locks[filename]:
            file_exists = os.path.isfile(path) and os.path.getsize(path) > 0
            with open(path, "a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                if not file_exists and filename not in self._headers_written:
                    w.writeheader()
                    self._headers_written.add(filename)
                elif filename not in self._headers_written:
                    self._headers_written.add(filename)
                w.writerow(row)

    def _append_jsonl(self, filename: str, obj: dict):
        path = self._p(filename)
        with self._locks[filename]:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    # ══════════════════════════════════════════
    #  NIVEL 0 – Sesión
    # ══════════════════════════════════════════
    def _log_session_start(self):
        path = self._p("sessions.json")
        sessions = []
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as f:
                    sessions = json.load(f)
            except Exception:
                sessions = []
        sessions.append({
            "session_id":   self.session_id,
            "label":        self.label,
            "start_time":   datetime.now().isoformat(),
            "end_time":     None,
            "duration_sec": None,
            "agent_count":  None,
            "total_convs":  None,
            "total_turns":  None,
            "status":       "running",
        })
        with self._locks["sessions.json"]:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(sessions, f, ensure_ascii=False, indent=2)

    def log_session_end(self, agent_count: int):
        """Llamar al cerrar la simulación."""
        path = self._p("sessions.json")
        duration = time.time() - self.start_ts
        try:
            with open(path, encoding="utf-8") as f:
                sessions = json.load(f)
            for s in sessions:
                if s["session_id"] == self.session_id:
                    s["end_time"]     = datetime.now().isoformat()
                    s["duration_sec"] = round(duration, 1)
                    s["agent_count"]  = agent_count
                    s["total_convs"]  = self._total_convs
                    s["total_turns"]  = self._total_utterances
                    s["status"]       = "completed"
            with self._locks["sessions.json"]:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(sessions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ResearchLogger] session_end error: {e}")

    # ══════════════════════════════════════════
    #  NIVEL 1 – Agente
    # ══════════════════════════════════════════
    AGENT_FIELDS = [
        "session_id","agent_id","name","trait","backstory",
        "init_hunger","init_energy","init_hygiene","init_social",
        "init_x","init_y","spawn_time",
    ]

    def log_agent_spawn(self, char):
        """Registrar agente al nacer. Llamar una sola vez por agente."""
        if char.id in self._agent_written:
            return
        self._agent_written.add(char.id)
        self._write_csv_safe("agents.csv", {
            "session_id":   self.session_id,
            "agent_id":     char.id,
            "name":         char.name,
            "trait":        char.trait,
            "backstory":    char.backstory,
            "init_hunger":  round(char.hunger,  2),
            "init_energy":  round(char.energy,  2),
            "init_hygiene": round(char.hygiene, 2),
            "init_social":  round(char.social,  2),
            "init_x":       round(char.x, 1),
            "init_y":       round(char.y, 1),
            "spawn_time":   round(time.time() - self.start_ts, 2),
        }, self.AGENT_FIELDS)
        # Inicializar timer de snapshots
        self._needs_timer[char.id] = time.time() + self.NEEDS_INTERVAL

    NEEDS_FIELDS = [
        "session_id","sim_time","agent_id","name","trait","state",
        "hunger","energy","hygiene","social",
        "need_deficit",       # suma de (100-necesidad) → cuánto le falta en total
        "dominant_need",      # la necesidad más baja
        "x","y",
    ]

    def tick_needs_snapshot(self, char, sim_time: float):
        """Llamar en cada frame. Internamente muestrea cada NEEDS_INTERVAL."""
        now = time.time()
        if now < self._needs_timer.get(char.id, 0):
            return
        self._needs_timer[char.id] = now + self.NEEDS_INTERVAL

        needs = {"hunger":char.hunger,"energy":char.energy,
                 "hygiene":char.hygiene,"social":char.social}
        dominant = min(needs, key=needs.get)
        deficit  = sum(100 - v for v in needs.values())

        self._write_csv_safe("needs_timeseries.csv", {
            "session_id":   self.session_id,
            "sim_time":     round(sim_time, 1),
            "agent_id":     char.id,
            "name":         char.name,
            "trait":        char.trait,
            "state":        char.state,
            "hunger":       round(char.hunger,  2),
            "energy":       round(char.energy,  2),
            "hygiene":      round(char.hygiene, 2),
            "social":       round(char.social,  2),
            "need_deficit": round(deficit, 2),
            "dominant_need":dominant,
            "x":            round(char.x, 1),
            "y":            round(char.y, 1),
        }, self.NEEDS_FIELDS)

    STATE_FIELDS = [
        "session_id","sim_time","agent_id","name","trait",
        "from_state","to_state",
        "hunger","energy","hygiene","social",
        "trigger_need",   # necesidad que disparó el cambio (si aplica)
    ]

    def log_state_change(self, char, from_state: str, to_state: str, sim_time: float):
        needs = {"hunger":char.hunger,"energy":char.energy,
                 "hygiene":char.hygiene,"social":char.social}
        state_need_map = {
            "busca_comida":"hunger","comiendo":"hunger",
            "busca_cama":"energy","durmiendo":"energy",
            "busca_ducha":"hygiene","duchando":"hygiene",
            "busca_chat":"social","charlando":"social",
        }
        trigger = state_need_map.get(to_state, "")
        self._write_csv_safe("state_events.csv", {
            "session_id":  self.session_id,
            "sim_time":    round(sim_time, 2),
            "agent_id":    char.id,
            "name":        char.name,
            "trait":       char.trait,
            "from_state":  from_state,
            "to_state":    to_state,
            "hunger":      round(char.hunger,  2),
            "energy":      round(char.energy,  2),
            "hygiene":     round(char.hygiene, 2),
            "social":      round(char.social,  2),
            "trigger_need":trigger,
        }, self.STATE_FIELDS)

    # ══════════════════════════════════════════
    #  NIVEL 2 – Conversación
    # ══════════════════════════════════════════
    CONV_FIELDS = [
        "session_id","conv_id","sim_time_start","sim_time_end","duration_sec",
        "initiator_id","initiator_name","initiator_trait",
        "responder_id","responder_name","responder_trait",
        "trait_pair",           # "amigable-timido" (sorted)
        "num_turns","distance_px",
        "avg_polarity","avg_aggression","avg_curiosity",
        "total_words","initiator_turns","responder_turns",
        "initiator_hunger_start","initiator_energy_start",
        "initiator_hygiene_start","initiator_social_start",
        "responder_hunger_start","responder_energy_start",
        "responder_hygiene_start","responder_social_start",
        "initiator_social_delta","responder_social_delta",
    ]

    def new_conversation_id(self) -> str:
        self._conv_counter += 1
        self._total_convs  += 1
        return f"{self.session_id}_conv{self._conv_counter:04d}"

    def log_conversation_end(self, conv_id: str, char_a, char_b,
                              history: list[tuple[str,str]],
                              start_sim_time: float, end_sim_time: float,
                              distance_px: float,
                              social_delta_a: float, social_delta_b: float):
        if not history:
            return

        # Agregar análisis por turno
        all_sent = [_sentiment_score(txt) for _, txt in history]
        avg_pol  = sum(s["polarity"]   for s in all_sent) / len(all_sent)
        avg_agg  = sum(s["aggression"] for s in all_sent) / len(all_sent)
        avg_cur  = sum(s["curiosity"]  for s in all_sent) / len(all_sent)
        total_w  = sum(s["word_count"] for s in all_sent)
        init_turns = sum(1 for n,_ in history if n == char_a.name)
        resp_turns = sum(1 for n,_ in history if n == char_b.name)

        traits = sorted([char_a.trait, char_b.trait])
        self._write_csv_safe("conversations.csv", {
            "session_id":              self.session_id,
            "conv_id":                 conv_id,
            "sim_time_start":          round(start_sim_time, 2),
            "sim_time_end":            round(end_sim_time, 2),
            "duration_sec":            round(end_sim_time - start_sim_time, 2),
            "initiator_id":            char_a.id,
            "initiator_name":          char_a.name,
            "initiator_trait":         char_a.trait,
            "responder_id":            char_b.id,
            "responder_name":          char_b.name,
            "responder_trait":         char_b.trait,
            "trait_pair":              f"{traits[0]}-{traits[1]}",
            "num_turns":               len(history),
            "distance_px":             round(distance_px, 1),
            "avg_polarity":            round(avg_pol, 4),
            "avg_aggression":          round(avg_agg, 4),
            "avg_curiosity":           round(avg_cur, 4),
            "total_words":             total_w,
            "initiator_turns":         init_turns,
            "responder_turns":         resp_turns,
            "initiator_hunger_start":  round(char_a.hunger,  2),
            "initiator_energy_start":  round(char_a.energy,  2),
            "initiator_hygiene_start": round(char_a.hygiene, 2),
            "initiator_social_start":  round(char_a.social,  2),
            "responder_hunger_start":  round(char_b.hunger,  2),
            "responder_energy_start":  round(char_b.energy,  2),
            "responder_hygiene_start": round(char_b.hygiene, 2),
            "responder_social_start":  round(char_b.social,  2),
            "initiator_social_delta":  round(social_delta_a, 2),
            "responder_social_delta":  round(social_delta_b, 2),
        }, self.CONV_FIELDS)

    EDGE_FIELDS = [
        "session_id","agent_a_id","agent_a_name","trait_a",
        "agent_b_id","agent_b_name","trait_b",
        "interaction_count","last_interaction_sim_time",
        "is_isolated",   # 1 si este par nunca se ha encontrado
    ]

    def log_social_edge(self, char_a, char_b, sim_time: float):
        """Actualiza el grafo de interacciones. Llamar al iniciar cada conversación."""
        key = (min(char_a.id, char_b.id), max(char_a.id, char_b.id))
        self._edge_counts[key] += 1
        self._edge_last[key]    = sim_time
        # El CSV de bordes se reescribe al final de sesión (ver flush_social_graph)

    def flush_social_graph(self, all_chars: list, sim_time: float):
        """
        Escribe/actualiza social_edges.csv con todos los pares posibles.
        Llamar periódicamente o al final de sesión.
        Incluye 'islas' (pares que nunca interactuaron).
        """
        path = self._p("social_edges.csv")
        rows = []
        char_map = {c.id: c for c in all_chars}
        ids = [c.id for c in all_chars]

        for i in range(len(ids)):
            for j in range(i+1, len(ids)):
                a_id, b_id = ids[i], ids[j]
                key = (min(a_id,b_id), max(a_id,b_id))
                ca  = char_map[a_id]
                cb  = char_map[b_id]
                cnt = self._edge_counts.get(key, 0)
                rows.append({
                    "session_id":               self.session_id,
                    "agent_a_id":               a_id,
                    "agent_a_name":             ca.name,
                    "trait_a":                  ca.trait,
                    "agent_b_id":               b_id,
                    "agent_b_name":             cb.name,
                    "trait_b":                  cb.trait,
                    "interaction_count":        cnt,
                    "last_interaction_sim_time":round(self._edge_last.get(key, -1), 2),
                    "is_isolated":              1 if cnt == 0 else 0,
                })

        with self._locks["social_edges.csv"]:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=self.EDGE_FIELDS, extrasaction="ignore")
                w.writeheader()
                w.writerows(rows)

    # ══════════════════════════════════════════
    #  NIVEL 3 – Turno de diálogo
    # ══════════════════════════════════════════
    UTT_FIELDS = [
        "session_id","conv_id","turn_index","sim_time",
        "speaker_id","speaker_name","speaker_trait",
        "listener_id","listener_name","listener_trait",
        "word_count","char_count",
        "polarity","aggression","curiosity",
        "positive_words","negative_words","aggressive_words","curious_words",
        "questions","exclamations",
        "avg_word_length","sentence_count","unique_words","lexical_richness",
        "speaker_hunger","speaker_energy","speaker_hygiene","speaker_social",
    ]

    def log_utterance(self, conv_id: str, turn_index: int,
                      speaker, listener,
                      text: str, sim_time: float):
        self._total_utterances += 1
        sent = _sentiment_score(text)
        feat = _text_features(text)

        row = {
            "session_id":     self.session_id,
            "conv_id":        conv_id,
            "turn_index":     turn_index,
            "sim_time":       round(sim_time, 2),
            "speaker_id":     speaker.id,
            "speaker_name":   speaker.name,
            "speaker_trait":  speaker.trait,
            "listener_id":    listener.id,
            "listener_name":  listener.name,
            "listener_trait": listener.trait,
            "speaker_hunger": round(speaker.hunger,  2),
            "speaker_energy": round(speaker.energy,  2),
            "speaker_hygiene":round(speaker.hygiene, 2),
            "speaker_social": round(speaker.social,  2),
            **sent, **feat,
        }
        self._write_csv_safe("utterances.csv", row, self.UTT_FIELDS)

        # JSONL con texto completo
        self._append_jsonl("utterances.jsonl", {
            **row,
            "text": text,
        })
