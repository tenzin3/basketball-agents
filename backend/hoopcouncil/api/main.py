"""HoopCouncil API (FastAPI).

GET  /players                       player cards
GET  /players/{player}              full profile
GET  /players/{player}/career       seasons, playoffs, aggregates, finals, shot profiles, peak scores
GET  /players/{player}/achievements structured awards
GET  /players/{player}/context      cached Career Context Package (inspection)
GET  /players/{player}/quality      data-quality report
GET  /config                        what the website needs to know (run mode, model choices, access code)
POST /simulations                   start a debate
POST /simulations/{id}/step         run the next round (step mode, used on Vercel)
GET  /simulations/{simulation_id}   poll status / transcript / coach decision
GET  /simulations                   recent simulations

Every route is also served under /api (e.g. /api/players), which is how the website reaches the backend
when both run on one Vercel domain.
"""
from __future__ import annotations

import asyncio
import logging
import os

import hmac

from fastapi import APIRouter, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .. import config
from ..context.builder import achievements_summary
from ..context.cache import load_package
from ..derive.aggregates import season_lines
from ..orchestrator import DEFAULT_LINEUP, MissingDataError, public_error, run_simulation, run_stage
from ..players import DISPLAY_ORDER, PLAYERS, get_player
from ..repository import get_repository
from .schemas import SimulationRequest

log = logging.getLogger(__name__)
app = FastAPI(title="HoopCouncil API", version="0.1.0",
              description="AI simulation based on player statistics and career tendencies.")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
router = APIRouter()
PROVIDERS = ["openrouter", "anthropic", "openai", "gemini", "local", "mock"]

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


@router.get("/health")
def health():
    return {"ok": True, "store": os.environ.get("HOOP_STORE", "db"), "llm_provider": config.LLM_PROVIDER,
            "run_mode": config.RUN_MODE}


def _allowed_providers() -> list:
    """HOOP_ALLOWED_PROVIDERS if set. Otherwise: locally everything; when hosted, only providers with a key set."""
    if config.ALLOWED_PROVIDERS:
        return [p for p in PROVIDERS if p in config.ALLOWED_PROVIDERS]
    if not os.environ.get("VERCEL"):
        return list(PROVIDERS)
    keys = {"openrouter": "OPENROUTER_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY",
            "gemini": "GEMINI_API_KEY"}
    return [p for p, k in keys.items() if os.environ.get(k)] or [config.LLM_PROVIDER]


@router.get("/config")
def site_config():
    """What the website needs before asking: how debates run, which models can be picked, whether a code is needed."""
    return {"run_mode": config.RUN_MODE, "default_provider": config.LLM_PROVIDER, "providers": _allowed_providers(),
            "access_code_required": bool(config.ACCESS_CODE), "daily_limit": config.DAILY_LIMIT or None}


async def _check_access(code: str | None) -> None:
    if config.ACCESS_CODE and not hmac.compare_digest((code or "").strip().encode(), config.ACCESS_CODE.encode()):
        await asyncio.sleep(1)  # slows down guessing
        raise HTTPException(401, "This council needs an access code. Ask the site owner for it.")


@router.get("/players")
def players():
    return {"disclaimer": DISCLAIMER, "lineup": DEFAULT_LINEUP, "players": [_card(s) for s in DISPLAY_ORDER]}


@router.get("/players/{player}")
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


@router.get("/players/{player}/career")
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


@router.get("/players/{player}/achievements")
def player_achievements(player: str):
    cfg = _resolve(player)
    ds = get_repository().load_dataset(cfg.slug)
    if ds is None:
        raise HTTPException(404, f"no data for {cfg.full_name}")
    return {"player": cfg.full_name, "summary": achievements_summary(ds["achievements"]), "achievements": ds["achievements"]}


@router.get("/players/{player}/context")
def player_context(player: str):
    cfg = _resolve(player)
    pkg = load_package(cfg.slug)
    if pkg is None:
        raise HTTPException(404, f"no context package for {cfg.full_name}")
    return pkg


@router.get("/players/{player}/quality")
def player_quality(player: str):
    cfg = _resolve(player)
    rep = get_repository().load_quality(cfg.slug)
    if rep is None:
        raise HTTPException(404, "no data-quality report yet")
    return rep


DEFAULT_SAMPLE_QUESTION = "We're down 1 with 9 seconds left and they switch everything. Who takes the last shot?"


@router.get("/prompts")
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


@router.post("/simulations", status_code=202)
async def create_simulation(req: SimulationRequest, x_access_code: str | None = Header(None)):
    await _check_access(x_access_code)
    provider = req.provider or None
    allowed = _allowed_providers()
    for p in (provider, req.coach_provider):
        if p and p not in allowed:
            raise HTTPException(400, f"The model '{p}' isn't available here. Choose one of: {', '.join(allowed)}.")
    if not provider and config.LLM_PROVIDER not in allowed:
        provider = allowed[0]
    if (req.player_model or req.coach_model) and not config.ALLOW_MODEL_OVERRIDE:
        raise HTTPException(400, "Choosing specific model names is turned off on this server.")
    store = _store()
    if config.DAILY_LIMIT and store.count_since(24) >= config.DAILY_LIMIT:
        raise HTTPException(429, "The council has answered its limit of questions for today. Please try again tomorrow.")
    scenario = req.scenario.model_dump(exclude_none=True)
    missing = [s for s in PLAYERS if load_package(s) is None]
    if missing:
        raise HTTPException(409, f"No career data for: {', '.join(missing)}. Run the data pipeline first.")
    sim_id = store.create(scenario, {"provider": provider, "player_model": req.player_model,
                                     "coach_provider": req.coach_provider or provider, "coach_model": req.coach_model})
    if config.RUN_MODE == "steps":
        # The browser calls POST /simulations/{id}/step once per round (work can't continue after a response here).
        return {"id": sim_id, "status": "queued", "run_mode": "steps"}

    async def runner():
        try:
            await run_simulation(scenario, store=store, sim_id=sim_id, provider=provider, player_model=req.player_model,
                                 coach_provider=req.coach_provider or provider, coach_model=req.coach_model)
        except MissingDataError as e:
            store.set_status(sim_id, "failed", public_error(e))
        except Exception as e:  # already recorded by the orchestrator, keep the task quiet
            log.warning("simulation %s failed: %s", sim_id, e)

    t = asyncio.create_task(runner())
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)
    return {"id": sim_id, "status": "queued", "run_mode": "background"}


@router.post("/simulations/{simulation_id}/step")
async def step_simulation(simulation_id: str, x_access_code: str | None = Header(None)):
    """Run the next stage of a debate (round 1, 2, 3 or the coach) and return the updated debate.
    If another request is already running that stage, returns straight away; the caller just polls again."""
    await _check_access(x_access_code)
    store = _store()
    if store.get(simulation_id) is None:
        raise HTTPException(404, "simulation not found")
    try:
        ran = await run_stage(store, simulation_id)
    except Exception as e:  # recorded as status=failed on the simulation
        log.warning("simulation %s step failed: %s", simulation_id, e)
        ran = None
    return {**store.get(simulation_id), "ran_stage": ran, "run_mode": config.RUN_MODE, "disclaimer": DISCLAIMER}


@router.get("/simulations")
async def list_simulations(limit: int = 20, x_access_code: str | None = Header(None)):
    """Recent questions from everyone. Off when hosted, so visitors can't read each other's questions;
    a single debate is still reachable by its unguessable id."""
    if config.HOSTED:
        raise HTTPException(404, "Not available on the hosted site.")
    await _check_access(x_access_code)
    return {"simulations": _store().list(max(1, min(limit, 100)))}


@router.get("/simulations/{simulation_id}")
def get_simulation(simulation_id: str):
    sim = _store().get(simulation_id)
    if sim is None:
        raise HTTPException(404, "simulation not found")
    return {**sim, "run_mode": config.RUN_MODE, "disclaimer": DISCLAIMER}


# Serve every route both at the root (local: http://localhost:8000/players) and under /api
# (Vercel: the website and backend share one domain, and the backend receives /api/players).
app.include_router(router)
app.include_router(router, prefix="/api")
