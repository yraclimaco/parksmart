"""Exercise the local smoke checker without network requests or private files."""

import io
import json

import pytest

from scripts import check_lambda_local as checker


def test_invoke_encodes_lambda_event_and_uses_only_loopback(monkeypatch):
    """The opener receives a loopback URL and a valid HTTP API v2 event."""
    seen = []

    class StubOpener:
        def open(self, request, timeout):
            seen.append((request, timeout))
            return io.BytesIO(json.dumps({
                "statusCode": 200, "body": json.dumps({"status": "fixture"}),
            }).encode())

    def build_opener(proxy_handler):
        assert proxy_handler.proxies == {}
        return StubOpener()

    monkeypatch.setattr(checker, "build_opener", build_opener)
    assert checker.invoke("POST", "/recommendations", {"fixture": True}) == {
        "status": "fixture"}
    request, timeout = seen[0]
    assert request.full_url == checker.INVOCATION_URL
    assert request.full_url.startswith("http://127.0.0.1:9000/")
    assert timeout > 0
    event = json.loads(request.data)
    assert event["version"] == "2.0"
    assert event["rawPath"] == "/recommendations"
    assert event["requestContext"]["http"]["method"] == "POST"
    assert json.loads(event["body"]) == {"fixture": True}


@pytest.mark.parametrize("envelope", [
    {"statusCode": 503, "body": "fixture-private-diagnostics"}, {},
])
def test_invoke_rejects_failed_envelopes_without_exposing_body(monkeypatch, envelope):
    """A failed Lambda envelope cannot be mistaken for a successful check."""
    class StubOpener:
        def open(self, request, timeout):
            return io.BytesIO(json.dumps(envelope).encode())

    monkeypatch.setattr(checker, "build_opener", lambda *_: StubOpener())
    with pytest.raises(RuntimeError) as error:
        checker.invoke("GET", "/readiness")
    assert "fixture-private-diagnostics" not in str(error.value)


def fixture_result():
    """Return a clearly synthetic response for checker branching tests."""
    return {
        "status": "ready", "is_example": False,
        "first_choice": {"location": {"location_id": "fixture-first"}},
        "backup_choice": {"location": {"location_id": "fixture-backup"}},
    }


@pytest.mark.parametrize("failure", [
    "not_ready", "baseline", "example", "duplicate", "no_backup", "unavailable",
])
def test_main_rejects_invalid_smoke_results(monkeypatch, capsys, failure):
    """Unavailable, sample and invalid choices must not produce success output."""
    ready = {"status": "ready", "prediction_mode": "saved"}
    result = fixture_result()
    if failure == "not_ready":
        ready["status"] = "unavailable"
    elif failure == "baseline":
        ready["prediction_mode"] = "baseline"
    elif failure == "example":
        result["is_example"] = True
    elif failure == "duplicate":
        result["backup_choice"] = result["first_choice"]
    elif failure == "no_backup":
        result["backup_choice"] = None
    elif failure == "unavailable":
        result["status"] = "predictions_unavailable"
    monkeypatch.setattr(checker, "invoke", lambda method, *_: ready if method == "GET" else result)
    with pytest.raises(RuntimeError):
        checker.main()
    assert capsys.readouterr().out == ""


def test_main_checks_two_recommendations_and_prints_summary(monkeypatch, capsys):
    """The happy path checks readiness and two distinct-choice responses."""
    calls = []

    def invoke(method, path, payload=None):
        calls.append((method, path))
        if method == "GET":
            return {"status": "ready", "prediction_mode": "saved"}
        return fixture_result()

    monkeypatch.setattr(checker, "invoke", invoke)
    checker.main()
    summary = json.loads(capsys.readouterr().out)
    assert calls == [
        ("GET", "/readiness"),
        ("POST", "/recommendations"),
        ("POST", "/recommendations"),
    ]
    assert summary["recommendation_requests"] == 2
    assert summary["choices"] == [["fixture-first", "fixture-backup"]] * 2
