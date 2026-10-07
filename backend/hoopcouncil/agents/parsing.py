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
    return obj
