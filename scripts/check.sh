#!/usr/bin/env bash
# Run every check a PR needs, in one command, and stop at the first failure.
#
# Usage, from the repository root:
#   scripts/check.sh            # backend tests, then website tests, type check and build
#   scripts/check.sh --backend  # only the backend (pytest)
#   scripts/check.sh --website  # only the website (tests, type check, build)
#
# Before opening or updating a PR, run this and make sure it ends with "All checks passed".
set -euo pipefail

cd "$(dirname "$0")/.."

run_backend=true
run_website=true
case "${1:-}" in
  "") ;;
  --backend) run_website=false ;;
  --website) run_backend=false ;;
  *) echo "Usage: scripts/check.sh [--backend | --website]" >&2; exit 1 ;;
esac

PYTHON="python3"
if [[ -x .venv/bin/python ]]; then PYTHON=".venv/bin/python"; fi

if $run_backend; then
  echo "== Backend tests =="
  MPLBACKEND=Agg "$PYTHON" -m pytest -q
fi

if $run_website; then
  if [[ ! -d frontend/node_modules ]]; then
    echo "Installing website dependencies (first run only)..."
    (cd frontend && npm ci)
  fi
  echo "== Website tests =="
  (cd frontend && npm test)
  echo "== Website type check =="
  (cd frontend && npm run lint)
  echo "== Website build =="
  # Quiet unless it fails (the large-chunk warning is known and harmless)
  build_log=$(cd frontend && npm run build 2>&1) || { echo "$build_log"; exit 1; }
fi

echo "All checks passed"
