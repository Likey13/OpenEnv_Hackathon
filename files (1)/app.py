from __future__ import annotations
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import TriageAction, TicketObservation, TicketState, ResetRequest, StepResponse
from environment import SupportTriageEnvironment
from tasks import TASKS

app = FastAPI(
    title="Support Triage OpenEnv",
    description="Customer support triage RL environment following the OpenEnv spec.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Single shared environment instance (stateful, single-worker deployment)
env = SupportTriageEnvironment()


@app.get("/", tags=["health"])
def health() -> dict:
    return {"status": "ok", "env": "support-triage-openenv"}


@app.post("/reset", response_model=StepResponse, tags=["env"])
def reset(request: ResetRequest = ResetRequest()) -> StepResponse:
    """Reset the environment and return the initial observation."""
    try:
        obs: TicketObservation = env.reset(task_id=request.task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return StepResponse(observation=obs, reward=0.0, done=False)


@app.post("/step", response_model=StepResponse, tags=["env"])
def step(action: TriageAction) -> StepResponse:
    """Apply an action and return the next observation, reward, and done flag."""
    try:
        obs, reward, done = env.step(action)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return StepResponse(observation=obs, reward=reward, done=done)


@app.get("/state", response_model=TicketState, tags=["env"])
def state() -> TicketState:
    """Return the current internal state of the environment."""
    return env.state()


@app.get("/tasks", tags=["info"])
def list_tasks() -> dict:
    """List available tasks with metadata."""
    return {
        "tasks": [
            {
                "task_id": t.task_id,
                "customer_tier": t.customer_tier,
                "correct_team": t.correct_team,
                "correct_urgency": t.correct_urgency,
                "needs_clarification": t.needs_clarification,
                "progress_hint": t.progress_hint,
            }
            for t in TASKS.values()
        ]
    }
