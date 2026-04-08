from __future__ import annotations

from models import TriageAction
from tasks import Task


def grade_action(action: TriageAction, task: Task, step_count: int) -> tuple[float, str]:
    """
    Return (score, feedback) where score is in [0.0, 1.0].

    Breakdown:
    +0.20 correct team chosen
    +0.20 correct urgency
    +0.20 clarification behaviour matches task requirement
    +0.20 response contains required keywords
    +0.20 response is concise (<= 300 chars) and not empty
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
        parts.append("✓ clarification decision correct")
    else:
        if task.needs_clarification:
            parts.append("✗ should ask for clarification")
        else:
            parts.append("✗ unnecessary clarification")

    # --- response keywords ---
    text_lower = action.response_text.lower().strip()
    required = [kw.lower() for kw in task.required_response_keywords]

    if all(keyword in text_lower for keyword in required):
        score += 0.20
        parts.append("✓ required keywords present")
    else:
        missing = [kw for kw in task.required_response_keywords if kw.lower() not in text_lower]
        parts.append(f"✗ missing keywords: {', '.join(missing)}")

    # --- response quality / brevity ---
    if 1 <= len(action.response_text.strip()) <= 300:
        score += 0.20
        parts.append("✓ response length acceptable")
    else:
        parts.append("✗ response must be 1-300 characters")

    score = max(0.0, min(1.0, round(score, 4)))
    feedback = f"Step {step_count}: " + "; ".join(parts)
    return score, feedback
