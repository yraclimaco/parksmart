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
# Afterwards: review `git diff -- frontend`, then commit on a feature branch.
set -euo pipefail

WEBSITE_REPO="https://github.com/dylanwang-main/ParkSmart-Website.git"
ref="main"
source_dir=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref) ref="$2"; shift 2 ;;
    --source) source_dir="$2"; shift 2 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
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

echo
echo "Synced frontend/ from ParkSmart-Website commit $commit."
echo "Review with: git diff --stat -- frontend"
