"""
tests/test_graders.py

Unit tests for graders.py and environment.py.
Run with:  pytest tests/test_graders.py -v
"""
from __future__ import annotations
import sys, os
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
    t = TASKS[task_id]
    return TriageAction(
        chosen_team=t.correct_team,
        urgency=t.correct_urgency,
        ask_clarification=t.needs_clarification,
        response_text="We will investigate your issue and escalate appropriately.",
    )


def wrong_action() -> TriageAction:
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

    def test_score_in_range(self):
        for tid in TASKS:
            score, _ = grade_action(wrong_action(), TASKS[tid], 1)
            assert 0.0 <= score <= 1.0, f"Score {score} out of [0,1] for task {tid}"

    def test_wrong_team_loses_points(self):
        task = TASKS["easy"]
        good = grade_action(perfect_action("easy"), task, 1)[0]
        bad_action = perfect_action("easy")
        bad_action = TriageAction(
            chosen_team="billing",  # wrong
            urgency=bad_action.urgency,
            ask_clarification=bad_action.ask_clarification,
            response_text=bad_action.response_text,
        )
        bad = grade_action(bad_action, task, 1)[0]
        assert good > bad

    def test_wrong_urgency_loses_points(self):
        task = TASKS["easy"]
        bad_action = TriageAction(
            chosen_team=task.correct_team,
            urgency="high",          # wrong
            ask_clarification=task.needs_clarification,
            response_text="We will reset your password shortly.",
        )
        score, _ = grade_action(bad_action, task, 1)
        assert score < 1.0

    def test_unnecessary_clarification_loses_points(self):
        # easy task does NOT need clarification
        task = TASKS["easy"]
        action = TriageAction(
            chosen_team=task.correct_team,
            urgency=task.correct_urgency,
            ask_clarification=True,  # wrong: not needed
            response_text="We will reset your password shortly.",
        )
        score, _ = grade_action(action, task, 1)
        assert score < 1.0

    def test_missing_clarification_loses_points(self):
        # medium task DOES need clarification
        task = TASKS["medium"]
        action = TriageAction(
            chosen_team=task.correct_team,
            urgency=task.correct_urgency,
            ask_clarification=False,  # wrong: should ask
            response_text="Your invoice will be reviewed.",
        )
        score, _ = grade_action(action, task, 1)
        assert score < 1.0

    def test_response_too_short(self):
        task = TASKS["easy"]
        action = TriageAction(
            chosen_team=task.correct_team,
            urgency=task.correct_urgency,
            ask_clarification=task.needs_clarification,
            response_text="ok",  # too short
        )
        score, _ = grade_action(action, task, 1)
        assert score < 1.0

    def test_response_too_long(self):
        task = TASKS["easy"]
        action = TriageAction(
            chosen_team=task.correct_team,
            urgency=task.correct_urgency,
            ask_clarification=task.needs_clarification,
            response_text="a" * 301,  # too long
        )
        score, _ = grade_action(action, task, 1)
        assert score < 1.0

    def test_feedback_is_string(self):
        _, feedback = grade_action(perfect_action("easy"), TASKS["easy"], 1)
        assert isinstance(feedback, str) and len(feedback) > 0


# ---------------------------------------------------------------------------
# Environment tests
# ---------------------------------------------------------------------------

class TestEnvironment:
    def setup_method(self):
        self.env = SupportTriageEnvironment()

    def test_reset_returns_observation(self):
        for tid in ["easy", "medium", "hard"]:
            obs = self.env.reset(tid)
            assert obs.task_id == tid
            assert obs.ticket_text
            assert not obs.done
            assert obs.reward == 0.0

    def test_invalid_task_raises(self):
        with pytest.raises(ValueError):
            self.env.reset("impossible")

    def test_step_before_reset_raises(self):
        env = SupportTriageEnvironment()
        with pytest.raises(RuntimeError):
            env.step(perfect_action("easy"))

    def test_perfect_episode_completes(self):
        self.env.reset("easy")
        obs, reward, done = self.env.step(perfect_action("easy"))
        assert reward == pytest.approx(1.0)
        assert done is True

    def test_step_after_done_raises(self):
        self.env.reset("easy")
        self.env.step(perfect_action("easy"))  # score 1.0, done
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

    def test_state_reflects_steps(self):
        self.env.reset("medium")
        state = self.env.state()
        assert state.step_count == 0
        self.env.step(wrong_action())
        state = self.env.state()
        assert state.step_count == 1

    def test_state_tracks_clarification(self):
        self.env.reset("easy")
        action = TriageAction(
            chosen_team="account_support",
            urgency="low",
            ask_clarification=True,
            response_text="Can you provide more details please?",
        )
        self.env.step(action)
        assert self.env.state().clarification_requested is True

    def test_cumulative_reward_accumulates(self):
        self.env.reset("easy")
        # Take a partial action (some criteria wrong)
        partial = TriageAction(
            chosen_team="account_support",
            urgency="low",
            ask_clarification=False,
            response_text="Password will be reset."
        )
        _, reward1, done = self.env.step(partial)
        if not done:
            state = self.env.state()
            assert state.cumulative_reward >= reward1

    def test_reset_clears_previous_episode(self):
        self.env.reset("easy")
        self.env.step(perfect_action("easy"))  # completes episode
        self.env.reset("hard")  # should reset cleanly
        state = self.env.state()
        assert state.task_id == "hard"
        assert state.step_count == 0
        assert not state.resolved

    def test_reward_always_in_range(self):
        for tid in ["easy", "medium", "hard"]:
            self.env.reset(tid)
            for _ in range(5):
                obs, reward, done = self.env.step(wrong_action())
                assert 0.0 <= reward <= 1.0
                if done:
                    break
