"""Assemble source fragments into the canonical per-player dataset.

The canonical dataset (a plain dict, JSON-serialisable) is what gets loaded into
PostgreSQL. Structure:

{
  "player": {...identity / bio...},
  "seasons": [season records; stat_type regular_season|playoffs; per_game/totals/advanced/shooting/pbp],
  "career_rows_source": {stat_type: {kind: values}}   # career rows as published, for validation
  "game_logs": [...], "achievements": [...], "bling": [...], "dnp_seasons": [...],
  "league_averages": {season: {...}}, "clutch": [...], "play_types": [...], "tracking_shots": [...],
  "sources": [...], "ingest_errors": [...]
}
"""
from __future__ import annotations

from ..players import PlayerConfig
from .sources.base import provenance

ROUND_NAMES = {1: "first_round", 2: "conference_semifinals", 3: "conference_finals", 4: "nba_finals"}


def _round_from_label(label: str | None) -> str | None:
    """Map a source series label (if the game-log table provides one) to a round key."""
    if not label:
        return None
    t = label.lower()
    if "conference finals" in t or "conf finals" in t or t.strip() in ("ecf", "wcf"):
        return "conference_finals"
    if "semifinal" in t or t.strip() in ("ecs", "wcs"):
        return "conference_semifinals"
    if "first round" in t or t.strip() in ("ec1", "wc1"):
        return "first_round"
    if "finals" in t or t.strip() == "f":
        return "nba_finals"
    return None


def infer_playoff_rounds(game_logs: list, champions: list) -> None:
    """Annotate playoff games with series_index and round (in place).

    Method (documented limitation): games are grouped into series by consecutive opponent.
    Since 1983-84 the NBA playoffs have four rounds. A series is labelled 'nba_finals' only
    when the player's team is listed as champion/runner-up for that season *and* the opponent
    is the other finalist. Other rounds are numbered by order of appearance, which assumes the
    player appeared in every series; seasons where that cannot be confirmed are flagged
    `round_confidence = 'inferred'`.
    """
    finals = {c["season"]: {c["champion"], c["runner_up"]} for c in champions}
    by_season: dict = {}
    for g in game_logs:
        if g["stat_type"] == "playoffs" and g.get("status") == "played" and g.get("opponent"):
            by_season.setdefault(g["season"], []).append(g)
    for season, games in by_season.items():
        games.sort(key=lambda g: g["date"])
        series: list = []
        for g in games:
            if not series or series[-1]["opponent"] != g["opponent"]:
                series.append({"opponent": g["opponent"], "team": g["team"], "games": []})
            series[-1]["games"].append(g)
        finalists = finals.get(season, set())
        n = len(series)
        for i, s in enumerate(series):
            label = next((g.get("series_label") for g in s["games"] if g.get("series_label")), None)
            labeled = _round_from_label(label)
            if labeled:
                for g in s["games"]:
                    g["series_index"] = i + 1
                    g["playoff_round"] = labeled
                    g["round_confidence"] = "labeled"
                continue
            is_finals = bool(finalists) and s["team"] in finalists and s["opponent"] in finalists
            if is_finals:
                rnd, conf = 4, "confirmed"
            else:
                rnd = i + 1
                conf = "inferred"
                # If the team reached the Finals with 4 series logged, the ordering is fully consistent.
                last_is_finals = bool(finalists) and series[-1]["team"] in finalists and series[-1]["opponent"] in finalists
                if last_is_finals and n == 4:
                    conf = "consistent"
                if rnd >= 4:  # cannot be Finals without confirmation
                    rnd, conf = None, "unknown"
            for g in s["games"]:
                g["series_index"] = i + 1
                g["playoff_round"] = ROUND_NAMES.get(rnd) if rnd else None
                g["round_confidence"] = conf


def _achievement(player_slug, atype, season, prov, detail=None, derived_from=None):
    return {"player": player_slug, "achievement_type": atype, "season": season, "count": 1,
            "detail": detail, "derived_from": derived_from, "provenance": prov}


def build_achievements(cfg: PlayerConfig, seasons: list, league: dict, bio: dict, all_star_rows: list) -> list:
    out: dict = {}

    def add(a):
        key = (a["achievement_type"], a["season"], str(a.get("detail")) if a["achievement_type"].endswith("VOTING_FINISH") or a["achievement_type"] == "OTHER_AWARD_TOKEN" else "")
        if key in out:
            srcs = out[key].setdefault("corroborated_by", [])
            srcs.append(a["provenance"]["source_url"])
            return
        out[key] = a

    from .sources.bref import LEADER_TITLES, parse_award_tokens

    # 1) award lists (authoritative per award page)
    for a in league.get("awards", []):
        if a["bref_id"] == cfg.bref_id:
            add(_achievement(cfg.slug, a["achievement_type"], a["season"], a["provenance"], derived_from="award_page"))
    # 2) awards column on the player's season rows
    for s in seasons:
        if s["stat_type"] != "regular_season" or s.get("is_team_split"):
            continue
        for tok in parse_award_tokens(s.get("awards_text")):
            add(_achievement(cfg.slug, tok["achievement_type"], s["season"], s["provenance"],
                             detail=tok["detail"], derived_from=f"awards_column:{tok['token']}"))
        # 3) league-leader markers (bold cells) -> statistical titles
        for key in s.get("league_leader_in", []):
            if key in LEADER_TITLES:
                add(_achievement(cfg.slug, LEADER_TITLES[key], s["season"], s["provenance"],
                                 detail={"stat": key, "value": s["per_game"].get(key)},
                                 derived_from="league_leader_marker"))
    # 4) All-Star table fallback
    for r in all_star_rows:
        add(_achievement(cfg.slug, "ALL_STAR", r["season"], provenance("Basketball Reference", cfg.bref_url, bio["provenance"]["retrieved_at"], r["season"], "award"),
                         derived_from="all_star_table"))
    # 5) championships / Finals appearances / Finals MVP from the league champions list
    playoff_teams = {}
    for s in seasons:
        if s["stat_type"] == "playoffs" and not s.get("is_team_split"):
            playoff_teams[s["season"]] = set(s.get("teams") or [s["team"]])
    for c in league.get("champions", []):
        teams = playoff_teams.get(c["season"], set())
        if c["champion"] and c["champion"] in teams:
            add(_achievement(cfg.slug, "NBA_CHAMPIONSHIP", c["season"], c["provenance"], detail={"team": c["champion"]},
                             derived_from="champions_index+player_playoff_team"))
        if teams & {c["champion"], c["runner_up"]} - {None}:
            add(_achievement(cfg.slug, "NBA_FINALS_APPEARANCE", c["season"], c["provenance"],
                             detail={"result": "won" if c["champion"] in teams else "lost"},
                             derived_from="champions_index+player_playoff_team"))
        if cfg.bref_id in c.get("finals_mvp_ids", []):
            add(_achievement(cfg.slug, "NBA_FINALS_MVP", c["season"], c["provenance"], derived_from="champions_index"))
    # 6) Hall of Fame
    if bio.get("hall_of_fame_inducted"):
        add(_achievement(cfg.slug, "HALL_OF_FAME", None, bio["provenance"], detail={"inducted": bio["hall_of_fame_inducted"]},
                         derived_from="bio"))
    return sorted(out.values(), key=lambda a: (a["season"] or "", a["achievement_type"]))


def assemble(cfg: PlayerConfig, bref_frag: dict, league: dict, nba_frag: dict | None = None) -> dict:
    bio = bref_frag["bio"]
    seasons = bref_frag["seasons"]
    reg = sorted({s["season"] for s in seasons if s["stat_type"] == "regular_season"})
    from .sources.bref import COMBINED_TEAM_RE

    teams: list = []
    for s in sorted((s for s in seasons if s["stat_type"] == "regular_season"), key=lambda s: s["season"]):
        for t in s.get("teams") or [s["team"]]:
            if t and not COMBINED_TEAM_RE.match(t) and t not in teams:
                teams.append(t)
    game_logs = bref_frag.get("game_logs", [])
    infer_playoff_rounds(game_logs, league.get("champions", []))
    player = {
        "slug": cfg.slug, "full_name": bio.get("full_name") or cfg.full_name, "bref_id": cfg.bref_id,
        "nba_id": cfg.nba_id, **{k: v for k, v in bio.items() if k not in ("full_name", "bling")},
        "teams": teams, "first_season": reg[0] if reg else None, "last_season": reg[-1] if reg else None,
        "seasons_played": len(reg),
    }
    league_avgs = {s: v for s, v in league.get("league_averages", {}).items() if s in set(reg)}
    nba_frag = nba_frag or {}
    sources = [{"source": "Basketball Reference", "homepage": "https://www.basketball-reference.com",
                "tables_found": bref_frag.get("tables_found", {})}]
    if nba_frag:
        sources.append({"source": "NBA.com Stats", "homepage": "https://www.nba.com/stats"})
    return {
        "schema_version": 1,
        "player": player,
        "seasons": seasons,
        "career_rows_source": bref_frag.get("career_rows", {}),
        "game_logs": game_logs,
        "achievements": build_achievements(cfg, seasons, league, bio, bref_frag.get("all_star_rows", [])),
        "bling": [{"text": b, "provenance": bio["provenance"]} for b in bio.get("bling", [])],
        "dnp_seasons": bref_frag.get("dnp_seasons", []),
        "league_averages": league_avgs,
        "champions": [c for c in league.get("champions", []) if c["season"] in set(reg)],
        "clutch": nba_frag.get("clutch", []),
        "play_types": nba_frag.get("play_types", []),
        "tracking_shots": nba_frag.get("tracking_shots", []),
        "sources": sources,
        "ingest_errors": bref_frag.get("gamelog_errors", []) + nba_frag.get("errors", []) + league.get("errors", []),
    }
