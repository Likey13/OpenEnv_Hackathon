"""
tests/test_graders.py

Unit tests for graders.py and environment.py.
Run with:  pytest tests/test_graders.py -v
"""
from __future__ import annotations
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from models import TriageAction
from tasks import TASKS
from graders import grade_action
from environment import SupportTriageEnvironment


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def perfect_action(task_id: str) -> TriageAction:
    """
    Return a TriageAction with all correct fields AND task-specific response
    text that satisfies each task's required_response_keywords in tasks.py:
      easy   → ["password", "reset", "account"]
      medium → ["invoice", "charge", "clarif"]
      hard   → ["escalat", "secur", "investigat"]
    """
    t = TASKS[task_id]
    response_map = {
        "easy":   "We will reset your account password right away.",
        "medium": "We need to clarify which invoice and charge is incorrect.",
        "hard":   "We will investigate the security breach and escalate immediately.",
    }
    return TriageAction(
        chosen_team=t.correct_team,
        urgency=t.correct_urgency,
        ask_clarification=t.needs_clarification,
        response_text=response_map[task_id],
    )


def wrong_action() -> TriageAction:
    """Return a deliberately wrong TriageAction (fails every grading criterion)."""
    return TriageAction(
        chosen_team="billing",
        urgency="high",
        ask_clarification=True,
        response_text="x",  # too short → quality penalty
    )


# ---------------------------------------------------------------------------
# Grader tests
# ---------------------------------------------------------------------------

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
                response_text="We will reset your account password right away.",
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
                response_text="We will reset your account password right away.",
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
                response_text="We will reset your account password right away.",
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
                response_text="We need to clarify which invoice and charge is incorrect.",
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
# Environment tests
# ---------------------------------------------------------------------------

class TestEnvironment:
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
        assert done

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
        _, reward1, done = self.env.step(TriageAction(
            chosen_team="account_support",
            urgency="low",
            ask_clarification=False,
            response_text="We will reset your account password right away.",
        ))
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
        for tid in ["easy", "medium", "hard"]:
            self.env.reset(tid)
            for _ in range(5):
                _, reward, done = self.env.step(wrong_action())
                assert 0.0 <= reward <= 1.0
                if done:
                    break
