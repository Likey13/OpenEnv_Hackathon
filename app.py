from __future__ import annotations
import threading
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

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

# ---------------------------------------------------------------------------
# Session registry – one SupportTriageEnvironment per episode_id.
# A global lock protects reads/writes to the registry dict itself.
# Each individual environment also carries its own lock so concurrent
# calls to the *same* episode are serialised correctly.
# ---------------------------------------------------------------------------
_registry: dict[str, tuple[SupportTriageEnvironment, threading.Lock]] = {}
_registry_lock = threading.Lock()

# Keep the latest episode_id so callers that omit the header still work
# (single-client / evaluator usage).
_latest_episode_id: str = ""


def _get_env(episode_id: str) -> tuple[SupportTriageEnvironment, threading.Lock]:
    with _registry_lock:
        if episode_id not in _registry:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown episode_id '{episode_id}'. Call POST /reset first.",
            )
        return _registry[episode_id]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", tags=["health"])
def health() -> dict:
    return {"status": "ok", "env": "support-triage-openenv"}


@app.post("/reset", response_model=StepResponse, tags=["env"])
def reset(request: ResetRequest = ResetRequest()) -> StepResponse:
    """
    Reset the environment and return the initial observation.
    The response includes the episode_id inside observation.task_id context;
    pass it back as the X-Episode-Id header on subsequent /step and /state calls.
    If omitted, the server uses the most recent episode (single-client mode).
    """
    env = SupportTriageEnvironment()
    env_lock = threading.Lock()

    try:
        obs: TicketObservation = env.reset(task_id=request.task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    episode_id = env.state().episode_id

    global _latest_episode_id
    with _registry_lock:
        # Evict old episodes beyond 50 to prevent unbounded growth
        if len(_registry) >= 50:
            oldest = next(iter(_registry))
            del _registry[oldest]
        _registry[episode_id] = (env, env_lock)
        _latest_episode_id = episode_id

    return StepResponse(
        observation=obs,
        reward=0.0,
        done=False,
        info={"episode_id": episode_id},
    )


@app.post("/step", response_model=StepResponse, tags=["env"])
def step(
    action: TriageAction,
    x_episode_id: Optional[str] = Header(default=None),
) -> StepResponse:
    """
    Apply an action and return the next observation, reward, and done flag.
    Pass the episode_id returned by /reset as the X-Episode-Id header.
    Omit the header to act on the most recent episode (single-client mode).
    """
    episode_id = x_episode_id or _latest_episode_id
    if not episode_id:
        raise HTTPException(status_code=400, detail="No active episode. Call POST /reset first.")

    env, env_lock = _get_env(episode_id)

    with env_lock:
        try:
            obs, reward, done = env.step(action)
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    return StepResponse(
        observation=obs,
        reward=reward,
        done=done,
        info={"episode_id": episode_id},
    )


@app.get("/state", response_model=TicketState, tags=["env"])
def state(x_episode_id: Optional[str] = Header(default=None)) -> TicketState:
    """
    Return the current internal state of the environment.
    Pass X-Episode-Id header or omit for the most recent episode.
    """
    episode_id = x_episode_id or _latest_episode_id
    if not episode_id:
        raise HTTPException(status_code=400, detail="No active episode. Call POST /reset first.")

    env, env_lock = _get_env(episode_id)
    with env_lock:
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
