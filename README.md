---
title: Support Triage OpenEnv
emoji: 🎫
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

Check out the configuration reference at https://huggingface.co/docs/hub/spaces-config-reference

# 🎫 Support Triage OpenEnv

A customer-support triage reinforcement-learning environment following the [OpenEnv](https://huggingface.co/openenv) specification, ready for local, Docker, Hugging Face Spaces, and generic PaaS deployment.

The agent reads support tickets and must:
- classify urgency (`low`, `medium`, `high`)
- route to the correct team
- request clarification when needed
- produce a short, policy-safe resolution response

---

## 📁 Repository layout

```text
.
├── .github/
│   └── workflows/
│       └── ci.yml          # CI: lint + pytest on push / PR
├── tests/
│   ├── test_graders.py     # Unit tests for graders + environment
│   └── validate_local.py   # End-to-end HTTP validator (needs server running)
├── .env.example            # Required environment variable template
├── .gitignore
├── Dockerfile              # Production image (non-root, PYTHONPATH=/app)
├── Procfile                # PaaS start command (Railway / Render)
├── README.md               # This file
├── app.py                  # FastAPI server — /reset /step /state /tasks
├── environment.py          # Core RL loop: reset() / step() / state()
├── graders.py              # Rule-based reward function → 0.0–1.0
├── inference.py            # Agent baseline script (OpenAI-compatible LLM)
├── models.py               # Pydantic models: Action, Observation, State
├── openenv.yaml            # OpenEnv manifest
├── pyproject.toml          # Build config, dependencies, pytest + ruff + mypy
├── requirements.txt        # Pinned runtime dependencies
├── runtime.txt             # Python version pin for PaaS
└── tasks.py                # Task definitions: easy / medium / hard
```

---

## 🗂 File guide

### Core application

| File | Purpose |
|------|---------|
| [`app.py`](app.py) | FastAPI entry point. Exposes `POST /reset`, `POST /step`, `GET /state`, `GET /tasks`. Session-safe: each episode gets its own UUID, passed back via `X-Episode-Id` header. |
| [`environment.py`](environment.py) | Stateful `SupportTriageEnvironment` class. Implements `reset()`, `step()`, and `state()`. Enforces max 5 steps per episode. |
| [`models.py`](models.py) | All Pydantic v2 models: `TriageAction`, `TicketObservation`, `TicketState`, `ResetRequest`, `StepResponse`. |
| [`tasks.py`](tasks.py) | Defines the three tasks (`easy`, `medium`, `hard`) as typed dataclasses with correct answers, required keywords, and progress hints. |
| [`graders.py`](graders.py) | Pure rule-based grader. Scores each action across 5 criteria (+0.20 each), returns `(score, feedback)` with score clamped to `[0.0, 1.0]`. |
| [`inference.py`](inference.py) | Agent baseline. Uses the OpenAI-compatible client, emits `[START]` / `[STEP]` / `[END]` logs, retries on JSON parse failure, passes `X-Episode-Id` header. |

### Configuration & deployment

| File | Purpose |
|------|---------|
| [`Dockerfile`](Dockerfile) | `python:3.11-slim`, non-root `appuser` (UID 1000), `PYTHONPATH=/app`, shell-form `CMD` for `$PORT` expansion. Required for HF Spaces. |
| [`openenv.yaml`](openenv.yaml) | OpenEnv manifest — describes tasks, models, endpoints, and reward structure. |
| [`pyproject.toml`](pyproject.toml) | Build backend (`setuptools.build_meta`), pinned dependencies, `[dev]` extras, `pytest` / `ruff` / `mypy` config. |
| [`requirements.txt`](requirements.txt) | Pinned runtime deps used by `pip install` inside Docker. |
| [`runtime.txt`](runtime.txt) | `python-3.11.x` — Python version pin for Railway / Render. |
| [`Procfile`](Procfile) | `web: python -m uvicorn app:app --host 0.0.0.0 --port ${PORT:-7860}` |
| [`.env.example`](.env.example) | Template for `API_BASE_URL`, `MODEL_NAME`, `HF_TOKEN`, `ENV_URL`. Copy to `.env` before running locally. |
| [`.gitignore`](.gitignore) | Ignores `.env`, `__pycache__`, `.venv`, `.pytest_cache`, `dist/`, `*.egg-info`. |

### Tests & validation

| File | Purpose |
|------|---------|
| [`tests/test_graders.py`](tests/test_graders.py) | 16 pytest unit tests covering perfect scores, partial penalties, env lifecycle, session reset, and reward bounds. Run with `pytest`. |
| [`tests/validate_local.py`](tests/validate_local.py) | 7-section HTTP validator (health, reset, step, state, score range, task discovery, session isolation). Requires the server to be running. |
| [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | Runs `ruff check` and `pytest` on every push and pull request. |

---

## 🏆 Tasks

| ID | Description | Correct team | Urgency | Clarification? |
|----|-------------|-------------|---------|----------------|
| `easy` | Password reset, clean ticket | `account_support` | `low` | No |
| `medium` | Double-charge complaint, missing invoice numbers | `billing` | `medium` | Yes |
| `hard` | Enterprise: security breach + billing anomaly + policy violation | `trust_safety` | `high` | No |

---

## 🎯 Reward breakdown (per step, sum capped at 1.0)

| Criterion | Points |
|-----------|--------|
| Correct team | +0.20 |
| Correct urgency | +0.20 |
| Clarification behaviour matches task | +0.20 |
| Response contains required keywords | +0.20 |
| Response is 10–300 chars | +0.20 |

---

## 🚀 Quickstart

### 1 — Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # fill in your values
```

### 2 — Run the server

```bash
python -m uvicorn app:app --reload --host 0.0.0.0 --port 7860
```

### 3 — Validate endpoints

```bash
python tests/validate_local.py
```

### 4 — Run unit tests

```bash
pytest
```

### 5 — Run the agent baseline

```bash
export $(cat .env | xargs)
python inference.py
```

---

## 🐳 Docker

```bash
docker build -t support-triage-openenv .
docker run --env-file .env -p 7860:7860 support-triage-openenv
```

---

## 🤗 Hugging Face Spaces

1. Create a new **Docker Space**.
2. Push this repository to the Space.
3. Add secrets in Space settings: `API_BASE_URL`, `MODEL_NAME`, `HF_TOKEN`.
4. The Space auto-builds and exposes the environment at `https://<your-space>.hf.space`.

---

## ☁️ Generic PaaS (Railway / Render)

The [`Procfile`](Procfile) and [`runtime.txt`](runtime.txt) are included for one-click deploy on platforms that support them. The default start command is:

```bash
python -m uvicorn app:app --host 0.0.0.0 --port ${PORT:-7860}
```

---

## 🔌 API reference

### `POST /reset`

```json
{ "task_id": "easy" }
```

Returns `StepResponse`. The `info.episode_id` field must be passed as `X-Episode-Id` on all subsequent calls.

### `POST /step`

Header: `X-Episode-Id: <episode_id>`

```json
{
  "chosen_team": "account_support",
  "urgency": "low",
  "ask_clarification": false,
  "response_text": "We will reset your password shortly."
}
```

Returns `StepResponse` with `reward` (`0.0–1.0`), `done`, and `feedback`.

### `GET /state`

Header: `X-Episode-Id: <episode_id>`

Returns current `TicketState`.

### `GET /tasks`

No header required. Returns metadata for all three tasks.
