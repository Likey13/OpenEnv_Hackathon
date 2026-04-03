"""
inference.py – agent baseline for the Support Triage OpenEnv.

Required environment variables:
    API_BASE_URL   – LLM API base URL (OpenAI-compatible)
    MODEL_NAME     – model identifier
    HF_TOKEN       – API key / Hugging Face token
    ENV_URL        – environment server URL (default: http://localhost:7860)
"""
from __future__ import annotations
import json
import os
import re
import sys

import requests
from openai import OpenAI

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
API_BASE_URL: str = os.environ["API_BASE_URL"]
MODEL_NAME: str = os.environ["MODEL_NAME"]
HF_TOKEN: str = os.environ["HF_TOKEN"]
ENV_URL: str = os.environ.get("ENV_URL", "http://localhost:7860")

client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)

SYSTEM_PROMPT = """\
You are an expert customer-support triage agent.
Given a support ticket observation, respond ONLY with a valid JSON object (no markdown, no extra text) \
with exactly these keys:
  chosen_team       – one of: account_support | billing | technical_support | trust_safety
  urgency           – one of: low | medium | high
  ask_clarification – true or false
  response_text     – a concise reply (10–300 characters)
"""

# ---------------------------------------------------------------------------
# Logging helpers  (format required by the evaluator)
# ---------------------------------------------------------------------------

def log_start(task_id: str) -> None:
    print(f"[START] task_id={task_id}", flush=True)


def log_step(task_id: str, step_idx: int, action: dict) -> None:
    print(
        f"[STEP] task_id={task_id} step={step_idx} action={json.dumps(action, sort_keys=True)}",
        flush=True,
    )


def log_end(task_id: str, score: float) -> None:
    print(f"[END] task_id={task_id} score={score:.4f}", flush=True)


# ---------------------------------------------------------------------------
# LLM helper
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict:
    """
    Robustly extract a JSON object from raw LLM output.
    Handles:
      - bare JSON
      - ```json ... ``` fences
      - leading/trailing prose with embedded JSON object
    Raises json.JSONDecodeError if no valid object is found.
    """
    text = text.strip()

    # 1. Strip markdown fences
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    # 2. Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 3. Grab first {...} block (handles leading prose)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())

    raise json.JSONDecodeError("No JSON object found", text, 0)


def llm_action(observation: dict, retries: int = 2) -> dict:
    """Ask the LLM to produce a triage action given the current observation."""
    user_content = (
        "Current observation:\n"
        + json.dumps(observation, indent=2)
        + "\n\nRespond with only the JSON action object."
    )
    last_exc: Exception = RuntimeError("no attempts made")

    for attempt in range(1, retries + 2):
        try:
            resp = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=0,
                max_tokens=256,
            )
            raw = resp.choices[0].message.content or ""
            return _extract_json(raw)
        except (json.JSONDecodeError, KeyError, IndexError) as exc:
            last_exc = exc
            print(f"[WARN] JSON parse failed (attempt {attempt}): {exc}", file=sys.stderr)

    # Final fallback: return a safe default action so the episode doesn't crash
    print("[WARN] All LLM attempts failed – using fallback action", file=sys.stderr)
    return {
        "chosen_team": "account_support",
        "urgency": "low",
        "ask_clarification": False,
        "response_text": "Unable to parse response; defaulting to account support.",
    }


# ---------------------------------------------------------------------------
# Episode runner
# ---------------------------------------------------------------------------

def run_task(task_id: str) -> float:
    # Reset
    r = requests.post(
        f"{ENV_URL}/reset",
        json={"task_id": task_id},
        timeout=30,
    )
    r.raise_for_status()
    payload = r.json()

    log_start(task_id)

    obs: dict = payload.get("observation", payload)
    final_score = 0.0

    for step_idx in range(1, 6):  # max 5 steps
        action = llm_action(obs)
        log_step(task_id, step_idx, action)

        s = requests.post(f"{ENV_URL}/step", json=action, timeout=30)
        s.raise_for_status()
        result = s.json()

        obs = result.get("observation", result)
        reward = result.get("reward", obs.get("reward", 0.0))
        done = result.get("done", obs.get("done", False))

        if done:
            final_score = float(reward)
            break
    else:
        final_score = float(obs.get("reward", 0.0))

    log_end(task_id, final_score)
    return final_score


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    task_ids = ["easy", "medium", "hard"]
    scores: list[float] = []

    for tid in task_ids:
        try:
            sc = run_task(tid)
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] task_id={tid} error={exc}", file=sys.stderr, flush=True)
            sc = 0.0
            log_end(tid, sc)
        scores.append(sc)

    summary = {
        "scores": scores,
        "mean_score": round(sum(scores) / len(scores), 4),
    }
    print(json.dumps(summary))
