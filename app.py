from __future__ import annotations

import threading
import uuid
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from environment import SupportTriageEnvironment
from models import ResetRequest, StepResponse, TicketState, TriageAction
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

# ---------------------------------------------------------------------------
# Session registry - one SupportTriageEnvironment per episode_id.
# A global lock protects reads/writes to the registry dict itself.
# Each individual environment also carries its own lock so concurrent
# calls to the same episode are serialized correctly.
# ---------------------------------------------------------------------------
_registry: dict[str, tuple[SupportTriageEnvironment, threading.Lock]] = {}
_registry_lock = threading.Lock()

# Keep the latest episode_id so callers that omit the header still work
# (single-client / evaluator usage).
_latest_episode_id: str = ""


def _create_episode(task_id: str) -> tuple[str, dict]:
    env = SupportTriageEnvironment()
    observation = env.reset(task_id)

    episode_id = str(uuid.uuid4())

    with _registry_lock:
        _registry[episode_id] = (env, threading.Lock())
        global _latest_episode_id
        _latest_episode_id = episode_id

    return episode_id, observation.model_dump()


def _resolve_episode_id(header_episode_id: Optional[str]) -> str:
    episode_id = header_episode_id or _latest_episode_id
    if not episode_id:
        raise HTTPException(status_code=400, detail="Missing episode ID")
    return episode_id


def _get_episode(header_episode_id: Optional[str]) -> tuple[str, SupportTriageEnvironment, threading.Lock]:
    episode_id = _resolve_episode_id(header_episode_id)

    with _registry_lock:
        record = _registry.get(episode_id)

    if record is None:
        raise HTTPException(status_code=404, detail="Episode not found")

    env, env_lock = record
    return episode_id, env, env_lock


@app.get("/")
def health() -> dict:
    return {"status": "ok", "environment": "support-triage-openenv"}


@app.post("/reset")
def reset(request: ResetRequest) -> dict:
    if request.task_id not in TASKS:
        raise HTTPException(status_code=400, detail=f"Unknown task_id: {request.task_id}")

    episode_id, observation = _create_episode(request.task_id)
    return {
        "observation": observation,
        "info": {"episode_id": episode_id},
    }


@app.post("/step", response_model=StepResponse)
def step(
    action: TriageAction,
    x_episode_id: Optional[str] = Header(default=None, alias="X-Episode-Id"),
) -> StepResponse:
    _, env, env_lock = _get_episode(x_episode_id)

    with env_lock:
        try:
            observation, reward, done = env.step(action)
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StepResponse(
        observation=observation,
        reward=reward,
        done=done,
    )


@app.get("/state", response_model=TicketState)
def state(
    x_episode_id: Optional[str] = Header(default=None, alias="X-Episode-Id"),
) -> TicketState:
    _, env, env_lock = _get_episode(x_episode_id)

    with env_lock:
        try:
            return env.state()
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/tasks")
def tasks() -> dict:
    return {
        "tasks": [
            {
                "task_id": task.task_id,
                "correct_team": task.correct_team,
                "correct_urgency": task.correct_urgency,
                "needs_clarification": task.needs_clarification,
                "progress_hint": task.progress_hint,
            }
            for task in TASKS.values()
        ]
    }
