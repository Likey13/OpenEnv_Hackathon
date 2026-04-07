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
    allowed_teams: list[str] = field(default_factory=lambda: [
        "account_support", "billing", "technical_support", "trust_safety"
    ])


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
        progress_hint="A straightforward account access issue. Identify the right team and urgency.",
    ),

    "medium": Task(
        task_id="medium",
        ticket_text=(
            "I was charged twice this month but I'm not sure which invoice is wrong. "
            "Can someone look into this?"
        ),
        customer_tier="premium",
        correct_team="billing",
        correct_urgency="medium",
        needs_clarification=True,
        required_response_keywords=["invoice", "charge", "clarif"],
        progress_hint=(
            "Incomplete billing complaint. You may need to ask for the invoice numbers "
            "before routing."
        ),
    ),

    "hard": Task(
        task_id="hard",
        ticket_text=(
            "URGENT: Our enterprise account has been compromised. Someone changed the admin "
            "email without authorisation. We are also being billed for 500 extra seats we "
            "never ordered, and one of our users has been sending threatening messages to "
            "our clients through the platform. We need immediate action on all three issues."
        ),
        customer_tier="enterprise",
        correct_team="trust_safety",
        correct_urgency="high",
        needs_clarification=False,
        required_response_keywords=["escalat", "secur", "investigat"],
        progress_hint=(
            "Multi-issue ticket: account security breach, billing anomaly, and policy violation. "
            "Prioritise the most critical issue and escalate appropriately."
        ),
    ),
}
