"""Prepare existing trusted model/data files for later private S3 provisioning.

No training, dataset building, AWS calls or uploads. Output is local/gitignored.
Run only with the trusted artifact and its exact training environment.
"""

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from src.api.bundle import file_sha256
from src.availability_prediction import DEFAULT_ARTIFACT, load_prediction_service
from src.location_registry import DEFAULT_DATASET, DEFAULT_REGISTRY, load_registry
from src.location_registry import unmapped_facilities
from src.parking_benchmarks import load_analysis_dataset



def main(argv=None):
    """Copy and checksum approved resources; return the prepared manifest path.

    Args:
        argv: optional CLI argument list, normally parsed from the shell.
    Returns:
        Path of a local manifest. Existing source files are never modified.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output-dir", type=Path, default=Path(".serving-bundle"))
    parser.add_argument("--s3-prefix", required=True,
                        help="Immutable release prefix, e.g. releases/demo-2026-11-05")
    parser.add_argument("--approved-model", default="historical_average")
    args = parser.parse_args(argv)
    prefix = args.s3_prefix.strip("/")
    if not prefix or ".." in prefix.split("/") or ":" in prefix:
        parser.error("Use a nonempty relative S3 release prefix")
    model = load_prediction_service(args.artifact)
    if model.name != args.approved_model:
        parser.error("Saved model does not match the explicitly approved model")
    registry = load_registry(args.registry)
    records = load_analysis_dataset(args.dataset)
    if unmapped_facilities(registry, records):
        parser.error("Dataset contains facilities not mapped by the registry")
    output = args.output_dir
    # Avoid overwriting an earlier release or mixing it with partially copied data.
    output.mkdir(parents=True, exist_ok=False)
    files = {}
    for name, source, filename in [
        ("artifact", args.artifact, "selected.pkl"),
        ("dataset", args.dataset, "analysis_dataset.csv"),
        ("registry", args.registry, "locations.json"),
    ]:
        target = output / filename
        shutil.copyfile(source, target)
        files[name] = {"key": f"{prefix}/{filename}", "sha256": file_sha256(target)}
    manifest = {
        "schema_version": 1,
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "model_name": model.name,
        "dependency_versions": model.dependency_versions,
        "files": files,
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    pins = [f"{name}=={value}" for name, value in
            model.dependency_versions.items() if name != "python"]
    (output / "requirements-model.txt").write_text("\n".join(pins) + "\n")
    print(f"Prepared {manifest_path}. No data was uploaded. Keep the bundle private.")
    return manifest_path


if __name__ == "__main__":
    main()
