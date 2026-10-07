from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Scenario(BaseModel):
    score_margin: Optional[int] = Field(None, description="offense's margin, e.g. -1 = down one")
    quarter: Optional[int] = 4
    game_clock: Optional[float] = Field(None, description="seconds remaining")
    shot_clock: Optional[float] = None
    timeouts: Optional[int] = None
    possession_start: Optional[str] = Field(None, description="e.g. 'sideline out of bounds', 'backcourt after rebound'")
    defensive_scheme: Optional[str] = None
    opponent_notes: Optional[str] = None
    question: str = "Who should take the final shot and what play should we run?"
    lineup: Optional[dict] = None


class SimulationRequest(BaseModel):
    scenario: Scenario
    provider: Optional[str] = None
    player_model: Optional[str] = None
    coach_provider: Optional[str] = None
    coach_model: Optional[str] = None
