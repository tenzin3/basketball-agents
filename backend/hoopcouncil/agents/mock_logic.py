"""Deterministic offline responses for the mock provider.

Used for tests and UI development without API keys. The "reasoning" is a transparent
heuristic over the context packages (no LLM), and every text is prefixed with [mock].
"""
from __future__ import annotations

import re

LOCS = ["top_of_key", "right_wing", "left_wing", "left_corner", "right_elbow"]
PLAY_WORDS = re.compile(r"\b(play|shot|shoot|possession|seconds?|inbound|run|set|clutch|final|last|down \d|tied)\b", re.I)


def _f(pkg, k):
    v = ((pkg or {}).get("features") or {}).get(k)
    return v if isinstance(v, (int, float)) else None


def rank_players(packages: dict) -> tuple:
    """Return (scorers ranked, playmakers ranked) as lists of (name, score, basis)."""
    scorers, makers = [], []
    for _slug, pkg in packages.items():
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
    question = meta.get("question") or ""
    wants_play = bool(PLAY_WORDS.search(question))
    scorers, makers = rank_players(packages)
    names = [p["player"] for p in packages.values() if p] or [me or "Player"]
    top = scorers[0][0] if scorers else names[0]
    second = scorers[1][0] if len(scorers) > 1 else names[-1]
    handler = makers[0][0] if makers else names[0]
    basis = scorers[0][2] if scorers else "no data"
    rnd = meta.get("round")
    if meta.get("role") == "coach":
        out = {
            "verdict": f"[mock] {top} is the council's answer.",
            "answer": f"[mock] On the heuristic of usage and league-relative efficiency, {top} ranks first and {second} second.",
            "reasoning": f"[mock] Placeholder ranking, not real reasoning: {top} ({basis}).",
            "key_data_points": [f"FACT: {s[0]}: {s[2]}" for s in scorers[:3]],
            "rejected_alternatives": [{"proposal": f"[mock] {s[0]}", "proposed_by": s[0], "reason": "[mock] lower heuristic score"}
                                      for s in scorers[2:4]],
            "vote_summary": "[mock] not a real evaluation", "confidence": 50, "play": None, "court": None,
        }
        if wants_play:
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
            out["play"] = {"play_name": f"[mock] {handler} initiates, {top} primary", "ball_handler": handler,
                           "primary_option": f"[mock] {top} shot", "secondary_option": f"[mock] {second} shot",
                           "third_option": f"[mock] {handler} drive", "counter": "[mock] swing to the weak side",
                           "player_roles": {n: ("[mock] primary" if n == top else "[mock] handler" if n == handler else "[mock] space") for n in names},
                           "off_ball_actions": ["[mock] spacers hold corners"]}
            out["court"] = {"start_positions": start, "ball_starts_with": handler, "play_sequence": seq}
        return out
    if rnd == 1:
        return {"message": f"[mock] My heuristic points to {top}: {basis}.", "position": f"[mock] {top}",
                "reasoning": f"[mock] {top} ranks highest on usage and league-relative efficiency.",
                "data_support": [f"FACT: {basis}"], "risks": ["[mock] placeholder reasoning"],
                "play": ({"play_name": "[mock] High PnR", "primary_option": f"[mock] {top} shot",
                          "secondary_option": f"[mock] {second} shot",
                          "your_role": "[mock] space the floor" if me not in (top, handler) else "[mock] featured role"}
                         if wants_play else None),
                "confidence": 55}
    if rnd == 2:
        r1 = meta.get("round1") or []
        return {"message": f"[mock] Agreed with the group: still {top}.",
                "evaluations": [{"of_player": x.get("player"), "stance": "agree", "comment": "[mock] consistent with heuristic"} for x in r1],
                "revised_position": f"[mock] {top}", "changed_position": False,
                "data_support": [f"FACT: {basis}"], "confidence": 55}
    return {"message": f"[mock] Final answer: {top}.", "final_answer": f"[mock] {top}", "backs": top,
            "reason": "[mock] heuristic", "confidence": 55}
