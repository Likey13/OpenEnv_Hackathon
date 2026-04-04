"""
tests/validate_local.py

Validates the running environment server end-to-end:
  1. GET /         → health check
  2. POST /reset   → three task_ids, captures episode_id
  3. POST /step    → one action per task with X-Episode-Id header
  4. GET /state    → state shape check
  5. Score range   → all rewards in [0.0, 1.0]
  6. GET /tasks    → discovery endpoint
  7. Session isolation → two concurrent episodes don't bleed into each other

Run with the server already started:
    uvicorn app:app --port 7860 &
    python tests/validate_local.py
"""
from __future__ import annotations
import sys
import json
import requests

BASE = "http://localhost:7860"

DUMMY_ACTION = {
    "chosen_team": "account_support",
    "urgency": "low",
    "ask_clarification": False,
    "response_text": "We will reset your password shortly.",
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
# 1. Health
# ------------------------------------------------------------------
print("\n[1] Health check")
r = requests.get(f"{BASE}/")
check("GET / returns 200", r.status_code == 200)
check("status == ok", r.json().get("status") == "ok")

# ------------------------------------------------------------------
# 2. Reset – all three tasks, capture episode_ids
# ------------------------------------------------------------------
print("\n[2] Reset")
episode_ids: dict[str, str] = {}
for tid in ["easy", "medium", "hard"]:
    r = requests.post(f"{BASE}/reset", json={"task_id": tid})
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
# 3. Step – use X-Episode-Id header
# ------------------------------------------------------------------
print("\n[3] Step (with X-Episode-Id header)")
easy_id = episode_ids.get("easy", "")
r = requests.post(
    f"{BASE}/step",
    json=DUMMY_ACTION,
    headers={"X-Episode-Id": easy_id},
)
check("POST /step returns 200", r.status_code == 200, r.text[:120])
data = r.json()
reward = data.get("reward", -1)
check("reward in [0.0, 1.0]", 0.0 <= reward <= 1.0, f"got {reward}")
check("'done' key present", "done" in data)
obs = data.get("observation", {})
check("observation.feedback non-empty", bool(obs.get("feedback")))

# ------------------------------------------------------------------
# 4. State
# ------------------------------------------------------------------
print("\n[4] State")
r = requests.get(f"{BASE}/state", headers={"X-Episode-Id": easy_id})
check("GET /state returns 200", r.status_code == 200)
state = r.json()
for key in ["episode_id", "step_count", "task_id", "clarification_requested", "resolved", "cumulative_reward"]:
    check(f"  state has key '{key}'", key in state)
check("  step_count == 1", state.get("step_count") == 1)

# ------------------------------------------------------------------
# 5. Score range across all tasks
# ------------------------------------------------------------------
print("\n[5] Score range (full episode)")
for tid in ["easy", "medium", "hard"]:
    r2 = requests.post(f"{BASE}/reset", json={"task_id": tid})
    ep = r2.json().get("info", {}).get("episode_id", "")
    headers = {"X-Episode-Id": ep} if ep else {}
    final_reward = 0.0
    for _ in range(5):
        r = requests.post(f"{BASE}/step", json=DUMMY_ACTION, headers=headers)
        d = r.json()
        final_reward = d.get("reward", 0.0)
        if d.get("done"):
            break
    check(f"task={tid} final reward in [0.0, 1.0]", 0.0 <= final_reward <= 1.0, str(final_reward))

# ------------------------------------------------------------------
# 6. Tasks discovery endpoint
# ------------------------------------------------------------------
print("\n[6] Tasks endpoint")
r = requests.get(f"{BASE}/tasks")
check("GET /tasks returns 200", r.status_code == 200)
tasks_data = r.json().get("tasks", [])
check("returns 3 tasks", len(tasks_data) == 3)
for t in tasks_data:
    for key in ["task_id", "correct_team", "correct_urgency", "needs_clarification", "progress_hint"]:
        check(f"  task '{t.get('task_id','?')}' has key '{key}'", key in t)

# ------------------------------------------------------------------
# 7. Session isolation – two episodes don't bleed
# ------------------------------------------------------------------
print("\n[7] Session isolation")
r_a = requests.post(f"{BASE}/reset", json={"task_id": "easy"})
r_b = requests.post(f"{BASE}/reset", json={"task_id": "hard"})
id_a = r_a.json().get("info", {}).get("episode_id", "")
id_b = r_b.json().get("info", {}).get("episode_id", "")
check("Two resets produce different episode_ids", id_a != id_b, f"a={id_a} b={id_b}")

s_a = requests.get(f"{BASE}/state", headers={"X-Episode-Id": id_a}).json()
s_b = requests.get(f"{BASE}/state", headers={"X-Episode-Id": id_b}).json()
check("Episode A is task=easy", s_a.get("task_id") == "easy", str(s_a.get("task_id")))
check("Episode B is task=hard", s_b.get("task_id") == "hard", str(s_b.get("task_id")))

# Step only episode A and confirm B is unaffected
requests.post(f"{BASE}/step", json=DUMMY_ACTION, headers={"X-Episode-Id": id_a})
s_a2 = requests.get(f"{BASE}/state", headers={"X-Episode-Id": id_a}).json()
s_b2 = requests.get(f"{BASE}/state", headers={"X-Episode-Id": id_b}).json()
check("Episode A step_count == 1 after step", s_a2.get("step_count") == 1)
check("Episode B step_count still 0 (not bleed)", s_b2.get("step_count") == 0)

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------
print()
if errors:
    print(f"FAILED – {len(errors)} error(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)
else:
    print("ALL CHECKS PASSED ✓")

