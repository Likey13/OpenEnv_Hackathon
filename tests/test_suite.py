"""
tests/test_suite.py
===================
Combined validation suite for the Support Triage OpenEnv.

Sections
--------
- TestGraders: unit tests for graders.py (no server needed)
- TestEnvironment: unit tests for environment.py (no server needed)
- TestHTTPEndpoints: integration tests against app.py (server must be running)

Run modes
---------
- Unit tests only:
  pytest tests/test_suite.py -v -m unit
- Integration tests only (server must be running on port 7860):
  pytest tests/test_suite.py -v -m integration
- Everything:
  pytest tests/test_suite.py -v
- Standalone HTTP validator:
  python tests/test_suite.py
  python tests/test_suite.py --base-url https://your-space.hf.space

Cross-file references
---------------------
- models.py -> TriageAction, TicketObservation, TicketState
- tasks.py -> TASKS dict, Task dataclass
- graders.py -> grade_action()
- environment.py -> SupportTriageEnvironment
- app.py -> HTTP endpoints /reset /step /state /tasks
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

import pytest
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from environment import SupportTriageEnvironment  # noqa: E402
from graders import grade_action  # noqa: E402
from models import TriageAction  # noqa: E402
from tasks import TASKS  # noqa: E402

BASE_URL = os.environ.get("BASE_URL", "http://localhost:7860")

DUMMY_ACTION = {
    "chosen_team": "account_support",
    "urgency": "low",
    "ask_clarification": False,
    "response_text": "We will reset your account password right away.",
}


def perfect_action(task_id: str) -> TriageAction:
    """
    Return a TriageAction with all correct fields and task-specific response
    text that satisfies each task's required_response_keywords.
    """
    task = TASKS[task_id]

    response_map = {
        "easy": "We will reset your account password right away.",
        "medium": "We need to clarify which invoice and charge is incorrect.",
        "hard": "We will investigate the security breach and escalate immediately.",
    }

    return TriageAction(
        chosen_team=task.correct_team,
        urgency=task.correct_urgency,
        ask_clarification=task.needs_clarification,
        response_text=response_map[task_id],
    )


def wrong_action() -> TriageAction:
    """Return a deliberately wrong TriageAction."""
    return TriageAction(
        chosen_team="billing",
        urgency="high",
        ask_clarification=True,
        response_text="x",
    )


@pytest.mark.unit
class TestGraders:
    def test_perfect_score_easy(self):
        score, feedback = grade_action(perfect_action("easy"), TASKS["easy"], 1)
        assert score == pytest.approx(1.0), f"Expected 1.0, got {score}. {feedback}"

    def test_perfect_score_medium(self):
        score, feedback = grade_action(perfect_action("medium"), TASKS["medium"], 1)
        assert score == pytest.approx(1.0), f"Expected 1.0, got {score}. {feedback}"

    def test_perfect_score_hard(self):
        score, feedback = grade_action(perfect_action("hard"), TASKS["hard"], 1)
        assert score == pytest.approx(1.0), f"Expected 1.0, got {score}. {feedback}"

    def test_score_always_in_range(self):
        for task_id in TASKS:
            score, _ = grade_action(wrong_action(), TASKS[task_id], 1)
            assert 0.0 <= score <= 1.0

    def test_wrong_team_loses_points(self):
        task = TASKS["easy"]
        good = grade_action(perfect_action("easy"), task, 1)[0]
        bad = grade_action(
            TriageAction(
                chosen_team="billing",
                urgency=task.correct_urgency,
                ask_clarification=task.needs_clarification,
                response_text="We will reset your account password right away.",
            ),
            task,
            1,
        )[0]
        assert good > bad

    def test_wrong_urgency_loses_points(self):
        task = TASKS["easy"]
        score, _ = grade_action(
            TriageAction(
                chosen_team=task.correct_team,
                urgency="high",
                ask_clarification=task.needs_clarification,
                response_text="We will reset your account password right away.",
            ),
            task,
            1,
        )
        assert score < 1.0

    def test_unnecessary_clarification_loses_points(self):
        task = TASKS["easy"]
        score, _ = grade_action(
            TriageAction(
                chosen_team=task.correct_team,
                urgency=task.correct_urgency,
                ask_clarification=True,
                response_text="We will reset your account password right away.",
            ),
            task,
            1,
        )
        assert score < 1.0

    def test_missing_clarification_loses_points(self):
        task = TASKS["medium"]
        score, _ = grade_action(
            TriageAction(
                chosen_team=task.correct_team,
                urgency=task.correct_urgency,
                ask_clarification=False,
                response_text="We need to clarify which invoice and charge is incorrect.",
            ),
            task,
            1,
        )
        assert score < 1.0

    def test_response_too_short(self):
        task = TASKS["easy"]
        score, _ = grade_action(
            TriageAction(
                chosen_team=task.correct_team,
                urgency=task.correct_urgency,
                ask_clarification=task.needs_clarification,
                response_text="ok",
            ),
            task,
            1,
        )
        assert score < 1.0

    def test_response_too_long(self):
        task = TASKS["easy"]
        score, _ = grade_action(
            TriageAction(
                chosen_team=task.correct_team,
                urgency=task.correct_urgency,
                ask_clarification=task.needs_clarification,
                response_text="a" * 301,
            ),
            task,
            1,
        )
        assert score < 1.0

    def test_feedback_is_non_empty_string(self):
        _, feedback = grade_action(perfect_action("easy"), TASKS["easy"], 1)
        assert isinstance(feedback, str) and len(feedback) > 0


@pytest.mark.unit
class TestEnvironment:
    def setup_method(self):
        self.env = SupportTriageEnvironment()

    def test_reset_returns_correct_observation(self):
        for task_id in ["easy", "medium", "hard"]:
            obs = self.env.reset(task_id)
            assert obs.task_id == task_id
            assert obs.ticket_text
            assert not obs.done
            assert obs.reward == 0.0

    def test_reset_invalid_task_raises_value_error(self):
        with pytest.raises(ValueError):
            self.env.reset("nonexistent")

    def test_step_before_reset_raises_runtime_error(self):
        with pytest.raises(RuntimeError):
            SupportTriageEnvironment().step(perfect_action("easy"))

    def test_perfect_action_completes_episode(self):
        self.env.reset("easy")
        _, reward, done = self.env.step(perfect_action("easy"))
        assert reward == pytest.approx(1.0)
        assert done is True

    def test_step_after_done_raises_runtime_error(self):
        self.env.reset("easy")
        self.env.step(perfect_action("easy"))
        with pytest.raises(RuntimeError):
            self.env.step(perfect_action("easy"))

    def test_max_steps_terminates_episode(self):
        self.env.reset("easy")
        done = False
        for _ in range(5):
            _, _, done = self.env.step(wrong_action())
            if done:
                break
        assert done

    def test_state_step_count_increments(self):
        self.env.reset("medium")
        assert self.env.state().step_count == 0
        self.env.step(wrong_action())
        assert self.env.state().step_count == 1

    def test_state_tracks_clarification_flag(self):
        self.env.reset("easy")
        self.env.step(
            TriageAction(
                chosen_team="account_support",
                urgency="low",
                ask_clarification=True,
                response_text="Can you provide more details please?",
            )
        )
        assert self.env.state().clarification_requested is True

    def test_cumulative_reward_accumulates(self):
        self.env.reset("easy")
        _, reward1, done = self.env.step(
            TriageAction(
                chosen_team="account_support",
                urgency="low",
                ask_clarification=False,
                response_text="We will reset your account password right away.",
            )
        )
        if not done:
            assert self.env.state().cumulative_reward >= reward1

    def test_reset_clears_previous_episode(self):
        self.env.reset("easy")
        self.env.step(perfect_action("easy"))
        self.env.reset("hard")
        state = self.env.state()
        assert state.task_id == "hard"
        assert state.step_count == 0
        assert not state.resolved

    def test_reward_always_in_range_all_tasks(self):
        for task_id in ["easy", "medium", "hard"]:
            self.env.reset(task_id)
            for _ in range(5):
                _, reward, done = self.env.step(wrong_action())
                assert 0.0 <= reward <= 1.0
                if done:
                    break


@pytest.mark.integration
class TestHTTPEndpoints:
    """
    Live HTTP tests against a running app.py server.

    Start the server before running:
    python -m uvicorn app:app --port 7860

    Override the URL with:
    BASE_URL=https://your-space.hf.space pytest -m integration
    """

    def _reset(self, task_id: str) -> tuple[str, dict]:
        response = requests.post(
            f"{BASE_URL}/reset", json={"task_id": task_id}, timeout=10
        )
        assert response.status_code == 200, f"/reset failed: {response.text}"
        data = response.json()
        return data.get("info", {}).get("episode_id", ""), data.get("observation", {})

    def _step(self, episode_id: str, action: dict | None = None) -> dict:
        response = requests.post(
            f"{BASE_URL}/step",
            json=action or DUMMY_ACTION,
            headers={"X-Episode-Id": episode_id},
            timeout=10,
        )
        assert response.status_code == 200, f"/step failed: {response.text}"
        return response.json()

    def _state(self, episode_id: str) -> dict:
        response = requests.get(
            f"{BASE_URL}/state",
            headers={"X-Episode-Id": episode_id},
            timeout=10,
        )
        assert response.status_code == 200, f"/state failed: {response.text}"
        return response.json()

    def test_health_returns_ok(self):
        response = requests.get(f"{BASE_URL}/", timeout=10)
        assert response.status_code == 200
        assert response.json().get("status") == "ok"

    def test_reset_all_tasks_return_200(self):
        for task_id in ["easy", "medium", "hard"]:
            episode_id, obs = self._reset(task_id)
            assert obs.get("task_id") == task_id
            assert obs.get("ticket_text")
            assert isinstance(obs.get("allowed_teams"), list)
            assert episode_id

    def test_reset_invalid_task_returns_400(self):
        response = requests.post(
            f"{BASE_URL}/reset", json={"task_id": "invalid"}, timeout=10
        )
        assert response.status_code == 400

    def test_step_returns_reward_and_done(self):
        episode_id, _ = self._reset("easy")
        result = self._step(episode_id)
        assert 0.0 <= result.get("reward", -1) <= 1.0
        assert "done" in result
        assert result.get("observation", {}).get("feedback")

    def test_step_without_header_uses_latest_episode(self):
        self._reset("easy")
        response = requests.post(f"{BASE_URL}/step", json=DUMMY_ACTION, timeout=10)
        assert response.status_code == 200

    def test_state_has_all_required_keys(self):
        episode_id, _ = self._reset("easy")
        self._step(episode_id)
        state = self._state(episode_id)
        for key in [
            "episode_id",
            "step_count",
            "task_id",
            "clarification_requested",
            "resolved",
            "cumulative_reward",
        ]:
            assert key in state

    def test_state_step_count_after_one_step(self):
        episode_id, _ = self._reset("easy")
        self._step(episode_id)
        assert self._state(episode_id).get("step_count") == 1

    def test_score_in_range_all_tasks(self):
        for task_id in ["easy", "medium", "hard"]:
            episode_id, _ = self._reset(task_id)
            final_reward = 0.0
            for _ in range(5):
                result = self._step(episode_id)
                final_reward = result.get("reward", 0.0)
                if result.get("done"):
                    break
            assert 0.0 <= final_reward <= 1.0

    def test_tasks_endpoint_returns_three_tasks(self):
        response = requests.get(f"{BASE_URL}/tasks", timeout=10)
        assert response.status_code == 200
        assert len(response.json().get("tasks", [])) == 3

    def test_tasks_have_required_fields(self):
        tasks = requests.get(f"{BASE_URL}/tasks", timeout=10).json().get("tasks", [])
        for task in tasks:
            for key in [
                "task_id",
                "correct_team",
                "correct_urgency",
                "needs_clarification",
                "progress_hint",
            ]:
                assert key in task

    def test_two_episodes_get_different_ids(self):
        id_a, _ = self._reset("easy")
        id_b, _ = self._reset("hard")
        assert id_a != id_b

    def test_stepping_episode_a_does_not_affect_episode_b(self):
        id_a, _ = self._reset("easy")
        id_b, _ = self._reset("hard")
        assert self._state(id_a).get("task_id") == "easy"
        assert self._state(id_b).get("task_id") == "hard"
        self._step(id_a)
        assert self._state(id_a).get("step_count") == 1
        assert self._state(id_b).get("step_count") == 0, "Session bleed detected"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Support Triage OpenEnv - full validator")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("BASE_URL", "http://localhost:7860"),
        help="Server base URL (default: http://localhost:7860)",
    )
    cli_args = parser.parse_args()
    BASE_URL = cli_args.base_url

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            __file__,
            "-v",
            "-m",
            "integration",
            "--tb=short",
            "--no-header",
        ],
        env={**os.environ, "BASE_URL": BASE_URL},
    )
    sys.exit(result.returncode)
