"""Offline checks for local Lambda release helpers and deployment naming."""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def release_prefix_pattern():
    """Extract ReleasePrefix validation without executing the SAM template."""
    template = (PROJECT_ROOT / "infra/template.yaml").read_text()
    section = template.split("  ReleasePrefix:\n", 1)[1].split(
        "  FrontendOrigins:\n", 1)[0]
    return re.search(r"AllowedPattern: '([^']+)'", section).group(1)


@pytest.mark.parametrize("release_id", [
    "issue33-lambda-2026-11-14", "release-v1.2", "v1_2", "Release2",
])
def test_preparation_release_names_are_deployable(release_id):
    """Names accepted by preparation must yield valid deployment prefixes."""
    script = (PROJECT_ROOT / "scripts/prepare_lambda_release.sh").read_text()
    helper_pattern = re.search(r'\$release_id" =~ ([^ ]+) ', script).group(1)
    assert re.fullmatch(helper_pattern, release_id)
    assert re.fullmatch(release_prefix_pattern(), f"releases/{release_id}")


@pytest.mark.parametrize("prefix", [
    "", "/releases/v1", "releases/../v1", "releases/./v1",
    "releases//v1", "releases/v1/", "releases/release with spaces",
])
def test_deployment_rejects_invalid_release_prefixes(prefix):
    """Prefixes must contain nonempty safe segments, not dot traversal."""
    assert re.fullmatch(release_prefix_pattern(), prefix) is None


@pytest.fixture
def helper_workspace(tmp_path):
    """Copy helpers into a temporary repo with a logging-only Docker stub."""
    repo = tmp_path / "repo"
    scripts = repo / "scripts"
    scripts.mkdir(parents=True)
    for name in ("build_lambda_serving.sh", "prepare_lambda_release.sh"):
        shutil.copyfile(PROJECT_ROOT / "scripts" / name, scripts / name)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "with open(os.environ['DOCKER_CALL_LOG'], 'a') as stream:\n"
        "    stream.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "if sys.argv[1] == 'build' and os.environ.get('FAIL_FAKE_BUILD'):\n"
        "    raise SystemExit(17)\n"
    )
    docker.chmod(0o755)
    log = tmp_path / "docker-calls.jsonl"
    env = dict(os.environ, PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
               DOCKER_CALL_LOG=str(log))
    return repo, env, log


def run_helper(workspace, name, *args):
    """Run a copied shell helper; the fake Docker cannot access AWS or images."""
    repo, env, _ = workspace
    return subprocess.run(
        ["bash", str(repo / "scripts" / name), *args],
        cwd=repo.parent, env=env, capture_output=True, text=True, check=False,
    )


def docker_calls(log):
    """Return only the argument lists recorded by the temporary Docker stub."""
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines()]


def add_fixture_bundle(repo, release_id="fixture-v1.2"):
    """Create synthetic presence-check files, never a real model or dataset."""
    bundle = repo / "models/issue33" / release_id / "bundle"
    bundle.mkdir(parents=True)
    (bundle / "requirements-model.txt").write_text("fixture-package==1.0\n")
    (bundle / "manifest.json").write_text("{}\n")
    return bundle


@pytest.mark.parametrize("image_tag", [None, "application-r2"])
def test_build_reuses_bundle_with_optional_separate_tag(helper_workspace, image_tag):
    repo, _, log = helper_workspace
    bundle = add_fixture_bundle(repo)
    args = ["fixture-v1.2"] + ([image_tag] if image_tag else [])
    result = run_helper(helper_workspace, "build_lambda_serving.sh", *args)
    assert result.returncode == 0, result.stderr
    calls = docker_calls(log)
    assert [call[0] for call in calls] == ["info", "build"]
    build = calls[1]
    assert build[build.index("-t") + 1] == f"parksmart-backend:{image_tag or args[0]}"
    assert build[build.index("--platform") + 1] == "linux/amd64"
    assert "--provenance=false" in build
    assert build[-1] == str(repo)
    assert (repo / ".lambda-build/requirements-model.txt").read_bytes() == (
        bundle / "requirements-model.txt").read_bytes()
    assert sorted(path.name for path in bundle.iterdir()) == [
        "manifest.json", "requirements-model.txt"]


def test_missing_bundle_stops_before_docker(helper_workspace):
    _, _, log = helper_workspace
    result = run_helper(helper_workspace, "build_lambda_serving.sh", "missing")
    assert result.returncode != 0
    assert "bundle missing" in result.stderr
    assert docker_calls(log) == []


@pytest.mark.parametrize("image_tag", ["-invalid", "has spaces", "bad/tag", "a" * 129])
def test_invalid_image_tag_stops_before_docker(helper_workspace, image_tag):
    _, _, log = helper_workspace
    result = run_helper(helper_workspace, "build_lambda_serving.sh", "fixture", image_tag)
    assert result.returncode != 0
    assert "Docker image tag" in result.stderr
    assert docker_calls(log) == []


def test_build_failure_does_not_report_success(helper_workspace):
    repo, env, log = helper_workspace
    add_fixture_bundle(repo)
    env["FAIL_FAKE_BUILD"] = "1"
    result = run_helper(helper_workspace, "build_lambda_serving.sh", "fixture-v1.2", "new-tag")
    assert result.returncode == 17
    assert "Built parksmart-backend" not in result.stdout
    assert [call[0] for call in docker_calls(log)] == ["info", "build"]


@pytest.mark.parametrize("name", ["build_lambda_serving.sh", "prepare_lambda_release.sh"])
def test_invalid_release_id_stops_before_docker(helper_workspace, name):
    _, _, log = helper_workspace
    result = run_helper(helper_workspace, name, "../escape")
    assert result.returncode != 0
    assert docker_calls(log) == []


def test_missing_dataset_does_not_start_preparation(helper_workspace):
    _, _, log = helper_workspace
    result = run_helper(helper_workspace, "prepare_lambda_release.sh", "new-release")
    assert result.returncode != 0
    assert "dataset is missing" in result.stderr
    assert docker_calls(log) == []
