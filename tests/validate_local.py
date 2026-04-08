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

# ---------------------------------------------------------------------------
# CLI argument — allows overriding the server URL without editing the file
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description="Support Triage OpenEnv – HTTP validator")
parser.add_argument(
    "--base-url",
    default="http://localhost:7860",
    help="Base URL of the running server (default: http://localhost:7860)",
)
args, _ = parser.parse_known_args()
BASE = args.base_url

DUMMY_ACTION = {
    "chosen_team": "account_support",
    "urgency": "low",
    "ask_clarification": False,
    "response_text": "We will reset your account password right away.",
}

PASS = "✓"
FAIL = "✗"
errors: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  {PASS} {label}")
    else:
        msg = f"  {FAIL} {label}" + (f" — {detail}" if detail else "")
        print(msg)
        errors.append(msg)


# ------------------------------------------------------------------
# [1] Health
# ------------------------------------------------------------------
print("\n[1] Health check")
r = requests.get(f"{BASE}/", timeout=10)
check("GET / returns 200", r.status_code == 200)
check("status == ok", r.json().get("status") == "ok")

# ------------------------------------------------------------------
# [2] Reset – all three tasks, capture episode_ids
# ------------------------------------------------------------------
print("\n[2] Reset")
episode_ids: dict[str, str] = {}
for tid in ["easy", "medium", "hard"]:
    r = requests.post(f"{BASE}/reset", json={"task_id": tid}, timeout=10)
    check(f"POST /reset task_id={tid} returns 200", r.status_code == 200, r.text[:120])
    data = r.json()
    obs = data.get("observation", {})
    check(f"  observation.task_id == {tid}", obs.get("task_id") == tid)
    check(f"  observation.ticket_text non-empty", bool(obs.get("ticket_text")))
    check(f"  observation.allowed_teams is list", isinstance(obs.get("allowed_teams"), list))
    ep_id = data.get("info", {}).get("episode_id", "")
    check(f"  info.episode_id non-empty", bool(ep_id))
    episode_ids[tid] = ep_id

# ------------------------------------------------------------------
# [3] Step – use X-Episode-Id header
# ------------------------------------------------------------------
print("\n[3] Step (with X-Episode-Id header)")
easy_id = episode_ids.get("easy", "")
r = requests.post(
    f"{BASE}/step",
    json=DUMMY_ACTION,
    headers={"X-Episode-Id": easy_id},
    timeout=10,
)
check("POST /step returns 200", r.status_code == 200, r.text[:120])
data = r.json()
reward = data.get("reward", -1)
check("reward in [0.0, 1.0]", 0.0 <= reward <= 1.0, f"got {reward}")
check("'done' key present", "done" in data)
obs = data.get("observation", {})
check("observation.feedback non-empty", bool(obs.get("feedback")))

# ------------------------------------------------------------------
# [4] State
# ------------------------------------------------------------------
print("\n[4] State")
r = requests.get(f"{BASE}/state", headers={"X-Episode-Id": easy_id}, timeout=10)
check("GET /state returns 200", r.status_code == 200)
state = r.json()
for key in ["episode_id", "step_count", "task_id",
            "clarification_requested", "resolved", "cumulative_reward"]:
    check(f"  state has key '{key}'", key in state)
check("  step_count == 1", state.get("step_count") == 1)

# ------------------------------------------------------------------
# [5] Score range across all tasks
# ------------------------------------------------------------------
print("\n[5] Score range (full episode)")
for tid in ["easy", "medium", "hard"]:
    r2 = requests.post(f"{BASE}/reset", json={"task_id": tid}, timeout=10)
    ep = r2.json().get("info", {}).get("episode_id", "")
    headers = {"X-Episode-Id": ep} if ep else {}
    final_reward = 0.0
    for _ in range(5):
        r = requests.post(f"{BASE}/step", json=DUMMY_ACTION, headers=headers, timeout=10)
        d = r.json()
        final_reward = d.get("reward", 0.0)
        if d.get("done"):
            break
    check(f"task={tid} reward in [0.0, 1.0]", 0.0 <= final_reward <= 1.0, str(final_reward))

# ------------------------------------------------------------------
# [6] Tasks discovery endpoint
# ------------------------------------------------------------------
print("\n[6] Tasks endpoint")
r = requests.get(f"{BASE}/tasks", timeout=10)
check("GET /tasks returns 200", r.status_code == 200)
tasks_data = r.json().get("tasks", [])
check("returns 3 tasks", len(tasks_data) == 3)
for t in tasks_data:
    for key in ["task_id", "correct_team", "correct_urgency",
                "needs_clarification", "progress_hint"]:
        check(f"  task '{t.get('task_id','?')}' has key '{key}'", key in t)

# ------------------------------------------------------------------
# [7] Session isolation
# ------------------------------------------------------------------
print("\n[7] Session isolation")
r_a = requests.post(f"{BASE}/reset", json={"task_id": "easy"}, timeout=10)
r_b = requests.post(f"{BASE}/reset", json={"task_id": "hard"}, timeout=10)
id_a = r_a.json().get("info", {}).get("episode_id", "")
id_b = r_b.json().get("info", {}).get("episode_id", "")
check("Two resets produce different episode_ids", id_a != id_b, f"a={id_a} b={id_b}")

s_a = requests.get(f"{BASE}/state", headers={"X-Episode-Id": id_a}, timeout=10).json()
s_b = requests.get(f"{BASE}/state", headers={"X-Episode-Id": id_b}, timeout=10).json()
check("Episode A is task=easy", s_a.get("task_id") == "easy")
check("Episode B is task=hard", s_b.get("task_id") == "hard")

requests.post(f"{BASE}/step", json=DUMMY_ACTION, headers={"X-Episode-Id": id_a}, timeout=10)
s_a2 = requests.get(f"{BASE}/state", headers={"X-Episode-Id": id_a}, timeout=10).json()
s_b2 = requests.get(f"{BASE}/state", headers={"X-Episode-Id": id_b}, timeout=10).json()
check("Episode A step_count == 1 after step", s_a2.get("step_count") == 1)
check("Episode B step_count still 0 (no bleed)", s_b2.get("step_count") == 0)

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------
print()
if errors:
    print(f"FAILED — {len(errors)} error(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)
else:
    print("ALL CHECKS PASSED ✓")
