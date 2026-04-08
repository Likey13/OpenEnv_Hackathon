"""
inference.py – agent baseline for the Support Triage OpenEnv.

Required environment variables:
- API_BASE_URL: LLM API base URL (OpenAI-compatible)
- MODEL_NAME: model identifier
- HF_TOKEN: API key / Hugging Face token

Optional environment variables:
- ENV_URL: environment server URL (default: http://localhost:7860)
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

import requests
from openai import OpenAI

API_BASE_URL: str = os.environ["API_BASE_URL"]
MODEL_NAME: str = os.environ["MODEL_NAME"]
HF_TOKEN: str = os.environ["HF_TOKEN"]
ENV_URL: str = os.environ.get("ENV_URL", "http://localhost:7860").rstrip("/")

client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)

SYSTEM_PROMPT = """\
You are an expert customer-support triage agent.
Given a support ticket observation, respond ONLY with a valid JSON object (no markdown, no extra text)
with exactly these keys:
- chosen_team: one of account_support | billing | technical_support | trust_safety
- urgency: one of low | medium | high
- ask_clarification: true or false
- response_text: a concise reply (10-300 characters)

Rules:
- Choose the best team based on the ticket.
- Set urgency based on customer impact and risk.
- Ask for clarification only when key information is genuinely missing.
- Keep response_text short, clear, and professional.
- Do not include any keys other than the required four.
"""

TASK_IDS = ["easy", "medium", "hard"]


def strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_action(raw_text: str) -> dict[str, Any]:
    cleaned = strip_code_fences(raw_text)
    data = json.loads(cleaned)

    required_keys = {
        "chosen_team",
        "urgency",
        "ask_clarification",
        "response_text",
    }
    if set(data.keys()) != required_keys:
        raise ValueError(
            f"Model output keys mismatch. Expected {sorted(required_keys)}, got {sorted(data.keys())}"
        )

    if data["chosen_team"] not in {
        "account_support",
        "billing",
        "technical_support",
        "trust_safety",
    }:
        raise ValueError(f"Invalid chosen_team: {data['chosen_team']}")

    if data["urgency"] not in {"low", "medium", "high"}:
        raise ValueError(f"Invalid urgency: {data['urgency']}")

    if not isinstance(data["ask_clarification"], bool):
        raise ValueError("ask_clarification must be a boolean")

    if not isinstance(data["response_text"], str):
        raise ValueError("response_text must be a string")

    data["response_text"] = data["response_text"].strip()
    if not 10 <= len(data["response_text"]) <= 300:
        raise ValueError("response_text must be between 10 and 300 characters")

    return data


def call_model(observation: dict[str, Any]) -> dict[str, Any]:
    user_prompt = (
        "Ticket observation:\n"
        f"{json.dumps(observation, indent=2)}\n\n"
        "Return only the JSON action object."
    )

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
    )

    raw_text = response.choices.message.content or ""
    return parse_action(raw_text)


def reset_episode(task_id: str) -> tuple[str, dict[str, Any]]:
    response = requests.post(
        f"{ENV_URL}/reset",
        json={"task_id": task_id},
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    episode_id = data.get("info", {}).get("episode_id", "")
    observation = data.get("observation", {})

    if not episode_id:
        raise RuntimeError(f"Missing episode_id in /reset response: {data}")

    return episode_id, observation


def step_episode(episode_id: str, action: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        f"{ENV_URL}/step",
        json=action,
        headers={"X-Episode-Id": episode_id},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def run_task(task_id: str) -> float:
    print(f"\n=== Running task: {task_id} ===")
    episode_id, observation = reset_episode(task_id)
    final_reward = 0.0

    for step_num in range(1, 6):
        action = call_model(observation)
        result = step_episode(episode_id, action)

        reward = float(result["reward"])
        done = bool(result["done"])
        observation = result["observation"]
        final_reward = reward

        print(f"Step {step_num} reward: {reward:.4f}")
        print(f"Action: {json.dumps(action, ensure_ascii=False)}")
        print(f"Feedback: {observation.get('feedback', '')}")

        if done:
            break

    print(f"Final reward for {task_id}: {final_reward:.4f}")
    return final_reward


def main() -> None:
    scores: list[float] = []

    for task_id in TASK_IDS:
        try:
            score = run_task(task_id)
            scores.append(score)
        except Exception as exc:
            print(f"Task {task_id} failed: {exc}", file=sys.stderr)
            scores.append(0.0)

    average = sum(scores) / len(scores) if scores else 0.0
    print("\n=== Summary ===")
    for task_id, score in zip(TASK_IDS, scores):
        print(f"{task_id}: {score:.4f}")
    print(f"Average: {average:.4f}")


if __name__ == "__main__":
    main()
