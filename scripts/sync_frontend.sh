#!/usr/bin/env bash
# One-way copy of the website from its source-of-truth repository into frontend/.
#
# The website is edited in dylanwang-main/ParkSmart-Website (synced with Google
# AI Studio). Never edit frontend/ directly: this script overwrites it.
#
# Usage, from the repository root:
#   scripts/sync_frontend.sh                    # latest main from GitHub
#   scripts/sync_frontend.sh --ref <branch|tag|commit>
#   scripts/sync_frontend.sh --source <local clone of ParkSmart-Website>
#
# With --source, only the clone's last commit is copied: commit the website first.
# The script stops if the clone has uncommitted changes, so nothing is silently left out.
#
# Afterwards: review `git diff -- frontend`, then commit on a feature branch.
set -euo pipefail

WEBSITE_REPO="https://github.com/dylanwang-main/ParkSmart-Website.git"
ref="main"
source_dir=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref) ref="$2"; shift 2 ;;
    --source) source_dir="$2"; shift 2 ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

repo_root="$(git rev-parse --show-toplevel)"
target="$repo_root/frontend"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

if [[ -z "$source_dir" ]]; then
  git clone --quiet "$WEBSITE_REPO" "$work/clone"
  git -C "$work/clone" checkout --quiet "$ref"
  source_dir="$work/clone"
fi
commit="$(git -C "$source_dir" rev-parse --short HEAD)"
branch="$(git -C "$source_dir" rev-parse --abbrev-ref HEAD)"

# Only committed files are copied, so uncommitted website edits would be silently left out.
if [[ -n "$(git -C "$source_dir" status --porcelain --untracked-files=normal)" ]]; then
  echo "The website clone at $source_dir has uncommitted changes, which would not be synced." >&2
  echo "Commit them in ParkSmart-Website first (or stash them), then run this again." >&2
  exit 1
fi
if [[ "$branch" != "main" && "$ref" == "main" ]]; then
  echo "Note: syncing from branch '$branch', not main. Merge it into ParkSmart-Website main before the PR here."
fi

# The backend checks at the end need the repo's Python requirements; check before
# frontend/ is overwritten, so a missing venv never leaves a half-finished sync.
PYTHON="python3"
if [[ -x "$repo_root/.venv/bin/python" ]]; then PYTHON="$repo_root/.venv/bin/python"; fi
if ! "$PYTHON" -c "import pytest, pandas" 2>/dev/null; then
  echo "$PYTHON lacks the backend requirements needed for the final checks." >&2
  echo "Create .venv and run: python -m pip install -r requirements.txt" >&2
  exit 1
fi

# Copy only tracked files, so local node_modules, builds, and .env files in the
# source clone can never leak in.
mkdir "$work/export"
git -C "$source_dir" archive HEAD | tar -x -C "$work/export"

# bun.lock is AI Studio's lockfile; this repo installs with npm (package-lock.json).
# Excluded paths are neither copied nor deleted, so local installs survive.
# rsync uses the first matching rule, so the .env.example include comes first.
rsync -a --delete \
  --include '.env.example' \
  --exclude bun.lock \
  --exclude node_modules/ \
  --exclude dist/ \
  --exclude '.env' \
  --exclude '.env.*' \
  "$work/export/" "$target/"

cd "$target"
# Refresh package-lock.json in case package.json changed without it.
npm install --no-audit --no-fund
npm test
npm run lint
npm run build

# Backend tests that read frontend/: pins must match the registry, and the landing page's
# figures and permit rules must match the backend (tests/test_website_facts.py).
cd "$repo_root"
echo
echo "== Backend checks on the synced website (pins, figures, permit rules) =="
MPLBACKEND=Agg "$PYTHON" -m pytest -q tests/test_location_registry.py tests/test_website_facts.py

echo
echo "Synced frontend/ from ParkSmart-Website commit $commit ($branch)."
git diff --stat -- frontend | tail -1
echo "Next: update AGENTS.md if behavior changed, run scripts/check.sh, then commit on a branch."
