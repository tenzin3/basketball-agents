"""Career phases: (1) team stints, (2) statistical phases from peak scores."""
from __future__ import annotations

from .aggregates import num, season_lines, summarize_lines

ROMAN = ["I", "II", "III", "IV"]
STAT_METHOD = ("Peak = contiguous span from the first to the last season with peak_score >= 0.85 x career best; "
               "Prime = seasons adjacent to the Peak span with peak_score >= 0.65 x career best "
               "(seasons under 500 minutes do not break a span); Early/Late = before/after Prime.")


def team_stints(ds: dict, player_name: str) -> list:
    lines = [l for l in ds.get("seasons", []) if l["stat_type"] == "regular_season" and (l.get("is_team_split") or len(l.get("teams") or []) <= 1)]
    lines.sort(key=lambda l: l["season"])
    stints: list = []
    for l in lines:
        team = l["team"]
        if stints and stints[-1]["team"] == team:
            if l["season"] not in stints[-1]["seasons"]:
                stints[-1]["seasons"].append(l["season"])
            continue
        stints.append({"team": team, "seasons": [l["season"]]})
    counts: dict = {}
    for s in stints:
        counts[s["team"]] = counts.get(s["team"], 0) + 1
    seen: dict = {}
    out = []
    full = {l["season"]: l for l in season_lines(ds, "regular_season")}
    for s in stints:
        seen[s["team"]] = seen.get(s["team"], 0) + 1
        suffix = f" {ROMAN[seen[s['team']] - 1]}" if counts[s["team"]] > 1 else ""
        name = f"{player_name} — {s['team']}{suffix}"
        summ = summarize_lines([full[x] for x in s["seasons"] if x in full])
        out.append({"phase_type": "team_stint", "name": name, "team": s["team"], "start_season": s["seasons"][0],
                    "end_season": s["seasons"][-1], "seasons": s["seasons"],
                    "summary": {"per_game": summ["per_game"], "shooting": summ["shooting"],
                                "advanced": {k: summ["advanced"].get(k) for k in ("usg_pct", "ast_pct", "bpm", "ws_per_48", "ts_pct")}},
                    "method": "consecutive regular-season team rows (team split rows used for traded seasons)"})
    return out


def statistical_phases(ds: dict, peak_scores: list) -> list:
    if not peak_scores:
        return []
    lines = {l["season"]: l for l in season_lines(ds, "regular_season")}
    order = [p["season"] for p in sorted(peak_scores, key=lambda p: p["season"])]
    score = {p["season"]: p["peak_score"] for p in peak_scores}
    minutes = {p["season"]: p.get("minutes") or 0 for p in peak_scores}
    best = max(score.values())
    if best <= 0:
        return []
    peak_idx = [i for i, s in enumerate(order) if score[s] >= 0.85 * best]
    lo, hi = min(peak_idx), max(peak_idx)
    p_lo, p_hi = lo, hi

    def ok_prime(i):
        s = order[i]
        return score[s] >= 0.65 * best or minutes[s] < 500

    while p_lo - 1 >= 0 and ok_prime(p_lo - 1):
        p_lo -= 1
    while p_hi + 1 < len(order) and ok_prime(p_hi + 1):
        p_hi += 1
    # trim low-minute seasons at the prime edges
    while p_lo < lo and minutes[order[p_lo]] < 500:
        p_lo += 1
    while p_hi > hi and minutes[order[p_hi]] < 500:
        p_hi -= 1
    spans = [("Early Career", 0, p_lo - 1), ("Prime", p_lo, lo - 1), ("Peak", lo, hi), ("Prime", hi + 1, p_hi),
             ("Late Career", p_hi + 1, len(order) - 1)]
    out = []
    for name, a, b in spans:
        if a > b:
            continue
        seasons = order[a:b + 1]
        summ = summarize_lines([lines[x] for x in seasons if x in lines])
        nm = name
        if name == "Prime":
            nm = "Prime (pre-peak)" if b < lo else "Prime (post-peak)"
        out.append({"phase_type": "statistical", "name": nm, "start_season": seasons[0], "end_season": seasons[-1],
                    "seasons": seasons,
                    "summary": {"per_game": summ["per_game"], "shooting": summ["shooting"],
                                "advanced": {k: summ["advanced"].get(k) for k in ("usg_pct", "ast_pct", "bpm", "ws_per_48", "ts_pct")},
                                "mean_peak_score": round(sum(score[s] for s in seasons) / len(seasons), 3)},
                    "method": STAT_METHOD})
    return out


def season_identity(ds: dict, season: str) -> dict | None:
    """Single-season identity used for season-specific questions."""
    for l in season_lines(ds, "regular_season"):
        if l["season"] == season:
            return {"season": season, "team": l.get("team"), "per_game": l.get("per_game"),
                    "advanced": l.get("advanced"), "shooting": l.get("shooting"),
                    "age": num(l.get("age"))}
    return None
