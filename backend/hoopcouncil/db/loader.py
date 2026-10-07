"""Write canonical datasets and derived results into the database (idempotent per player)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, select

from . import models as m

SEASON_CHILD_TABLES = [m.PlayerRegularSeasonStats, m.PlayerPlayoffStats, m.PlayerAdvancedStats, m.PlayerShotProfile,
                       m.PlayerGameLog, m.PlayerAchievement, m.PlayerClutchStats, m.PlayerPlayType,
                       m.PlayerTrackingShots, m.PlayerSeason]
DERIVED_TABLES = [m.PlayerFinalsStats, m.PlayerCareerAggregate, m.PlayerCareerPhase, m.PlayerArchetype,
                  m.PlayerDerivedProfile, m.PlayerRecord]

STATLINE_COLS = ["g", "gs", "mp_per_g", "pts_per_g", "trb_per_g", "ast_per_g", "stl_per_g", "blk_per_g", "tov_per_g",
                 "fga_per_g", "fg_pct", "fg2a_per_g", "fg2_pct", "fg3a_per_g", "fg3_pct", "fta_per_g", "ft_pct", "efg_pct"]
ADV_COLS = ["per", "ts_pct", "usg_pct", "ast_pct", "trb_pct", "tov_pct", "stl_pct", "blk_pct", "ows", "dws", "ws",
            "ws_per_48", "obpm", "dbpm", "bpm", "vorp"]


def _prov(p: dict | None) -> dict:
    p = p or {}
    return {"source": p.get("source"), "source_url": p.get("source_url"), "retrieved_at": p.get("retrieved_at"),
            "stat_type": p.get("stat_type")}


def _n(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def upsert_player(session, ds: dict) -> m.Player:
    p = ds["player"]
    player = session.scalar(select(m.Player).where(m.Player.slug == p["slug"]))
    if player is None:
        player = m.Player(slug=p["slug"], full_name=p["full_name"])
        session.add(player)
        session.flush()
    for k in ("full_name", "bref_id", "nba_id", "height_in", "height_cm", "weight_lb", "weight_kg", "wingspan_in",
              "primary_position", "secondary_positions", "shoots", "birth_date", "draft_year", "draft_team",
              "draft_round", "draft_pick", "hall_of_fame_inducted", "teams", "first_season", "last_season",
              "seasons_played"):
        setattr(player, k, p.get(k))
    player.bio_provenance = p.get("provenance")
    player.bling = [b["text"] for b in ds.get("bling", [])]
    player.raw_dataset_meta = {"sources": ds.get("sources"), "ingest_errors": ds.get("ingest_errors"),
                               "dnp_seasons": ds.get("dnp_seasons"), "career_rows_source": ds.get("career_rows_source"),
                               "schema_version": ds.get("schema_version")}
    return player


def load_dataset(session, ds: dict) -> m.Player:
    player = upsert_player(session, ds)
    pid = player.id
    for t in SEASON_CHILD_TABLES:
        session.execute(delete(t).where(t.player_id == pid))
    for s in ds.get("seasons", []):
        prov = _prov(s.get("provenance"))
        session.add(m.PlayerSeason(
            player_id=pid, season=s["season"], team=s.get("team"), team_text=s.get("team_text"), teams=s.get("teams"),
            age=_n(s.get("age")), league=s.get("league"), pos=s.get("pos"), is_combined=bool(s.get("is_combined")),
            is_team_split=bool(s.get("is_team_split")), awards_text=s.get("awards_text"),
            league_leader_in=s.get("league_leader_in"), **prov))
        cls = m.PlayerRegularSeasonStats if s["stat_type"] == "regular_season" else m.PlayerPlayoffStats
        pg = s.get("per_game") or {}
        line = cls(player_id=pid, season=s["season"], team=s.get("team"), is_combined=not s.get("is_team_split"),
                   per_game=pg, totals=s.get("totals"), per_poss=s.get("per_poss"), **prov)
        for c in STATLINE_COLS:
            setattr(line, c, _n(pg.get(c)))
        session.add(line)
        if s.get("advanced") or s.get("pbp"):
            adv = s.get("advanced") or {}
            a = m.PlayerAdvancedStats(player_id=pid, season=s["season"], team=s.get("team"),
                                      is_combined=not s.get("is_team_split"), values=adv, pbp=s.get("pbp"),
                                      ortg=_n((s.get("per_poss") or {}).get("ortg")),
                                      drtg=_n((s.get("per_poss") or {}).get("drtg")), **prov)
            for c in ADV_COLS:
                setattr(a, c, _n(adv.get(c)))
            session.add(a)
        sh = s.get("shooting") or {}
        if sh:
            def sm(*ks):
                vals = [_n(sh.get(k)) for k in ks]
                return None if any(v is None for v in vals) else round(sum(vals), 4)
            a10, b16 = _n(sh.get("fga_share_10_16")), _n(sh.get("fga_share_16_3p"))
            p10, p16 = _n(sh.get("fg_pct_10_16")), _n(sh.get("fg_pct_16_3p"))
            mid_pct = round((a10 * p10 + b16 * p16) / (a10 + b16), 4) if None not in (a10, b16, p10, p16) and (a10 + b16) else None
            session.add(m.PlayerShotProfile(
                player_id=pid, season=s["season"], team=s.get("team"), values=sh,
                avg_shot_distance_ft=_n(sh.get("avg_shot_distance_ft")), rim_frequency=_n(sh.get("fga_share_0_3")),
                short_midrange_frequency=_n(sh.get("fga_share_3_10")), midrange_frequency=sm("fga_share_10_16", "fga_share_16_3p"),
                long_midrange_frequency=_n(sh.get("fga_share_16_3p")), three_point_frequency=_n(sh.get("fga_share_3p")),
                corner_three_share_of_3pa=_n(sh.get("corner3_share_of_3pa")), rim_fg_pct=_n(sh.get("fg_pct_0_3")),
                midrange_fg_pct=mid_pct, three_fg_pct=_n(sh.get("fg_pct_3p")), corner_three_fg_pct=_n(sh.get("corner3_fg_pct")),
                assisted_share_2p=_n(sh.get("assisted_share_2p")), assisted_share_3p=_n(sh.get("assisted_share_3p")), **prov))
    for g in ds.get("game_logs", []):
        st = g.get("stats") or {}
        session.add(m.PlayerGameLog(
            player_id=pid, season=g["season"], game_date=g["date"], team=g.get("team"), opponent=g.get("opponent"),
            home=g.get("home"), result=g.get("result"), margin=g.get("margin"), status=g.get("status"),
            series_index=g.get("series_index"), playoff_round=g.get("playoff_round"),
            round_confidence=g.get("round_confidence"), mp=_n(st.get("mp")), pts=_n(st.get("pts")), trb=_n(st.get("trb")),
            ast=_n(st.get("ast")), fg=_n(st.get("fg")), fga=_n(st.get("fga")), fg3=_n(st.get("fg3")),
            fg3a=_n(st.get("fg3a")), ft=_n(st.get("ft")), fta=_n(st.get("fta")), stats=st,
            boxscore_url=g.get("boxscore_url"), **_prov(g.get("provenance"))))
    for a in ds.get("achievements", []):
        session.add(m.PlayerAchievement(player_id=pid, achievement_type=a["achievement_type"], season=a.get("season"),
                                        count=a.get("count", 1), detail=a.get("detail"), derived_from=a.get("derived_from"),
                                        corroborated_by=a.get("corroborated_by"), **_prov(a.get("provenance"))))
    for c in ds.get("clutch", []):
        session.add(m.PlayerClutchStats(player_id=pid, season=c["season"], definition=c.get("definition"),
                                        gp=_n(c.get("gp")), minutes=_n(c.get("minutes")), pts=_n(c.get("pts")),
                                        fga=_n(c.get("fga")), fg_pct=_n(c.get("fg_pct")), fg3a=_n(c.get("fg3a")),
                                        fg3_pct=_n(c.get("fg3_pct")), fta=_n(c.get("fta")), ft_pct=_n(c.get("ft_pct")),
                                        ast=_n(c.get("ast")), tov=_n(c.get("tov")), plus_minus=_n(c.get("plus_minus")),
                                        values={k: v for k, v in c.items() if k != "provenance"}, **_prov(c.get("provenance"))))
    for r in ds.get("play_types", []):
        session.add(m.PlayerPlayType(player_id=pid, season=r["season"], play_type=r["play_type"],
                                     frequency=_n(r.get("frequency")), ppp=_n(r.get("ppp")), percentile=_n(r.get("percentile")),
                                     possessions=_n(r.get("possessions")),
                                     values={k: v for k, v in r.items() if k != "provenance"}, **_prov(r.get("provenance"))))
    for r in ds.get("tracking_shots", []):
        session.add(m.PlayerTrackingShots(player_id=pid, season=r["season"], category=r["category"], label=r.get("label"),
                                          values={k: v for k, v in r.items() if k != "provenance"}, **_prov(r.get("provenance"))))
    for season, vals in ds.get("league_averages", {}).items():
        row = session.scalar(select(m.LeagueSeasonAverage).where(m.LeagueSeasonAverage.season == season))
        v = {k: x for k, x in vals.items() if k != "provenance"}
        if row is None:
            session.add(m.LeagueSeasonAverage(season=season, values=v, **_prov(vals.get("provenance"))))
        else:
            row.values = v
    for c in ds.get("champions", []):
        row = session.scalar(select(m.LeagueChampion).where(m.LeagueChampion.season == c["season"]))
        if row is None:
            session.add(m.LeagueChampion(season=c["season"], champion=c.get("champion"), runner_up=c.get("runner_up"),
                                         finals_mvp_ids=c.get("finals_mvp_ids"), **_prov(c.get("provenance"))))
    for src in ds.get("sources", []):
        row = session.scalar(select(m.DataSource).where(m.DataSource.name == src["source"]))
        if row is None:
            row = m.DataSource(name=src["source"], homepage=src.get("homepage"))
            session.add(row)
        row.last_run_at = datetime.now(timezone.utc)
        row.notes = {"tables_found": src.get("tables_found")}
    session.flush()
    return player


def store_derived(session, player: m.Player, derived: dict, quality: dict | None = None) -> None:
    pid = player.id
    for t in DERIVED_TABLES:
        session.execute(delete(t).where(t.player_id == pid))
    for st, vals in derived["aggregates"].items():
        session.add(m.PlayerCareerAggregate(player_id=pid, scope="career", stat_type=st, values=vals, method=vals.get("method")))
    for ph in derived["career_phases"]:
        session.add(m.PlayerCareerPhase(player_id=pid, phase_type=ph["phase_type"], name=ph["name"],
                                        start_season=ph["start_season"], end_season=ph["end_season"],
                                        seasons=ph["seasons"], summary=ph.get("summary"), method=ph.get("method")))
    for fs in derived["finals_series"]:
        session.add(m.PlayerFinalsStats(player_id=pid, season=fs["season"], playoff_round=fs["playoff_round"],
                                        team=fs.get("team"), opponent=fs.get("opponent"), games=fs["games"],
                                        wins=fs.get("wins"), losses=fs.get("losses"), round_confidence=fs.get("round_confidence"),
                                        totals=fs.get("totals"), per_game=fs.get("per_game"), method=fs.get("method"),
                                        **_prov(fs.get("provenance"))))
    for a in derived["archetypes"]:
        session.add(m.PlayerArchetype(player_id=pid, archetype=a["archetype"], status=a["status"], score=a.get("score"),
                                      evidence=a.get("evidence"), rule=a.get("rule")))
    for r in derived["records"]:
        session.add(m.PlayerRecord(player_id=pid, kind=r["kind"], key=r["key"], label=r["label"], value=r["value"],
                                   unit=r.get("unit"), stat_type=r.get("stat_type"), season=r.get("season"),
                                   computed_from=r.get("computed_from")))
    for key in ("features", "strengths", "limitations", "shot_profile_summary", "play_type_tendencies",
                "peak_seasons", "peak_formula", "peak_scores"):
        session.add(m.PlayerDerivedProfile(player_id=pid, key=key, value=derived[key] if key != "peak_formula" else {"formula": derived[key]}))
    scores = {p["season"]: p for p in derived["peak_scores"]}
    for row in session.scalars(select(m.PlayerSeason).where(m.PlayerSeason.player_id == pid,
                                                             m.PlayerSeason.stat_type == "regular_season")):
        if not row.is_team_split and row.season in scores:
            row.peak_score = scores[row.season]["peak_score"]
            row.peak_components = scores[row.season]
    if quality is not None:
        session.add(m.DataQualityReport(player_id=pid, report=quality))
    session.flush()
