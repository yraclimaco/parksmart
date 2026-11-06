"""Fetch a trusted, checksummed private S3 serving bundle before app startup.

Nothing here runs at import time. This never trains, builds a dataset, uploads,
or searches for credentials; boto3 uses the deployment's IAM execution role.
"""

import hashlib
import json
import re
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

BUNDLE_VERSION = 1
MAX_MANIFEST_BYTES = 65536
CHUNK_BYTES = 1024 * 1024
FILENAMES = {"artifact": "selected.pkl", "dataset": "analysis_dataset.csv",
             "registry": "locations.json"}
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def file_sha256(path):
    """Return the SHA-256 of an existing file, reading it in bounded chunks."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_manifest(document, prefix):
    """Validate a v1 S3 manifest within one release prefix; return its file map.

    Args:
        document: decoded manifest with artifact/dataset/registry keys.
        prefix: manifest object's directory, including its trailing slash.
    Raises:
        ValueError: incomplete, invalid or out-of-prefix object descriptions.
    """
    if not isinstance(document, dict) or document.get("schema_version") != BUNDLE_VERSION:
        raise ValueError("Unsupported serving bundle manifest version")
    files = document.get("files")
    if not isinstance(files, dict) or set(files) != set(FILENAMES):
        raise ValueError("Bundle requires artifact, dataset and registry files")
    for item in files.values():
        if not isinstance(item, dict):
            raise ValueError("Each bundle file must describe key and sha256")
        key, digest = item.get("key"), item.get("sha256")
        if (not isinstance(key, str) or not key.startswith(prefix)
                or key == prefix or ".." in key.split("/")):
            raise ValueError("Bundle object must stay within its release prefix")
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise ValueError("Each bundle object requires a lowercase SHA-256")
    return files


def materialize_bundle(uri, cache_dir, client=None):
    """Download/check one immutable trusted S3 bundle and return local paths.

    Args:
        uri: s3://bucket/release-prefix/manifest.json, never a public HTTP URL.
        cache_dir: writable local cache (Lambda uses /tmp).
        client: optional S3 client for injection; defaults to boto3's IAM client.
    Returns:
        Dict artifact/dataset/registry -> checksum-verified local Path. Cached
        files are verified before reuse; partial/corrupt downloads are rejected.
    """
    parts = urlsplit(uri)
    key = parts.path.lstrip("/")
    if (parts.scheme != "s3" or not parts.netloc or not key
            or "/" not in key or parts.query or parts.fragment
            or parts.username or parts.password):
        raise ValueError("Use s3://bucket/release-prefix/manifest.json")
    prefix = key.rsplit("/", 1)[0] + "/"
    if client is None:
        import boto3
        client = boto3.client("s3")
    body = client.get_object(Bucket=parts.netloc, Key=key)["Body"]
    try:
        raw = body.read(MAX_MANIFEST_BYTES + 1)
    finally:
        body.close()
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError("Serving manifest exceeds its size limit")
    files = validate_manifest(json.loads(raw), prefix)
    # A changed manifest gets a different directory; releases cannot mix files.
    target = Path(cache_dir) / hashlib.sha256(raw).hexdigest()
    target.mkdir(parents=True, exist_ok=True)
    result = {}
    for name, item in files.items():
        path = target / FILENAMES[name]
        if not path.is_file() or file_sha256(path) != item["sha256"]:
            body = client.get_object(Bucket=parts.netloc, Key=item["key"])["Body"]
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="wb", dir=target, prefix=path.name + ".", suffix=".part",
                    delete=False,
                ) as stream:
                    temporary = Path(stream.name)
                    for chunk in iter(lambda: body.read(CHUNK_BYTES), b""):
                        stream.write(chunk)
                if file_sha256(temporary) != item["sha256"]:
                    raise ValueError(f"Checksum mismatch for serving {name}")
                temporary.replace(path)
            finally:
                body.close()
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        result[name] = path
    return result
