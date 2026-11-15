"""Reproduce the approved historical artifact locally without model experiments.

This command never overwrites the working Issue #18 artifact or contacts AWS.
It fits on all validated records for serving, after evaluation/selection has
already established historical_average as the approved method in PR #23.
"""

import argparse
import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .api.bundle import file_sha256
from .availability_prediction import PredictionService, load_prediction_service
from .location_registry import DEFAULT_REGISTRY, load_registry, unmapped_facilities
from .parking_benchmarks import DEFAULT_DATASET, load_analysis_dataset

APPROVED_MODEL = "historical_average"
DEFAULT_OUTPUT_ROOT = Path("models/issue27")
RELEASE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPRODUCTION_SOURCES = (
    "src/prepare_prediction_artifact.py",
    "src/availability_prediction.py",
    "src/parking_benchmarks.py",
)


def _source_commit():
    """Return an optional checkout reference; file hashes identify actual code."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, check=True,
            capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def prepare_artifact(dataset, registry, output_dir):
    """Fit the approved baseline and publish a new local immutable directory.

    Args:
        dataset: Existing integrated analysis CSV; never rebuilt or modified.
        registry: Validated location registry covering every dataset facility.
        output_dir: New directory for selected.pkl, metadata.json and model pins.
    Returns:
        Path of metadata.json. Invalid inputs or an existing directory raise;
        source hashes bind this artifact to its exact supporting files.
    """
    dataset, registry, output_dir = map(Path, (dataset, registry, output_dir))
    if output_dir.exists():
        raise FileExistsError(f"Release already exists: {output_dir}")
    input_hashes = {"dataset": file_sha256(dataset), "registry": file_sha256(registry)}
    records = load_analysis_dataset(dataset).sort_values(
        ["observation_date", "record_id"]).reset_index(drop=True)
    locations = load_registry(registry)
    if unmapped_facilities(locations, records):
        raise ValueError("Dataset contains facilities not mapped by the registry")
    service = PredictionService(records, name=APPROVED_MODEL)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
            dir=output_dir.parent, prefix=".prepare-") as folder:
        staging = Path(folder) / "release"
        staging.mkdir()
        artifact = service.save(staging / "selected.pkl")
        # Exercise the same exact-version loader used by Daira before publishing.
        restored = load_prediction_service(artifact)
        if restored.name != APPROVED_MODEL:
            raise ValueError("Generated artifact does not use the approved method")
        for role, path in (("dataset", dataset), ("registry", registry)):
            if file_sha256(path) != input_hashes[role]:
                raise ValueError(f"Source {role} changed during artifact generation")
        input_hashes["artifact"] = file_sha256(artifact)
        metadata = {
            "schema_version": 1,
            "release_id": output_dir.name,
            "prepared_at": datetime.now(timezone.utc).isoformat(),
            "model_name": restored.name,
            "artifact_version": restored.artifact_version,
            "dependency_versions": restored.dependency_versions,
            "input_sha256": input_hashes,
            "source_sha256": {path: file_sha256(PROJECT_ROOT / path)
                              for path in REPRODUCTION_SOURCES},
            "source_commit": _source_commit(),
            "source_commit_note": (
                "Checkout reference only; source_sha256 identifies actual files, "
                "including any uncommitted changes"),
            "records": len(records),
            "training_start": restored.training_start,
            "training_end": restored.training_end,
            "survey_times": restored.survey_times,
            "feature_mode": restored.feature_mode,
            "approval_basis": "PR #23 serving-aligned validation; historical_average",
            "serving_refit": "all validated records; no model selection here",
            "support_policy": "PredictionService.support_labels; unsupported stays NaN",
        }
        (staging / "metadata.json").write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        pins = [f"{name}=={value}" for name, value in
                restored.dependency_versions.items() if name != "python"]
        (staging / "requirements-model.txt").write_text(
            "\n".join(pins) + "\n", encoding="utf-8")
        staging.rename(output_dir)
    return output_dir / "metadata.json"


def main(argv=None):
    """Parse optional CLI arguments and return the generated metadata path.

    The required release ID names a new directory under --output-root. Defaults
    use the integrated dataset, shared registry and private models/issue27 root.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--release-id", required=True)
    args = parser.parse_args(argv)
    if not RELEASE_ID.fullmatch(args.release_id) or args.release_id in {".", ".."}:
        parser.error("release-id must be one alphanumeric directory name")
    result = prepare_artifact(args.dataset, args.registry,
                              args.output_root / args.release_id)
    print(f"Prepared {result}. Existing artifacts are unchanged; no AWS calls.")
    return result


if __name__ == "__main__":
    main()
