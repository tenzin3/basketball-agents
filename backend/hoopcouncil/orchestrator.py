"""Debate orchestrator: Round 1 (independent) -> Round 2 (debate) -> Round 3 (final votes) -> Coach."""
from __future__ import annotations

import asyncio
import logging
import re

from . import config
from .agents.agents import CoachAgent, PlayerAgent
from .context.cache import load_all_packages
from .context.retrieval import generate_query
from .llm.providers import make_provider
from .players import DISPLAY_ORDER, PLAYERS
from .repository import get_repository

log = logging.getLogger(__name__)

DEFAULT_LINEUP = {"PG": "Stephen Curry", "SG": "Kobe Bryant", "SF": "Michael Jordan", "PF": "Kevin Durant",
                  "C / Point Forward": "LeBron James"}
ROUND_NAMES = {1: "First answers", 2: "Debate", 3: "Final word", 4: "Coach's answer"}


class MissingDataError(RuntimeError):
    pass


_SECRETS = [
    (re.compile(r"(?i)(key|token|api[_-]?key|password)=[^&\s'\"]+"), r"\1=[hidden]"),
    (re.compile(r"(?i)bearer\s+[a-z0-9._\-]+"), "Bearer [hidden]"),
    (re.compile(r"\b(sk|pk|rk)-[A-Za-z0-9_\-]{8,}"), "[hidden key]"),
    (re.compile(r"(?i)\b(postgres(?:ql)?(?:\+\w+)?://)[^@\s]+@"), r"\1[hidden]@"),
]


def public_error(e: Exception) -> str:
    """The error text saved with a debate and shown to visitors: one line, short, with anything that looks like a
    key, password or database login removed. Full details stay in the server log."""
    text = (str(e).strip().splitlines() or [type(e).__name__])[0][:300]
    for rx, repl in _SECRETS:
        text = rx.sub(repl, text)
    return text


def normalize_scenario(s: dict) -> dict:
    """A chat question; any extra game-state fields are optional and passed through as context."""
    out = {k: v for k, v in dict(s).items() if v not in (None, "")}
    out["question"] = (out.get("question") or "").strip() or "Who should take the final shot when we're down one?"
    return out


def _setup(scenario: dict, provider=None, player_model=None, coach_provider=None, coach_model=None,
           packages: dict | None = None, documents: dict | None = None):
    """Load data, build the five player agents for this question, and pick the models."""
    repo = None
    if packages is None:
        repo = get_repository()
        packages = load_all_packages(repo)
    missing = [slug for slug in PLAYERS if not packages.get(slug)]
    if missing:
        raise MissingDataError(
            f"No career data for: {', '.join(missing)}. Run the data pipeline first (see README: hoop pipeline).")
    if documents is None:
        repo = repo or get_repository()
        documents = {slug: repo.load_documents(slug) for slug in PLAYERS}
    p_provider = make_provider(provider, player_model, tier="player")
    c_provider = make_provider(coach_provider or provider or config.COACH_PROVIDER, coach_model, tier="coach")
    query = generate_query(scenario)
    agents = []
    for slug in DISPLAY_ORDER:
        cfg = PLAYERS[slug]
        mates = [PLAYERS[o].full_name for o in DISPLAY_ORDER if o != slug]
        a = PlayerAgent(cfg, packages[slug], documents.get(slug, []), p_provider, mates, config.CONTEXT_TOKEN_BUDGET, packages)
        a.prepare(query)
        agents.append(a)
    return agents, p_provider, c_provider, packages, query


def _coach_meta(packages: dict, query: dict) -> dict:
    return {"contexts": [packages[s]["player"] for s in DISPLAY_ORDER], "rounds": [1, 2, 3],
            "retrieval_intents": query.get("intents")}


async def run_simulation(scenario: dict, store=None, sim_id: str | None = None, provider: str | None = None,
                         player_model: str | None = None, coach_provider: str | None = None, coach_model: str | None = None,
                         packages: dict | None = None, documents: dict | None = None, on_event=None) -> dict:
    """Run all four stages in one go (CLI and local API)."""
    scenario = normalize_scenario(scenario)
    agents, p_provider, c_provider, packages, query = _setup(scenario, provider, player_model, coach_provider,
                                                             coach_model, packages, documents)
    llm_cfg = {"player_provider": p_provider.name, "player_model": p_provider.model,
               "coach_provider": c_provider.name, "coach_model": c_provider.model}
    if store is not None and sim_id is None:
        sim_id = store.create(scenario, llm_cfg)

    def emit(kind, payload=None):
        if on_event:
            on_event(kind, payload)

    async def run_round(n, coros):
        if store:
            store.set_status(sim_id, f"round{n}")
            store.start_round(sim_id, n, ROUND_NAMES[n])
        emit("round_start", n)
        res = await asyncio.gather(*coros)
        if store:
            for r in res:
                store.add_message(sim_id, r)
            store.complete_round(sim_id, n)
        emit("round_complete", {"round": n, "messages": res})
        return res

    try:
        lineup = scenario.get("lineup") or DEFAULT_LINEUP
        round1 = await run_round(1, [a.analyze(scenario, lineup) for a in agents])
        round2 = await run_round(2, [a.debate(scenario, round1) for a in agents])
        round3 = await run_round(3, [a.final_vote(scenario, round1, round2) for a in agents])
        if store:
            store.set_status(sim_id, "coach")
            store.start_round(sim_id, 4, ROUND_NAMES[4])
        emit("round_start", 4)
        coach = CoachAgent(c_provider, packages)
        coach_call = await coach.decide(scenario, round1, round2, round3)
        coach_call["data_considered"] = _coach_meta(packages, query)
        if store:
            store.set_coach(sim_id, coach_call)
            store.complete_round(sim_id, 4)
            store.set_status(sim_id, "complete")
        emit("coach", coach_call)
    except Exception as e:
        log.exception("simulation failed")
        if store and sim_id:
            store.set_status(sim_id, "failed", public_error(e))
        raise
    return {"id": sim_id, "scenario": scenario, "llm_config": llm_cfg, "query": query,
            "round1": round1, "round2": round2, "round3": round3, "coach_call": coach_call}


STATUS_FOR_STAGE = {1: "round1", 2: "round2", 3: "round3", 4: "coach"}


def next_stage(sim: dict) -> int | None:
    """The first stage (1-3 rounds, 4 coach) that hasn't completed yet; None when the debate is finished."""
    if sim["status"] in ("complete", "failed"):
        return None
    done = {r["round_number"] for r in sim.get("rounds", []) if r.get("completed_at")}
    for n in (1, 2, 3, 4):
        if n not in done:
            return n
    return None


async def run_stage(store, sim_id: str, packages: dict | None = None, documents: dict | None = None) -> int | None:
    """Run exactly one stage of a stored debate, then return. Used when the browser drives the debate
    one request at a time (hosting where work stops once a response is sent, such as Vercel).

    Returns the stage that ran, or None if there was nothing to do (finished, or another request is running it).
    Each stage rebuilds the agents from the stored question and earlier rounds, so no state is kept in memory."""
    sim = store.get(sim_id)
    if sim is None:
        raise KeyError(sim_id)
    n = next_stage(sim)
    if n is None or not store.claim_stage(sim_id, n):
        return None
    store.reset_stage(sim_id, n)  # clear leftovers if an earlier attempt at this stage timed out
    cfg = sim.get("llm_config") or {}
    scenario = normalize_scenario(sim["scenario"])
    try:
        agents, _p, c_provider, packages, query = _setup(scenario, cfg.get("provider"), cfg.get("player_model"),
                                                         cfg.get("coach_provider"), cfg.get("coach_model"),
                                                         packages, documents)
        by_round: dict = {}
        for m in sim.get("messages", []):
            by_round.setdefault(m["round"], []).append(m)
        order = {slug: i for i, slug in enumerate(DISPLAY_ORDER)}
        r1, r2, r3 = ([dict(m) for m in sorted(by_round.get(k, []), key=lambda m: order.get(m["slug"], 9))]
                      for k in (1, 2, 3))

        store.set_status(sim_id, STATUS_FOR_STAGE[n])
        store.start_round(sim_id, n, ROUND_NAMES[n])
        if n == 4:
            coach_call = await CoachAgent(c_provider, packages).decide(scenario, r1, r2, r3)
            coach_call["data_considered"] = _coach_meta(packages, query)
            store.set_coach(sim_id, coach_call)
        else:
            if n == 1:
                lineup = scenario.get("lineup") or DEFAULT_LINEUP
                coros = [a.analyze(scenario, lineup) for a in agents]
            elif n == 2:
                coros = [a.debate(scenario, r1) for a in agents]
            else:
                coros = [a.final_vote(scenario, r1, r2) for a in agents]
            for r in await asyncio.gather(*coros):
                store.add_message(sim_id, r)
        store.complete_round(sim_id, n)
        store.finish_stage(sim_id, n)
        store.set_status(sim_id, "complete" if n == 4 else STATUS_FOR_STAGE[n + 1])
        return n
    except Exception as e:
        log.exception("simulation %s stage %s failed", sim_id, n)
        store.set_status(sim_id, "failed", public_error(e))
        raise
