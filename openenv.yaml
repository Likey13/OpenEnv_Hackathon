# openenv.yaml — OpenEnv manifest
# Cross-file reference: describes the contract implemented by app.py,
# models.py, environment.py, graders.py, tasks.py, and inference.py.

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
    schema: TriageAction       # defined in models.py
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
    schema: TicketObservation  # defined in models.py
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
    schema: TicketState        # defined in models.py
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
    implemented_in: app.py     # calls environment.py SupportTriageEnvironment.reset()
    body:
      task_id: str             # "easy" | "medium" | "hard" — see tasks.py
    returns: StepResponse      # models.py — includes info.episode_id

  step:
    method: POST
    path: /step
    implemented_in: app.py     # calls environment.py SupportTriageEnvironment.step()
    headers:
      X-Episode-Id: str        # UUID returned by /reset; omit for single-client mode
    body: TriageAction         # models.py
    returns: StepResponse      # models.py — reward scored by graders.py

  state:
    method: GET
    path: /state
    implemented_in: app.py     # calls environment.py SupportTriageEnvironment.state()
    headers:
      X-Episode-Id: str
    returns: TicketState       # models.py

  tasks:
    method: GET
    path: /tasks
    implemented_in: app.py     # reads tasks.py TASKS dict directly
    returns: dict              # list of task metadata objects

reward:
  type: dense
  range: [0.0, 1.0]
  implemented_in: graders.py  # grade_action() — pure rule-based, no LLM dependency
  description: >
    Partial rewards on each step:
      +0.20 correct team          (vs tasks.py Task.correct_team)
      +0.20 correct urgency       (vs tasks.py Task.correct_urgency)
      +0.20 clarification matches (vs tasks.py Task.needs_clarification)
      +0.20 response keywords     (vs tasks.py Task.required_response_keywords)
      +0.20 response 10–300 chars

runtime:
  max_steps: 5                 # enforced in environment.py SupportTriageEnvironment.MAX_STEPS
  max_minutes: 20
  hardware: "2 vCPU, 8 GB RAM"
  entry_point: inference.py    # agent baseline — reads API_BASE_URL, MODEL_NAME, HF_TOKEN
