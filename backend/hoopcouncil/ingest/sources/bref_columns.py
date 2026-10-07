"""Mapping from Basketball Reference header labels to HoopCouncil stat keys.

Conventions for stored values:
* every percentage / share / rate is a FRACTION in [0, 1] (BR shows some
  advanced percentages such as USG% as percentage points; they are divided by 100).
* per-game counting stats carry a `_per_g` suffix; totals carry none.
"""
from __future__ import annotations

import re

from .table_parse import Row, parse_number

META_LABELS = {"Season": "season", "Age": "age", "Team": "team", "Tm": "team", "Lg": "league",
               "Pos": "pos", "Awards": "awards"}

BASIC = {"G": "g", "GS": "gs", "MP": "mp", "FG": "fg", "FGA": "fga", "FG%": "fg_pct", "3P": "fg3",
         "3PA": "fg3a", "3P%": "fg3_pct", "2P": "fg2", "2PA": "fg2a", "2P%": "fg2_pct", "eFG%": "efg_pct",
         "FT": "ft", "FTA": "fta", "FT%": "ft_pct", "ORB": "orb", "DRB": "drb", "TRB": "trb", "AST": "ast",
         "STL": "stl", "BLK": "blk", "TOV": "tov", "PF": "pf", "PTS": "pts", "Trp-Dbl": "trp_dbl",
         "Trp Dbl": "trp_dbl", "GmSc": "game_score", "+/-": "plus_minus"}
NO_PER_G_SUFFIX = {"g", "gs", "fg_pct", "fg3_pct", "fg2_pct", "efg_pct", "ft_pct", "game_score", "plus_minus"}

ADVANCED = {"PER": "per", "TS%": "ts_pct", "3PAr": "fg3a_rate", "FTr": "fta_rate", "ORB%": "orb_pct",
            "DRB%": "drb_pct", "TRB%": "trb_pct", "AST%": "ast_pct", "STL%": "stl_pct", "BLK%": "blk_pct",
            "TOV%": "tov_pct", "USG%": "usg_pct", "OWS": "ows", "DWS": "dws", "WS": "ws", "WS/48": "ws_per_48",
            "OBPM": "obpm", "DBPM": "dbpm", "BPM": "bpm", "VORP": "vorp", "G": "g", "GS": "gs", "MP": "mp"}
# BR displays these in percentage points (e.g. 32.6) -> convert to fraction.
PERCENT_POINT_KEYS = {"orb_pct", "drb_pct", "trb_pct", "ast_pct", "stl_pct", "blk_pct", "tov_pct", "usg_pct"}

_DIST = {"2P": "2p", "0-3": "0_3", "3-10": "3_10", "10-16": "10_16", "16-3P": "16_3p", "16-3pt": "16_3p",
         "16 ft-3P": "16_3p", "3P": "3p"}


def slug(s: str) -> str:
    s = s.lower().replace("%", "pct").replace("+/-", "pm").replace("/", "_per_")
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def shooting_key(label: str, group: str) -> str:
    g = group.lower()
    if "% of fga" in g:
        return f"fga_share_{_DIST.get(label, slug(label))}"
    if "fg% by" in g:
        return f"fg_pct_{_DIST.get(label, slug(label))}"
    if "ast" in g:
        return f"assisted_share_{_DIST.get(label, slug(label))}"
    if "dunk" in g:
        return {"%FGA": "dunk_fga_share", "#": "dunks", "Md.": "dunks"}.get(label, f"dunk_{slug(label)}")
    if "corner" in g:
        return {"%3PA": "corner3_share_of_3pa", "3P%": "corner3_fg_pct"}.get(label, f"corner3_{slug(label)}")
    if "court" in g or "heave" in g:
        return {"Att.": "heave_att", "#": "heave_made", "Md.": "heave_made"}.get(label, f"heave_{slug(label)}")
    return {"FG%": "fg_pct", "Dist.": "avg_shot_distance_ft", "G": "g", "MP": "mp", "GS": "gs"}.get(label, slug(label))


def pbp_key(label: str, group: str) -> str:
    g = group.lower()
    if "position" in g:
        return f"pos_{label.replace('%', '').lower()}_share"
    if "+/-" in g or "per 100" in g:
        return {"OnCourt": "on_court_pm_per100", "On-Off": "on_off_pm_per100"}.get(label, f"pm_{slug(label)}")
    if "turnover" in g:
        return {"BadPass": "tov_bad_pass", "LostBall": "tov_lost_ball"}.get(label, f"tov_{slug(label)}")
    if "committed" in g:
        return {"Shoot": "fouls_shooting", "Off.": "fouls_offensive"}.get(label, f"fouls_{slug(label)}")
    if "drawn" in g:
        return {"Shoot": "drawn_shooting", "Off.": "drawn_offensive"}.get(label, f"drawn_{slug(label)}")
    if "misc" in g:
        return {"PGA": "points_generated_by_assists", "And1": "and1", "Blkd": "fga_blocked"}.get(label, slug(label))
    return {"G": "g", "MP": "mp", "GS": "gs"}.get(label, slug(label))


def row_meta(row: Row) -> dict:
    out = {}
    for col, cell in row.cells:
        if col is None:
            continue
        k = META_LABELS.get(col.label)
        if k and k not in out:
            out[k] = cell.text or None
            if k == "team":
                out["team_hrefs"] = cell.hrefs
    if "season" not in out:  # unlabeled first column
        out["season"] = row.first_text()
    return out


def map_row(row: Row, kind: str) -> tuple:
    """Return (values, leader_flags). kind in per_game|totals|per_poss|advanced|shooting|pbp."""
    vals: dict = {}
    leaders: list = []
    for col, cell in row.cells:
        if col is None or col.label in META_LABELS or col.label in ("Rk", ""):
            continue
        if kind in ("per_game", "totals"):
            base = BASIC.get(col.label)
            if base is None:
                continue
            key = base if (kind == "totals" or base in NO_PER_G_SUFFIX) else f"{base}_per_g"
        elif kind == "per_poss":
            if col.label in ("ORtg", "DRtg"):
                key = col.label.lower()
            else:
                base = BASIC.get(col.label)
                if base is None:
                    continue
                key = base if base in NO_PER_G_SUFFIX else f"{base}_per_100"
        elif kind == "advanced":
            key = ADVANCED.get(col.label) or slug(col.label)
        elif kind == "shooting":
            key = shooting_key(col.label, col.group)
        elif kind == "pbp":
            key = pbp_key(col.label, col.group)
        else:
            key = slug(col.label)
        v = parse_number(cell.text)
        if kind == "advanced" and key in PERCENT_POINT_KEYS and v is not None:
            v = round(v / 100.0, 4)
        if key not in vals:
            vals[key] = v
        if cell.bold and v is not None:
            leaders.append(key)
    return vals, leaders
