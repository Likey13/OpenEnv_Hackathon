#!/usr/bin/env bash
# run_eval.sh – one-command local evaluation
# Usage:
#   ./run_eval.sh                      # start server, validate, stop
#   ./run_eval.sh --with-agent         # also run inference.py
#
# Requires: Python 3.11+, packages in requirements.txt installed.

set -euo pipefail

WITH_AGENT=false
[[ "${1:-}" == "--with-agent" ]] && WITH_AGENT=true

PORT=7860
PID_FILE=".uvicorn.pid"

cleanup() {
    if [[ -f "$PID_FILE" ]]; then
        kill "$(cat $PID_FILE)" 2>/dev/null || true
        rm -f "$PID_FILE"
        echo "→ Server stopped."
    fi
}
trap cleanup EXIT

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Support Triage OpenEnv – Local Eval"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Install dependencies
echo ""
echo "[1/4] Installing dependencies…"
pip install -q -r requirements.txt

# 2. Start server
echo ""
echo "[2/4] Starting environment server on port $PORT…"
python -m uvicorn app:app --host 0.0.0.0 --port "$PORT" &
echo $! > "$PID_FILE"
sleep 3   # give uvicorn a moment to bind

# 3. Validate
echo ""
echo "[3/4] Running endpoint validator…"
python tests/validate_local.py

# 4. Optional agent
if $WITH_AGENT; then
    echo ""
    echo "[4/4] Running inference.py…"
    if [[ ! -f ".env" ]]; then
        echo "  ⚠  .env not found – copy .env.example and fill in your credentials."
        exit 1
    fi
    set -a; source .env; set +a
    export ENV_URL="http://localhost:$PORT"
    python inference.py
else
    echo ""
    echo "[4/4] Skipped agent run (pass --with-agent to include)."
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Done."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
