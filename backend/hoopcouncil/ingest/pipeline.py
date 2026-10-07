"""End-to-end data pipeline.

  ingest   : fetch sources -> canonical dataset JSON (data/processed/<slug>.json)
  load     : dataset JSON  -> PostgreSQL
  derive   : DB (or files) -> aggregates, peaks, phases, archetypes, records -> DB
  validate : checks + per-player data-quality report (data/reports/)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from .. import config
from ..players import PLAYERS, PlayerConfig, get_player
from .dataset import assemble
from .http import PoliteFetcher, RateLimitedError

log = logging.getLogger(__name__)


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, default=str))


def ingest(players: list | None = None, include_gamelogs: bool = True, with_nba_stats: bool = False,
           offline: bool = False, refresh: bool = False) -> list:
    from .sources.bref import BasketballReferenceSource

    cfgs = [get_player(p) for p in (players or list(PLAYERS))]
    fetcher = PoliteFetcher(min_interval_s=config.BREF_MIN_INTERVAL_S, offline=offline, refresh=refresh)
    bref = BasketballReferenceSource(fetcher, include_gamelogs=include_gamelogs)
    log.info("collecting league-wide pages (champions, awards, league averages)")
    league = bref.collect_league()
    written = []
    for cfg in cfgs:
        log.info("collecting %s", cfg.full_name)
        try:
            frag = bref.collect_player(cfg, league)
        except RateLimitedError as e:
            log.error("%s", e)
            raise
        nba_frag = None
        if with_nba_stats:
            nba_frag = _collect_nba(cfg, frag, offline, refresh)
        ds = assemble(cfg, frag, league, nba_frag)
        out = config.PROCESSED_DIR / f"{cfg.slug}.json"
        _write_json(out, ds)
        written.append(out)
        log.info("wrote %s (%d season rows, %d game logs, %d achievements)", out, len(ds["seasons"]),
                 len(ds["game_logs"]), len(ds["achievements"]))
    return written


def _collect_nba(cfg: PlayerConfig, frag: dict, offline: bool, refresh: bool) -> dict:
    from .sources.nba_stats import HEADERS, NBAStatsSource

    fetcher = PoliteFetcher(min_interval_s=config.NBA_STATS_MIN_INTERVAL_S, offline=offline, refresh=refresh,
                            user_agent="Mozilla/5.0 (HoopCouncil research; rate limited)", extra_headers=HEADERS,
                            respect_robots=False)
    years = sorted({int(s["season"][:4]) + 1 for s in frag["seasons"] if s["stat_type"] == "regular_season"})
    src = NBAStatsSource(fetcher)
    try:
        return src.collect_player(cfg, {"player_end_years": {cfg.slug: years}})
    except RateLimitedError as e:
        log.error("NBA stats rate limited: %s", e)
        return {"errors": [str(e)]}


def load_processed(slug: str) -> dict:
    p = config.PROCESSED_DIR / f"{slug}.json"
    if not p.exists():
        raise FileNotFoundError(f"{p} missing - run `hoop ingest` first")
    return json.loads(p.read_text())


def load_to_db(players: list | None = None) -> None:
    from ..db.loader import load_dataset
    from ..db.session import init_db, session_scope

    init_db()
    for slug in [get_player(p).slug for p in (players or list(PLAYERS))]:
        ds = load_processed(slug)
        with session_scope() as s:
            load_dataset(s, ds)
        log.info("loaded %s into database", slug)


def derive_and_validate(players: list | None = None, use_db: bool = True) -> dict:
    from ..derive.run import derive_all
    from ..quality.validate import format_report, validate

    reports = {}
    for slug in [get_player(p).slug for p in (players or list(PLAYERS))]:
        if use_db:
            from ..repository import SQLRepository

            ds = SQLRepository().load_dataset(slug)
            if ds is None:
                raise RuntimeError(f"{slug} not in database - run `hoop load` first")
        else:
            ds = load_processed(slug)
        derived = derive_all(ds)
        rep = validate(ds, derived)
        _write_json(config.DATA_DIR / "derived" / f"{slug}.json", derived)
        _write_json(config.REPORTS_DIR / f"{slug}.json", rep)
        (config.REPORTS_DIR / f"{slug}.txt").write_text(format_report(rep))
        if use_db:
            from sqlalchemy import select

            from ..db import models as m
            from ..db.loader import store_derived
            from ..db.session import session_scope

            with session_scope() as s:
                player = s.scalar(select(m.Player).where(m.Player.slug == slug))
                store_derived(s, player, derived, rep)
        reports[slug] = rep
        log.info("derived + validated %s: %s", slug, rep["summary"])
    return reports
