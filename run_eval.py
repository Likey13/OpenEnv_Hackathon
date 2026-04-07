#!/usr/bin/env bash
# run_eval.sh — one-command local evaluation
#
# Cross-file references
# ─────────────────────
#  requirements.txt       → installed by pip in step 1
#  app.py                 → uvicorn entry point started in step 2
#  tests/validate_local.py → 7-section HTTP validator run in step 3
#  inference.py           → agent baseline run in optional step 4
#  .env / .env.example    → API_BASE_URL, MODEL_NAME, HF_TOKEN loaded in step 4
#
# Usage
#   ./run_eval.sh               # steps 1–3 only
#   ./run_eval.sh --with-agent  # steps 1–4 (requires .env)

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

# 1. Install dependencies from requirements.txt
echo ""
echo "[1/4] Installing dependencies (requirements.txt)…"
pip install -q -r requirements.txt

# 2. Start app.py via uvicorn
echo ""
echo "[2/4] Starting environment server (app.py) on port $PORT…"
python -m uvicorn app:app --host 0.0.0.0 --port "$PORT" &
echo $! > "$PID_FILE"
sleep 3

# 3. Run tests/validate_local.py — hits /reset /step /state /tasks
echo ""
echo "[3/4] Running endpoint validator (tests/validate_local.py)…"
python tests/validate_local.py

# 4. Optional: run inference.py agent baseline
if $WITH_AGENT; then
    echo ""
    echo "[4/4] Running agent baseline (inference.py)…"
    if [[ ! -f ".env" ]]; then
        echo "  ⚠  .env not found — copy .env.example and fill in your credentials."
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
