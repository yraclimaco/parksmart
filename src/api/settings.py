"""Nonsecret serving configuration; environment files are never read implicitly."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _path(value, default):
    """Resolve a configured file relative to the project, independent of cwd."""
    path = Path(value or default).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


@dataclass(frozen=True)
class ServingSettings:
    """Paths and policy for one server process; no credentials belong here."""

    model_mode: str
    artifact_path: Path
    dataset_path: Path
    registry_path: Path
    approved_model: str
    bundle_manifest: Optional[str]
    cache_dir: Path

    @classmethod
    def from_env(cls, environ=None):
        """Return validated settings from a mapping or the process environment.

        Relative input paths resolve against the repository. Baseline mode must
        be explicitly selected; it is never a fallback for failed artifact load.
        """
        env = os.environ if environ is None else environ
        mode = env.get("PARKSMART_MODEL_MODE", "saved").strip()
        if mode not in {"saved", "baseline"}:
            raise ValueError("PARKSMART_MODEL_MODE must be saved or baseline")
        approved = env.get("PARKSMART_APPROVED_MODEL", "historical_average").strip()
        if not approved:
            raise ValueError("PARKSMART_APPROVED_MODEL cannot be empty")
        return cls(
            model_mode=mode,
            artifact_path=_path(env.get("PARKSMART_ARTIFACT_PATH"),
                                "models/issue18/selected.pkl"),
            dataset_path=_path(env.get("PARKSMART_DATASET_PATH"),
                               "data/processed/pipeline/analysis_dataset.csv"),
            registry_path=_path(env.get("PARKSMART_REGISTRY_PATH"),
                                "config/locations.json"),
            approved_model=approved,
            bundle_manifest=env.get("PARKSMART_BUNDLE_MANIFEST") or None,
            cache_dir=_path(env.get("PARKSMART_CACHE_DIR"), "/tmp/parksmart-serving"),
        )
