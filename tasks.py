from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Task:
    task_id: str
    ticket_text: str
    customer_tier: str
    correct_team: str
    correct_urgency: str
    needs_clarification: bool
    required_response_keywords: list[str]
    progress_hint: str
    allowed_teams: list[str] = field(
        default_factory=lambda: [
            "account_support",
            "billing",
            "technical_support",
            "trust_safety",
        ]
    )


TASKS: dict[str, Task] = {
    "easy": Task(
        task_id="easy",
        ticket_text=(
            "Hi, I forgot my password and can't log in to my account. "
            "I've tried the reset link but didn't receive the email. "
            "My username is john.doe@example.com."
        ),
        customer_tier="standard",
        correct_team="account_support",
        correct_urgency="low",
        needs_clarification=False,
        required_response_keywords=["password", "reset", "account"],
        progress_hint=(
            "A straightforward account access issue. "
            "Identify the right team and urgency."
        ),
    ),
    "medium": Task(
        task_id="medium",
        ticket_text=(
            "Hello, I was charged twice on my last invoice, but I can't tell "
            "which subscription line item caused it. Please help me fix this."
        ),
        customer_tier="premium",
        correct_team="billing",
        correct_urgency="medium",
        needs_clarification=True,
        required_response_keywords=["invoice", "charge", "clarify"],
        progress_hint=(
            "Billing issue, but some details are missing. "
            "A clarification request is appropriate before resolution."
        ),
    ),
    "hard": Task(
        task_id="hard",
        ticket_text=(
            "We believe our enterprise workspace may have been compromised. "
            "Several users were locked out, suspicious API activity appeared overnight, "
            "and customer data may have been exposed. We need immediate help."
        ),
        customer_tier="enterprise",
        correct_team="trust_safety",
        correct_urgency="high",
        needs_clarification=False,
        required_response_keywords=["investigate", "security", "escalate"],
        progress_hint=(
            "High-risk security incident affecting an enterprise customer. "
            "Prioritize safety, severity, and correct escalation path."
        ),
    ),
}
