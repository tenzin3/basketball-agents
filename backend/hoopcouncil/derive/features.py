"""Feature extraction: career-level numbers (with era context) used by archetypes,
strengths/limitations and the context builder. Every feature records how many seasons
it is based on so downstream text can state coverage honestly."""
from __future__ import annotations

from collections import Counter, defaultdict

from .aggregates import num, season_lines

SHOT_KEYS = {
    "rim_share": ["fga_share_0_3"],
    "short_mid_share": ["fga_share_3_10"],
    "mid_share": ["fga_share_10_16", "fga_share_16_3p"],
    "long_mid_share": ["fga_share_16_3p"],
    "three_share": ["fga_share_3p"],
    "rim_fg_pct": ["fg_pct_0_3"],
    "three_fg_pct_bydist": ["fg_pct_3p"],
    "assisted_share_2p": ["assisted_share_2p"],
    "assisted_share_3p": ["assisted_share_3p"],
    "corner3_share_of_3pa": ["corner3_share_of_3pa"],
    "corner3_fg_pct": ["corner3_fg_pct"],
    "avg_shot_distance_ft": ["avg_shot_distance_ft"],
    "dunk_fga_share": ["dunk_fga_share"],
}


def _mw(lines: list, getter) -> tuple:
    """Minutes-weighted mean over seasons where getter returns a value. -> (value, n_seasons, seasons)."""
    pairs = []
    for l in lines:
        v = getter(l)
        w = num(l.get("totals", {}).get("mp")) or num(l.get("advanced", {}).get("mp"))
        if v is not None and w:
            pairs.append((v, w, l["season"]))
    if not pairs:
        return None, 0, []
    tot = sum(w for _, w, _ in pairs)
    return round(sum(v * w for v, w, _ in pairs) / tot, 4), len(pairs), [s for _, _, s in pairs]


def _shot_value(line: dict, keys: list):
    vals = [num(line.get("shooting", {}).get(k)) for k in keys]
    if any(v is None for v in vals):
        return None
    return sum(vals)


def _midrange_fg(line: dict):
    sh = line.get("shooting", {})
    a, b = num(sh.get("fga_share_10_16")), num(sh.get("fga_share_16_3p"))
    pa, pb = num(sh.get("fg_pct_10_16")), num(sh.get("fg_pct_16_3p"))
    if None in (a, b, pa, pb) or (a + b) == 0:
        return None
    return (a * pa + b * pb) / (a + b)


def league_relative(ds: dict, lines: list, player_key: str, league_key: str, mode: str = "diff"):
    """Minutes-weighted player stat minus (or divided by) league average of the same seasons."""
    la = ds.get("league_averages", {})

    def get(l):
        p = num(l.get("advanced", {}).get(player_key)) if player_key in ("ts_pct", "fg3a_rate", "fta_rate") else None
        if p is None:
            p = num(l.get("per_game", {}).get(player_key))
        lv = num(la.get(l["season"], {}).get(league_key))
        if p is None or lv is None or (mode == "ratio" and not lv):
            return None
        return p - lv if mode == "diff" else p / lv

    return _mw(lines, get)


def compute_features(ds: dict, achievements: list | None = None) -> dict:
    reg = [l for l in season_lines(ds, "regular_season")]
    po = season_lines(ds, "playoffs")
    achievements = achievements if achievements is not None else ds.get("achievements", [])
    f: dict = {"coverage": {}}

    def put(name, triple, total=None):
        v, n, seasons = triple
        f[name] = v
        f["coverage"][name] = {"seasons": n, "of": total if total is not None else len(reg)}

    for k in ("usg_pct", "ast_pct", "trb_pct", "orb_pct", "drb_pct", "stl_pct", "blk_pct", "tov_pct", "ts_pct",
              "fg3a_rate", "fta_rate", "bpm", "obpm", "dbpm", "per"):
        put(k, _mw(reg, lambda l, k=k: num(l.get("advanced", {}).get(k))))
        put(f"playoff_{k}", _mw(po, lambda l, k=k: num(l.get("advanced", {}).get(k))), len(po))
    for k in ("fg3_pct", "ft_pct", "fg_pct", "pts_per_g", "ast_per_g", "trb_per_g", "mp_per_g"):
        put(k, _mw(reg, lambda l, k=k: num(l.get("per_game", {}).get(k))))
    put("rel_ts_pct", league_relative(ds, reg, "ts_pct", "ts_pct"))
    put("rel_fg3a_rate", league_relative(ds, reg, "fg3a_rate", "fg3a_rate", "ratio"))
    put("rel_fg3_pct", league_relative(ds, reg, "fg3_pct", "fg3_pct"))
    put("rel_ft_pct", league_relative(ds, reg, "ft_pct", "ft_pct"))
    put("playoff_rel_ts_pct", league_relative(ds, po, "ts_pct", "ts_pct"), len(po))
    for name, keys in SHOT_KEYS.items():
        put(name, _mw(reg, lambda l, keys=keys: _shot_value(l, keys)))
    put("midrange_fg_pct", _mw(reg, _midrange_fg))
    # play-by-play derived
    for pos in ("pg", "sg", "sf", "pf", "c"):
        put(f"pos_{pos}_share", _mw(reg, lambda l, pos=pos: num(l.get("pbp", {}).get(f"pos_{pos}_share"))
                                    if l.get("pbp") else None))

    def per36(l, k):
        v, mp = num(l.get("pbp", {}).get(k)), num(l.get("pbp", {}).get("mp"))
        return v / mp * 36 if v is not None and mp else None

    put("and1_per36", _mw(reg, lambda l: per36(l, "and1")))
    put("shooting_fouls_drawn_per36", _mw(reg, lambda l: per36(l, "drawn_shooting")))
    put("on_off_pm_per100", _mw(reg, lambda l: num(l.get("pbp", {}).get("on_off_pm_per100"))))
    # totals-based
    reg_tot = defaultdict(float)
    for l in reg:
        for k in ("fta", "mp", "g"):
            v = num(l.get("totals", {}).get(k))
            if v is not None:
                reg_tot[k] += v
    f["fta_per36"] = round(reg_tot["fta"] / reg_tot["mp"] * 36, 2) if reg_tot["mp"] else None
    f["avg_games_per_season"] = round(reg_tot["g"] / len(reg), 1) if reg else None
    f["seasons_under_50_games"] = [l["season"] for l in reg if (num(l.get("per_game", {}).get("g")) or 0) < 50]
    # award counts
    c = Counter(a["achievement_type"] for a in achievements)
    f["award_counts"] = dict(c)
    f["all_defensive_selections"] = c.get("ALL_DEFENSIVE_FIRST", 0) + c.get("ALL_DEFENSIVE_SECOND", 0)
    # play types (Synergy): mean frequency/ppp across seasons available, regular season
    pt: dict = defaultdict(list)
    for r in ds.get("play_types", []):
        if r.get("stat_type") == "regular_season" and r.get("frequency") is not None:
            pt[r["play_type"]].append(r)
    f["play_types"] = {
        k: {"frequency": round(sum(x["frequency"] for x in v) / len(v), 3),
            "ppp": round(sum(x["ppp"] for x in v if x.get("ppp") is not None) / max(1, len([x for x in v if x.get("ppp") is not None])), 3),
            "percentile": round(sum(x["percentile"] for x in v if x.get("percentile") is not None) / max(1, len([x for x in v if x.get("percentile") is not None])), 3),
            "seasons": sorted({x["season"] for x in v})}
        for k, v in pt.items()
    }
    # tracking shots
    tr: dict = defaultdict(list)
    for r in ds.get("tracking_shots", []):
        if r.get("stat_type") == "regular_season" and r.get("fga_frequency") is not None:
            tr[(r["category"], r["label"])].append(r)
    f["tracking"] = {f"{cat}:{lab}": {"fga_frequency": round(sum(x["fga_frequency"] for x in v) / len(v), 3),
                                      "efg_pct": round(sum(x["efg_pct"] for x in v if x.get("efg_pct") is not None) / max(1, len([x for x in v if x.get("efg_pct") is not None])), 3),
                                      "seasons": sorted({x["season"] for x in v})}
                     for (cat, lab), v in tr.items()}
    # clutch
    cl = [r for r in ds.get("clutch", []) if r.get("stat_type") == "regular_season"]
    if cl:
        tot = defaultdict(float)
        for r in cl:
            for k in ("gp", "minutes", "pts", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "ast", "tov", "plus_minus"):
                if num(r.get(k)) is not None:
                    tot[k] += r[k]
        f["clutch"] = {
            "seasons": sorted({r["season"] for r in cl}), **{k: round(v, 1) for k, v in tot.items()},
            "pts_per36": round(tot["pts"] / tot["minutes"] * 36, 1) if tot["minutes"] else None,
            "fg_pct": round(tot["fgm"] / tot["fga"], 3) if tot["fga"] else None,
            "ts_pct": round(tot["pts"] / (2 * (tot["fga"] + 0.44 * tot["fta"])), 3) if tot["fga"] else None,
            "definition": cl[0].get("definition"),
        }
    else:
        f["clutch"] = None
    f["height_in"] = ds.get("player", {}).get("height_in")
    f["primary_position"] = ds.get("player", {}).get("primary_position")
    return f
