"""Offline checksum/S3 protocol tests for prepared, trusted serving bundles."""

import hashlib
import io
import json

import pytest

from src.api.bundle import materialize_bundle


class S3Fixture:
    def __init__(self, files):
        self.files = files
        self.calls = []

    def get_object(self, Bucket, Key):
        self.calls.append((Bucket, Key))
        if Key not in self.files:
            raise OSError("Object unavailable")
        return {"Body": io.BytesIO(self.files[Key])}


def bundle():
    files = {f"releases/v1/{name}": name.encode() for name in
             ("selected.pkl", "analysis_dataset.csv", "locations.json")}
    document = {"schema_version": 1, "files": {}}
    for role, name in zip(("artifact", "dataset", "registry"), files):
        document["files"][role] = {
            "key": name, "sha256": hashlib.sha256(files[name]).hexdigest()}
    files["releases/v1/manifest.json"] = json.dumps(document).encode()
    return files, document


def test_download_verified_cache_and_redownload_corruption(tmp_path):
    files, _ = bundle()
    client = S3Fixture(files)
    uri = "s3://private-bucket/releases/v1/manifest.json"
    paths = materialize_bundle(uri, tmp_path, client)
    assert len(client.calls) == 4
    materialize_bundle(uri, tmp_path, client)
    assert len(client.calls) == 5  # Recheck manifest; verified files are cached.
    paths["dataset"].write_bytes(b"corrupt")
    materialize_bundle(uri, tmp_path, client)
    assert len(client.calls) == 7  # Manifest plus only the corrupted object.


def test_bad_checksum_rejects_download_and_cleans_partial_file(tmp_path):
    files, _ = bundle()
    files["releases/v1/selected.pkl"] = b"changed"
    with pytest.raises(ValueError, match="Checksum"):
        materialize_bundle("s3://private-bucket/releases/v1/manifest.json", tmp_path,
                           S3Fixture(files))
    assert not list(tmp_path.rglob("*.part"))
    assert not list(tmp_path.rglob("selected.pkl"))


def test_manifest_cannot_pull_another_release(tmp_path):
    files, document = bundle()
    document["files"]["artifact"]["key"] = "other-release/model.pkl"
    files["releases/v1/manifest.json"] = json.dumps(document).encode()
    client = S3Fixture(files)
    with pytest.raises(ValueError, match="prefix"):
        materialize_bundle("s3://private-bucket/releases/v1/manifest.json", tmp_path,
                           client)
    assert len(client.calls) == 1


def test_missing_s3_resource_is_explicit(tmp_path):
    with pytest.raises(OSError):
        materialize_bundle("s3://private-bucket/releases/v1/manifest.json", tmp_path,
                           S3Fixture({}))
