from __future__ import annotations
import uuid
from models import TriageAction, TicketObservation, TicketState
from tasks import TASKS, Task
from graders import grade_action


class SupportTriageEnvironment:
    MAX_STEPS = 5

    def __init__(self):
        self._episode_id: str = ""
        self._task: Task | None = None
        self._step_count: int = 0
        self._clarification_requested: bool = False
        self._resolved: bool = False
        self._cumulative_reward: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reset(self, task_id: str = "easy") -> TicketObservation:
        if task_id not in TASKS:
            raise ValueError(f"Unknown task_id '{task_id}'. Valid: {list(TASKS)}")

        self._episode_id = str(uuid.uuid4())
        self._task = TASKS[task_id]
        self._step_count = 0
        self._clarification_requested = False
        self._resolved = False
        self._cumulative_reward = 0.0

        return self._build_observation(reward=0.0, done=False, feedback="")

    def step(self, action: TriageAction) -> tuple[TicketObservation, float, bool]:
        if self._task is None:
            raise RuntimeError("Call reset() before step().")
        if self._resolved:
            raise RuntimeError("Episode already finished. Call reset().")

        self._step_count += 1

        if action.ask_clarification:
            self._clarification_requested = True

        reward, feedback = grade_action(action, self._task, self._step_count)
        self._cumulative_reward = min(1.0, self._cumulative_reward + reward)

        # Episode ends: agent resolved OR max steps reached
        done = reward >= 0.8 or self._step_count >= self.MAX_STEPS
        if done:
            self._resolved = True

        obs = self._build_observation(reward=reward, done=done, feedback=feedback)
        return obs, reward, done

    def state(self) -> TicketState:
        if self._task is None:
            return TicketState(
                episode_id="",
                step_count=0,
                task_id="none",
                clarification_requested=False,
                resolved=False,
                cumulative_reward=0.0,
            )
        return TicketState(
            episode_id=self._episode_id,
            step_count=self._step_count,
            task_id=self._task.task_id,
            clarification_requested=self._clarification_requested,
            resolved=self._resolved,
            cumulative_reward=round(self._cumulative_reward, 4),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_observation(self, reward: float, done: bool, feedback: str) -> TicketObservation:
        assert self._task is not None
        return TicketObservation(
            task_id=self._task.task_id,
            ticket_text=self._task.ticket_text,
            customer_tier=self._task.customer_tier,
            allowed_teams=self._task.allowed_teams,
            progress_hint=self._task.progress_hint,
            reward=round(reward, 4),
            done=done,
            feedback=feedback,
        )
