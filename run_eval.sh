#!/usr/bin/env bash
# run_eval.sh — one-command local evaluation
#
# Cross-file references
# requirements.txt / pyproject.toml -> installed by pip in step 1
# app.py -> uvicorn entry point started in step 2
# tests/validate_local.py -> 7-section HTTP validator run in step 3
# inference.py -> agent baseline run in optional step 4
# .env -> API_BASE_URL, MODEL_NAME, HF_TOKEN loaded in step 4
#
# Usage
# ./run_eval.sh
# ./run_eval.sh --with-agent

set -euo pipefail

WITH_AGENT=false
if [[ "${1:-}" == "--with-agent" ]]; then
  WITH_AGENT=true
fi

PORT=7860
PID_FILE=".uvicorn.pid"

cleanup() {
  if [[ -f "$PID_FILE" ]]; then
    kill "$(cat "$PID_FILE")" 2>/dev/null || true
    rm -f "$PID_FILE"
    echo "→ Server stopped."
  fi
}

trap cleanup EXIT

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Support Triage OpenEnv – Local Eval"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo
echo "1) Installing dependencies..."
python -m pip install --upgrade pip

if [[ -f "pyproject.toml" ]]; then
  python -m pip install -e ".[dev]"
elif [[ -f "requirements.txt" ]]; then
  python -m pip install -r requirements.txt
else
  echo "No pyproject.toml or requirements.txt found."
  exit 1
fi

echo
echo "2) Starting local server on port ${PORT}..."
python -m uvicorn app:app --host 0.0.0.0 --port "${PORT}" > .uvicorn.log 2>&1 &
echo $! > "$PID_FILE"

echo "Waiting for server to become healthy..."
for _ in {1..30}; do
  if python - <<'PY'
import urllib.request
try:
    with urllib.request.urlopen("http://127.0.0.1:7860/", timeout=2) as r:
        raise SystemExit(0 if r.status == 200 else 1)
except Exception:
    raise SystemExit(1)
PY
  then
    echo "→ Server is up."
    break
  fi
  sleep 1
done

if ! python - <<'PY'
import urllib.request
try:
    with urllib.request.urlopen("http://127.0.0.1:7860/", timeout=2) as r:
        raise SystemExit(0 if r.status == 200 else 1)
except Exception:
    raise SystemExit(1)
PY
then
  echo "Server failed to start. Recent log output:"
  tail -n 50 .uvicorn.log || true
  exit 1
fi

echo
echo "3) Running HTTP validator..."
python tests/validate_local.py --base-url "http://127.0.0.1:${PORT}"

if [[ "$WITH_AGENT" == "true" ]]; then
  echo
  echo "4) Running baseline agent..."
  if [[ -f ".env" ]]; then
    set -a
    source .env
    set +a
  fi
  ENV_URL="http://127.0.0.1:${PORT}" python inference.py
fi

echo
echo "✅ Local evaluation completed successfully."
