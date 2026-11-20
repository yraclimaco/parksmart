#!/usr/bin/env bash
# Run the real backend and the website together, already connected.
#
# Usage, from the repository root:
#   scripts/dev.sh
#
# Starts the FastAPI backend on http://127.0.0.1:8000 and the website on
# http://localhost:3000 in API mode (searches go to POST /recommendations, never
# to sample data). Port 3000 is on the backend's CORS allowlist. Ctrl+C stops both.
# Needs the integrated dataset (see AGENTS.md) and `npm ci` run once in frontend/.
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON="python3"
if [[ -x .venv/bin/python ]]; then PYTHON=".venv/bin/python"; fi

if [[ ! -d frontend/node_modules ]]; then
  echo "Installing website dependencies (first run only)..."
  (cd frontend && npm ci)
fi

for port in 8000 3000; do
  if lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $port is already in use. Stop whatever is using it and run again." >&2
    exit 1
  fi
done

"$PYTHON" -m uvicorn src.api.main:app --port 8000 &
backend=$!
trap 'kill "$backend" 2>/dev/null || true' EXIT

# Wait for the backend before opening the site, so the first search does not fail
for _ in $(seq 1 60); do
  if curl -fs http://127.0.0.1:8000/health >/dev/null 2>&1; then break; fi
  if ! kill -0 "$backend" 2>/dev/null; then
    echo "Backend stopped while starting. Check the messages above." >&2
    exit 1
  fi
  sleep 1
done

echo "Backend ready. Website: http://localhost:3000 (add ?home to see the landing page)"
cd frontend
VITE_API_BASE_URL=http://127.0.0.1:8000 VITE_RECOMMENDATION_SOURCE=api \
  npm run dev -- --port 3000 --strictPort
