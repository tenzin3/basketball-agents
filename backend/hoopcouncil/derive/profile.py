"""Strengths, limitations, shot-profile summary and milestones (raw facts only)."""
from __future__ import annotations

from collections import Counter

from .aggregates import num, season_lines


def _p(x):
    return f"{x * 100:.1f}%" if isinstance(x, (int, float)) else "n/a"


def strengths_and_limitations(f: dict, agg: dict) -> tuple:
    s, l = [], []

    def add(lst, label, evidence, metric, value):
        lst.append({"label": label, "evidence": evidence, "metric": metric, "value": value})

    rts, usg = f.get("rel_ts_pct"), f.get("usg_pct")
    if rts is not None:
        if rts >= 0.03:
            add(s, "Scoring efficiency above league average", f"TS% {rts * 100:+.1f} pts vs league (minutes-weighted)", "rel_ts_pct", rts)
        elif rts <= -0.01:
            add(l, "Scoring efficiency below league average", f"TS% {rts * 100:+.1f} pts vs league", "rel_ts_pct", rts)
    rft = f.get("rel_ft_pct")
    if rft is not None:
        if rft >= 0.07:
            add(s, "Free-throw shooting", f"FT% {_p(f.get('ft_pct'))}, {rft * 100:+.1f} pts vs league", "rel_ft_pct", rft)
        elif rft <= -0.03:
            add(l, "Free-throw shooting", f"FT% {_p(f.get('ft_pct'))}, {rft * 100:+.1f} pts vs league", "rel_ft_pct", rft)
    r3p, r3a = f.get("rel_fg3_pct"), f.get("rel_fg3a_rate")
    if r3p is not None and r3a is not None:
        if r3p >= 0.03 and r3a >= 1.0:
            add(s, "Three-point shooting (volume and accuracy)", f"3P% {r3p * 100:+.1f} pts vs league at {r3a:.2f}x league 3PA rate", "rel_fg3_pct", r3p)
        elif r3a < 0.6 or r3p <= -0.02:
            add(l, "Three-point volume/accuracy relative to era", f"3PA rate {r3a:.2f}x league, 3P% {r3p * 100:+.1f} pts", "rel_fg3a_rate", r3a)
    ast = f.get("ast_pct")
    if ast is not None and ast >= 0.30:
        add(s, "Playmaking", f"career AST% {_p(ast)}", "ast_pct", ast)
    tov = f.get("tov_pct")
    if tov is not None:
        if tov <= 0.10 and (usg or 0) >= 0.25:
            add(s, "Ball security at high usage", f"TOV% {_p(tov)} at USG% {_p(usg)}", "tov_pct", tov)
        elif tov >= 0.14:
            add(l, "Turnover rate", f"TOV% {_p(tov)}", "tov_pct", tov)
    for k, thr, label in (("stl_pct", 0.02, "Steal rate"), ("blk_pct", 0.02, "Shot blocking"), ("trb_pct", 0.12, "Rebounding")):
        v = f.get(k)
        if v is not None and v >= thr:
            add(s, label, f"career {k.replace('_pct', '').upper()}% {_p(v)}", k, v)
    db = f.get("dbpm")
    if db is not None:
        if db >= 1.0:
            add(s, "Defensive box impact", f"career DBPM {db:+.1f}", "dbpm", db)
        elif db <= -1.0:
            add(l, "Defensive box impact", f"career DBPM {db:+.1f}", "dbpm", db)
    gps = f.get("avg_games_per_season")
    if gps is not None:
        if gps >= 72:
            add(s, "Availability", f"{gps} games per season on average", "avg_games_per_season", gps)
        if len(f.get("seasons_under_50_games", [])) >= 3:
            add(l, "Availability", f"seasons under 50 games: {', '.join(f['seasons_under_50_games'])}", "seasons_under_50_games",
                len(f["seasons_under_50_games"]))
    reg_ts = (agg.get("regular_season") or {}).get("shooting", {}).get("ts_pct")
    po_ts = (agg.get("playoffs") or {}).get("shooting", {}).get("ts_pct")
    if reg_ts and po_ts:
        d = po_ts - reg_ts
        if d >= 0.0:
            add(s, "Playoff efficiency held up", f"playoff TS% {_p(po_ts)} vs regular season {_p(reg_ts)}", "playoff_ts_delta", round(d, 3))
        elif d <= -0.03:
            add(l, "Playoff efficiency drop", f"playoff TS% {_p(po_ts)} vs regular season {_p(reg_ts)}", "playoff_ts_delta", round(d, 3))
    return s, l


def shot_profile_summary(f: dict, ds: dict) -> dict:
    """Career shot-profile summary with spec field names; null when not sourced."""
    tr = f.get("tracking") or {}
    cs = tr.get("GeneralShooting:Catch and Shoot")
    pu = tr.get("GeneralShooting:Pull Ups")
    cov = f.get("coverage", {}).get("rim_share", {})
    seasons_with = [l["season"] for l in season_lines(ds, "regular_season") if l.get("shooting")]
    return {
        "rim_frequency": f.get("rim_share"), "short_midrange_frequency": f.get("short_mid_share"),
        "midrange_frequency": f.get("mid_share"), "long_midrange_frequency": f.get("long_mid_share"),
        "three_point_frequency": f.get("three_share"), "corner_three_share_of_3pa": f.get("corner3_share_of_3pa"),
        "rim_fg_pct": f.get("rim_fg_pct"), "midrange_fg_pct": f.get("midrange_fg_pct"),
        "corner_three_fg_pct": f.get("corner3_fg_pct"), "assisted_share_2p": f.get("assisted_share_2p"),
        "assisted_share_3p": f.get("assisted_share_3p"), "avg_shot_distance_ft": f.get("avg_shot_distance_ft"),
        "catch_and_shoot_frequency": cs["fga_frequency"] if cs else None,
        "pull_up_frequency": pu["fga_frequency"] if pu else None,
        "isolation_frequency": (f.get("play_types") or {}).get("Isolation", {}).get("frequency"),
        "post_up_frequency": (f.get("play_types") or {}).get("Postup", {}).get("frequency"),
        "transition_frequency": (f.get("play_types") or {}).get("Transition", {}).get("frequency"),
        "late_clock_frequency": (tr.get("ShotClockShooting:4-0 Very Late") or {}).get("fga_frequency"),
        "seasons_with_shot_distance_data": seasons_with,
        "coverage_note": f"shot-distance data for {cov.get('seasons', 0)} of {cov.get('of', 0)} regular seasons "
                         "(Basketball Reference shot tracking starts 1996-97; tracking/Synergy from 2013-14/2015-16)",
        "method": "minutes-weighted averages of season values",
    }


def milestones(ds: dict, agg: dict, achievements: list) -> list:
    """Raw statistical facts computed from stored data. No interpretation."""
    out = []

    def fact(key, label, value, unit, stat_type, computed_from, season=None):
        if value is None:
            return
        out.append({"kind": "fact", "key": key, "label": label, "value": value, "unit": unit,
                    "stat_type": stat_type, "season": season, "computed_from": computed_from})

    for st in ("regular_season", "playoffs"):
        t = (agg.get(st) or {}).get("totals", {})
        for k, lab in (("pts", "points"), ("trb", "rebounds"), ("ast", "assists"), ("stl", "steals"),
                       ("blk", "blocks"), ("fg3", "three-pointers made"), ("g", "games"), ("mp", "minutes")):
            if k in t:
                cov = (agg.get(st) or {}).get("coverage", {}).get(k)
                note = f" (seasons with data: {cov['seasons_with_data']})" if cov else ""
                fact(f"career_{st}_{k}", f"Career {st.replace('_', ' ')} {lab}{note}", t[k], lab, st, "sum of season totals")
    c = Counter(a["achievement_type"] for a in achievements)
    for k, lab in (("NBA_CHAMPIONSHIP", "NBA championships"), ("NBA_FINALS_APPEARANCE", "NBA Finals appearances"),
                   ("NBA_MVP", "MVP awards"), ("NBA_FINALS_MVP", "Finals MVP awards"), ("ALL_STAR", "All-Star selections"),
                   ("SCORING_TITLE", "scoring titles (league-leader marker)")):
        if c.get(k):
            fact(f"count_{k.lower()}", lab[0].upper() + lab[1:], c[k], "count", None, "count of player_achievements rows")
    for st in ("regular_season", "playoffs"):
        games = [g for g in ds.get("game_logs", []) if g["stat_type"] == st and g.get("status") == "played" and g.get("stats")]
        if not games:
            continue
        best = max(games, key=lambda g: num(g["stats"].get("pts")) or -1)
        fact(f"career_high_pts_{st}", f"Career-high points in a {st.replace('_', ' ')} game ({best['date']} vs {best['opponent']})",
             best["stats"].get("pts"), "points", st, "max over stored game logs", best["season"])
        for thr in (40, 50):
            n = sum(1 for g in games if (num(g["stats"].get("pts")) or 0) >= thr)
            fact(f"games_{thr}plus_{st}", f"{thr}+ point {st.replace('_', ' ')} games", n, "games", st, "count over stored game logs")
        if st == "playoffs":
            w = sum(1 for g in games if g.get("result") == "W")
            fact("playoff_wins_played", "Playoff wins in games played", w, "games", st, "count of W results in played playoff game logs")
    reg = season_lines(ds, "regular_season")
    n30 = [l["season"] for l in reg if (num(l.get("per_game", {}).get("pts_per_g")) or 0) >= 30]
    fact("seasons_30ppg", "Seasons averaging 30+ points", len(n30), "seasons", "regular_season", "per-game rows")
    return out
