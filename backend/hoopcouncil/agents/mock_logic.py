"""Deterministic offline responses for the mock provider.

Used for tests and UI development without API keys. The 'reasoning' is a transparent
heuristic over the context packages (no LLM), and every text is prefixed with [mock].
"""
from __future__ import annotations

LOCS = ["top_of_key", "right_wing", "left_wing", "left_corner", "right_elbow"]


def _f(pkg, k):
    v = ((pkg or {}).get("features") or {}).get(k)
    return v if isinstance(v, (int, float)) else None


def rank_players(packages: dict) -> tuple:
    """Return (scorers ranked, playmakers ranked) as lists of (name, score, basis)."""
    scorers, makers = [], []
    for slug, pkg in packages.items():
        if not pkg:
            continue
        name = pkg["player"]
        usg, rts, prts = _f(pkg, "usg_pct"), _f(pkg, "rel_ts_pct"), _f(pkg, "playoff_rel_ts_pct")
        s = (usg or 0) * 2 + (rts or 0) * 5 + (prts or 0) * 3
        scorers.append((name, round(s, 3), f"USG {usg}, TS vs league {rts}, playoff TS vs league {prts}"))
        ast = _f(pkg, "ast_pct")
        makers.append((name, ast or 0, f"AST% {ast}"))
    scorers.sort(key=lambda x: -x[1])
    makers.sort(key=lambda x: -x[1])
    return scorers, makers


def mock_response(meta: dict) -> dict:
    packages = meta.get("packages") or {}
    me = meta.get("player")
    scorers, makers = rank_players(packages)
    names = [p["player"] for p in packages.values() if p] or [me or "Player"]
    top = scorers[0][0] if scorers else names[0]
    second = scorers[1][0] if len(scorers) > 1 else names[-1]
    handler = makers[0][0] if makers else names[0]
    basis = scorers[0][2] if scorers else "no data"
    rnd = meta.get("round")
    if meta.get("role") == "coach":
        others = [n for n in names if n not in (top, handler)]
        start = {n: LOCS[i % len(LOCS)] for i, n in enumerate(names)}
        start[handler] = "top_of_key"
        if top != handler:
            start[top] = "right_wing"
        seq = [{"time": 0, "player": handler, "action": "dribble", "destination": "top_of_key"}]
        if top != handler:
            seq += [{"time": 1, "player": others[0] if others else handler, "action": "screen", "target": top, "location": "right_slot"},
                    {"time": 2, "player": top, "action": "cut", "destination": "right_elbow"},
                    {"time": 3, "player": handler, "action": "pass", "target": top},
                    {"time": 5, "player": top, "action": "shoot", "location": "right_elbow"}]
        else:
            seq += [{"time": 2, "player": handler, "action": "drive", "destination": "right_elbow"},
                    {"time": 4, "player": handler, "action": "shoot", "location": "right_elbow"}]
        return {
            "play_name": f"[mock] {handler} initiates, {top} primary",
            "ball_handler": handler, "inbounder": None,
            "primary_option": f"[mock] {top} shot", "secondary_option": f"[mock] {second} shot",
            "third_option": f"[mock] {handler} drive", "counter": "[mock] swing to the weak side",
            "player_roles": {n: ("[mock] primary" if n == top else "[mock] handler" if n == handler else "[mock] space") for n in names},
            "off_ball_actions": ["[mock] spacers hold corners"],
            "reasoning": f"[mock] Heuristic ranking by usage and league-relative efficiency: {top} ({basis}).",
            "key_data_points": [f"FACT: {s[0]}: {s[2]}" for s in scorers[:3]],
            "career_data_considered": ["usage", "league-relative TS%", "playoff TS%", "AST%"],
            "rejected_alternatives": [{"proposal": f"[mock] {s[0]} primary", "proposed_by": s[0], "reason": "[mock] lower heuristic score"} for s in scorers[2:4]],
            "vote_summary": "[mock] not a real evaluation", "confidence": 50,
            "court": {"start_positions": start, "ball_starts_with": handler, "play_sequence": seq},
        }
    if rnd == 1:
        return {"proposed_play": f"[mock] {handler} high pick-and-roll, {top} as finisher", "play_name": "[mock] High PnR",
                "primary_option": f"[mock] {top} shot", "secondary_option": f"[mock] {second} shot",
                "your_role": "[mock] space the floor" if me not in (top, handler) else "[mock] featured role",
                "tactical_reasoning": f"[mock] {top} ranks highest on the heuristic ({basis}).",
                "data_support": [f"FACT: {basis}"], "risks": ["[mock] switch neutralises the screen"],
                "confidence": 55, "huddle_line": f"[mock] Get {top} the ball off a {handler} action."}
    if rnd == 2:
        r1 = meta.get("round1") or []
        return {"evaluations": [{"of_player": x.get("player"), "stance": "agree", "comment": "[mock] consistent with heuristic"} for x in r1],
                "spacing_concerns": [], "matchup_advantages": [], "defensive_counters": [],
                "revised_proposal": f"[mock] {handler} PnR, {top} primary", "changed_position": False,
                "data_support": [f"FACT: {basis}"], "confidence": 55, "huddle_line": f"[mock] Still {top}."}
    return {"final_vote": f"[mock] {handler} PnR for {top}", "voted_for_proposal_of": top,
            "preferred_primary_option": f"[mock] {top} shot", "reason": "[mock] heuristic", "confidence": 55,
            "huddle_line": f"[mock] Vote: {top}."}
