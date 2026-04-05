name: support-triage-openenv
version: "1.0.0"
description: >
  A customer-support triage RL environment.
  The agent reads support tickets, classifies urgency, routes to the correct team,
  requests clarification when needed, and produces a short resolution response.

tasks:
  - id: easy
    description: Clean ticket with obvious routing (password reset → account_support, low urgency).
  - id: medium
    description: Incomplete billing complaint requiring one clarification before correct routing.
  - id: hard
    description: Multi-issue enterprise ticket requiring prioritisation, escalation, and compliance-safe wording.

models:
  action:
    schema: TriageAction
    fields:
      - name: chosen_team
        type: "Literal['account_support','billing','technical_support','trust_safety']"
      - name: urgency
        type: "Literal['low','medium','high']"
      - name: ask_clarification
        type: bool
      - name: response_text
        type: str

  observation:
    schema: TicketObservation
    fields:
      - name: task_id
        type: str
      - name: ticket_text
        type: str
      - name: customer_tier
        type: str
      - name: allowed_teams
        type: "list[str]"
      - name: progress_hint
        type: str
      - name: reward
        type: float
      - name: done
        type: bool
      - name: feedback
        type: str

  state:
    schema: TicketState
    fields:
      - name: episode_id
        type: str
      - name: step_count
        type: int
      - name: task_id
        type: str
      - name: clarification_requested
        type: bool
      - name: resolved
        type: bool
      - name: cumulative_reward
        type: float

endpoints:
  reset:
    method: POST
    path: /reset
    body:
      task_id: str  # "easy" | "medium" | "hard"
    returns: StepResponse

  step:
    method: POST
    path: /step
    body: TriageAction
    returns: StepResponse

  state:
    method: GET
    path: /state
    returns: TicketState

reward:
  type: dense
  range: [0.0, 1.0]
  description: >
    Partial rewards on each step:
      +0.20 correct team
      +0.20 correct urgency
      +0.20 clarification behaviour matches task requirement
      +0.20 response contains required keywords
      +0.20 response is concise (10–300 chars)

runtime:
  max_steps: 5
  max_minutes: 20
  hardware: "2 vCPU, 8 GB RAM"
