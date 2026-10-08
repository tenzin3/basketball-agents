"""HoopCouncil API (FastAPI).

GET  /players                       player cards
GET  /players/{player}              full profile
GET  /players/{player}/career       seasons, playoffs, aggregates, finals, shot profiles, peak scores
GET  /players/{player}/achievements structured awards
GET  /players/{player}/context      cached Career Context Package (inspection)
GET  /players/{player}/quality      data-quality report
POST /simulations                   start a debate (runs in the background)
GET  /simulations/{simulation_id}   poll status / transcript / coach decision
GET  /simulations                   recent simulations
"""
from __future__ import annotations

import asyncio
import logging
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .. import config
from ..context.builder import achievements_summary
from ..context.cache import load_package
from ..derive.aggregates import season_lines
from ..orchestrator import DEFAULT_LINEUP, MissingDataError, run_simulation
from ..players import DISPLAY_ORDER, PLAYERS, get_player
from ..repository import get_repository
from .schemas import SimulationRequest

log = logging.getLogger(__name__)
app = FastAPI(title="HoopCouncil API", version="0.1.0",
              description="AI simulation based on player statistics and career tendencies.")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

DISCLAIMER = "AI simulation based on player statistics and career tendencies."
_tasks: set = set()


def _store():
    from ..simulation_store import MemorySimulationStore, SQLSimulationStore

    if not hasattr(app.state, "store"):
        app.state.store = MemorySimulationStore() if os.environ.get("HOOP_STORE", "db") == "files" else SQLSimulationStore()
    return app.state.store


def _resolve(player: str):
    try:
        return get_player(player)
    except KeyError:
        raise HTTPException(404, f"unknown player '{player}'")


def _card(slug: str) -> dict:
    cfg = PLAYERS[slug]
    pkg = load_package(slug)
    base = {"slug": slug, "name": cfg.full_name, "lineup_slot": cfg.lineup_slot, "agent": cfg.agent_name,
            "focus_areas": list(cfg.focus_areas), "data_available": pkg is not None}
    if pkg is None:
        return base
    i = pkg["identity"]
    reg = pkg["career_summary"]["regular_season"] or {}
    return {**base,
            "career_years": f"{i.get('first_season')} – {i.get('last_season')}", "seasons_played": i.get("seasons_played"),
            "position": i.get("primary_position"), "height_in": i.get("height_in"), "teams": i.get("teams"),
            "archetypes": [a["archetype"] for a in pkg.get("basketball_archetypes", [])][:5],
            "achievements": [{"label": a["label"], "count": a["count"]} for a in pkg.get("achievements", [])
                             if a["achievement_type"] in ("NBA_CHAMPIONSHIP", "NBA_MVP", "NBA_FINALS_MVP", "ALL_STAR", "SCORING_TITLE", "DEFENSIVE_PLAYER_OF_THE_YEAR")],
            "career_stats": {**{k: (reg.get("per_game") or {}).get(k) for k in ("pts_per_g", "trb_per_g", "ast_per_g")},
                             "ts_pct": (reg.get("shooting") or {}).get("ts_pct"), "games": (reg.get("totals") or {}).get("g")},
            "peak_seasons": [p["season"] for p in pkg.get("peak_seasons", [])]}


@app.get("/health")
def health():
    return {"ok": True, "store": os.environ.get("HOOP_STORE", "db"), "llm_provider": config.LLM_PROVIDER}


@app.get("/players")
def players():
    return {"disclaimer": DISCLAIMER, "lineup": DEFAULT_LINEUP, "players": [_card(s) for s in DISPLAY_ORDER]}


@app.get("/players/{player}")
def player_profile(player: str):
    cfg = _resolve(player)
    pkg = load_package(cfg.slug)
    if pkg is None:
        raise HTTPException(404, f"no data for {cfg.full_name}; run the data pipeline")
    return {"card": _card(cfg.slug), "identity": pkg["identity"], "career_summary": pkg["career_summary"],
            "playoff_summary": pkg["playoff_summary"], "finals_summary": pkg["finals_summary"],
            "achievements": pkg["achievements"], "records": pkg["records"], "shot_profile_summary": pkg["shot_profile_summary"],
            "play_type_tendencies": pkg["play_type_tendencies"], "clutch_summary": pkg.get("clutch_summary"),
            "career_phases": pkg["career_phases"], "peak_seasons": pkg["peak_seasons"], "peak_formula": pkg.get("peak_formula"),
            "archetypes": pkg["archetypes_all"], "strengths": pkg["strengths"], "limitations": pkg["limitations"],
            "data_limitations": pkg["data_limitations"], "built_at": pkg.get("built_at")}


@app.get("/players/{player}/career")
def player_career(player: str):
    cfg = _resolve(player)
    repo = get_repository()
    ds, derived = repo.load_dataset(cfg.slug), repo.load_derived(cfg.slug)
    if ds is None:
        raise HTTPException(404, f"no data for {cfg.full_name}")
    peak = {p["season"]: p for p in (derived or {}).get("peak_scores", [])}

    def line(l):
        return {"season": l["season"], "team": l.get("team"), "teams": l.get("teams"), "age": l.get("age"),
                "per_game": l.get("per_game"), "totals": l.get("totals"), "advanced": l.get("advanced"),
                "shooting": l.get("shooting"), "per_poss": l.get("per_poss"), "awards_text": l.get("awards_text"),
                "peak_score": (peak.get(l["season"]) or {}).get("peak_score") if l["stat_type"] == "regular_season" else None,
                "provenance": l.get("provenance")}
    return {"player": cfg.full_name, "regular_season": [line(l) for l in season_lines(ds, "regular_season")],
            "playoffs": [line(l) for l in season_lines(ds, "playoffs")],
            "team_splits": [line(l) for l in ds["seasons"] if l.get("is_team_split")],
            "aggregates": (derived or {}).get("aggregates"), "finals_series": (derived or {}).get("finals_series"),
            "peak_scores": (derived or {}).get("peak_scores"), "dnp_seasons": ds.get("dnp_seasons")}


@app.get("/players/{player}/achievements")
def player_achievements(player: str):
    cfg = _resolve(player)
    ds = get_repository().load_dataset(cfg.slug)
    if ds is None:
        raise HTTPException(404, f"no data for {cfg.full_name}")
    return {"player": cfg.full_name, "summary": achievements_summary(ds["achievements"]), "achievements": ds["achievements"]}


@app.get("/players/{player}/context")
def player_context(player: str):
    cfg = _resolve(player)
    pkg = load_package(cfg.slug)
    if pkg is None:
        raise HTTPException(404, f"no context package for {cfg.full_name}")
    return pkg


@app.get("/players/{player}/quality")
def player_quality(player: str):
    cfg = _resolve(player)
    rep = get_repository().load_quality(cfg.slug)
    if rep is None:
        raise HTTPException(404, "no data-quality report yet")
    return rep


DEFAULT_SAMPLE_QUESTION = "We're down 1 with 9 seconds left and they switch everything. Who takes the last shot?"


@app.get("/prompts")
def prompts(question: str = DEFAULT_SAMPLE_QUESTION):
    """The exact prompt templates every agent receives, plus how each agent's inputs differ:
    its own context package, its focus lenses, and what retrieval picks for a sample question."""
    from ..agents import prompts as P
    from ..context.builder import assemble_agent_context
    from ..context.retrieval import generate_query, retrieve

    scenario = {"question": question}
    query = generate_query(scenario)
    repo = get_repository()
    players_out = []
    for slug in DISPLAY_ORDER:
        cfg = PLAYERS[slug]
        pkg = load_package(slug)
        item = {"slug": slug, "name": cfg.full_name, "agent_name": cfg.agent_name, "lineup_slot": cfg.lineup_slot,
                "focus_areas": list(cfg.focus_areas), "data_available": pkg is not None}
        if pkg is not None:
            try:
                docs = repo.load_documents(slug)
            except Exception:  # retrieval documents are optional for this view
                docs = []
            retrieved = retrieve(docs, query, token_budget=int(config.CONTEXT_TOKEN_BUDGET * 0.35))
            _text, considered = assemble_agent_context(pkg, retrieved, config.CONTEXT_TOKEN_BUDGET)
            item.update({
                "archetypes": [a["archetype"] for a in pkg.get("basketball_archetypes", [])],
                "not_testable": [a["archetype"] for a in pkg.get("archetypes_all", []) if a["status"] == "insufficient_data"],
                "strengths": [s["label"] for s in pkg.get("strengths", [])],
                "limitations": [s["label"] for s in pkg.get("limitations", [])],
                "peak_seasons": [p["season"] for p in pkg.get("peak_seasons", [])],
                "layer1_tokens": pkg["text"]["layer1_tokens"], "layer2_tokens": pkg["text"]["layer2_tokens"],
                "context_tokens_sent": considered.get("approx_tokens"),
                "layers_sent": considered.get("layers"),
                "retrieved_for_sample": [{"title": d["title"], "score": d.get("score")} for d in retrieved],
                "layer1_text": pkg["text"]["layer1"],
            })
        players_out.append(item)
    return {
        "sample": {"question": question, "intents": query["intents"],
                   "topics": query["topics"]},
        "templates": {
            "player_system": P.PLAYER_SYSTEM, "round1": P.ROUND1_USER, "round2": P.ROUND2_USER,
            "round3": P.ROUND3_USER, "coach_system": P.COACH_SYSTEM, "coach_user": P.COACH_USER,
            "grounding_rules": P.GROUNDING_RULES, "coach_rules": P.COACH_RULES,
        },
        "models": {"player_provider": config.LLM_PROVIDER, "player_model": config.PLAYER_MODEL or "provider default (cheap tier)",
                   "coach_provider": config.COACH_PROVIDER, "coach_model": config.COACH_MODEL or "provider default (strong tier)"},
        "context_token_budget": config.CONTEXT_TOKEN_BUDGET,
        "players": players_out,
    }


@app.post("/simulations", status_code=202)
async def create_simulation(req: SimulationRequest):
    store = _store()
    scenario = req.scenario.model_dump(exclude_none=True)
    missing = [s for s in PLAYERS if load_package(s) is None]
    if missing:
        raise HTTPException(409, f"No career data for: {', '.join(missing)}. Run the data pipeline first.")
    sim_id = store.create(scenario, {"provider": req.provider, "player_model": req.player_model,
                                     "coach_provider": req.coach_provider, "coach_model": req.coach_model})

    async def runner():
        try:
            await run_simulation(scenario, store=store, sim_id=sim_id, provider=req.provider, player_model=req.player_model,
                                 coach_provider=req.coach_provider, coach_model=req.coach_model)
        except MissingDataError as e:
            store.set_status(sim_id, "failed", str(e))
        except Exception as e:  # already recorded by the orchestrator, keep the task quiet
            log.warning("simulation %s failed: %s", sim_id, e)

    t = asyncio.create_task(runner())
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)
    return {"id": sim_id, "status": "queued"}


@app.get("/simulations")
def list_simulations(limit: int = 20):
    return {"simulations": _store().list(limit)}


@app.get("/simulations/{simulation_id}")
def get_simulation(simulation_id: str):
    sim = _store().get(simulation_id)
    if sim is None:
        raise HTTPException(404, "simulation not found")
    return {**sim, "disclaimer": DISCLAIMER}
