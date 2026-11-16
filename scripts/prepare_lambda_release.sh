#!/usr/bin/env bash
# Local-only release generation. No AWS login, uploads, provisioning or deployment.
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
release_id="${1:-issue33-lambda-2026-11-14}"
if [[ ! "$release_id" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  echo "Use one alphanumeric release name (letters, digits, dot, underscore, hyphen)." >&2
  exit 1
fi
input_file="$repo_dir/data/processed/pipeline/analysis_dataset.csv"
output_root="$repo_dir/models/issue33"
if [[ ! -f "$input_file" ]]; then
  echo "Required local analysis dataset is missing; no dataset will be rebuilt." >&2
  exit 1
fi
if [[ -e "$output_root/$release_id" ]]; then
  echo "Release already exists. Choose a new release ID; existing files stay unchanged." >&2
  exit 1
fi
command -v docker >/dev/null
docker info >/dev/null
mkdir -p "$output_root"
docker build --platform linux/amd64 \
  -f "$repo_dir/infra/Dockerfile.release" \
  -t parksmart-release-prep:local "$repo_dir"

docker run --rm --platform linux/amd64 --network none \
  --mount "type=bind,source=$input_file,target=/input/analysis_dataset.csv,readonly" \
  --mount "type=bind,source=$output_root,target=/output" \
  -e PARKSMART_RELEASE_ID="$release_id" \
  parksmart-release-prep:local -ec '
    python -m src.prepare_prediction_artifact \
      --dataset /input/analysis_dataset.csv --output-root /output \
      --release-id "$PARKSMART_RELEASE_ID"
    python -m scripts.prepare_serving_bundle \
      --artifact "/output/$PARKSMART_RELEASE_ID/selected.pkl" \
      --metadata "/output/$PARKSMART_RELEASE_ID/metadata.json" \
      --dataset /input/analysis_dataset.csv \
      --output-dir "/output/$PARKSMART_RELEASE_ID/bundle" \
      --s3-prefix "releases/$PARKSMART_RELEASE_ID"
    python -m scripts.verify_prediction_release \
      --release-dir "/output/$PARKSMART_RELEASE_ID/bundle"
  '
echo "Verified local release: models/issue33/$release_id/bundle"
echo "No AWS resources created or files uploaded. Do not commit the release files."
