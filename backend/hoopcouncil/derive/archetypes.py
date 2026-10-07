"""Archetype tags derived from statistics. Each rule states its thresholds; a tag is
`supported`, `not_supported`, or `insufficient_data` (when the needed data is absent,
e.g. Synergy play types before 2015-16). Nothing here is asserted by hand.
See docs/archetypes.md.
"""
from __future__ import annotations


def _pct(x):
    return f"{x * 100:.1f}%" if isinstance(x, (int, float)) else "n/a"


def _cov(f, k):
    c = f.get("coverage", {}).get(k)
    return f" ({c['seasons']}/{c['of']} seasons with data)" if c else ""


def _pt(f, name):
    return (f.get("play_types") or {}).get(name)


def _tag(name, status, score, evidence, rule):
    return {"archetype": name, "status": status, "score": round(score, 3) if score is not None else None,
            "evidence": evidence, "rule": rule}


def _ratio(v, thr):
    return min(1.0, v / thr) if v is not None and thr else None


def rule_threshold(name, value, thr, rule, evidence_fmt, cmp=">=", insufficient_if_none=True):
    if value is None:
        return _tag(name, "insufficient_data", None, ["required statistic not available in stored data"], rule)
    ok = value >= thr if cmp == ">=" else value <= thr
    score = _ratio(value, thr) if cmp == ">=" else (min(1.0, thr / value) if value else 1.0)
    return _tag(name, "supported" if ok else "not_supported", score, [evidence_fmt], rule)


def derive_archetypes(f: dict) -> list:
    out = []
    usg, a2 = f.get("usg_pct"), f.get("assisted_share_2p")
    # 1 high-usage self creator
    if usg is None:
        out.append(_tag("high-volume shot creator", "insufficient_data", None, ["USG% unavailable"], "USG% >= 30% and <= 45% of 2P FG assisted"))
    else:
        ok = usg >= 0.30 and (a2 is None or a2 <= 0.45)
        ev = [f"career USG% {_pct(usg)}{_cov(f, 'usg_pct')}"]
        ev.append(f"share of 2P FG assisted {_pct(a2)}{_cov(f, 'assisted_share_2p')}" if a2 is not None
                  else "assisted-share data unavailable (shot tracking on Basketball Reference begins 1996-97)")
        out.append(_tag("high-volume shot creator", "supported" if ok else "not_supported", min(1, usg / 0.30), ev,
                        "USG% >= 30% and (if available) <= 45% of made 2s assisted"))
    # 2 deep-range shooter (era relative)
    r3a, r3p = f.get("rel_fg3a_rate"), f.get("rel_fg3_pct")
    if r3a is None or r3p is None:
        out.append(_tag("high-volume three-point shooter", "insufficient_data", None, ["league-relative 3P data unavailable"],
                        "3PA rate >= 1.4x league and 3P% >= league + 3.0 pts"))
    else:
        out.append(_tag("high-volume three-point shooter", "supported" if (r3a >= 1.4 and r3p >= 0.03) else "not_supported",
                        min(1, r3a / 1.4) * (1 if r3p >= 0.03 else 0.5),
                        [f"3PA rate {r3a:.2f}x league average{_cov(f, 'rel_fg3a_rate')}",
                         f"3P% {r3p * 100:+.1f} pts vs league{_cov(f, 'rel_fg3_pct')}"],
                        "3PA rate >= 1.4x league and 3P% >= league + 3.0 pts (same seasons, minutes-weighted)"))
    # 3 midrange scorer
    ms, mfg = f.get("mid_share"), f.get("midrange_fg_pct")
    if ms is None:
        out.append(_tag("midrange scorer", "insufficient_data", None, ["shot-distance data unavailable for these seasons"],
                        ">= 30% of FGA from 10 ft to the 3P line and FG% there >= 42%"))
    else:
        ok = ms >= 0.30 and (mfg or 0) >= 0.42
        out.append(_tag("midrange scorer", "supported" if ok else "not_supported", min(1, ms / 0.30),
                        [f"{_pct(ms)} of FGA from 10 ft to 3P line{_cov(f, 'mid_share')}", f"FG% on those shots {_pct(mfg)}"],
                        ">= 30% of FGA from 10 ft to the 3P line and FG% there >= 42%"))
    # 4 rim attacker
    rim, ftr = f.get("rim_share"), f.get("fta_rate")
    if rim is None and ftr is None:
        out.append(_tag("rim attacker", "insufficient_data", None, ["no shot-distance or FT-rate data"], ">= 30% FGA at 0-3 ft or FTA rate >= 0.40"))
    else:
        ok = (rim or 0) >= 0.30 or (ftr or 0) >= 0.40
        ev = []
        if rim is not None:
            ev.append(f"{_pct(rim)} of FGA at 0-3 ft{_cov(f, 'rim_share')}")
        if ftr is not None:
            ev.append(f"FTA rate (FTA/FGA) {ftr:.3f}{_cov(f, 'fta_rate')}")
        out.append(_tag("rim attacker", "supported" if ok else "not_supported", max(_ratio(rim, 0.30) or 0, _ratio(ftr, 0.40) or 0), ev,
                        ">= 30% of FGA at 0-3 ft or FTA rate >= 0.40"))
    # 5 three-level scorer
    th = f.get("three_share")
    rts = f.get("rel_ts_pct")
    if None in (rim, ms, th):
        out.append(_tag("three-level scorer", "insufficient_data", None, ["shot-distance data unavailable"],
                        ">= 15% FGA at rim, >= 20% midrange, >= 15% threes, TS% >= league + 2 pts"))
    else:
        ok = rim >= 0.15 and ms >= 0.20 and th >= 0.15 and (rts or 0) >= 0.02
        out.append(_tag("three-level scorer", "supported" if ok else "not_supported", None,
                        [f"FGA mix: rim {_pct(rim)}, midrange {_pct(ms)}, three {_pct(th)}",
                         f"TS% vs league {rts * 100:+.1f} pts" if rts is not None else "league TS% unavailable"],
                        ">= 15% FGA at rim, >= 20% midrange, >= 15% threes, TS% >= league + 2 pts"))
    # 6/7 playmaking
    ast = f.get("ast_pct")
    out.append(rule_threshold("primary playmaker", ast, 0.35, "AST% >= 35%", f"career AST% {_pct(ast)}{_cov(f, 'ast_pct')}"))
    if ast is not None:
        sec = 0.20 <= ast < 0.35
        out.append(_tag("secondary playmaker", "supported" if sec else "not_supported", None,
                        [f"career AST% {_pct(ast)}"], "20% <= AST% < 35%"))
    # 8 efficient high-usage scorer
    if rts is not None and usg is not None:
        out.append(_tag("efficient volume scorer", "supported" if (rts >= 0.04 and usg >= 0.25) else "not_supported",
                        min(1, max(0, rts) / 0.04), [f"TS% {rts * 100:+.1f} pts vs league at USG% {_pct(usg)}"],
                        "TS% >= league + 4 pts with USG% >= 25%"))
    # 9 perimeter defender: recognition + steal rate
    adef, stl, dbpm = f.get("all_defensive_selections", 0), f.get("stl_pct"), f.get("dbpm")
    dpoy = f.get("award_counts", {}).get("DEFENSIVE_PLAYER_OF_THE_YEAR", 0)
    if stl is None and not adef:
        out.append(_tag("elite perimeter defender", "insufficient_data", None, ["no defensive data"], "see rule"))
    else:
        ok = (adef >= 3 or dpoy >= 1) and (stl or 0) >= 0.018
        out.append(_tag("elite perimeter defender", "supported" if ok else "not_supported", None,
                        [f"All-Defensive selections: {adef}", f"DPOY awards: {dpoy}", f"career STL% {_pct(stl)}",
                         f"career DBPM {dbpm:+.1f}" if dbpm is not None else "DBPM unavailable"],
                        "(>= 3 All-Defensive selections or a DPOY) and STL% >= 1.8%"))
    # 10 help-side rim protection
    blk = f.get("blk_pct")
    out.append(rule_threshold("weak-side rim protector", blk, 0.025, "BLK% >= 2.5% (non-center)",
                              f"career BLK% {_pct(blk)}{_cov(f, 'blk_pct')}"))
    # 11 rebounding
    trb = f.get("trb_pct")
    out.append(rule_threshold("rebounding forward/wing", trb, 0.12, "TRB% >= 12%", f"career TRB% {_pct(trb)}"))
    # 12 free-throw pressure
    fta36 = f.get("fta_per36")
    out.append(rule_threshold("foul-drawing pressure", fta36, 7.0, "FTA per 36 min >= 7.0", f"FTA per 36 minutes {fta36}"))
    # 13 positional versatility (play-by-play position estimates)
    shares = {p: f.get(f"pos_{p}_share") for p in ("pg", "sg", "sf", "pf", "c")}
    if all(v is None for v in shares.values()):
        out.append(_tag("positional versatility", "insufficient_data", None, ["position estimates begin 2000-01 on Basketball Reference"],
                        ">= 2 positions each >= 20% of minutes"))
    else:
        many = [p.upper() for p, v in shares.items() if (v or 0) >= 0.20]
        out.append(_tag("positional versatility", "supported" if len(many) >= 2 else "not_supported", None,
                        [", ".join(f"{p.upper()} {_pct(v)}" for p, v in shares.items() if v)], ">= 2 positions each >= 20% of minutes"))
    # 14 big shooter / mismatch size
    h = f.get("height_in")
    if h is not None:
        ok = h >= 81 and (f.get("rel_fg3_pct") or -1) >= 0.0 and (f.get("rel_ts_pct") or -1) >= 0.03
        out.append(_tag("size mismatch scorer", "supported" if ok else "not_supported", None,
                        [f"listed height {h // 12}-{h % 12}", f"3P% vs league {(f.get('rel_fg3_pct') or 0) * 100:+.1f} pts"],
                        "listed height >= 6-9 with league-average-or-better 3P% and TS% >= league + 3 pts"))
    # Synergy-dependent tags
    for name, ptype, thr in (("isolation scorer", "Isolation", 0.15), ("pick-and-roll creator", "PRBallHandler", 0.20),
                             ("post scorer", "Postup", 0.08), ("transition scorer", "Transition", 0.15),
                             ("movement shooter", "OffScreen", 0.07), ("spot-up shooter", "Spotup", 0.20)):
        p = _pt(f, ptype)
        rule = f"Synergy {ptype} frequency >= {thr:.0%} of possessions (data from 2015-16 only)"
        if not p:
            out.append(_tag(name, "insufficient_data", None, [f"no Synergy {ptype} data for this player's seasons"], rule))
        else:
            out.append(_tag(name, "supported" if p["frequency"] >= thr else "not_supported", min(1, p["frequency"] / thr),
                            [f"{ptype} frequency {_pct(p['frequency'])}, {p['ppp']:.2f} PPP, percentile {p['percentile']:.2f} "
                             f"(seasons {p['seasons'][0]}..{p['seasons'][-1]})"], rule))
    # tracking-dependent
    tr = f.get("tracking") or {}
    late = tr.get("ShotClockShooting:4-0 Very Late")
    rule = "share of FGA with 4-0 s on shot clock >= 8% (tracking data from 2013-14)"
    out.append(_tag("late-clock creator", "insufficient_data", None, ["no shot-clock tracking data"], rule) if not late else
               _tag("late-clock creator", "supported" if late["fga_frequency"] >= 0.08 else "not_supported", None,
                    [f"{_pct(late['fga_frequency'])} of FGA in final 4 s of shot clock, eFG% {_pct(late['efg_pct'])}"], rule))
    pull = tr.get("GeneralShooting:Pull Ups")
    rule = "pull-up FGA >= 35% of FGA (tracking data from 2013-14)"
    out.append(_tag("pull-up scorer", "insufficient_data", None, ["no pull-up tracking data"], rule) if not pull else
               _tag("pull-up scorer", "supported" if pull["fga_frequency"] >= 0.35 else "not_supported", None,
                    [f"pull-ups {_pct(pull['fga_frequency'])} of FGA, eFG% {_pct(pull['efg_pct'])}"], rule))
    cl = f.get("clutch")
    rule = "clutch (last 5 min, within 5) points per 36 >= 30 over >= 100 clutch minutes"
    if not cl or not cl.get("minutes") or cl["minutes"] < 100:
        out.append(_tag("clutch scorer", "insufficient_data", None, ["clutch splits unavailable or < 100 clutch minutes"], rule))
    else:
        out.append(_tag("clutch scorer", "supported" if (cl.get("pts_per36") or 0) >= 30 else "not_supported", None,
                        [f"{cl['pts_per36']} pts/36 in {cl['minutes']} clutch minutes, TS% {_pct(cl.get('ts_pct'))} "
                         f"({cl['seasons'][0]}..{cl['seasons'][-1]})"], rule))
    return out
