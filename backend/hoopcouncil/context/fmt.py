"""Small formatting helpers for LLM-readable numeric text."""
from __future__ import annotations


def pct(x, nd=1):
    return f"{x * 100:.{nd}f}%" if isinstance(x, (int, float)) and not isinstance(x, bool) else "n/a"


def n(x, nd=1):
    if x is None or isinstance(x, bool):
        return "n/a"
    if isinstance(x, int):
        return f"{x:,}"
    if isinstance(x, float):
        return f"{x:,.{nd}f}"
    return str(x)


def signed(x, nd=1):
    return f"{x:+.{nd}f}" if isinstance(x, (int, float)) else "n/a"


def height(h):
    return f"{h // 12}-{h % 12}" if isinstance(h, int) else "n/a"


def est_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def season_line(l: dict, peak: float | None = None) -> str:
    pg, adv, _tot = l.get("per_game", {}), l.get("advanced", {}), l.get("totals", {})
    teams = "/".join(t for t in (l.get("teams") or [l.get("team")]) if t)
    parts = [
        f"{l['season']} {teams:<7}",
        f"G {n(pg.get('g'))}", f"MP {n(pg.get('mp_per_g'))}", f"PTS {n(pg.get('pts_per_g'))}",
        f"TRB {n(pg.get('trb_per_g'))}", f"AST {n(pg.get('ast_per_g'))}", f"STL {n(pg.get('stl_per_g'))}",
        f"BLK {n(pg.get('blk_per_g'))}", f"TOV {n(pg.get('tov_per_g'))}",
        f"FG {pct(pg.get('fg_pct'))}", f"3P {pct(pg.get('fg3_pct'))} on {n(pg.get('fg3a_per_g'))} 3PA",
        f"FT {pct(pg.get('ft_pct'))} on {n(pg.get('fta_per_g'))} FTA", f"TS {pct(adv.get('ts_pct'))}",
        f"USG {pct(adv.get('usg_pct'))}", f"AST% {pct(adv.get('ast_pct'))}", f"BPM {signed(adv.get('bpm'))}",
        f"WS/48 {n(adv.get('ws_per_48'), 3)}",
    ]
    if peak is not None:
        parts.append(f"peak {peak:.2f}")
    if l.get("awards_text"):
        parts.append(f"awards: {l['awards_text']}")
    return " | ".join(parts)
