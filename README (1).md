# Support Triage OpenEnv

A customer-support triage reinforcement-learning environment that follows the OpenEnv specification and is prepared for local, Docker, Hugging Face Spaces, and generic PaaS deployment.

The agent reads support tickets and must:
- classify urgency (`low`, `medium`, `high`)
- route to the correct team
- request clarification when needed
- produce a short, policy-safe resolution response

## Tasks

| ID | Description | Correct team | Urgency | Clarification? |
|---|---|---|---|---|
| `easy` | Password reset, clean ticket | `account_support` | `low` | No |
| `medium` | Double-charge complaint, missing invoice numbers | `billing` | `medium` | Yes |
| `hard` | Enterprise security breach + billing anomaly + policy violation | `trust_safety` | `high` | No |

## Reward breakdown

| Criterion | Points |
|---|---:|
| Correct team | +0.20 |
| Correct urgency | +0.20 |
| Clarification behavior matches task | +0.20 |
| Response contains required keywords | +0.20 |
| Response is 10–300 chars | +0.20 |

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
uvicorn app:app --reload --host 0.0.0.0 --port 7860
```

## Testing

```bash
pytest
```

If your repository still uses `tests/validate_local.py`, you can also run:

```bash
python tests/validate_local.py
```

## Docker

```bash
docker build -t support-triage-openenv .
docker run --env-file .env -p 7860:7860 support-triage-openenv
```

## Hugging Face Spaces

1. Create a new **Docker Space**.
2. Push this repository to the Space.
3. Add any required secrets in the Space settings, for example `API_BASE_URL`, `MODEL_NAME`, `HF_TOKEN`, or `OPENAI_API_KEY`.
4. The included `Dockerfile` will start the FastAPI app on port `7860` by default.

If needed, keep the README YAML front matter aligned with Docker Spaces settings:

```yaml
---
title: Support Triage OpenEnv
emoji: 🚀
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
---
```

## Generic PaaS deployment

This repo also includes:
- `Procfile` for platforms such as Railway or Render-style Procfile setups.
- `runtime.txt` for Python runtime pinning where supported.
- `.github/workflows/ci.yml` for CI on pushes and pull requests.

Default start command:

```bash
python -m uvicorn app:app --host 0.0.0.0 --port ${PORT:-7860}
```

## API reference

### `POST /reset`

```json
{ "task_id": "easy" }
```

### `POST /step`

```json
{
  "chosen_team": "account_support",
  "urgency": "low",
  "ask_clarification": false,
  "response_text": "We will reset your password shortly."
}
```

### `GET /state`

Returns the current ticket state.

## Suggested root layout

```text
.
├── .github/
│   └── workflows/
│       └── ci.yml
├── .env.example
├── .gitignore
├── Dockerfile
├── Procfile
├── README.md
├── app.py
├── environment.py
├── graders.py
├── inference.py
├── models.py
├── openenv.yaml
├── pyproject.toml
├── requirements.txt
├── runtime.txt
├── tasks.py
└── tests/
```
