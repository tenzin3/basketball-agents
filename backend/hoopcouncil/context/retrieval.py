"""Situation-specific retrieval of layer-3 documents.

scenario -> query generator (intent rules) -> topics + query text
         -> BM25 over the player's documents (+ topic boost, + optional embeddings)
         -> top documents within a token budget
"""
from __future__ import annotations

import math
import re
from collections import Counter

from .. import config
from .fmt import est_tokens

INTENTS = [
    # (pattern, topics, description)
    (r"final shot|last shot|game[- ]?winn|buzzer|down \d|tied|seconds? (left|remaining)|\b\d{1,2} ?s(ec)?\b|clutch|closing|late[- ]game|crunch",
     ["final-shot", "clutch", "late-game", "close-games", "late-clock", "shot-creation", "isolation", "pull-up", "playoff-scoring", "pressure"],
     "late-game shot creation"),
    (r"initiat|run the offense|ball[- ]handl|point guard|who brings|bring it up|orchestrat|pick[- ]and[- ]roll|\bpnr\b|ball screen",
     ["playmaking", "usage", "pick-and-roll", "turnovers", "initiator"], "offensive initiation / playmaking"),
    (r"switch", ["isolation", "mismatch", "shot-creation", "pull-up", "post", "positions"], "attacking a switching defense"),
    (r"\bzone\b", ["three-point", "spot-up", "playmaking", "off-ball"], "zone offense"),
    (r"defen|guard (him|their)|stop|contain|get a stop", ["defense", "steals", "blocks", "rebounding"], "defense"),
    (r"transition|fast ?break|push the pace|outlet", ["transition", "rim", "playmaking"], "transition"),
    (r"inbound|\bato\b|sideline out|baseline out|after (a )?timeout", ["off-ball", "spot-up", "catch-and-shoot", "playmaking"], "inbounds play"),
    (r"three|down 3|need a 3|triple", ["three-point", "catch-and-shoot", "pull-up", "shot-profile"], "three-point need"),
    (r"free throw|foul|and[- ]1", ["foul-drawing", "free-throws", "rim"], "foul drawing"),
    (r"rebound|board|putback", ["rebounding"], "rebounding"),
    (r"post|mismatch|size|smaller", ["post", "mismatch", "positions", "shot-creation"], "mismatch / post"),
    (r"playoff|finals|game 7|elimination|series", ["playoffs", "playoff-scoring", "finals", "pressure"], "playoff pressure"),
    (r"double[- ]team|trap|blitz|hedge", ["playmaking", "turnovers", "off-ball", "spot-up"], "beating pressure on the ball"),
    (r"\bbest\b|greatest|\bgoat\b|better|compare|versus|\bvs\.?\b|who was|\brank|all[- ]time",
     ["awards", "efficiency", "playoffs", "playoff-scoring", "finals", "scoring"], "comparison / greatness"),
    (r"one[- ]on[- ]one|1v1|1-on-1|\biso\b|isolation|create (his|their|a) own", ["isolation", "shot-creation", "mismatch", "self-creation"],
     "one-on-one scoring"),
    (r"pass|assist|playmak|vision|set up", ["playmaking", "usage", "turnovers", "pick-and-roll"], "playmaking"),
    (r"shoot|shooter|jumper|range|midrange|mid-range", ["three-point", "midrange", "shot-profile", "efficiency"], "shooting"),
    (r"prime|peak|best season|career", ["season", "awards", "efficiency", "playoffs"], "career / peak seasons"),
]
TOKEN_RE = re.compile(r"[a-z0-9%\-\.]+")
STOP = {"the", "a", "an", "and", "or", "of", "to", "in", "on", "is", "are", "we", "should", "what", "who", "with", "for",
        "it", "be", "this", "that", "at", "by", "vs", "from", "n/a", "|"}


def tokenize(text: str) -> list:
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOP and len(t) > 1]


def generate_query(scenario: dict) -> dict:
    text = " ".join(str(scenario.get(k) or "") for k in ("question", "defensive_scheme", "notes", "situation"))
    gc = scenario.get("game_clock")
    if isinstance(gc, (int, float)) and gc <= 24 and (scenario.get("quarter") or 4) >= 4:
        text += " late-game final shot clutch"
    topics, matched = [], []
    for pat, tps, desc in INTENTS:
        if re.search(pat, text, re.I):
            matched.append(desc)
            for t in tps:
                if t not in topics:
                    topics.append(t)
    seasons = re.findall(r"\b(19[5-9]\d|20[0-4]\d)-(\d{2})\b", text)
    years = re.findall(r"\b(19[5-9]\d|20[0-4]\d)\b", text)
    season_topics = [f"season:{a}-{b}" for a, b in seasons]
    for y in years:
        y = int(y)
        season_topics.append(f"season:{y - 1}-{y % 100:02d}")
    if not topics:
        topics = ["shot-creation", "playmaking", "efficiency", "playoffs"]
        matched.append("general")
    return {"text": text, "topics": topics + season_topics, "intents": matched}


class BM25:
    def __init__(self, docs: list, k1: float = 1.4, b: float = 0.75):
        self.docs = docs
        self.toks = [tokenize(d["title"] + " " + " ".join(d.get("topics", [])) + " " + d["text"]) for d in docs]
        self.k1, self.b = k1, b
        self.avgdl = sum(len(t) for t in self.toks) / max(1, len(self.toks))
        df = Counter()
        for t in self.toks:
            df.update(set(t))
        N = len(docs)
        self.idf = {w: math.log(1 + (N - c + 0.5) / (c + 0.5)) for w, c in df.items()}
        self.tf = [Counter(t) for t in self.toks]

    def score(self, query: str) -> list:
        q = tokenize(query)
        out = []
        for i, tf in enumerate(self.tf):
            dl = len(self.toks[i]) or 1
            s = 0.0
            for w in q:
                if w in tf:
                    f = tf[w]
                    s += self.idf.get(w, 0) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            out.append(s)
        return out


def _cosine(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def retrieve(docs: list, query: dict, token_budget: int = 2500, max_docs: int = 8, query_embedding=None) -> list:
    if not docs:
        return []
    bm = BM25(docs).score(query["text"] + " " + " ".join(query["topics"]))
    mx = max(bm) or 1.0
    topics = query["topics"]
    scored = []
    for d, s in zip(docs, bm):
        overlap = len(set(d.get("topics", [])) & set(topics))
        # topic order = priority; earlier intent topics weigh more
        prio = sum(1.0 / (1 + topics.index(t)) for t in d.get("topics", []) if t in topics)
        score = 0.5 * (s / mx) + 0.35 * min(1.0, overlap / 3) + 0.15 * min(1.0, prio)
        if query_embedding is not None and d.get("embedding"):
            score = 0.7 * score + 0.3 * _cosine(query_embedding, d["embedding"])
        scored.append((score, d))
    scored.sort(key=lambda x: -x[0])
    out, used = [], 0
    for score, d in scored:
        if score <= 0.05:
            break
        t = est_tokens(d["text"])
        if used + t > token_budget:
            continue
        out.append({**{k: v for k, v in d.items() if k != "embedding"}, "score": round(score, 3)})
        used += t
        if len(out) >= max_docs:
            break
    return out


def embed_texts(texts: list) -> list | None:
    """Optional embeddings (HOOP_EMBEDDINGS_PROVIDER=openai|local). Returns None when disabled."""
    prov = config.EMBEDDINGS_PROVIDER
    if prov == "none" or not texts:
        return None
    import os

    import httpx

    if prov == "openai":
        url = "https://api.openai.com/v1/embeddings"
        headers = {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"}
        model = os.environ.get("HOOP_EMBEDDINGS_MODEL", "text-embedding-3-small")
    else:  # local OpenAI-compatible server (e.g. Ollama)
        url = config.LOCAL_LLM_BASE_URL.rstrip("/") + "/embeddings"
        headers = {}
        model = os.environ.get("HOOP_EMBEDDINGS_MODEL", "nomic-embed-text")
    r = httpx.post(url, json={"model": model, "input": texts}, headers=headers, timeout=60)
    r.raise_for_status()
    return [d["embedding"] for d in r.json()["data"]]
