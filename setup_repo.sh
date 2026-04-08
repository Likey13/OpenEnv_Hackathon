#!/usr/bin/env bash
# setup_repo.sh — scaffolds the full support-triage-openenv repo structure
#
# Usage:
#   chmod +x setup_repo.sh
#   ./setup_repo.sh
#   ./setup_repo.sh my-custom-folder-name

set -euo pipefail

REPO="${1:-support-triage-openenv}"

if [[ -d "$REPO" ]]; then
  echo "⚠ Folder '$REPO' already exists. Remove it first or pass a different name."
  exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Scaffolding: $REPO"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Directories ──────────────────────────────────────────────────────────────
mkdir -p "$REPO/tests"
mkdir -p "$REPO/.github/workflows"

echo "✓ Directories created"

# ── Root-level files ─────────────────────────────────────────────────────────
touch "$REPO/.env.example"
touch "$REPO/.gitignore"
touch "$REPO/Dockerfile"
touch "$REPO/Procfile"
touch "$REPO/README.md"
touch "$REPO/app.py"
touch "$REPO/docker-compose.yml"
touch "$REPO/environment.py"
touch "$REPO/graders.py"
touch "$REPO/inference.py"
touch "$REPO/models.py"
touch "$REPO/openenv.yaml"
touch "$REPO/pyproject.toml"
touch "$REPO/requirements.txt"
touch "$REPO/run_eval.sh"
touch "$REPO/runtime.txt"
touch "$REPO/setup_repo.sh"
touch "$REPO/tasks.py"

# ── Test and workflow files ──────────────────────────────────────────────────
touch "$REPO/tests/test_graders.py"
touch "$REPO/tests/test_suite.py"
touch "$REPO/tests/validate_local.py"
touch "$REPO/.github/workflows/ci.yml"

echo "✓ Files created"

cat <<EOF

Done. Repository scaffold created at:
  $REPO

Next steps:
  1. cd "$REPO"
  2. Add the file contents
  3. chmod +x run_eval.sh setup_repo.sh
  4. git init

EOF
