"""Read access to player data.

`SQLRepository` (default) reads PostgreSQL - the source of truth.
`FileRepository` reads the pipeline's intermediate JSON files and exists for tests and
offline development only (HOOP_STORE=files). Both return the same shapes:

  load_dataset(slug) -> canonical dataset (see ingest/dataset.py)
  load_derived(slug) -> derived results (see derive/run.py)
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from . import config


class Repository:
    def player_slugs(self) -> list:
        raise NotImplementedError

    def load_dataset(self, slug: str) -> dict | None:
        raise NotImplementedError

    def load_derived(self, slug: str) -> dict | None:
        raise NotImplementedError

    def load_quality(self, slug: str) -> dict | None:
        raise NotImplementedError

    def load_documents(self, slug: str) -> list:
        return []

    def save_documents(self, slug: str, docs: list) -> None:
        pass

    def load_package(self, slug: str) -> dict | None:
        """The built career context package, if the repository stores one (the file cache is checked first)."""
        return None

    def save_package(self, slug: str, package: dict) -> None:
        pass


class FileRepository(Repository):
    def __init__(self, base: Path | None = None):
        self.base = Path(base or config.DATA_DIR)

    def _read(self, sub: str, slug: str):
        p = self.base / sub / f"{slug}.json"
        return json.loads(p.read_text()) if p.exists() else None

    def player_slugs(self):
        d = self.base / "processed"
        return sorted(p.stem for p in d.glob("*.json")) if d.exists() else []

    def load_dataset(self, slug):
        return self._read("processed", slug)

    def load_derived(self, slug):
        return self._read("derived", slug)

    def load_quality(self, slug):
        return self._read("reports", slug)

    def load_documents(self, slug):
        return self._read("documents", slug) or []

    def save_documents(self, slug, docs):
        p = self.base / "documents" / f"{slug}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(docs))


class SQLRepository(Repository):
    def __init__(self):
        from .db.session import get_engine

        get_engine()

    def _session(self):
        from .db.session import session_scope

        return session_scope()

    def player_slugs(self):
        from sqlalchemy import select

        from .db import models as m

        with self._session() as s:
            return list(s.scalars(select(m.Player.slug).order_by(m.Player.slug)))

    def load_dataset(self, slug):
        from sqlalchemy import select

        from .db import models as m

        with self._session() as s:
            p = s.scalar(select(m.Player).where(m.Player.slug == slug))
            if p is None:
                return None
            meta = p.raw_dataset_meta or {}
            player = {k: getattr(p, k) for k in (
                "slug", "full_name", "bref_id", "nba_id", "height_in", "height_cm", "weight_lb", "weight_kg",
                "wingspan_in", "primary_position", "secondary_positions", "shoots", "birth_date", "draft_year",
                "draft_team", "draft_round", "draft_pick", "hall_of_fame_inducted", "teams", "first_season",
                "last_season", "seasons_played")}
            player["provenance"] = p.bio_provenance

            def prov(r, season=None):
                return {"source": r.source, "source_url": r.source_url, "retrieved_at": r.retrieved_at,
                        "stat_type": r.stat_type, "season": season if season is not None else getattr(r, "season", None)}

            lines = {}
            for cls, st in ((m.PlayerRegularSeasonStats, "regular_season"), (m.PlayerPlayoffStats, "playoffs")):
                for r in s.scalars(select(cls).where(cls.player_id == p.id)):
                    lines[(st, r.season, r.team)] = r
            adv = {(r.stat_type, r.season, r.team): r for r in s.scalars(select(m.PlayerAdvancedStats).where(m.PlayerAdvancedStats.player_id == p.id))}
            shot = {(r.stat_type, r.season, r.team): r for r in s.scalars(select(m.PlayerShotProfile).where(m.PlayerShotProfile.player_id == p.id))}
            seasons = []
            for r in s.scalars(select(m.PlayerSeason).where(m.PlayerSeason.player_id == p.id).order_by(m.PlayerSeason.season)):
                key = (r.stat_type, r.season, r.team)
                ln, ad, sh = lines.get(key), adv.get(key), shot.get(key)
                seasons.append({
                    "season": r.season, "stat_type": r.stat_type, "team": r.team, "team_text": r.team_text,
                    "teams": r.teams, "age": r.age, "league": r.league, "pos": r.pos, "is_combined": r.is_combined,
                    "is_team_split": r.is_team_split, "awards_text": r.awards_text,
                    "league_leader_in": r.league_leader_in or [],
                    "per_game": (ln.per_game if ln else None) or {}, "totals": (ln.totals if ln else None) or {},
                    "per_poss": (ln.per_poss if ln else None) or {}, "advanced": (ad.values if ad else None) or {},
                    "pbp": (ad.pbp if ad else None) or {}, "shooting": (sh.values if sh else None) or {},
                    "peak_score": r.peak_score, "provenance": prov(r)})
            game_logs = [{
                "season": g.season, "stat_type": g.stat_type, "date": g.game_date, "team": g.team, "opponent": g.opponent,
                "home": g.home, "result": g.result, "margin": g.margin, "status": g.status, "series_index": g.series_index,
                "playoff_round": g.playoff_round, "round_confidence": g.round_confidence, "stats": g.stats or {},
                "boxscore_url": g.boxscore_url, "provenance": prov(g)}
                for g in s.scalars(select(m.PlayerGameLog).where(m.PlayerGameLog.player_id == p.id).order_by(m.PlayerGameLog.game_date))]
            achievements = [{
                "player": slug, "achievement_type": a.achievement_type, "season": a.season, "count": a.count,
                "detail": a.detail, "derived_from": a.derived_from, "corroborated_by": a.corroborated_by,
                "provenance": prov(a)} for a in s.scalars(select(m.PlayerAchievement).where(m.PlayerAchievement.player_id == p.id))]
            reg_seasons = {x["season"] for x in seasons if x["stat_type"] == "regular_season"}
            league = {r.season: {**(r.values or {}), "provenance": prov(r)}
                      for r in s.scalars(select(m.LeagueSeasonAverage)) if r.season in reg_seasons}
            champions = [{"season": c.season, "champion": c.champion, "runner_up": c.runner_up,
                          "finals_mvp_ids": c.finals_mvp_ids, "provenance": prov(c)}
                         for c in s.scalars(select(m.LeagueChampion)) if c.season in reg_seasons]
            clutch = [{**(c.values or {}), "provenance": prov(c)} for c in s.scalars(select(m.PlayerClutchStats).where(m.PlayerClutchStats.player_id == p.id))]
            play_types = [{**(r.values or {}), "provenance": prov(r)} for r in s.scalars(select(m.PlayerPlayType).where(m.PlayerPlayType.player_id == p.id))]
            tracking = [{**(r.values or {}), "provenance": prov(r)} for r in s.scalars(select(m.PlayerTrackingShots).where(m.PlayerTrackingShots.player_id == p.id))]
            return {"schema_version": meta.get("schema_version", 1), "player": player, "seasons": seasons,
                    "career_rows_source": meta.get("career_rows_source") or {}, "game_logs": game_logs,
                    "achievements": achievements, "bling": [{"text": b, "provenance": p.bio_provenance} for b in (p.bling or [])],
                    "dnp_seasons": meta.get("dnp_seasons") or [], "playoff_series": meta.get("playoff_series") or [],
                    "collection_notes": meta.get("collection_notes") or [], "league_averages": league, "champions": champions,
                    "clutch": clutch, "play_types": play_types, "tracking_shots": tracking,
                    "sources": meta.get("sources") or [], "ingest_errors": meta.get("ingest_errors") or []}

    def load_derived(self, slug):
        from sqlalchemy import select

        from .db import models as m

        with self._session() as s:
            p = s.scalar(select(m.Player).where(m.Player.slug == slug))
            if p is None:
                return None
            prof = {r.key: r.value for r in s.scalars(select(m.PlayerDerivedProfile).where(m.PlayerDerivedProfile.player_id == p.id))}
            if not prof:
                return None
            aggs = {r.stat_type: r.values for r in s.scalars(select(m.PlayerCareerAggregate).where(
                m.PlayerCareerAggregate.player_id == p.id, m.PlayerCareerAggregate.scope == "career"))}
            phases = [{"phase_type": r.phase_type, "name": r.name, "start_season": r.start_season, "end_season": r.end_season,
                       "seasons": r.seasons, "summary": r.summary, "method": r.method}
                      for r in s.scalars(select(m.PlayerCareerPhase).where(m.PlayerCareerPhase.player_id == p.id).order_by(m.PlayerCareerPhase.id))]
            archetypes = [{"archetype": r.archetype, "status": r.status, "score": r.score, "evidence": r.evidence, "rule": r.rule}
                          for r in s.scalars(select(m.PlayerArchetype).where(m.PlayerArchetype.player_id == p.id).order_by(m.PlayerArchetype.id))]
            records = [{"kind": r.kind, "key": r.key, "label": r.label, "value": r.value, "unit": r.unit,
                        "stat_type": r.stat_type, "season": r.season, "computed_from": r.computed_from}
                       for r in s.scalars(select(m.PlayerRecord).where(m.PlayerRecord.player_id == p.id).order_by(m.PlayerRecord.id))]
            finals = [{"season": r.season, "playoff_round": r.playoff_round, "team": r.team, "opponent": r.opponent,
                       "games": r.games, "wins": r.wins, "losses": r.losses, "round_confidence": r.round_confidence,
                       "totals": r.totals, "per_game": r.per_game, "method": r.method}
                      for r in s.scalars(select(m.PlayerFinalsStats).where(m.PlayerFinalsStats.player_id == p.id).order_by(m.PlayerFinalsStats.season))]
            return {"aggregates": aggs, "finals_series": finals, "career_phases": phases, "archetypes": archetypes,
                    "records": records, "features": prof.get("features", {}), "strengths": prof.get("strengths", []),
                    "limitations": prof.get("limitations", []), "shot_profile_summary": prof.get("shot_profile_summary", {}),
                    "play_type_tendencies": prof.get("play_type_tendencies", {}), "peak_seasons": prof.get("peak_seasons", []),
                    "peak_scores": prof.get("peak_scores", []),
                    "peak_formula": (prof.get("peak_formula") or {}).get("formula")}

    def load_quality(self, slug):
        from sqlalchemy import select

        from .db import models as m

        with self._session() as s:
            p = s.scalar(select(m.Player).where(m.Player.slug == slug))
            if p is None:
                return None
            r = s.scalar(select(m.DataQualityReport).where(m.DataQualityReport.player_id == p.id)
                         .order_by(m.DataQualityReport.created_at.desc()))
            return r.report if r else None

    def load_documents(self, slug):
        from sqlalchemy import select

        from .db import models as m

        with self._session() as s:
            p = s.scalar(select(m.Player).where(m.Player.slug == slug))
            if p is None:
                return []
            return [{"doc_key": d.doc_key, "title": d.title, "topics": d.topics, "season": d.season, "text": d.text,
                     "embedding": d.embedding}
                    for d in s.scalars(select(m.CareerDocument).where(m.CareerDocument.player_id == p.id))]

    def save_documents(self, slug, docs):
        from sqlalchemy import delete, select

        from .db import models as m

        with self._session() as s:
            p = s.scalar(select(m.Player).where(m.Player.slug == slug))
            if p is None:
                return
            s.execute(delete(m.CareerDocument).where(m.CareerDocument.player_id == p.id))
            for d in docs:
                s.add(m.CareerDocument(player_id=p.id, doc_key=d["doc_key"], title=d["title"], topics=d["topics"],
                                       season=d.get("season"), text=d["text"], embedding=d.get("embedding")))


    def load_package(self, slug):
        from .db import models as m

        try:
            with self._session() as s:
                row = s.get(m.ContextPackage, slug)
                return row.package if row else None
        except Exception:  # older local database without the table
            return None

    def save_package(self, slug, package):
        import json as _json

        from .db import models as m
        from .db.session import ensure_runtime_tables

        ensure_runtime_tables()
        package = _json.loads(_json.dumps(package, default=str))  # dates etc. -> JSON-safe
        with self._session() as s:
            row = s.get(m.ContextPackage, slug)
            if row:
                row.package = package
            else:
                s.add(m.ContextPackage(slug=slug, package=package))


@lru_cache(maxsize=1)
def get_repository() -> Repository:
    if os.environ.get("HOOP_STORE", "db") == "files":
        return FileRepository()
    return SQLRepository()
