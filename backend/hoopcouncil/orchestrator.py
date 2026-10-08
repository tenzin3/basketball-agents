"""Debate orchestrator: Round 1 (independent) -> Round 2 (debate) -> Round 3 (final votes) -> Coach."""
from __future__ import annotations

import asyncio
import logging

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


def normalize_scenario(s: dict) -> dict:
    """A chat question; any extra game-state fields are optional and passed through as context."""
    out = {k: v for k, v in dict(s).items() if v not in (None, "")}
    out["question"] = (out.get("question") or "").strip() or "Who should take the final shot when we're down one?"
    return out


async def run_simulation(scenario: dict, store=None, sim_id: str | None = None, provider: str | None = None,
                         player_model: str | None = None, coach_provider: str | None = None, coach_model: str | None = None,
                         packages: dict | None = None, documents: dict | None = None, on_event=None) -> dict:
    scenario = normalize_scenario(scenario)
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
    llm_cfg = {"player_provider": p_provider.name, "player_model": p_provider.model,
               "coach_provider": c_provider.name, "coach_model": c_provider.model}
    if store is not None and sim_id is None:
        sim_id = store.create(scenario, llm_cfg)

    def emit(kind, payload=None):
        if on_event:
            on_event(kind, payload)

    query = generate_query(scenario)
    order = DISPLAY_ORDER
    agents = []
    for slug in order:
        cfg = PLAYERS[slug]
        mates = [PLAYERS[o].full_name for o in order if o != slug]
        a = PlayerAgent(cfg, packages[slug], documents.get(slug, []), p_provider, mates, config.CONTEXT_TOKEN_BUDGET, packages)
        a.prepare(query)
        agents.append(a)

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
        coach_call["data_considered"] = {"contexts": [packages[s]["player"] for s in order], "rounds": [1, 2, 3],
                                         "retrieval_intents": query.get("intents")}
        if store:
            store.set_coach(sim_id, coach_call)
            store.complete_round(sim_id, 4)
            store.set_status(sim_id, "complete")
        emit("coach", coach_call)
    except Exception as e:
        log.exception("simulation failed")
        if store and sim_id:
            store.set_status(sim_id, "failed", str(e))
        raise
    return {"id": sim_id, "scenario": scenario, "llm_config": llm_cfg, "query": query,
            "round1": round1, "round2": round2, "round3": round3, "coach_call": coach_call}
