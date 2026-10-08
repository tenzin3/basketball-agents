"""Robust JSON extraction + normalisation of agent outputs."""
from __future__ import annotations

import json
import re


def extract_json(text: str) -> dict:
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.I | re.M).strip()
    try:
        v = json.loads(t)
        if isinstance(v, dict):
            return v
    except ValueError:
        pass
    # find the outermost balanced {...}
    start = t.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(t)):
            c = t[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    cand = t[start:i + 1]
                    for attempt in (cand, re.sub(r",\s*([}\]])", r"\1", cand)):
                        try:
                            v = json.loads(attempt)
                            if isinstance(v, dict):
                                return v
                        except ValueError:
                            pass
                    break
        start = t.find("{", start + 1)
    return {"parse_error": True, "raw": text}


def clamp_conf(v) -> int | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if 0 < x <= 1:
        x *= 100
    return int(max(0, min(100, round(x))))


def as_list(v) -> list:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def normalize(obj: dict, round_number: int, player_name: str) -> dict:
    obj = dict(obj)
    obj["player"] = player_name
    if "confidence" in obj:
        obj["confidence"] = clamp_conf(obj.get("confidence"))
    for k in ("data_support", "risks", "spacing_concerns", "matchup_advantages", "defensive_counters", "evaluations"):
        if k in obj:
            obj[k] = as_list(obj[k])
    if round_number == 1:
        obj.setdefault("proposal", obj.get("proposed_play"))
        obj.setdefault("reasoning", obj.get("tactical_reasoning"))
    return clean_output(obj)


TEXT_KEYS = ("text", "fact", "point", "statement", "description", "detail", "value", "note", "claim")
LIST_FIELDS = ("data_support", "risks", "key_data_points", "off_ball_actions", "career_data_considered")
TEXT_FIELDS = ("message", "position", "reasoning", "reason", "revised_position", "final_answer", "backs", "verdict",
               "answer", "vote_summary", "huddle_line")


def to_text(v) -> str:
    """Models sometimes return objects where text was asked for; flatten them to readable text."""
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, (int, float, bool)):
        return str(v)
    if isinstance(v, dict):
        for k in TEXT_KEYS:
            if isinstance(v.get(k), str) and len(v) <= 2:
                other = [str(x) for kk, x in v.items() if kk != k and x not in (None, "")]
                return v[k] + (f" ({other[0]})" if other else "")
        # a full sentence inside the object already says it all (e.g. {"fact": "LeBron's peak PER is 29.3", "value": 29.3})
        sentences = [x for x in v.values() if isinstance(x, str) and len(x.split()) >= 4]
        if sentences:
            return max(sentences, key=len)
        return ", ".join(to_text(x) for x in v.values() if x not in (None, "", [], {}))
    if isinstance(v, (list, tuple)):
        return "; ".join(to_text(x) for x in v)
    return str(v)


def clean_output(obj: dict) -> dict:
    """Coerce known text / list-of-text fields so the UI always receives strings."""
    if not isinstance(obj, dict) or obj.get("parse_error"):
        return obj
    for k in LIST_FIELDS:
        if k in obj:
            obj[k] = [to_text(x) for x in as_list(obj[k]) if x not in (None, "")]
    for k in TEXT_FIELDS:
        if k in obj and obj[k] is not None and not isinstance(obj[k], str):
            obj[k] = to_text(obj[k])
    if isinstance(obj.get("evaluations"), list):
        obj["evaluations"] = [
            {"of_player": to_text(e.get("of_player")), "stance": to_text(e.get("stance")), "comment": to_text(e.get("comment"))}
            if isinstance(e, dict) else {"of_player": "", "stance": "", "comment": to_text(e)}
            for e in obj["evaluations"]]
    if isinstance(obj.get("rejected_alternatives"), list):
        obj["rejected_alternatives"] = [
            {"proposal": to_text(r.get("proposal")), "proposed_by": to_text(r.get("proposed_by")), "reason": to_text(r.get("reason"))}
            if isinstance(r, dict) else {"proposal": to_text(r), "proposed_by": "", "reason": ""}
            for r in obj["rejected_alternatives"]]
    play = obj.get("play")
    if isinstance(play, dict):
        for k, v in list(play.items()):
            if k == "player_roles" and isinstance(v, dict):
                play[k] = {to_text(n): to_text(r) for n, r in v.items()}
            elif k == "off_ball_actions":
                play[k] = [to_text(x) for x in as_list(v)]
            elif not isinstance(v, str) and v is not None:
                play[k] = to_text(v)
    elif play is not None and not isinstance(play, dict):
        obj["play"] = None
    return obj
