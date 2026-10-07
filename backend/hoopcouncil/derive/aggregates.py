"""Career aggregates computed from stored season totals and game logs.

Rules:
* regular season and playoffs are aggregated separately (never mixed);
* for traded seasons only the combined row counts (team splits are excluded);
* if a counting stat is missing for some seasons (e.g. turnovers before 1977-78), the
  aggregate is computed over the seasons that have it and flagged in `coverage`.
"""
from __future__ import annotations

COUNT_KEYS = ["g", "gs", "mp", "fg", "fga", "fg3", "fg3a", "fg2", "fg2a", "ft", "fta", "orb", "drb", "trb",
              "ast", "stl", "blk", "tov", "pf", "pts"]
ADV_WEIGHTED = ["per", "ts_pct", "usg_pct", "ast_pct", "trb_pct", "orb_pct", "drb_pct", "stl_pct", "blk_pct",
                "tov_pct", "obpm", "dbpm", "bpm", "fg3a_rate", "fta_rate"]
ADV_SUMMED = ["ows", "dws", "ws", "vorp"]


def num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def safe_div(a, b, nd=3):
    a, b = num(a), num(b)
    if a is None or not b:
        return None
    return round(a / b, nd)


def season_lines(ds: dict, stat_type: str) -> list:
    """Combined (non-split) season records for a stat type, chronological."""
    rows = [s for s in ds.get("seasons", []) if s["stat_type"] == stat_type and not s.get("is_team_split")]
    return sorted(rows, key=lambda s: s["season"])


def shooting_derived(t: dict) -> dict:
    """Percentages / efficiency from a totals-like dict."""
    fga, fta, pts = num(t.get("fga")), num(t.get("fta")), num(t.get("pts"))
    out = {
        "fg_pct": safe_div(t.get("fg"), fga),
        "fg3_pct": safe_div(t.get("fg3"), t.get("fg3a")),
        "fg2_pct": safe_div(t.get("fg2"), t.get("fg2a")),
        "ft_pct": safe_div(t.get("ft"), fta),
        "efg_pct": safe_div((num(t.get("fg")) or 0) + 0.5 * (num(t.get("fg3")) or 0), fga) if fga else None,
        "ts_pct": round(pts / (2 * (fga + 0.44 * fta)), 3) if pts is not None and fga and fta is not None else None,
        "fg3a_rate": safe_div(t.get("fg3a"), fga),
        "fta_rate": safe_div(fta, fga),
        "ast_to_tov": safe_div(t.get("ast"), t.get("tov"), 2),
    }
    return out


def aggregate_totals(lines: list, key: str = "totals") -> dict:
    totals: dict = {}
    coverage: dict = {}
    n = len(lines)
    for k in COUNT_KEYS:
        vals = [num(l.get(key, {}).get(k)) for l in lines]
        have = [v for v in vals if v is not None]
        if have:
            totals[k] = round(sum(have), 1) if any(isinstance(v, float) for v in have) else sum(have)
        missing = [l["season"] for l, v in zip(lines, vals) if v is None]
        if missing and have:
            coverage[k] = {"seasons_missing": missing, "seasons_with_data": n - len(missing)}
    # fg2/fg2a fallback from fg - fg3 when the source did not list them
    if "fg2" not in totals and "fg" in totals and "fg3" in totals:
        totals["fg2"] = totals["fg"] - totals["fg3"]
        totals["fg2a"] = totals.get("fga", 0) - totals.get("fg3a", 0)
    return {"totals": totals, "coverage": coverage}


def per_game_and_36(totals: dict, coverage: dict | None = None) -> tuple:
    coverage = coverage or {}
    g, mp = num(totals.get("g")), num(totals.get("mp"))
    per_game, per36 = {}, {}
    for k in COUNT_KEYS:
        if k in ("g", "gs") or k not in totals:
            continue
        if k in coverage:
            # partial-coverage stat: cannot divide by career games; omit rather than distort
            continue
        if g:
            per_game[f"{k}_per_g"] = round(totals[k] / g, 1)
        if mp and k != "mp":
            per36[f"{k}_per36"] = round(totals[k] / mp * 36, 1)
    return per_game, per36


def advanced_aggregate(lines: list) -> dict:
    out: dict = {}
    for k in ADV_WEIGHTED:
        pairs = [(num(l.get("advanced", {}).get(k)), num(l.get("advanced", {}).get("mp")) or num(l.get("totals", {}).get("mp")))
                 for l in lines]
        pairs = [(v, w) for v, w in pairs if v is not None and w]
        if pairs:
            out[k] = round(sum(v * w for v, w in pairs) / sum(w for _, w in pairs), 4)
    for k in ADV_SUMMED:
        vals = [num(l.get("advanced", {}).get(k)) for l in lines]
        vals = [v for v in vals if v is not None]
        if vals:
            out[k] = round(sum(vals), 1)
    mp = sum(num(l.get("advanced", {}).get("mp")) or num(l.get("totals", {}).get("mp")) or 0 for l in lines
             if num(l.get("advanced", {}).get("ws")) is not None)
    if out.get("ws") is not None and mp:
        out["ws_per_48"] = round(out["ws"] * 48 / mp, 3)
    for k in ("ortg", "drtg"):
        pairs = [(num(l.get("per_poss", {}).get(k)), num(l.get("totals", {}).get("mp"))) for l in lines]
        pairs = [(v, w) for v, w in pairs if v is not None and w]
        if pairs:
            out[k] = round(sum(v * w for v, w in pairs) / sum(w for _, w in pairs), 1)
    return out


def summarize_lines(lines: list) -> dict:
    agg = aggregate_totals(lines)
    per_game, per36 = per_game_and_36(agg["totals"], agg["coverage"])
    return {
        "seasons": [l["season"] for l in lines],
        "num_seasons": len(lines),
        "totals": agg["totals"],
        "per_game": per_game,
        "per36": per36,
        "shooting": shooting_derived(agg["totals"]),
        "advanced": advanced_aggregate(lines),
        "coverage": agg["coverage"],
        "method": "sum of combined season totals; percentages from summed makes/attempts; "
                  "advanced rates minutes-weighted; WS/VORP summed",
    }


def game_log_summary(games: list) -> dict:
    """Aggregate a list of game logs (e.g. one Finals series, or all Finals games)."""
    played = [g for g in games if g.get("status") == "played" and g.get("stats")]
    totals: dict = {}
    for k in COUNT_KEYS:
        vals = [num(g["stats"].get(k)) for g in played]
        have = [v for v in vals if v is not None]
        if have:
            totals[k] = round(sum(have), 1)
    totals["g"] = len(played)
    per_game = {f"{k}_per_g": round(v / len(played), 1) for k, v in totals.items() if k not in ("g", "gs") and played}
    wins = sum(1 for g in played if g.get("result") == "W")
    losses = sum(1 for g in played if g.get("result") == "L")
    return {"games": len(played), "wins": wins, "losses": losses, "totals": totals, "per_game": per_game,
            "shooting": shooting_derived(totals)}


def finals_series(ds: dict) -> list:
    """Per-series aggregates for conference finals and NBA Finals, from playoff game logs."""
    series: dict = {}
    for g in ds.get("game_logs", []):
        rnd = g.get("playoff_round")
        if g["stat_type"] != "playoffs" or rnd not in ("nba_finals", "conference_finals"):
            continue
        series.setdefault((g["season"], rnd), []).append(g)
    out = []
    for (season, rnd), games in sorted(series.items()):
        s = game_log_summary(games)
        played = [g for g in games if g.get("status") == "played"]
        out.append({"season": season, "playoff_round": rnd, "team": played[0]["team"] if played else None,
                    "opponent": played[0]["opponent"] if played else None,
                    "round_confidence": games[0].get("round_confidence"), **s,
                    "provenance": games[0]["provenance"],
                    "method": "aggregated from Basketball Reference playoff game logs; round inferred "
                              "(see ingest.dataset.infer_playoff_rounds)"})
    return out


def career_aggregates(ds: dict) -> dict:
    reg = season_lines(ds, "regular_season")
    po = season_lines(ds, "playoffs")
    out = {"regular_season": summarize_lines(reg), "playoffs": summarize_lines(po)}
    for rnd in ("nba_finals", "conference_finals"):
        games = [g for g in ds.get("game_logs", []) if g["stat_type"] == "playoffs" and g.get("playoff_round") == rnd]
        if games:
            s = game_log_summary(games)
            s["series"] = len({g["season"] for g in games})
            s["method"] = "aggregated from playoff game logs with inferred round labels"
            per36 = {}
            mp = s["totals"].get("mp")
            if mp:
                per36 = {f"{k}_per36": round(v / mp * 36, 1) for k, v in s["totals"].items() if k not in ("g", "gs", "mp")}
            s["per36"] = per36
            out[rnd] = s
    return out
