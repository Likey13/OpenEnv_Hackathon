"""
tests/validate_local.py

End-to-end HTTP validator for the Support Triage OpenEnv.
Covers 7 sections: health, reset, step, state, score range,
task discovery, and session isolation.

Run with the server already started:
    python -m uvicorn app:app --port 7860
    python tests/validate_local.py
    python tests/validate_local.py --base-url https://your-space.hf.space
"""

from __future__ import annotations

import argparse
import sys

import requests

parser = argparse.ArgumentParser(
    description="Support Triage OpenEnv - HTTP validator"
)
parser.add_argument(
    "--base-url",
    default="http://localhost:7860",
    help="Base URL of the running server (default: http://localhost:7860)",
)
args, _ = parser.parse_known_args()
BASE = args.base_url.rstrip("/")

DUMMY_ACTION = {
    "chosen_team": "account_support",
    "urgency": "low",
    "ask_clarification": False,
    "response_text": "We will reset your account password right away.",
}


def check(condition: bool, label: str, detail: str = "") -> None:
    if condition:
        print(f"[PASS] {label}")
    else:
        print(f"[FAIL] {label}" + (f" - {detail}" if detail else ""))
        raise SystemExit(1)


def post_reset(task_id: str) -> tuple[str, dict]:
    response = requests.post(
        f"{BASE}/reset",
        json={"task_id": task_id},
        timeout=10,
    )
    check(response.status_code == 200, f"POST /reset ({task_id})", response.text)
    data = response.json()
    episode_id = data.get("info", {}).get("episode_id", "")
    observation = data.get("observation", {})
    check(bool(episode_id), "reset returns episode_id")
    return episode_id, observation


def post_step(episode_id: str, action: dict | None = None) -> dict:
    response = requests.post(
        f"{BASE}/step",
        json=action or DUMMY_ACTION,
        headers={"X-Episode-Id": episode_id},
        timeout=10,
    )
    check(response.status_code == 200, "POST /step", response.text)
    return response.json()


def get_state(episode_id: str) -> dict:
    response = requests.get(
        f"{BASE}/state",
        headers={"X-Episode-Id": episode_id},
        timeout=10,
    )
    check(response.status_code == 200, "GET /state", response.text)
    return response.json()


def get_tasks() -> list[dict]:
    response = requests.get(f"{BASE}/tasks", timeout=10)
    check(response.status_code == 200, "GET /tasks", response.text)
    return response.json().get("tasks", [])


def validate_health() -> None:
    response = requests.get(f"{BASE}/", timeout=10)
    check(response.status_code == 200, "GET /")
    check(response.json().get("status") == "ok", "health status is ok", str(response.json()))


def validate_reset() -> None:
    for task_id in ["easy", "medium", "hard"]:
        episode_id, observation = post_reset(task_id)
        check(observation.get("task_id") == task_id, f"reset task_id matches ({task_id})")
        check(bool(observation.get("ticket_text")), f"reset ticket_text exists ({task_id})")
        check(isinstance(observation.get("allowed_teams"), list), f"allowed_teams is list ({task_id})")
        check(bool(episode_id), f"episode_id exists ({task_id})")

    response = requests.post(f"{BASE}/reset", json={"task_id": "invalid"}, timeout=10)
    check(response.status_code == 400, "invalid task returns 400", response.text)


def validate_step() -> None:
    episode_id, _ = post_reset("easy")
    result = post_step(episode_id)

    reward = result.get("reward", -1)
    check(isinstance(reward, (int, float)), "step returns numeric reward")
    check(0.0 <= reward <= 1.0, "step reward in range", str(result))
    check("done" in result, "step returns done flag")
    check(bool(result.get("observation", {}).get("feedback")), "step returns feedback")


def validate_state() -> None:
    episode_id, _ = post_reset("easy")
    post_step(episode_id)
    state = get_state(episode_id)

    required_keys = [
        "episode_id",
        "step_count",
        "task_id",
        "clarification_requested",
        "resolved",
        "cumulative_reward",
    ]
    for key in required_keys:
        check(key in state, f"state contains {key}")

    check(state.get("step_count") == 1, "state step_count increments")


def validate_score_range() -> None:
    for task_id in ["easy", "medium", "hard"]:
        episode_id, _ = post_reset(task_id)
        final_reward = 0.0
        for _ in range(5):
            result = post_step(episode_id)
            final_reward = result.get("reward", 0.0)
            if result.get("done"):
                break
        check(0.0 <= final_reward <= 1.0, f"final reward in range ({task_id})")


def validate_tasks() -> None:
    tasks = get_tasks()
    check(len(tasks) == 3, "tasks endpoint returns three tasks", str(tasks))

    required_keys = [
        "task_id",
        "correct_team",
        "correct_urgency",
        "needs_clarification",
        "progress_hint",
    ]
    for i, task in enumerate(tasks, start=1):
        for key in required_keys:
            check(key in task, f"task {i} contains {key}")


def validate_session_isolation() -> None:
    episode_a, _ = post_reset("easy")
    episode_b, _ = post_reset("hard")

    state_a = get_state(episode_a)
    state_b = get_state(episode_b)

    check(state_a.get("task_id") == "easy", "episode A has easy task")
    check(state_b.get("task_id") == "hard", "episode B has hard task")

    post_step(episode_a)

    state_a_after = get_state(episode_a)
    state_b_after = get_state(episode_b)

    check(state_a_after.get("step_count") == 1, "episode A step_count increments")
    check(state_b_after.get("step_count") == 0, "episode B remains unchanged")


def main() -> None:
    print(f"Validating server at: {BASE}")
    validate_health()
    validate_reset()
    validate_step()
    validate_state()
    validate_score_range()
    validate_tasks()
    validate_session_isolation()
    print("All validations passed.")


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as exc:
        print(f"[FAIL] Request error - {exc}")
        sys.exit(1)
