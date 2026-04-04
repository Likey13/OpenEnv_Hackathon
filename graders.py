from __future__ import annotations
from models import TriageAction
from tasks import Task


def grade_action(action: TriageAction, task: Task, step_count: int) -> tuple[float, str]:
    """
    Return (score, feedback) where score is in [0.0, 1.0].

    Breakdown:
      +0.20  correct team chosen
      +0.20  correct urgency
      +0.20  clarification behaviour matches task requirement
      +0.20  response contains required keywords
      +0.20  response is concise (≤ 300 chars) and not empty
    """
    score = 0.0
    parts: list[str] = []

    # --- team ---
    if action.chosen_team == task.correct_team:
        score += 0.20
        parts.append("✓ correct team")
    else:
        parts.append(f"✗ wrong team (expected {task.correct_team})")

    # --- urgency ---
    if action.urgency == task.correct_urgency:
        score += 0.20
        parts.append("✓ correct urgency")
    else:
        parts.append(f"✗ wrong urgency (expected {task.correct_urgency})")

    # --- clarification behaviour ---
    if action.ask_clarification == task.needs_clarification:
        score += 0.20
        parts.append("✓ clarification behaviour correct")
    else:
        expected = "required" if task.needs_clarification else "not required"
        parts.append(f"✗ clarification {expected}")

    # --- required keywords in response ---
    text_lower = action.response_text.lower()
    hits = [kw for kw in task.required_response_keywords if kw in text_lower]
    if hits:
        score += 0.20
        parts.append(f"✓ response keywords found: {hits}")
    else:
        parts.append(f"✗ missing response keywords: {task.required_response_keywords}")

    # --- response quality (non-empty and concise) ---
    response_len = len(action.response_text.strip())
    if 10 <= response_len <= 300:
        score += 0.20
        parts.append("✓ response length acceptable")
    elif response_len > 300:
        parts.append("✗ response too long (> 300 chars)")
    else:
        parts.append("✗ response too short or empty")

    # Clamp to [0.0, 1.0] (safety net)
    score = max(0.0, min(1.0, round(score, 4)))
    feedback = " | ".join(parts)
    return score, feedback
