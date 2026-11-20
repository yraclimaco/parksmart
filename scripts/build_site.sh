#!/usr/bin/env bash
# Build the website for the hosted demo and package it for Amplify.
#
# Usage, from the repository root:
#   scripts/build_site.sh <revision-id> [api-url]
#
# <revision-id> must be new each time (ZIPs reused with the same name can keep old
# files). api-url defaults to the deployed demo API. The build is connected to that
# API in API mode; nothing here is secret (VITE_ variables are public).
# Output: frontend/parksmart-site-<revision-id>.zip (ignored by Git). Upload it with
# "Deploy updates" on the existing `parksmart-website` Amplify app, branch `demo`.
set -euo pipefail

cd "$(dirname "$0")/.."

DEFAULT_API="https://3auautq1ga.execute-api.us-west-2.amazonaws.com"
revision="${1:-}"
api_url="${2:-$DEFAULT_API}"

if [[ -z "$revision" ]]; then
  echo "Usage: scripts/build_site.sh <revision-id> [api-url]" >&2
  exit 1
fi

# The site must be exactly what ParkSmart-Website produced: frontend/ is never hand-edited
if [[ -n "$(git status --porcelain -- frontend)" ]]; then
  echo "frontend/ has uncommitted changes. Commit or discard them first." >&2
  exit 1
fi

# Backend must be up so the built site is known to work with it
echo "Checking $api_url ..."
if ! curl -fs -m 30 "$api_url/readiness" | grep -q '"status":"ready"'; then
  echo "The API at $api_url is not ready. Fix that before building." >&2
  exit 1
fi

cd frontend
npm ci
npm test
npm run lint
VITE_API_BASE_URL="$api_url" VITE_RECOMMENDATION_SOURCE=api npm run build

zip_path="$PWD/parksmart-site-$revision.zip"
rm -f "$zip_path"
(cd dist && zip -qr "$zip_path" .)
echo "Built $zip_path"
echo "Upload it with Deploy updates on Amplify app parksmart-website, branch demo."
