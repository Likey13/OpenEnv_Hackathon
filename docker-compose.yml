# docker-compose.yml — Local multi-service orchestration
#
# Cross-file references
# ─────────────────────
#  Dockerfile        → builds the image used by all three services
#                      (python:3.11-slim, non-root appuser, PYTHONPATH=/app)
#  app.py            → uvicorn entry point started by env_server
#  requirements.txt  → installed during Docker build (RUN pip install ...)
#  .env              → loaded by the `agent` service (copy from .env.example)
#  tests/validate_local.py → run by the `validator` service
#  inference.py      → run by the optional `agent` service
#  openenv.yaml      → describes the env contract validated at /reset /step /state
#
# Usage
# ─────
#  Full stack (server + validator):
#    docker compose up --build
#
#  With agent baseline (requires .env to be filled in):
#    docker compose --profile agent up --build
#
#  Server only:
#    docker compose up env_server

version: "3.9"

services:

  # ── 1. Environment server ──────────────────────────────────────────────────
  # Builds from Dockerfile → starts app.py via uvicorn on port 7860
  # Exposes: POST /reset  POST /step  GET /state  GET /tasks
  env_server:
    build: .                          # uses Dockerfile in repo root
    ports:
      - "7860:7860"
    environment:
      PORT: "7860"
      PYTHONPATH: "/app"              # mirrors ENV PYTHONPATH=/app in Dockerfile
    healthcheck:
      # Hits app.py GET / → {"status": "ok"} before dependants start
      test: ["CMD", "python", "-c",
             "import urllib.request; urllib.request.urlopen('http://localhost:7860/')"]
      interval: 5s
      timeout: 5s
      retries: 6

  # ── 2. Endpoint validator ──────────────────────────────────────────────────
  # Runs tests/validate_local.py (7 sections: health, reset, step, state,
  # score range, task discovery, session isolation) against env_server.
  # Exits 0 on ALL CHECKS PASSED, non-zero on any failure.
  validator:
    build: .                          # same image as env_server
    depends_on:
      env_server:
        condition: service_healthy    # waits for app.py GET / to return 200
    environment:
      BASE_URL: "http://env_server:7860"   # read by validate_local.py
      PYTHONPATH: "/app"
    command: ["python", "tests/validate_local.py"]

  # ── 3. Agent baseline (opt-in) ─────────────────────────────────────────────
  # Runs inference.py — requires .env to be populated (copy from .env.example).
  # env vars needed:  API_BASE_URL  MODEL_NAME  HF_TOKEN
  # Emits [START] [STEP] [END] logs as defined in inference.py.
  # Only starts when --profile agent is passed (keeps default stack clean).
  agent:
    build: .                          # same image as env_server
    depends_on:
      env_server:
        condition: service_healthy
    env_file: .env                    # API_BASE_URL, MODEL_NAME, HF_TOKEN
    environment:
      ENV_URL: "http://env_server:7860"    # overrides default localhost in inference.py
      PYTHONPATH: "/app"
    command: ["python", "inference.py"]
    profiles:
      - agent   # activate with: docker compose --profile agent up agent
