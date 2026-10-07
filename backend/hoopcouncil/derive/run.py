"""Run every derivation on a canonical dataset."""
from __future__ import annotations

from .aggregates import career_aggregates, finals_series
from .archetypes import derive_archetypes
from .features import compute_features
from .peak import FORMULA, compute_peak_scores, select_peak_seasons
from .phases import statistical_phases, team_stints
from .profile import milestones, shot_profile_summary, strengths_and_limitations


def derive_all(ds: dict) -> dict:
    name = ds["player"]["full_name"]
    ach = ds.get("achievements", [])
    agg = career_aggregates(ds)
    feats = compute_features(ds, ach)
    peaks = compute_peak_scores(ds)
    strengths, limitations = strengths_and_limitations(feats, agg)
    return {
        "aggregates": agg,
        "finals_series": finals_series(ds),
        "features": feats,
        "peak_scores": peaks,
        "peak_seasons": select_peak_seasons(peaks),
        "peak_formula": FORMULA,
        "career_phases": team_stints(ds, name) + statistical_phases(ds, peaks),
        "archetypes": derive_archetypes(feats),
        "strengths": strengths,
        "limitations": limitations,
        "shot_profile_summary": shot_profile_summary(feats, ds),
        "play_type_tendencies": feats.get("play_types") or {},
        "records": milestones(ds, agg, ach),
    }
