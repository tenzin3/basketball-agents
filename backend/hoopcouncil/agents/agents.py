"""Player agents and the Coach agent."""
from __future__ import annotations

from ..context.builder import assemble_agent_context
from ..context.retrieval import retrieve
from ..llm.providers import LLMProvider
from ..players import PlayerConfig
from .parsing import extract_json, normalize
from .prompts import (COACH_SYSTEM, COACH_USER, COURT_VOCAB, GROUNDING_RULES, PLAYER_SYSTEM, ROUND1_USER, ROUND2_USER,
                      ROUND3_USER, compact, lineup_text, scenario_text)


def _slim_r1(r: dict) -> dict:
    keys = ("player", "play_name", "proposed_play", "primary_option", "secondary_option", "your_role",
            "tactical_reasoning", "data_support", "risks", "confidence")
    return {k: r.get(k) for k in keys if k in r}


def _slim_r2(r: dict) -> dict:
    keys = ("player", "evaluations", "spacing_concerns", "matchup_advantages", "defensive_counters",
            "revised_proposal", "changed_position", "confidence")
    return {k: r.get(k) for k in keys if k in r}


def _slim_r3(r: dict) -> dict:
    keys = ("player", "final_vote", "voted_for_proposal_of", "preferred_primary_option", "reason", "confidence")
    return {k: r.get(k) for k in keys if k in r}


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
                                    teammates=", ".join(self.teammates), rules=GROUNDING_RULES)

    async def _run(self, rnd: int, user: str, extra_meta: dict | None = None) -> dict:
        meta = {"role": "player", "round": rnd, "player": self.name, "packages": self.all_packages, **(extra_meta or {})}
        res = await self.provider.complete(self.system_prompt(), user, meta)
        obj = normalize(extract_json(res.text), rnd, self.name)
        return {"player": self.name, "slug": self.cfg.slug, "round": rnd, "content": obj, "raw_text": res.text,
                "model": res.model, "latency_ms": res.latency_ms, "data_considered": self.data_considered}

    async def analyze(self, scenario: dict, lineup: dict) -> dict:
        return await self._run(1, ROUND1_USER.format(scenario=scenario_text(scenario), lineup=lineup_text(lineup)))

    async def debate(self, scenario: dict, round1: list) -> dict:
        props = compact([_slim_r1(r["content"]) for r in round1])
        return await self._run(2, ROUND2_USER.format(scenario=scenario_text(scenario), proposals=props),
                               {"round1": [r["content"] for r in round1]})

    async def final_vote(self, scenario: dict, round1: list, round2: list) -> dict:
        return await self._run(3, ROUND3_USER.format(scenario=scenario_text(scenario),
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
        system = COACH_SYSTEM.format(contexts=self._contexts(), rules=GROUNDING_RULES)
        user = COACH_USER.format(scenario=scenario_text(scenario), round1=compact([_slim_r1(r["content"]) for r in round1]),
                                 round2=compact([_slim_r2(r["content"]) for r in round2]),
                                 round3=compact([_slim_r3(r["content"]) for r in round3]), vocab=COURT_VOCAB)
        res = await self.provider.complete(system, user, {"role": "coach", "packages": self.packages})
        obj = extract_json(res.text)
        from .parsing import clamp_conf

        if "confidence" in obj:
            obj["confidence"] = clamp_conf(obj["confidence"])
        obj = validate_court(obj)
        return {"decision": obj, "raw_text": res.text, "model": res.model, "latency_ms": res.latency_ms}


VALID_LOCS = {x.strip() for x in COURT_VOCAB.split(",")}
VALID_ACTIONS = {"screen", "dribble", "drive", "cut", "space", "relocate", "pass", "handoff", "roll", "pop", "post_up",
                 "shoot", "inbound"}


def validate_court(obj: dict) -> dict:
    """Keep only well-formed court instructions; record any dropped steps."""
    court = obj.get("court") or {}
    seq = court.get("play_sequence") or obj.get("play_sequence") or []
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
    obj["court"] = {"start_positions": starts, "ball_starts_with": court.get("ball_starts_with") or obj.get("ball_handler"),
                    "play_sequence": good, "dropped_steps": dropped}
    return obj
