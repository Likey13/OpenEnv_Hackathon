"""
environment.py – Core RL loop for the Support Triage OpenEnv.

Cross-file dependencies
-----------------------
models.py → TriageAction, TicketObservation, TicketState
    (defines every data shape this module produces/consumes)
tasks.py → TASKS dict + Task dataclass
    (provides ticket text, correct answers, and allowed teams)
graders.py → grade_action(action, task, step) → (float, str)
    (scores each agent action and returns dense reward + feedback)

Used by
-------
app.py → instantiates SupportTriageEnvironment per episode inside the
    session registry; calls reset(), step(), state() via HTTP routes
tests/test_graders.py → imports SupportTriageEnvironment directly for unit tests

Protocol (OpenEnv spec)
-----------------------
1. Call reset(task_id) → returns TicketObservation, episode starts fresh
2. Call step(action) → returns (TicketObservation, reward, done)
   repeat until done=True or MAX_STEPS reached
3. Call state() → returns TicketState snapshot at any point

Reward contract (see graders.py for breakdown)
----------------------------------------------
Each step returns a score in [0.0, 1.0].
done=True when reward >= 0.8 (strong solve) or step_count >= MAX_STEPS.
"""

from __future__ import annotations

import uuid

from graders import grade_action
from models import TicketObservation, TicketState, TriageAction
from tasks import TASKS, Task


class SupportTriageEnvironment:
    """
    Stateful single-episode environment.

    Thread safety:
        This class is NOT thread-safe on its own.
        app.py wraps each instance with a threading.Lock inside the session
        registry so concurrent HTTP calls to the same episode are serialised.
    """

    MAX_STEPS = 5  # matches runtime.max_steps in openenv.yaml

    def __init__(self) -> None:
        self._episode_id: str = ""
        self._task: Task | None = None
        self._step_count: int = 0
        self._clarification_requested: bool = False
        self._resolved: bool = False
        self._cumulative_reward: float = 0.0

    # ------------------------------------------------------------------
    # Public API (called by app.py routes and tests)
    # ------------------------------------------------------------------

    def reset(self, task_id: str = "easy") -> TicketObservation:
        """
        Start a new episode for the given task.

        Args:
            task_id: one of "easy" | "medium" | "hard" (see tasks.py TASKS)

        Returns:
            TicketObservation with reward=0.0, done=False, feedback=""

        Raises:
            ValueError: if task_id is not in tasks.TASKS
        """
        if task_id not in TASKS:
            raise ValueError(
                f"Unknown task_id '{task_id}'. "
                f"Valid options (from tasks.py): {list(TASKS)}"
            )

        self._episode_id = str(uuid.uuid4())
        self._task = TASKS[task_id]
        self._step_count = 0
        self._clarification_requested = False
        self._resolved = False
        self._cumulative_reward = 0.0

        return self._build_observation(reward=0.0, done=False, feedback="")

    def step(self, action: TriageAction) -> tuple[TicketObservation, float, bool]:
        """
        Apply one agent action and advance the episode.

        Args:
            action: TriageAction (from models.py) — chosen_team, urgency,
                ask_clarification, response_text

        Returns:
            (TicketObservation, reward, done)
            reward is in [0.0, 1.0] — see graders.py for breakdown
            done=True when reward >= 0.8 or step_count >= MAX_STEPS

        Raises:
            RuntimeError: if reset() has not been called first
            RuntimeError: if the episode is already finished (done=True)
        """
        if self._task is None:
            raise RuntimeError(
                "Call reset() before step(). "
                "See app.py POST /reset → POST /step flow."
            )

        if self._resolved:
            raise RuntimeError(
                "Episode already finished. Call reset() to start a new one. "
                "app.py will return HTTP 400 if you send a step to a resolved episode."
            )

        self._step_count += 1

        if action.ask_clarification:
            self._clarification_requested = True

        reward, feedback = grade_action(action, self._task, self._step_count)
        self._cumulative_reward = min(1.0, self._cumulative_reward + reward)

        done = reward >= 0.8 or self._step_count >= self.MAX_STEPS
        if done:
            self._resolved = True

        obs = self._build_observation(reward=reward, done=done, feedback=feedback)
        return obs, reward, done

    def state(self) -> TicketState:
        """
        Return a snapshot of current episode state (TicketState from models.py).

        Safe to call at any point — before reset, mid-episode, or after done.
        Called by app.py GET /state and tests/test_graders.py assertions.
        """
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
    # Private helpers
    # ------------------------------------------------------------------

    def _build_observation(
        self, reward: float, done: bool, feedback: str
    ) -> TicketObservation:
        """
        Construct a TicketObservation (models.py) from current task state.

        ticket_text, customer_tier, allowed_teams, progress_hint all come
        from the Task dataclass in tasks.py.
        """
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
