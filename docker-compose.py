version: "3.9"

services:
  env_server:
    build: .
    ports:
      - "7860:7860"
    environment:
      PORT: "7860"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:7860/')"]
      interval: 5s
      timeout: 5s
      retries: 6

  validator:
    build: .
    depends_on:
      env_server:
        condition: service_healthy
    environment:
      ENV_URL: "http://env_server:7860"
    command: ["python", "tests/validate_local.py"]

  # Optional: run the agent baseline (set real values in .env before running)
  agent:
    build: .
    depends_on:
      env_server:
        condition: service_healthy
    env_file: .env
    environment:
      ENV_URL: "http://env_server:7860"
    command: ["python", "inference.py"]
    profiles:
      - agent   # only starts with: docker compose --profile agent up agent
