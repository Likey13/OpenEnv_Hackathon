from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


class TriageAction(BaseModel):
    chosen_team: Literal["account_support", "billing", "technical_support", "trust_safety"]
    urgency: Literal["low", "medium", "high"]
    ask_clarification: bool
    response_text: str


class TicketObservation(BaseModel):
    task_id: str
    ticket_text: str
    customer_tier: str
    allowed_teams: list[str]
    progress_hint: str
    reward: float = 0.0
    done: bool = False
    feedback: str = ""


class TicketState(BaseModel):
    episode_id: str
    step_count: int
    task_id: str
    clarification_requested: bool
    resolved: bool
    cumulative_reward: float


class ResetRequest(BaseModel):
    task_id: Literal["easy", "medium", "hard"] = "easy"


class StepResponse(BaseModel):
    observation: TicketObservation
    reward: float
    done: bool
    info: dict = Field(default_factory=dict)
