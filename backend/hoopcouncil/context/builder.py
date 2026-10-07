"""career_context_builder: structured DB data -> compact, numeric, LLM-readable context.

Layer 1 - career summary (always sent)
Layer 2 - season summaries (compact one-line-per-season tables; sent when budget allows)
Layer 3 - raw detail documents, retrieved per scenario (see retrieval.py)
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone

from ..derive.aggregates import season_lines
from .fmt import est_tokens, height, n, pct, season_line, signed

ACH_ORDER = [
    ("NBA_CHAMPIONSHIP", "NBA championships"), ("NBA_FINALS_APPEARANCE", "NBA Finals appearances"),
    ("NBA_MVP", "MVP awards"), ("NBA_FINALS_MVP", "Finals MVP awards"), ("ALL_STAR", "All-Star selections"),
    ("ALL_STAR_GAME_MVP", "All-Star Game MVP"), ("ALL_NBA_FIRST", "All-NBA First Team"),
    ("ALL_NBA_SECOND", "All-NBA Second Team"), ("ALL_NBA_THIRD", "All-NBA Third Team"),
    ("ALL_DEFENSIVE_FIRST", "All-Defensive First Team"), ("ALL_DEFENSIVE_SECOND", "All-Defensive Second Team"),
    ("DEFENSIVE_PLAYER_OF_THE_YEAR", "Defensive Player of the Year"), ("ROOKIE_OF_THE_YEAR", "Rookie of the Year"),
    ("CLUTCH_PLAYER_OF_THE_YEAR", "Clutch Player of the Year"), ("SCORING_TITLE", "Scoring titles (league leader, PPG)"),
    ("ASSIST_TITLE", "Assist titles"), ("STEALS_TITLE", "Steals titles"), ("REBOUNDING_TITLE", "Rebounding titles"),
    ("BLOCKS_TITLE", "Blocks titles"), ("HALL_OF_FAME", "Hall of Fame"),
]


def achievements_summary(achievements: list) -> list:
    by = defaultdict(list)
    for a in achievements:
        by[a["achievement_type"]].append(a)
    out = []
    for key, label in ACH_ORDER:
        rows = by.get(key)
        if not rows:
            continue
        seasons = sorted(r["season"] for r in rows if r.get("season"))
        item = {"achievement_type": key, "label": label, "count": len(rows), "seasons": seasons}
        if key == "HALL_OF_FAME":
            item["detail"] = rows[0].get("detail")
        out.append(item)
    mvp_votes = sorted(((a["season"], (a.get("detail") or {}).get("rank")) for a in by.get("NBA_MVP_VOTING_FINISH", [])))
    if mvp_votes:
        out.append({"achievement_type": "NBA_MVP_VOTING_FINISH", "label": "MVP voting finishes",
                    "count": len(mvp_votes), "seasons": [f"{s} (#{r})" for s, r in mvp_votes]})
    return out


def _fingerprint(ds: dict, derived: dict) -> str:
    basis = json.dumps({"retrieved": sorted({str((s.get("provenance") or {}).get("retrieved_at")) for s in ds.get("seasons", [])}),
                        "n_seasons": len(ds.get("seasons", [])), "n_ach": len(ds.get("achievements", [])),
                        "n_logs": len(ds.get("game_logs", [])), "peaks": derived.get("peak_scores")}, sort_keys=True, default=str)
    return hashlib.sha1(basis.encode()).hexdigest()[:16]


def build_package(ds: dict, derived: dict) -> dict:
    p = ds["player"]
    agg = derived.get("aggregates", {})
    reg, po = agg.get("regular_season") or {}, agg.get("playoffs") or {}
    peak = {x["season"]: x["peak_score"] for x in derived.get("peak_scores", [])}
    season_stats = []
    for l in season_lines(ds, "regular_season"):
        season_stats.append({"season": l["season"], "teams": l.get("teams"), "age": l.get("age"),
                             "per_game": {k: l["per_game"].get(k) for k in ("g", "mp_per_g", "pts_per_g", "trb_per_g", "ast_per_g",
                                                                            "stl_per_g", "blk_per_g", "tov_per_g", "fg_pct", "fg3_pct",
                                                                            "fg3a_per_g", "ft_pct", "fta_per_g")},
                             "advanced": {k: l.get("advanced", {}).get(k) for k in ("ts_pct", "usg_pct", "ast_pct", "bpm", "ws_per_48", "per")},
                             "peak_score": peak.get(l["season"]), "awards_text": l.get("awards_text")})
    playoff_seasons = [{"season": l["season"], "team": l.get("team"),
                        "per_game": {k: l["per_game"].get(k) for k in ("g", "mp_per_g", "pts_per_g", "trb_per_g", "ast_per_g", "fg_pct", "fg3_pct", "ft_pct")},
                        "advanced": {k: l.get("advanced", {}).get(k) for k in ("ts_pct", "usg_pct", "bpm", "ws_per_48")}}
                       for l in season_lines(ds, "playoffs")]
    sup = [a for a in derived.get("archetypes", []) if a["status"] == "supported"]
    insuff = [a["archetype"] for a in derived.get("archetypes", []) if a["status"] == "insufficient_data"]
    cov = (derived.get("features") or {}).get("coverage", {})
    limitations = [
        "Wingspan is not published by the ingested sources (null).",
        f"Shot-distance profile covers {cov.get('rim_share', {}).get('seasons', 0)} of {len(season_stats)} regular seasons.",
        ("Playoff round labels come from the source's playoff-series table." if any(g.get("round_confidence") == "labeled" for g in ds.get("game_logs", []))
         else "Playoff round labels (conference finals / Finals) are inferred from game-log opponent sequences; Finals are confirmed against the league champions list."),
        "'Close games' are full-game box scores of games decided by <= 3 points, not late-game possessions.",
    ]
    for note in ds.get("collection_notes", []):
        limitations.append(f"Collection note: {note}. Single-game regular-season data is unavailable; per-season and playoff game data are used instead.")
    if insuff:
        limitations.append("Archetypes not testable with stored data: " + ", ".join(insuff) + ".")
    if not ds.get("clutch"):
        limitations.append("No clutch (last 5 min, within 5) splits stored; clutch performance is not established by the data.")
    if not ds.get("play_types"):
        limitations.append("No Synergy play-type data stored (isolation/PnR/post/transition frequencies unavailable).")
    if ds.get("dnp_seasons"):
        limitations.append("Seasons without games: " + ", ".join(f"{d['season']} ({d['note']})" for d in ds["dnp_seasons"]) + ".")
    pkg = {
        "player": p["full_name"],
        "slug": p["slug"],
        "identity": {k: p.get(k) for k in ("full_name", "primary_position", "secondary_positions", "height_in", "height_cm",
                                           "weight_lb", "wingspan_in", "shoots", "birth_date", "draft_year", "draft_team",
                                           "draft_pick", "teams", "first_season", "last_season", "seasons_played",
                                           "hall_of_fame_inducted")},
        "career_summary": {"regular_season": {k: reg.get(k) for k in ("num_seasons", "totals", "per_game", "per36", "shooting", "advanced", "coverage")}},
        "season_stats": season_stats,
        "playoff_summary": {k: po.get(k) for k in ("num_seasons", "totals", "per_game", "per36", "shooting", "advanced")},
        "playoff_seasons": playoff_seasons,
        "finals_summary": {"nba_finals": agg.get("nba_finals"), "conference_finals": agg.get("conference_finals"),
                           "series": derived.get("finals_series", [])},
        "achievements": achievements_summary(ds.get("achievements", [])),
        "records": derived.get("records", []),
        "shot_profile_summary": derived.get("shot_profile_summary", {}),
        "play_type_tendencies": derived.get("play_type_tendencies", {}),
        "clutch_summary": (derived.get("features") or {}).get("clutch"),
        "career_phases": derived.get("career_phases", []),
        "peak_seasons": derived.get("peak_seasons", []),
        "peak_formula": derived.get("peak_formula"),
        "basketball_archetypes": [{"archetype": a["archetype"], "evidence": a["evidence"], "rule": a["rule"]} for a in sup],
        "archetypes_all": derived.get("archetypes", []),
        "features": {k: v for k, v in (derived.get("features") or {}).items() if k not in ("coverage",)},
        "strengths": derived.get("strengths", []),
        "limitations": derived.get("limitations", []),
        "data_limitations": limitations,
        "sources": sorted({(s.get("provenance") or {}).get("source_url") for s in ds.get("seasons", [])} - {None})[:5],
        "built_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "fingerprint": _fingerprint(ds, derived),
    }
    pkg["text"] = render_text(pkg)
    return pkg


# --------------------------------------------------------------------------- rendering
def render_layer1(pkg: dict) -> str:
    i = pkg["identity"]
    cs = pkg["career_summary"]["regular_season"] or {}
    pg, sh, adv, tot, p36 = cs.get("per_game") or {}, cs.get("shooting") or {}, cs.get("advanced") or {}, cs.get("totals") or {}, cs.get("per36") or {}
    out = [f"=== PLAYER ===\n{pkg['player']}",
           "=== CAREER PROFILE ===",
           f"Position: {i.get('primary_position')}" + (f" (also {', '.join(i['secondary_positions'])})" if i.get("secondary_positions") else "")
           + f" | Height {height(i.get('height_in'))} ({n(i.get('height_cm'))} cm) | Weight {n(i.get('weight_lb'))} lb | Wingspan: not available in data"
           + f" | Shoots {i.get('shoots') or 'n/a'}",
           f"Drafted {i.get('draft_year') or 'n/a'} by {i.get('draft_team') or 'n/a'} (pick {n(i.get('draft_pick'))}) | Seasons {i.get('first_season')}..{i.get('last_season')} "
           f"({i.get('seasons_played')} seasons) | Teams: {', '.join(i.get('teams') or [])}"
           + (f" | Hall of Fame inducted {i['hall_of_fame_inducted']}" if i.get("hall_of_fame_inducted") else "")]
    out.append("=== MAJOR ACHIEVEMENTS (structured award records) ===")
    if pkg["achievements"]:
        for a in pkg["achievements"]:
            seasons = f": {', '.join(a['seasons'])}" if a.get("seasons") else ""
            out.append(f"- {a['label']}: {a['count']}{seasons}")
    else:
        out.append("- no award records stored")
    out.append("=== CAREER STATISTICS (regular season) ===")
    out.append(f"{n(tot.get('g'))} G, {n(tot.get('pts'))} PTS, {n(tot.get('trb'))} TRB, {n(tot.get('ast'))} AST, {n(tot.get('stl'))} STL, "
               f"{n(tot.get('blk'))} BLK, {n(tot.get('fg3'))} 3PM, {n(tot.get('mp'))} MIN")
    out.append(f"Per game: {n(pg.get('pts_per_g'))} PTS, {n(pg.get('trb_per_g'))} TRB, {n(pg.get('ast_per_g'))} AST, {n(pg.get('stl_per_g'))} STL, "
               f"{n(pg.get('blk_per_g'))} BLK, {n(pg.get('tov_per_g'))} TOV, {n(pg.get('mp_per_g'))} MIN")
    out.append(f"Per 36: {n(p36.get('pts_per36'))} PTS, {n(p36.get('trb_per36'))} TRB, {n(p36.get('ast_per36'))} AST, {n(p36.get('fga_per36'))} FGA, "
               f"{n(p36.get('fg3a_per36'))} 3PA, {n(p36.get('fta_per36'))} FTA")
    out.append(f"Shooting: FG {pct(sh.get('fg_pct'))}, 2P {pct(sh.get('fg2_pct'))}, 3P {pct(sh.get('fg3_pct'))}, FT {pct(sh.get('ft_pct'))}, "
               f"eFG {pct(sh.get('efg_pct'))}, TS {pct(sh.get('ts_pct'))}, 3PA rate {n(sh.get('fg3a_rate'), 3)}, FTA rate {n(sh.get('fta_rate'), 3)}")
    out.append(f"Advanced (minutes-weighted): PER {n(adv.get('per'))}, USG {pct(adv.get('usg_pct'))}, AST% {pct(adv.get('ast_pct'))}, "
               f"TRB% {pct(adv.get('trb_pct'))}, TOV% {pct(adv.get('tov_pct'))}, STL% {pct(adv.get('stl_pct'))}, BLK% {pct(adv.get('blk_pct'))}, "
               f"OBPM {signed(adv.get('obpm'))}, DBPM {signed(adv.get('dbpm'))}, BPM {signed(adv.get('bpm'))}, WS {n(adv.get('ws'))}, "
               f"WS/48 {n(adv.get('ws_per_48'), 3)}, VORP {n(adv.get('vorp'))}, ORtg {n(adv.get('ortg'), 0)}, DRtg {n(adv.get('drtg'), 0)}")
    f = pkg.get("features") or {}
    out.append(f"Era context (vs league average, same seasons): TS {signed((f.get('rel_ts_pct') or 0) * 100) if f.get('rel_ts_pct') is not None else 'n/a'} pts, "
               f"3PA rate {n(f.get('rel_fg3a_rate'), 2)}x, 3P% {signed((f.get('rel_fg3_pct') or 0) * 100) if f.get('rel_fg3_pct') is not None else 'n/a'} pts, "
               f"FT% {signed((f.get('rel_ft_pct') or 0) * 100) if f.get('rel_ft_pct') is not None else 'n/a'} pts")
    ps = pkg.get("playoff_summary") or {}
    out.append("=== PLAYOFF PROFILE ===")
    if ps.get("totals"):
        ppg, psh, padv = ps.get("per_game") or {}, ps.get("shooting") or {}, ps.get("advanced") or {}
        out.append(f"{ps.get('num_seasons')} postseasons, {n(ps['totals'].get('g'))} G: {n(ppg.get('pts_per_g'))} PTS, {n(ppg.get('trb_per_g'))} TRB, "
                   f"{n(ppg.get('ast_per_g'))} AST, {n(ppg.get('tov_per_g'))} TOV, {n(ppg.get('mp_per_g'))} MIN; FG {pct(psh.get('fg_pct'))}, "
                   f"3P {pct(psh.get('fg3_pct'))}, FT {pct(psh.get('ft_pct'))}, TS {pct(psh.get('ts_pct'))}; USG {pct(padv.get('usg_pct'))}, "
                   f"BPM {signed(padv.get('bpm'))}, WS/48 {n(padv.get('ws_per_48'), 3)}; playoff TS vs league {signed((f.get('playoff_rel_ts_pct') or 0) * 100) if f.get('playoff_rel_ts_pct') is not None else 'n/a'} pts")
    else:
        out.append("No playoff data stored.")
    fin = pkg.get("finals_summary") or {}
    for key, label in (("nba_finals", "NBA FINALS"), ("conference_finals", "CONFERENCE FINALS")):
        x = fin.get(key)
        if x:
            out.append(f"{label} (from game logs, {x.get('series')} series): {x['games']} G, {x.get('wins')}-{x.get('losses')}, "
                       f"{n(x['per_game'].get('pts_per_g'))} PTS, {n(x['per_game'].get('trb_per_g'))} TRB, {n(x['per_game'].get('ast_per_g'))} AST, "
                       f"FG {pct(x['shooting'].get('fg_pct'))}, 3P {pct(x['shooting'].get('fg3_pct'))}, TS {pct(x['shooting'].get('ts_pct'))}")
    sp = pkg.get("shot_profile_summary") or {}
    out.append("=== SHOT PROFILE ===")
    out.append(f"Share of FGA: rim (0-3 ft) {pct(sp.get('rim_frequency'))}, 3-10 ft {pct(sp.get('short_midrange_frequency'))}, "
               f"10 ft-3P {pct(sp.get('midrange_frequency'))} (16 ft-3P {pct(sp.get('long_midrange_frequency'))}), threes {pct(sp.get('three_point_frequency'))}; "
               f"FG% rim {pct(sp.get('rim_fg_pct'))}, midrange {pct(sp.get('midrange_fg_pct'))}, corner 3 {pct(sp.get('corner_three_fg_pct'))}; "
               f"assisted share 2P {pct(sp.get('assisted_share_2p'))} / 3P {pct(sp.get('assisted_share_3p'))}; "
               f"catch-and-shoot {pct(sp.get('catch_and_shoot_frequency'))}, pull-up {pct(sp.get('pull_up_frequency'))}, "
               f"late clock {pct(sp.get('late_clock_frequency'))}. {sp.get('coverage_note', '')}")
    out.append("=== OFFENSIVE TENDENCIES ===")
    pt = pkg.get("play_type_tendencies") or {}
    if pt:
        out.append("Play types (Synergy, regular season avg): " + "; ".join(
            f"{k} {pct(v['frequency'])} freq, {n(v['ppp'], 2)} PPP" for k, v in sorted(pt.items(), key=lambda kv: -kv[1]["frequency"])))
    else:
        out.append("Play-type data: not available in stored data.")
    out.append(f"Scoring: {n(pg.get('pts_per_g'))} PPG at USG {pct(adv.get('usg_pct'))}, FTA per 36 {n(f.get('fta_per36'))}, "
               f"and-1s per 36 {n(f.get('and1_per36'), 2)} (play-by-play era)")
    out.append(f"Playmaking: AST% {pct(adv.get('ast_pct'))}, AST/TOV {n(sh.get('ast_to_tov'), 2)}, TOV% {pct(adv.get('tov_pct'))}")
    pos = [f"{k.upper()} {pct(f.get(f'pos_{k}_share'), 0)}" for k in ("pg", "sg", "sf", "pf", "c") if f.get(f"pos_{k}_share")]
    if pos:
        out.append("Position estimates (minutes share, play-by-play era): " + ", ".join(pos))
    cl = pkg.get("clutch_summary")
    out.append("Clutch: " + (f"{n(cl.get('minutes'))} clutch min, {n(cl.get('pts_per36'))} pts/36, TS {pct(cl.get('ts_pct'))} ({cl.get('definition')})"
                             if cl else "not established by stored data"))
    out.append("=== DEFENSIVE PROFILE ===")
    out.append(f"STL% {pct(adv.get('stl_pct'))}, BLK% {pct(adv.get('blk_pct'))}, DRB% {pct(f.get('drb_pct'))}, DBPM {signed(adv.get('dbpm'))}, "
               f"DRtg {n(adv.get('drtg'), 0)}, All-Defensive selections {f.get('all_defensive_selections', 0)}")
    out.append("=== PEAK SEASONS (computed peak_score, see formula) ===")
    for pk in pkg.get("peak_seasons", []):
        c = pk["components"]
        out.append(f"- {pk['season']}: peak_score {pk['peak_score']:.3f} (impact {c.get('impact')}, scoring {c.get('scoring')}, "
                   f"efficiency {c.get('efficiency')}, playoffs {c.get('playoffs')}, recognition {c.get('recognition')})")
    out.append("=== CAREER PHASES ===")
    for ph in pkg.get("career_phases", []):
        s = ph.get("summary") or {}
        out.append(f"- [{ph['phase_type']}] {ph['name']} {ph['start_season']}..{ph['end_season']}: "
                   f"{n((s.get('per_game') or {}).get('pts_per_g'))} PTS, {n((s.get('per_game') or {}).get('ast_per_g'))} AST, "
                   f"TS {pct((s.get('shooting') or {}).get('ts_pct'))}, USG {pct((s.get('advanced') or {}).get('usg_pct'))}, "
                   f"BPM {signed((s.get('advanced') or {}).get('bpm'))}")
    out.append("=== ARCHETYPES (statistically supported) ===")
    for a in pkg.get("basketball_archetypes", []):
        out.append(f"- {a['archetype']}: {'; '.join(a['evidence'])}")
    if not pkg.get("basketball_archetypes"):
        out.append("- none supported by stored data")
    out.append("=== STRENGTHS (data) ===")
    out.extend(f"- {s['label']}: {s['evidence']}" for s in pkg.get("strengths", []))
    out.append("=== LIMITATIONS (data) ===")
    out.extend(f"- {s['label']}: {s['evidence']}" for s in pkg.get("limitations", []))
    recs = [r for r in pkg.get("records", []) if r["key"].startswith(("career_high", "games_", "playoff_wins", "seasons_30"))]
    if recs:
        out.append("=== MILESTONES (raw facts) ===")
        out.extend(f"- {r['label']}: {n(r['value'])}" for r in recs)
    out.append("=== DATA LIMITATIONS ===")
    out.extend(f"- {x}" for x in pkg.get("data_limitations", []))
    return "\n".join(out)


def render_layer2(pkg: dict) -> str:
    out = ["=== SEASON HISTORY (regular season, combined rows) ==="]
    for s in pkg.get("season_stats", []):
        l = {"season": s["season"], "teams": s.get("teams"), "per_game": s["per_game"], "advanced": s["advanced"],
             "awards_text": s.get("awards_text")}
        out.append(season_line(l, s.get("peak_score")))
    if pkg.get("playoff_seasons"):
        out.append("=== PLAYOFF HISTORY ===")
        for s in pkg["playoff_seasons"]:
            pg, adv = s["per_game"], s["advanced"]
            out.append(f"{s['season']} {s.get('team') or ''} | G {n(pg.get('g'))} | PTS {n(pg.get('pts_per_g'))} | TRB {n(pg.get('trb_per_g'))} | "
                       f"AST {n(pg.get('ast_per_g'))} | FG {pct(pg.get('fg_pct'))} | 3P {pct(pg.get('fg3_pct'))} | FT {pct(pg.get('ft_pct'))} | "
                       f"TS {pct(adv.get('ts_pct'))} | USG {pct(adv.get('usg_pct'))} | BPM {signed(adv.get('bpm'))}")
    series = (pkg.get("finals_summary") or {}).get("series") or []
    if series:
        out.append("=== CONFERENCE FINALS / FINALS SERIES ===")
        for x in series:
            out.append(f"{x['season']} {x['playoff_round']} vs {x.get('opponent')}: {x['games']} G ({x.get('wins')}-{x.get('losses')}), "
                       f"{n((x.get('per_game') or {}).get('pts_per_g'))} PTS, TS {pct((x.get('shooting') or {}).get('ts_pct'))}")
    return "\n".join(out)


def render_text(pkg: dict) -> dict:
    l1, l2 = render_layer1(pkg), render_layer2(pkg)
    return {"layer1": l1, "layer2": l2, "layer1_tokens": est_tokens(l1), "layer2_tokens": est_tokens(l2)}


LAYER1_SECTIONS = ["CAREER PROFILE", "MAJOR ACHIEVEMENTS", "CAREER STATISTICS", "PLAYOFF PROFILE", "SHOT PROFILE",
                   "OFFENSIVE TENDENCIES", "DEFENSIVE PROFILE", "PEAK SEASONS", "CAREER PHASES", "ARCHETYPES",
                   "STRENGTHS", "LIMITATIONS", "DATA LIMITATIONS"]


def assemble_agent_context(pkg: dict, retrieved: list, token_budget: int) -> tuple:
    """Return (context_text, data_considered) for one agent within a token budget."""
    l1 = pkg["text"]["layer1"]
    l2 = pkg["text"]["layer2"]
    parts = [l1]
    considered = {"layers": ["layer1: career summary"], "sections": list(LAYER1_SECTIONS), "retrieved_documents": [],
                  "peak_seasons": [p["season"] for p in pkg.get("peak_seasons", [])]}
    used = est_tokens(l1)
    if used + est_tokens(l2) <= token_budget * 0.7:
        parts.append(l2)
        used += est_tokens(l2)
        considered["layers"].append("layer2: season-by-season history")
        considered["sections"] += ["SEASON HISTORY", "PLAYOFF HISTORY"]
    else:
        considered["layers"].append("layer2 omitted (token budget)")
    docs_txt = []
    for d in retrieved:
        t = est_tokens(d["text"])
        if used + t > token_budget:
            continue
        docs_txt.append(f"[{d['title']}]\n{d['text']}")
        considered["retrieved_documents"].append({"title": d["title"], "topics": d.get("topics"), "score": d.get("score")})
        used += t
    if docs_txt:
        parts.append("=== RETRIEVED DETAIL (layer 3, selected for this situation) ===\n" + "\n\n".join(docs_txt))
        considered["layers"].append("layer3: situation-specific retrieval")
    considered["approx_tokens"] = used
    return "\n\n".join(parts), considered
