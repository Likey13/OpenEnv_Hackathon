#!/usr/bin/env bash
# setup_repo.sh — scaffolds the full support-triage-openenv repo structure
# Usage:
#   chmod +x setup_repo.sh
#   ./setup_repo.sh                        # creates ./support-triage-openenv/
#   ./setup_repo.sh my-custom-folder-name  # creates in named folder

set -euo pipefail

REPO="${1:-support-triage-openenv}"

if [[ -d "$REPO" ]]; then
  echo "⚠  Folder '$REPO' already exists. Remove it first or pass a different name."
  exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Scaffolding: $REPO"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Directories ──────────────────────────────────────────────────────────────
mkdir -p "$REPO/tests"
mkdir -p "$REPO/.github/workflows"
echo "  ✓ directories created"

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
touch "$REPO/tasks.py"
echo "  ✓ root files created"

# ── tests/ ────────────────────────────────────────────────────────────────────
touch "$REPO/tests/test_graders.py"
touch "$REPO/tests/validate_local.py"
echo "  ✓ tests/ files created"

# ── .github/workflows/ ───────────────────────────────────────────────────────
touch "$REPO/.github/workflows/ci.yml"
echo "  ✓ .github/workflows/ci.yml created"

# ── Make shell scripts executable ────────────────────────────────────────────
chmod +x "$REPO/run_eval.sh"

# ── Verify tree ──────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Structure:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
find "$REPO" -type f | sort | sed "s|$REPO/||" | while read -r f; do
  echo "  $f"
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Done — $REPO/ is ready."
echo " Next: copy your source files into each placeholder."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
