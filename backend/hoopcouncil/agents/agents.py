"""Player agents and the Coach agent."""
from __future__ import annotations

from ..context.builder import assemble_agent_context
from ..context.retrieval import retrieve
from ..llm.providers import LLMProvider
from ..players import PlayerConfig
from .parsing import clamp_conf, clean_output, extract_json, normalize
from .prompts import (COACH_RULES, COACH_SYSTEM, COACH_USER, COURT_VOCAB, EXPLAIN_NUMBERS, GROUNDING_RULES, PLAYER_SYSTEM,
                      ROUND1_USER, ROUND2_USER, ROUND3_USER, compact, lineup_text, question_text)


def _unusable(obj: dict, *keys: str) -> bool:
    """A reply we can't show: not JSON, or none of the expected text fields filled in."""
    return bool(obj.get("parse_error")) or not any(str(obj.get(k) or "").strip() for k in keys)


async def _retry_on_backup(provider, system: str, user: str, res, obj, parse, *keys):
    """Free models sometimes return broken or empty JSON. Try once more on the provider's backup model
    (OpenRouter only); keep the original if the backup isn't better."""
    if not _unusable(obj, *keys) or not hasattr(provider, "retry_backup"):
        return res, obj
    try:
        res2 = await provider.retry_backup(system, user)
    except Exception:  # keep the original reply; the debate goes on
        return res, obj
    if res2 is None:
        return res, obj
    obj2 = parse(res2.text)
    return (res2, obj2) if not _unusable(obj2, *keys) else (res, obj)


def _pick(r: dict, keys: tuple) -> dict:
    return {k: r.get(k) for k in keys if r.get(k) not in (None, "", [])}


# What players see of each other: arguments and numbers, not confidence scores (those only go to the coach).
def _slim_r1(r: dict, coach: bool = False) -> dict:
    keys = ("player", "message", "position", "reasoning", "data_support", "risks", "play")
    return _pick(r, keys + (("confidence",) if coach else ()))


def _slim_r2(r: dict, coach: bool = False) -> dict:
    keys = ("player", "message", "evaluations", "revised_position", "changed_position")
    return _pick(r, keys + (("confidence",) if coach else ()))


def _slim_r3(r: dict, coach: bool = False) -> dict:
    keys = ("player", "message", "final_answer", "backs", "reason")
    return _pick(r, keys + (("confidence",) if coach else ()))


class PlayerAgent:
    def __init__(self, cfg: PlayerConfig, package: dict, documents: list, provider: LLMProvider,
                 teammates: list, token_budget: int, all_packages: dict):
        self.cfg = cfg
        self.package = package
        self.documents = documents
        self.provider = provider
        self.teammates = teammates
        self.token_budget = token_budget
        self.all_packages = all_packages  # only used by the mock provider
        self.context_text = None
        self.data_considered = None

    @property
    def name(self) -> str:
        return self.cfg.full_name

    def prepare(self, query: dict) -> None:
        retrieved = retrieve(self.documents, query, token_budget=int(self.token_budget * 0.35))
        self.context_text, self.data_considered = assemble_agent_context(self.package, retrieved, self.token_budget)
        self.data_considered["retrieval_intents"] = query.get("intents")

    def system_prompt(self) -> str:
        return PLAYER_SYSTEM.format(name=self.name, focus=", ".join(self.cfg.focus_areas), context=self.context_text,
                                    teammates=", ".join(self.teammates), explain=EXPLAIN_NUMBERS,
                                    rules=GROUNDING_RULES.format(name=self.name))

    async def _run(self, rnd: int, user: str, extra_meta: dict | None = None) -> dict:
        meta = {"role": "player", "round": rnd, "player": self.name, "packages": self.all_packages, **(extra_meta or {})}
        system = self.system_prompt()
        res = await self.provider.complete(system, user, meta)

        def parse(text):
            return normalize(extract_json(text), rnd, self.name)
        obj = parse(res.text)
        res, obj = await _retry_on_backup(self.provider, system, user, res, obj, parse, "message")
        return {"player": self.name, "slug": self.cfg.slug, "round": rnd, "content": obj, "raw_text": res.text,
                "model": res.model, "latency_ms": res.latency_ms, "data_considered": self.data_considered}

    async def analyze(self, scenario: dict, lineup: dict) -> dict:
        return await self._run(1, ROUND1_USER.format(question=question_text(scenario), lineup=lineup_text(lineup)),
                               {"question": scenario.get("question")})

    async def debate(self, scenario: dict, round1: list) -> dict:
        props = compact([_slim_r1(r["content"]) for r in round1])
        return await self._run(2, ROUND2_USER.format(question=question_text(scenario), proposals=props, name=self.name),
                               {"round1": [r["content"] for r in round1]})

    async def final_vote(self, scenario: dict, round1: list, round2: list) -> dict:
        return await self._run(3, ROUND3_USER.format(question=question_text(scenario), name=self.name,
                                                     proposals=compact([_slim_r1(r["content"]) for r in round1]),
                                                     debate=compact([_slim_r2(r["content"]) for r in round2])))


class CoachAgent:
    def __init__(self, provider: LLMProvider, packages: dict, per_player_tokens: int = 3500):
        self.provider = provider
        self.packages = packages
        self.per_player_tokens = per_player_tokens

    def _contexts(self) -> str:
        parts = []
        for slug, pkg in self.packages.items():
            if not pkg:
                parts.append(f"### {slug}: NO DATA AVAILABLE")
                continue
            txt = pkg["text"]["layer1"]
            limit = self.per_player_tokens * 4
            if len(txt) > limit:
                txt = txt[:limit] + "\n[... truncated for length ...]"
            parts.append(f"### {pkg['player']}\n{txt}")
        return "\n\n".join(parts)

    async def decide(self, scenario: dict, round1: list, round2: list, round3: list) -> dict:
        system = COACH_SYSTEM.format(contexts=self._contexts(), explain=EXPLAIN_NUMBERS, rules=COACH_RULES)
        user = COACH_USER.format(question=question_text(scenario),
                                 round1=compact([_slim_r1(r["content"], coach=True) for r in round1]),
                                 round2=compact([_slim_r2(r["content"], coach=True) for r in round2]),
                                 round3=compact([_slim_r3(r["content"], coach=True) for r in round3]), vocab=COURT_VOCAB)
        res = await self.provider.complete(system, user, {"role": "coach", "packages": self.packages,
                                                          "question": scenario.get("question")})
        obj = clean_output(extract_json(res.text))
        res, obj = await _retry_on_backup(self.provider, system, user, res, obj,
                                          lambda text: clean_output(extract_json(text)), "verdict", "answer")
        if "confidence" in obj:
            obj["confidence"] = clamp_conf(obj["confidence"])
        obj = validate_court(obj)
        return {"decision": obj, "raw_text": res.text, "model": res.model, "latency_ms": res.latency_ms}


VALID_LOCS = {x.strip() for x in COURT_VOCAB.split(",")}
VALID_ACTIONS = {"screen", "dribble", "drive", "cut", "space", "relocate", "pass", "handoff", "roll", "pop", "post_up",
                 "shoot", "inbound"}


def validate_court(obj: dict) -> dict:
    """Keep only well-formed court instructions; record any dropped steps. A missing court stays None."""
    court = obj.get("court")
    seq = (court or {}).get("play_sequence") or obj.get("play_sequence") or []
    if not court and not seq:
        obj["court"] = None
        return obj
    court = court or {}
    good, dropped = [], []
    for st in seq if isinstance(seq, list) else []:
        if not isinstance(st, dict) or st.get("action") not in VALID_ACTIONS or not st.get("player"):
            dropped.append(st)
            continue
        for k in ("location", "destination"):
            if st.get(k) and st[k] not in VALID_LOCS:
                st[k] = None
        try:
            st["time"] = float(st.get("time", len(good)))
        except (TypeError, ValueError):
            st["time"] = float(len(good))
        good.append(st)
    good.sort(key=lambda s: s["time"])
    starts = {k: (v if v in VALID_LOCS else None) for k, v in (court.get("start_positions") or {}).items()}
    play = obj.get("play") if isinstance(obj.get("play"), dict) else {}
    obj["court"] = {"start_positions": starts,
                    "ball_starts_with": court.get("ball_starts_with") or play.get("ball_handler") or obj.get("ball_handler"),
                    "play_sequence": good, "dropped_steps": dropped}
    return obj
