"""
tests/test_suite.py
===================
Combined validation suite for the Support Triage OpenEnv.

Merges:
  - test_graders.py   → unit tests (graders.py, environment.py) — no server needed
  - validate_local.py → HTTP integration tests (app.py endpoints) — server must be running

Cross-file references
---------------------
  models.py      → TriageAction, TicketObservation, TicketState (imported directly)
  tasks.py       → TASKS dict, Task dataclass (imported directly)
  graders.py     → grade_action() (imported directly)
  environment.py → SupportTriageEnvironment (imported directly)
  app.py         → HTTP endpoints /reset /step /state /tasks (hit via requests)

Run modes
---------
  Unit tests only (no server required):
    pytest tests/test_suite.py -v -m unit

  HTTP integration tests only (server must be running on port 7860):
    pytest tests/test_suite.py -v -m integration

  All tests (server must be running):
    pytest tests/test_suite.py -v

  Standalone HTTP validator (mirrors old validate_local.py behaviour):
    python tests/test_suite.py
    python tests/test_suite.py --base-url http://my-space.hf.space
"""
from __future__ import annotations

import argparse
import os
import sys

import pytest
import requests

# Make repo root importable when running directly or via pytest from any CWD
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Direct imports — unit tests use these without a running server
from models import TriageAction          # noqa: E402
from tasks import TASKS                  # noqa: E402
from graders import grade_action         # noqa: E402
from environment import SupportTriageEnvironment  # noqa: E402

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("BASE_URL", "http://localhost:7860")

DUMMY_ACTION = {
    "chosen_team": "account_support",
    "urgency": "low",
    "ask_clarification": False,
    "response_text": "We will reset your password shortly.",
}


def perfect_action(task_id: str) -> TriageAction:
    """Return a TriageAction with all correct fields for the given task."""
    t = TASKS[task_id]
    return TriageAction(
        chosen_team=t.correct_team,
        urgency=t.correct_urgency,
        ask_clarification=t.needs_clarification,
        response_text="We will investigate your issue and escalate appropriately.",
    )


def wrong_action() -> TriageAction:
    """Return a deliberately wrong TriageAction (fails every criterion)."""
    return TriageAction(
        chosen_team="billing",
        urgency="high",
        ask_clarification=True,
        response_text="x",  # too short → quality penalty
    )


# ---------------------------------------------------------------------------
# SECTION 1 — Unit tests: graders.py
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGraders:
    """
    Pure unit tests for graders.grade_action().
    No server required — imports graders.py and tasks.py directly.
    """

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
        for tid in TASKS:
            score, _ = grade_action(wrong_action(), TASKS[tid], 1)
            assert 0.0 <= score <= 1.0, f"Score {score} out of [0,1] for task={tid}"

    def test_wrong_team_loses_points(self):
        task = TASKS["easy"]
        good = grade_action(perfect_action("easy"), task, 1)[0]
        bad = grade_action(
            TriageAction(
                chosen_team="billing",           # wrong
                urgency=task.correct_urgency,
                ask_clarification=task.needs_clarification,
                response_text="We will investigate your issue and escalate appropriately.",
            ),
            task, 1,
        )[0]
        assert good > bad

    def test_wrong_urgency_loses_points(self):
        task = TASKS["easy"]
        score, _ = grade_action(
            TriageAction(
                chosen_team=task.correct_team,
                urgency="high",                  # wrong
                ask_clarification=task.needs_clarification,
                response_text="We will reset your password shortly.",
            ),
            task, 1,
        )
        assert score < 1.0

    def test_unnecessary_clarification_loses_points(self):
        task = TASKS["easy"]  # does NOT need clarification
        score, _ = grade_action(
            TriageAction(
                chosen_team=task.correct_team,
                urgency=task.correct_urgency,
                ask_clarification=True,          # wrong: not needed
                response_text="We will reset your password shortly.",
            ),
            task, 1,
        )
        assert score < 1.0

    def test_missing_clarification_loses_points(self):
        task = TASKS["medium"]  # DOES need clarification
        score, _ = grade_action(
            TriageAction(
                chosen_team=task.correct_team,
                urgency=task.correct_urgency,
                ask_clarification=False,         # wrong: should ask
                response_text="Your invoice will be reviewed.",
            ),
            task, 1,
        )
        assert score < 1.0

    def test_response_too_short(self):
        task = TASKS["easy"]
        score, _ = grade_action(
            TriageAction(
                chosen_team=task.correct_team,
                urgency=task.correct_urgency,
                ask_clarification=task.needs_clarification,
                response_text="ok",              # too short (< 10 chars)
            ),
            task, 1,
        )
        assert score < 1.0

    def test_response_too_long(self):
        task = TASKS["easy"]
        score, _ = grade_action(
            TriageAction(
                chosen_team=task.correct_team,
                urgency=task.correct_urgency,
                ask_clarification=task.needs_clarification,
                response_text="a" * 301,         # too long (> 300 chars)
            ),
            task, 1,
        )
        assert score < 1.0

    def test_feedback_is_non_empty_string(self):
        _, feedback = grade_action(perfect_action("easy"), TASKS["easy"], 1)
        assert isinstance(feedback, str) and len(feedback) > 0


# ---------------------------------------------------------------------------
# SECTION 2 — Unit tests: environment.py
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestEnvironment:
    """
    Pure unit tests for environment.SupportTriageEnvironment.
    No server required — imports environment.py directly.
    """

    def setup_method(self):
        self.env = SupportTriageEnvironment()

    def test_reset_returns_correct_observation(self):
        for tid in ["easy", "medium", "hard"]:
            obs = self.env.reset(tid)
            assert obs.task_id == tid
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
        self.env.step(perfect_action("easy"))  # done=True
        with pytest.raises(RuntimeError):
            self.env.step(perfect_action("easy"))

    def test_max_steps_terminates_episode(self):
        self.env.reset("easy")
        done = False
        for _ in range(5):
            _, _, done = self.env.step(wrong_action())
            if done:
                break
        assert done  # must terminate by step 5

    def test_state_step_count_increments(self):
        self.env.reset("medium")
        assert self.env.state().step_count == 0
        self.env.step(wrong_action())
        assert self.env.state().step_count == 1

    def test_state_tracks_clarification_flag(self):
        self.env.reset("easy")
        self.env.step(TriageAction(
            chosen_team="account_support",
            urgency="low",
            ask_clarification=True,
            response_text="Can you provide more details please?",
        ))
        assert self.env.state().clarification_requested is True

    def test_cumulative_reward_accumulates(self):
        self.env.reset("easy")
        partial = TriageAction(
            chosen_team="account_support",
            urgency="low",
            ask_clarification=False,
            response_text="Password will be reset.",
        )
        _, reward1, done = self.env.step(partial)
        if not done:
            assert self.env.state().cumulative_reward >= reward1

    def test_reset_clears_previous_episode(self):
        self.env.reset("easy")
        self.env.step(perfect_action("easy"))  # completes episode
        self.env.reset("hard")
        state = self.env.state()
        assert state.task_id == "hard"
        assert state.step_count == 0
        assert not state.resolved

    def test_reward_always_in_range_across_all_tasks(self):
        for tid in ["easy", "medium", "hard"]:
            self.env.reset(tid)
            for _ in range(5):
                _, reward, done = self.env.step(wrong_action())
                assert 0.0 <= reward <= 1.0
                if done:
                    break


# ---------------------------------------------------------------------------
# SECTION 3 — Integration tests: app.py HTTP endpoints
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestHTTPEndpoints:
    """
    Live HTTP tests against a running app.py server.
    Start the server before running:
        python -m uvicorn app:app --port 7860

    Uses BASE_URL env var (default: http://localhost:7860).
    Cross-references: app.py routes, models.py response shapes,
    tasks.py task list, environment.py session logic.
    """

    def _reset(self, task_id: str) -> tuple[str, dict]:
        """POST /reset and return (episode_id, observation)."""
        r = requests.post(f"{BASE_URL}/reset", json={"task_id": task_id}, timeout=10)
        assert r.status_code == 200, f"/reset failed: {r.text}"
        data = r.json()
        ep_id = data.get("info", {}).get("episode_id", "")
        obs = data.get("observation", {})
        return ep_id, obs

    def _step(self, ep_id: str, action: dict | None = None) -> dict:
        """POST /step with X-Episode-Id header."""
        r = requests.post(
            f"{BASE_URL}/step",
            json=action or DUMMY_ACTION,
            headers={"X-Episode-Id": ep_id},
            timeout=10,
        )
        assert r.status_code == 200, f"/step failed: {r.text}"
        return r.json()

    def _state(self, ep_id: str) -> dict:
        """GET /state with X-Episode-Id header."""
        r = requests.get(
            f"{BASE_URL}/state",
            headers={"X-Episode-Id": ep_id},
            timeout=10,
        )
        assert r.status_code == 200, f"/state failed: {r.text}"
        return r.json()

    # ── [1] Health ────────────────────────────────────────────────────────────

    def test_health_returns_ok(self):
        r = requests.get(f"{BASE_URL}/", timeout=10)
        assert r.status_code == 200
        assert r.json().get("status") == "ok"

    # ── [2] Reset ─────────────────────────────────────────────────────────────

    def test_reset_all_tasks_return_200(self):
        for tid in ["easy", "medium", "hard"]:
            ep_id, obs = self._reset(tid)
            assert obs.get("task_id") == tid
            assert obs.get("ticket_text")
            assert isinstance(obs.get("allowed_teams"), list)
            assert ep_id, "episode_id should be non-empty"

    def test_reset_invalid_task_returns_400(self):
        r = requests.post(f"{BASE_URL}/reset", json={"task_id": "invalid"}, timeout=10)
        assert r.status_code == 400

    # ── [3] Step ──────────────────────────────────────────────────────────────

    def test_step_returns_reward_and_done(self):
        ep_id, _ = self._reset("easy")
        result = self._step(ep_id)
        assert 0.0 <= result.get("reward", -1) <= 1.0
        assert "done" in result
        assert result.get("observation", {}).get("feedback")

    def test_step_without_episode_id_uses_latest(self):
        # Single-client fallback: omitting header should still work
        self._reset("easy")  # sets _latest_episode_id on server
        r = requests.post(f"{BASE_URL}/step", json=DUMMY_ACTION, timeout=10)
        assert r.status_code == 200

    # ── [4] State ─────────────────────────────────────────────────────────────

    def test_state_has_all_required_keys(self):
        ep_id, _ = self._reset("easy")
        self._step(ep_id)
        state = self._state(ep_id)
        for key in ["episode_id", "step_count", "task_id",
                    "clarification_requested", "resolved", "cumulative_reward"]:
            assert key in state, f"Missing key '{key}' in state"

    def test_state_step_count_after_one_step(self):
        ep_id, _ = self._reset("easy")
        self._step(ep_id)
        assert self._state(ep_id).get("step_count") == 1

    # ── [5] Score range ───────────────────────────────────────────────────────

    def test_score_in_range_all_tasks(self):
        for tid in ["easy", "medium", "hard"]:
            ep_id, _ = self._reset(tid)
            final_reward = 0.0
            for _ in range(5):
                result = self._step(ep_id)
                final_reward = result.get("reward", 0.0)
                if result.get("done"):
                    break
            assert 0.0 <= final_reward <= 1.0, \
                f"task={tid} reward {final_reward} out of range"

    # ── [6] Tasks discovery ───────────────────────────────────────────────────

    def test_tasks_endpoint_returns_three_tasks(self):
        r = requests.get(f"{BASE_URL}/tasks", timeout=10)
        assert r.status_code == 200
        tasks = r.json().get("tasks", [])
        assert len(tasks) == 3

    def test_tasks_have_required_fields(self):
        tasks = requests.get(f"{BASE_URL}/tasks", timeout=10).json().get("tasks", [])
        for t in tasks:
            for key in ["task_id", "correct_team", "correct_urgency",
                        "needs_clarification", "progress_hint"]:
                assert key in t, f"Task missing key '{key}': {t}"

    # ── [7] Session isolation ─────────────────────────────────────────────────

    def test_two_episodes_get_different_ids(self):
        id_a, _ = self._reset("easy")
        id_b, _ = self._reset("hard")
        assert id_a != id_b

    def test_stepping_episode_a_does_not_affect_episode_b(self):
        id_a, _ = self._reset("easy")
        id_b, _ = self._reset("hard")

        assert self._state(id_a).get("task_id") == "easy"
        assert self._state(id_b).get("task_id") == "hard"

        self._step(id_a)  # advance only episode A

        assert self._state(id_a).get("step_count") == 1
        assert self._state(id_b).get("step_count") == 0, \
            "Episode B step_count should still be 0 — session bleed detected"


# ---------------------------------------------------------------------------
# Standalone script mode  (mirrors old validate_local.py CLI behaviour)
# ---------------------------------------------------------------------------

def _run_standalone(base_url: str) -> None:
    """
    Run all HTTP checks with human-readable pass/fail output.
    Exits 0 on full pass, 1 on any failure.
    """
    global BASE_URL
    BASE_URL = base_url

    PASS_SYM = "✓"
    FAIL_SYM = "✗"
    errors: list[str] = []

    def check(label: str, condition: bool, detail: str = "") -> None:
        if condition:
            print(f"  {PASS_SYM} {label}")
        else:
            msg = f"  {FAIL_SYM} {label}" + (f" — {detail}" if detail else "")
            print(msg)
            errors.append(msg)

    def reset(tid: str) -> tuple[str, dict]:
        r = requests.post(f"{base_url}/reset", json={"task_id": tid}, timeout=10)
        data = r.json()
        return data.get("info", {}).get("episode_id", ""), data.get("observation", {})

    def step(ep: str, action: dict | None = None) -> dict:
        return requests.post(
            f"{base_url}/step",
            json=action or DUMMY_ACTION,
            headers={"X-Episode-Id": ep},
            timeout=10,
        ).json()

    def state(ep: str) -> dict:
        return requests.get(
            f"{base_url}/state",
            headers={"X-Episode-Id": ep},
            timeout=10,
        ).json()

    # [1] Health
    print("\n[1] Health check")
    r = requests.get(f"{base_url}/", timeout=10)
    check("GET / returns 200", r.status_code == 200)
    check("status == ok", r.json().get("status") == "ok")

    # [2] Reset
    print("\n[2] Reset")
    episode_ids: dict[str, str] = {}
    for tid in ["easy", "medium", "hard"]:
        ep_id, obs = reset(tid)
        check(f"POST /reset task_id={tid} returns 200", bool(ep_id))
        check(f"  observation.task_id == {tid}", obs.get("task_id") == tid)
        check(f"  observation.ticket_text non-empty", bool(obs.get("ticket_text")))
        check(f"  observation.allowed_teams is list", isinstance(obs.get("allowed_teams"), list))
        check(f"  info.episode_id non-empty", bool(ep_id))
        episode_ids[tid] = ep_id

    # [3] Step
    print("\n[3] Step (with X-Episode-Id header)")
    easy_id = episode_ids.get("easy", "")
    result = step(easy_id)
    reward = result.get("reward", -1)
    check("POST /step returns reward", reward >= 0)
    check("reward in [0.0, 1.0]", 0.0 <= reward <= 1.0, f"got {reward}")
    check("'done' key present", "done" in result)
    check("observation.feedback non-empty", bool(result.get("observation", {}).get("feedback")))

    # [4] State
    print("\n[4] State")
    st = state(easy_id)
    for key in ["episode_id", "step_count", "task_id",
                "clarification_requested", "resolved", "cumulative_reward"]:
        check(f"  state has key '{key}'", key in st)
    check("  step_count == 1", st.get("step_count") == 1)

    # [5] Score range
    print("\n[5] Score range (full episode)")
    for tid in ["easy", "medium", "hard"]:
        ep_id, _ = reset(tid)
        final_reward = 0.0
        for _ in range(5):
            res = step(ep_id)
            final_reward = res.get("reward", 0.0)
            if res.get("done"):
                break
        check(f"task={tid} reward in [0.0, 1.0]", 0.0 <= final_reward <= 1.0, str(final_reward))

    # [6] Tasks
    print("\n[6] Tasks endpoint")
    r = requests.get(f"{base_url}/tasks", timeout=10)
    check("GET /tasks returns 200", r.status_code == 200)
    tasks = r.json().get("tasks", [])
    check("returns 3 tasks", len(tasks) == 3)
    for t in tasks:
        for key in ["task_id", "correct_team", "correct_urgency",
                    "needs_clarification", "progress_hint"]:
            check(f"  task '{t.get('task_id','?')}' has key '{key}'", key in t)

    # [7] Session isolation
    print("\n[7] Session isolation")
    id_a, _ = reset("easy")
    id_b, _ = reset("hard")
    check("Two resets produce different episode_ids", id_a != id_b)
    check("Episode A is task=easy", state(id_a).get("task_id") == "easy")
    check("Episode B is task=hard", state(id_b).get("task_id") == "hard")
    step(id_a)
    check("Episode A step_count == 1 after step", state(id_a).get("step_count") == 1)
    check("Episode B step_count still 0", state(id_b).get("step_count") == 0)

    # Summary
    print()
    if errors:
        print(f"FAILED — {len(errors)} error(s):")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
    else:
        total = 2 + 4*3 + 4 + 7 + 3 + 3*(5+1) + 7  # approx
        print("ALL CHECKS PASSED ✓")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Support Triage OpenEnv — HTTP validator")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("BASE_URL", "http://localhost:7860"),
        help="Server base URL (default: http://localhost:7860)",
    )
    args = parser.parse_args()
    _run_standalone(args.base_url)
