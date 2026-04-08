pip install ruff---
title: Support Triage OpenEnv
emoji: 🎫
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# 🎫 Support Triage OpenEnv

A customer-support triage reinforcement-learning environment following the OpenEnv specification, ready for local development, Docker, Hugging Face Spaces, and generic PaaS deployment. [query]

The agent reads support tickets and must:
- Classify urgency (`low`, `medium`, `high`)
- Route to the correct team
- Request clarification when needed
- Produce a short, policy-safe resolution response

## Repository layout

```text
.
├── .github/
│   └── workflows/
│       └── ci.yml                 # Runs Ruff + pytest on every push / PR
├── tests/
│   ├── test_graders.py            # Unit tests for graders.py + environment.py
│   ├── test_suite.py              # Combined unit + integration suite
│   └── validate_local.py          # Standalone HTTP validator
├── app.py                         # FastAPI server exposing OpenEnv endpoints
├── environment.py                 # Episode state and environment transitions
├── graders.py                     # Reward / scoring logic
├── inference.py                   # Agent inference helpers
├── models.py                      # Pydantic models
├── tasks.py                       # Task definitions
├── Dockerfile                     # Container build for Spaces / Docker
├── Procfile                       # Procfile-based deployment entry
├── pyproject.toml                 # Project metadata and tool config
└── README.md
```

## API endpoints

The app exposes these endpoints:
- `GET /` — Health check
- `POST /reset` — Start a new episode for a task
- `POST /step` — Submit an action for the current episode
- `GET /state` — Inspect current episode state
- `GET /tasks` — List available tasks

## Local run

Install dependencies and start the server:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m uvicorn app:app --host 0.0.0.0 --port 7860
```

Then validate locally:

```bash
pytest -v
python tests/validate_local.py
```

## Docker run

Build and run with Docker:

```bash
docker build -t support-triage-openenv .
docker run -p 7860:7860 support-triage-openenv
```

## CI

The CI workflow is intended to:
- Set up Python 3.11
- Install the project with dev dependencies
- Run Ruff
- Run pytest

## Notes

This project is configured for Hugging Face Spaces with `sdk: docker` and `app_port: 7860`, which matches the Docker-based deployment metadata in the README front matter. The repository metadata in `pyproject.toml` points to the Hugging Face Space and the GitHub repository for this project. [query]
