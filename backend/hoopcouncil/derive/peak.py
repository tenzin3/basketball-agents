"""Data-driven peak-season detection. The formula is documented in docs/peak_score.md.

peak_score = sqrt(availability) * (0.35*impact + 0.15*scoring + 0.15*efficiency
                                   + 0.15*playoffs + 0.20*recognition)

All components are clipped to [0, 1] on fixed (cross-player) scales, so scores are
comparable between players. Awards contribute at most 20%, so a season cannot be a
peak on awards alone.
"""
from __future__ import annotations

from collections import defaultdict

from .aggregates import num, season_lines

WEIGHTS = {"impact": 0.35, "scoring": 0.15, "efficiency": 0.15, "playoffs": 0.15, "recognition": 0.20}
RECOGNITION_POINTS = {
    "NBA_MVP": 0.60, "NBA_FINALS_MVP": 0.40, "NBA_CHAMPIONSHIP": 0.25, "ALL_NBA_FIRST": 0.35,
    "ALL_NBA_SECOND": 0.20, "ALL_NBA_THIRD": 0.10, "SCORING_TITLE": 0.15, "DEFENSIVE_PLAYER_OF_THE_YEAR": 0.20,
    "ALL_DEFENSIVE_FIRST": 0.10, "ALL_DEFENSIVE_SECOND": 0.05,
}
FORMULA = ("peak_score = sqrt(min(1, MP/2800)) * (0.35*impact + 0.15*scoring + 0.15*efficiency + "
           "0.15*playoffs + 0.20*recognition); impact = mean(clip((BPM+2)/14), clip(WS48/0.30), "
           "clip((PER-10)/22)); scoring = clip((PPG-10)/25); efficiency = clip((TS - leagueTS + 0.02)/0.10); "
           "playoffs = mean(clip((pBPM+2)/14), clip(pWS48/0.30)) * min(1, playoff G/16); "
           "recognition = min(1, sum of award points: MVP .60, Finals MVP .40, title .25, All-NBA 1st/2nd/3rd "
           ".35/.20/.10, scoring title .15, DPOY .20, All-Def 1st/2nd .10/.05, MVP vote 2nd-5th .15)")


def clip(x: float) -> float:
    return max(0.0, min(1.0, x))


def _mean(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def season_components(line: dict, playoff_line: dict | None, league: dict | None, awards: list) -> dict:
    adv, pg, tot = line.get("advanced", {}), line.get("per_game", {}), line.get("totals", {})
    bpm, ws48, per = num(adv.get("bpm")), num(adv.get("ws_per_48")), num(adv.get("per"))
    impact = _mean([clip((bpm + 2) / 14) if bpm is not None else None,
                    clip(ws48 / 0.30) if ws48 is not None else None,
                    clip((per - 10) / 22) if per is not None else None])
    ppg = num(pg.get("pts_per_g"))
    scoring = clip((ppg - 10) / 25) if ppg is not None else None
    ts = num(adv.get("ts_pct"))
    lts = num((league or {}).get("ts_pct"))
    if ts is not None and lts is not None:
        efficiency = clip((ts - lts + 0.02) / 0.10)
        eff_basis = "relative to league TS%"
    elif ts is not None:
        efficiency = clip((ts - 0.50) / 0.15)
        eff_basis = "absolute TS% (league average unavailable)"
    else:
        efficiency, eff_basis = None, "missing"
    playoffs = 0.0
    if playoff_line:
        padv = playoff_line.get("advanced", {})
        pg_g = num(playoff_line.get("per_game", {}).get("g")) or num(playoff_line.get("totals", {}).get("g")) or 0
        pb, pw = num(padv.get("bpm")), num(padv.get("ws_per_48"))
        m = _mean([clip((pb + 2) / 14) if pb is not None else None, clip(pw / 0.30) if pw is not None else None])
        playoffs = (m or 0.0) * min(1.0, pg_g / 16)
    rec = 0.0
    for a in awards:
        t = a["achievement_type"]
        if t in RECOGNITION_POINTS:
            rec += RECOGNITION_POINTS[t]
        elif t == "NBA_MVP_VOTING_FINISH" and (a.get("detail") or {}).get("rank") in (2, 3, 4, 5):
            rec += 0.15
    recognition = clip(rec)
    mp = num(tot.get("mp")) or num(adv.get("mp")) or 0
    availability = clip(mp / 2800)
    comps = {"impact": impact, "scoring": scoring, "efficiency": efficiency, "playoffs": playoffs,
             "recognition": recognition}
    base = sum(WEIGHTS[k] * (v if v is not None else 0.0) for k, v in comps.items())
    missing = [k for k, v in comps.items() if v is None]
    score = round((availability ** 0.5) * base, 3)
    return {"peak_score": score, "components": {k: (round(v, 3) if v is not None else None) for k, v in comps.items()},
            "availability": round(availability, 3), "minutes": mp, "efficiency_basis": eff_basis,
            "missing_components": missing}


def compute_peak_scores(ds: dict) -> list:
    reg = season_lines(ds, "regular_season")
    po = {l["season"]: l for l in season_lines(ds, "playoffs")}
    by_season = defaultdict(list)
    for a in ds.get("achievements", []):
        if a.get("season"):
            by_season[a["season"]].append(a)
    out = []
    for l in reg:
        r = season_components(l, po.get(l["season"]), ds.get("league_averages", {}).get(l["season"]), by_season[l["season"]])
        out.append({"season": l["season"], **r})
    # within-career rank
    ranked = sorted(out, key=lambda r: -r["peak_score"])
    for i, r in enumerate(ranked, 1):
        r["career_rank"] = i
    return out


def select_peak_seasons(scores: list, max_n: int = 5) -> list:
    """Peak seasons: score >= max(0.55, 0.85 * career best), at most max_n, best first."""
    if not scores:
        return []
    best = max(r["peak_score"] for r in scores)
    thr = max(0.55, 0.85 * best)
    peaks = [r for r in scores if r["peak_score"] >= thr]
    if not peaks:  # always surface the best season, flagged
        peaks = [max(scores, key=lambda r: r["peak_score"])]
    return sorted(peaks, key=lambda r: -r["peak_score"])[:max_n]
