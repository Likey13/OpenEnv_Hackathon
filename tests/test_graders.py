"""
tests/test_graders.py

Unit tests for graders.py and environment.py.
Run with: pytest tests/test_graders.py -v
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from environment import SupportTriageEnvironment
from graders import grade_action
from models import TriageAction
from tasks import TASKS


def perfect_action(task_id: str) -> TriageAction:
    """
    Return a TriageAction with all correct fields and task-specific response
    text that satisfies each task's required_response_keywords in tasks.py.
    """
    task = TASKS[task_id]

    response_map = {
        "easy": "We will reset your account password right away.",
        "medium": "We need to clarify which invoice and charge is incorrect.",
        "hard": "We will investigate the security breach and escalate immediately.",
    }

    return TriageAction(
        category=task.correct_category,
        priority=task.correct_priority,
        response_text=response_map[task_id],
    )


@pytest.mark.parametrize("task_id", list(TASKS.keys()))
def test_grade_action_perfect_scores(task_id: str) -> None:
    task = TASKS[task_id]
    action = perfect_action(task_id)

    result = grade_action(task, action)

    assert isinstance(result, dict)
    assert result["score"] == pytest.approx(1.0)
    assert result["category_correct"] is True
    assert result["priority_correct"] is True
    assert result["response_keywords_present"] is True


@pytest.mark.parametrize("task_id", list(TASKS.keys()))
def test_grade_action_wrong_category_reduces_score(task_id: str) -> None:
    task = TASKS[task_id]
    action = perfect_action(task_id)

    wrong_category = "billing" if task.correct_category != "billing" else "technical"
    action.category = wrong_category

    result = grade_action(task, action)

    assert result["category_correct"] is False
    assert result["score"] < 1.0


@pytest.mark.parametrize("task_id", list(TASKS.keys()))
def test_grade_action_wrong_priority_reduces_score(task_id: str) -> None:
    task = TASKS[task_id]
    action = perfect_action(task_id)

    wrong_priority = "low" if task.correct_priority != "low" else "high"
    action.priority = wrong_priority

    result = grade_action(task, action)

    assert result["priority_correct"] is False
    assert result["score"] < 1.0


@pytest.mark.parametrize("task_id", list(TASKS.keys()))
def test_grade_action_missing_keywords_reduces_score(task_id: str) -> None:
    task = TASKS[task_id]
    action = perfect_action(task_id)
    action.response_text = "Thank you for contacting support."

    result = grade_action(task, action)

    assert result["response_keywords_present"] is False
    assert result["score"] < 1.0


def test_environment_reset_returns_valid_observation() -> None:
    env = SupportTriageEnvironment()
    observation = env.reset()

    assert observation is not None


def test_environment_step_returns_result() -> None:
    env = SupportTriageEnvironment()
    observation = env.reset()

    assert observation is not None

    first_task_id = next(iter(TASKS.keys()))
    action = perfect_action(first_task_id)
    result = env.step(action)

    assert result is not None
