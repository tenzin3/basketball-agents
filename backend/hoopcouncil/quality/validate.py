"""Data validation and per-player data-quality reports.

Checks (each yields PASS / WARN / FAIL with details):
  * career totals ~= sum of season totals (vs the source's own career row)
  * regular season and playoff data are never mixed
  * game-log games per season match season G
  * award counts match individual award records (vs the source's summary badges)
  * seasons are chronologically valid
  * percentages fall in [0, 1]; makes <= attempts; no negative counts
Missing data is reported, never filled in.
"""
from __future__ import annotations

import re
from collections import Counter

from ..derive.aggregates import COUNT_KEYS, aggregate_totals, num, season_lines

PCT_KEY = re.compile(r"(_pct|_share|_rate|_frequency)(_|$)")


def _check(name, status, detail):
    return {"check": name, "status": status, "detail": detail}


def check_career_totals(ds: dict) -> list:
    out = []
    for st in ("regular_season", "playoffs"):
        lines = season_lines(ds, st)
        src = (ds.get("career_rows_source", {}).get(st) or {}).get("totals")
        if not lines:
            out.append(_check(f"career_totals[{st}]", "WARN", "no season rows"))
            continue
        if not src:
            out.append(_check(f"career_totals[{st}]", "WARN", "source career totals row not found; cannot cross-check"))
            continue
        mine = aggregate_totals(lines)["totals"]
        diffs = {}
        for k in COUNT_KEYS:
            a, b = num(mine.get(k)), num(src.get(k))
            if a is None or b is None:
                continue
            tol = max(1.0, abs(b) * 0.005)
            if abs(a - b) > tol:
                diffs[k] = {"sum_of_seasons": a, "source_career": b}
        out.append(_check(f"career_totals[{st}]", "FAIL" if diffs else "PASS", diffs or "sum of seasons matches source career row"))
    return out


def check_not_mixed(ds: dict) -> list:
    out = []
    keys = Counter((s["stat_type"], s["season"], s["team"]) for s in ds.get("seasons", []))
    dup = [k for k, c in keys.items() if c > 1]
    out.append(_check("unique_season_rows", "FAIL" if dup else "PASS", dup or "one row per (stat_type, season, team)"))
    bad_types = sorted({s["stat_type"] for s in ds.get("seasons", [])} - {"regular_season", "playoffs"})
    out.append(_check("stat_type_values", "FAIL" if bad_types else "PASS", bad_types or "only regular_season/playoffs"))
    bad_dates = []
    for g in ds.get("game_logs", []):
        m = int(g["date"][5:7])
        if g["stat_type"] == "playoffs" and m in (11, 12, 1, 2, 3):
            bad_dates.append(g["date"])
    out.append(_check("playoff_game_dates", "FAIL" if bad_dates else "PASS", bad_dates[:10] or "playoff games fall in Apr-Oct"))
    return out


def check_gamelogs(ds: dict) -> list:
    out = []
    logs = ds.get("game_logs", [])
    if not logs:
        return [_check("gamelog_counts", "WARN", "no game logs stored")]
    for st in ("regular_season", "playoffs"):
        if not any(g["stat_type"] == st for g in logs):
            note = "; ".join(ds.get("collection_notes", [])) or "none stored"
            out.append(_check(f"gamelog_counts[{st}]", "PASS", f"not collected ({note})"))
            continue
        played = Counter(g["season"] for g in logs if g["stat_type"] == st and g.get("status") == "played")
        mism = {}
        for l in season_lines(ds, st):
            g = num(l.get("per_game", {}).get("g"))
            if g is not None and played.get(l["season"], 0) != g:
                mism[l["season"]] = {"season_G": g, "game_logs_played": played.get(l["season"], 0)}
        out.append(_check(f"gamelog_counts[{st}]", "WARN" if mism else "PASS", mism or "game logs match season G"))
    return out


BLING_PATTERNS = {
    "NBA_MVP": r"(\d+)x MVP$|^(\d{4}-\d{2}) MVP$",
    "ALL_STAR": r"(\d+)x All Star|^(\d{4}-\d{2}) All Star",
    "NBA_CHAMPIONSHIP": r"(\d+)x NBA Champ|^(\d{4}-\d{2}) NBA Champ",
    "NBA_FINALS_MVP": r"(\d+)x Finals MVP|^(\d{4}-\d{2}) Finals MVP",
    "SCORING_TITLE": r"(\d+)x Scoring Champ|^(\d{4}-\d{2}) Scoring Champ",
    "DEFENSIVE_PLAYER_OF_THE_YEAR": r"(\d+)x Def\. POY|^(\d{4}-\d{2}) Def\. POY",
    "ROOKIE_OF_THE_YEAR": r"Rookie of the Year|ROY",
    "ALL_STAR_GAME_MVP": r"(\d+)x AS MVP|^(\d{4}-\d{2}) AS MVP",
}


def badge_count(bling: list, atype: str):
    pat = re.compile(BLING_PATTERNS[atype], re.I)
    for b in bling:
        m = pat.search(b["text"].strip())
        if m:
            if m.lastindex and m.group(1) and m.group(1).isdigit():
                return int(m.group(1))
            return 1
    return None


def check_award_counts(ds: dict) -> list:
    c = Counter(a["achievement_type"] for a in ds.get("achievements", []))
    bling = ds.get("bling", [])
    out = []
    if not bling:
        return [_check("award_counts", "WARN", "no summary badges to cross-check against")]
    for atype in BLING_PATTERNS:
        expected = badge_count(bling, atype)
        got = c.get(atype, 0)
        if expected is None and got == 0:
            continue
        if expected is None:
            out.append(_check(f"award_count[{atype}]", "WARN", f"{got} records but no summary badge found"))
        else:
            out.append(_check(f"award_count[{atype}]", "PASS" if expected == got else "FAIL",
                              {"records": got, "source_summary": expected}))
    return out


def check_chronology(ds: dict) -> list:
    issues = []
    for st in ("regular_season", "playoffs"):
        prev = None
        for l in season_lines(ds, st):
            m = re.match(r"^(\d{4})-(\d{2})$", l["season"])
            if not m or (int(m.group(1)) + 1) % 100 != int(m.group(2)):
                issues.append(f"bad season label {l['season']}")
                continue
            y = int(m.group(1))
            if prev is not None and y <= prev:
                issues.append(f"{st}: {l['season']} not after previous season")
            prev = y
    ages = [(l["season"], num(l.get("age"))) for l in season_lines(ds, "regular_season")]
    for (s1, a1), (s2, a2) in zip(ages, ages[1:]):
        if a1 is not None and a2 is not None:
            gap = int(s2[:4]) - int(s1[:4])
            if not (gap - 1 <= a2 - a1 <= gap + 1):
                issues.append(f"age jump {s1}->{s2}: {a1}->{a2}")
    return [_check("chronology", "FAIL" if issues else "PASS", issues or "seasons ordered; ages consistent")]


def check_ranges(ds: dict) -> list:
    bad = []

    def scan(where, d):
        for k, v in (d or {}).items():
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                continue
            # eFG% and TS% can legitimately exceed 1.0 in tiny samples (e.g. 1-for-1 from three = 1.5)
            upper = 1.5 if k in ("efg_pct", "ts_pct") else 1.0
            if PCT_KEY.search(k) and not (0 <= v <= upper):
                bad.append(f"{where}.{k}={v}")
            if k in COUNT_KEYS and v < 0:
                bad.append(f"{where}.{k}={v} negative")
    for s in ds.get("seasons", []):
        w = f"{s['stat_type']}:{s['season']}:{s['team']}"
        for kind in ("per_game", "totals", "advanced", "shooting"):
            scan(f"{w}.{kind}", s.get(kind))
        t = s.get("totals", {})
        for m, a in (("fg", "fga"), ("fg3", "fg3a"), ("ft", "fta"), ("fg2", "fg2a")):
            if num(t.get(m)) is not None and num(t.get(a)) is not None and t[m] > t[a]:
                bad.append(f"{w}: {m} > {a}")
    for g in ds.get("game_logs", []):
        scan(f"game:{g['date']}", g.get("stats"))
    return [_check("value_ranges", "FAIL" if bad else "PASS", bad[:25] or "all percentages in [0,1], makes <= attempts")]


def coverage_report(ds: dict, derived: dict | None = None) -> dict:
    p = ds.get("player", {})
    reg = season_lines(ds, "regular_season")
    po = season_lines(ds, "playoffs")

    def status(have, total):
        if total == 0 or have == 0:
            return "MISSING"
        return "COMPLETE" if have >= total else "PARTIAL"

    bio_fields = ["height_in", "weight_lb", "primary_position", "draft_year", "birth_date"]
    bio_have = sum(1 for k in bio_fields if p.get(k) is not None)
    shot_eligible = [l for l in reg if int(l["season"][:4]) >= 1996]
    shot_have = [l for l in shot_eligible if l.get("shooting")]
    pt_eligible = [l for l in reg if int(l["season"][:4]) >= 2015]
    pt_have = {r["season"] for r in ds.get("play_types", []) if r.get("stat_type") == "regular_season"}
    cl_eligible = [l for l in reg if int(l["season"][:4]) >= 1996]
    cl_have = {r["season"] for r in ds.get("clutch", []) if r.get("stat_type") == "regular_season"}
    gl_have = {g["season"] for g in ds.get("game_logs", []) if g["stat_type"] == "regular_season"}
    adv_have = [l for l in reg if l.get("advanced")]
    finals_ach = [a for a in ds.get("achievements", []) if a["achievement_type"] == "NBA_FINALS_APPEARANCE"]
    finals_logged = {g["season"] for g in ds.get("game_logs", []) if g.get("playoff_round") == "nba_finals"}
    labeled = any(g.get("round_confidence") == "labeled" for g in ds.get("game_logs", []))
    rep = {
        "Career bio": {"status": "COMPLETE" if bio_have == len(bio_fields) else ("PARTIAL" if bio_have else "MISSING"),
                       "detail": f"{bio_have}/{len(bio_fields)} core fields; wingspan: not published by sources (null)"},
        "Regular season stats": {"status": status(len([l for l in reg if l.get("per_game") and l.get("totals")]), len(reg)),
                                 "detail": f"{len(reg)} seasons"},
        "Advanced stats": {"status": status(len(adv_have), len(reg)), "detail": f"{len(adv_have)}/{len(reg)} seasons"},
        "Playoffs": {"status": status(len([l for l in po if l.get("per_game")]), len(po)) if po else "MISSING",
                     "detail": f"{len(po)} postseasons"},
        "Finals splits": {"status": status(len(finals_logged), len(finals_ach)) if finals_ach else "N/A",
                          "detail": f"{len(finals_logged)}/{len(finals_ach)} Finals with game-log splits (round labels {'from the source series table' if labeled else 'inferred'})"},
        "Awards": {"status": "COMPLETE" if ds.get("achievements") else "MISSING",
                   "detail": f"{len(ds.get('achievements', []))} award records"},
        "Game logs": ({"status": "PLAYOFFS ONLY", "detail": f"playoff game logs stored; regular season not collected ({'; '.join(ds['collection_notes'])})"}
                      if not gl_have and ds.get("collection_notes") else
                      {"status": status(len(gl_have), len(reg)), "detail": f"{len(gl_have)}/{len(reg)} regular seasons"}),
        "Shot profile": {"status": status(len(shot_have), len(reg)) if shot_have else ("N/A" if not shot_eligible else "MISSING"),
                         "detail": f"{len(shot_have)}/{len(reg)} seasons (source shot tracking starts 1996-97)"},
        "Play-type data": {"status": status(len(pt_have), len(reg)) if pt_have else "MISSING",
                           "detail": f"{len(pt_have)}/{len(pt_eligible)} eligible seasons (Synergy starts 2015-16)"},
        "Clutch data": {"status": status(len(cl_have), len(reg)) if cl_have else "MISSING",
                        "detail": f"{len(cl_have)}/{len(cl_eligible)} eligible seasons (NBA.com clutch starts 1996-97)"},
    }
    return rep


def validate(ds: dict, derived: dict | None = None) -> dict:
    checks = (check_career_totals(ds) + check_not_mixed(ds) + check_gamelogs(ds) + check_award_counts(ds)
              + check_chronology(ds) + check_ranges(ds))
    summary = Counter(c["status"] for c in checks)
    return {"player": ds.get("player", {}).get("full_name"), "checks": checks, "summary": dict(summary),
            "coverage": coverage_report(ds, derived), "ingest_errors": ds.get("ingest_errors", [])}


def format_report(rep: dict) -> str:
    lines = [rep["player"] or "?", ""]
    for k, v in rep["coverage"].items():
        lines.append(f"{k}: {v['status']}  ({v['detail']})")
    lines.append("")
    lines.append("Checks: " + ", ".join(f"{k} {v}" for k, v in sorted(rep["summary"].items())))
    for c in rep["checks"]:
        if c["status"] != "PASS":
            lines.append(f"  [{c['status']}] {c['check']}: {c['detail']}")
    if rep.get("ingest_errors"):
        lines.append(f"Ingest errors: {len(rep['ingest_errors'])}")
        lines.extend(f"  - {e}" for e in rep["ingest_errors"][:10])
    return "\n".join(lines)
