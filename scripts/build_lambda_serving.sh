#!/usr/bin/env bash
# Build locally only; no registry login, image upload or AWS resource changes.
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
release_id="${1:-issue33-lambda-2026-11-14}"
image_tag="${2:-$release_id}"
if [[ ! "$release_id" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  echo "Use a single alphanumeric release ID with dots, underscores or hyphens." >&2
  exit 1
fi
if [[ ! "$image_tag" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$ ]]; then
  echo "Use a Docker image tag of 1-128 letters, digits, dots, underscores or hyphens; start with a letter, digit or underscore." >&2
  exit 1
fi
bundle_dir="$repo_dir/models/issue33/$release_id/bundle"
if [[ ! -f "$bundle_dir/requirements-model.txt" || ! -f "$bundle_dir/manifest.json" ]]; then
  echo "Verified release bundle missing; run preparation successfully first." >&2
  exit 1
fi
command -v docker >/dev/null
docker info >/dev/null
mkdir -p "$repo_dir/.lambda-build"
# Only the nonsecret dependency lock enters Docker's allowlisted build context.
# Actual model/data/metadata remain in the private bundle and are mounted later.
cp "$bundle_dir/requirements-model.txt" "$repo_dir/.lambda-build/requirements-model.txt"
docker build --platform linux/amd64 --provenance=false \
  --build-arg MODEL_REQUIREMENTS_FILE=.lambda-build/requirements-model.txt \
  -f "$repo_dir/infra/Dockerfile" \
  -t "parksmart-backend:$image_tag" "$repo_dir"
echo "Built parksmart-backend:$image_tag locally using bundle $release_id. No image was pushed."
