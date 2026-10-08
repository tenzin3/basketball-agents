from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Scenario(BaseModel):
    """A chat question. The game-state fields are optional extras."""
    context: Optional[str] = Field(None, max_length=2000, description="optional extra context typed by the fan")
    score_margin: Optional[int] = Field(None, description="offense's margin, e.g. -1 = down one")
    quarter: Optional[int] = None
    game_clock: Optional[float] = Field(None, description="seconds remaining")
    shot_clock: Optional[float] = None
    timeouts: Optional[int] = None
    possession_start: Optional[str] = Field(None, max_length=200, description="e.g. 'sideline out of bounds', 'backcourt after rebound'")
    defensive_scheme: Optional[str] = Field(None, max_length=300)
    opponent_notes: Optional[str] = Field(None, max_length=1000)
    question: str = Field(..., min_length=1, max_length=2000)
    lineup: Optional[dict[str, str]] = None

    @field_validator("lineup")
    @classmethod
    def _small_lineup(cls, v):
        # everything here ends up in every prompt, so keep it to a real lineup
        if v is not None and (len(v) > 5 or any(len(k) > 40 or len(x) > 60 for k, x in v.items())):
            raise ValueError("lineup: at most 5 positions, short names only")
        return v


class SimulationRequest(BaseModel):
    scenario: Scenario
    provider: Optional[str] = Field(None, max_length=32)
    player_model: Optional[str] = Field(None, max_length=120)
    coach_provider: Optional[str] = Field(None, max_length=32)
    coach_model: Optional[str] = Field(None, max_length=120)
