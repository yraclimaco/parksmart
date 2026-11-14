"""Offline smoke checks distinguish API health, predictions and source status."""

import json
from datetime import datetime, timezone

import httpx
import pytest

from scripts.check_trip_alerts import (
    MAX_RESPONSE_BYTES, check_backend, main, normalize_base_url, parse_arrival,
)

ARRIVAL = datetime(2026, 11, 18, 18, tzinfo=timezone.utc)


def source(status):
    """Return an attributed synthetic source result in the shared DTO shape."""
    return {"status": status, "source_name": "Fixture", "source_url":
            "https://example.test/source", "last_checked_at":
            "2026-11-18T17:30:00Z" if status != "unavailable" else None,
            "last_attempt_at": "2026-11-18T17:30:00Z", "alerts": [],
            "forecast": None, "limitations": ["Synthetic fixture"]}


def transport(weather="available", construction="no_relevant", readiness=200,
              alter=None):
    """Return a mocked client and call list; no actual server/provider is used."""
    calls = []

    def handle(request):
        calls.append(request)
        path = request.url.path
        if path.endswith("/health"):
            body, status = {"status": "ok"}, 200
        elif path.endswith("/readiness"):
            body, status = {"status": "ready" if readiness == 200 else "unavailable",
                            "catalog_ready": True,
                            "predictions_ready": readiness == 200,
                            "prediction_mode": "saved"}, readiness
        else:
            assert path.endswith("/trip-alerts")
            assert request.method == "POST"
            payload = json.loads(request.content)
            assert payload["parking_location_id"] == "gilman-ps"
            body, status = {
                "schema_version": "0.1", "is_example": False,
                "arrival_time": payload["arrival_time"],
                "time_zone": "America/Los_Angeles", "weather": source(weather),
                "construction": source(construction), "limitations": []}, 200
        if alter is not None:
            return alter(request, body, status)
        return httpx.Response(status, json=body)

    return httpx.Client(transport=httpx.MockTransport(handle)), calls


def test_smoke_preserves_prefix_and_separates_live_and_cloud_claims():
    client, calls = transport()
    with client:
        result = check_backend("https://backend.example.test/prod/", ARRIVAL,
                               client=client)
    assert [request.url.path for request in calls] == [
        "/prod/health", "/prod/readiness", "/prod/trip-alerts"]
    assert result["api_contract_passed"]
    assert result["backend_predictions_ready"]
    assert result["both_sources_report_fresh"]
    assert result["aws_hosting_verified"] is False
    assert result["live_upstream_refresh_verified"] is False
    assert all(request.extensions["timeout"]["connect"] <= 1 for request in calls)
    assert all(request.extensions["timeout"]["read"] <= 8 for request in calls)


def test_source_failures_and_readiness_503_are_valid_but_not_ready():
    client, _ = transport("unavailable", "stale", readiness=503)
    with client:
        result = check_backend("http://127.0.0.1:8000", ARRIVAL, client=client)
    assert result["api_contract_passed"]
    assert result["backend_predictions_ready"] is False
    assert result["both_sources_report_fresh"] is False
    assert result["sources"]["weather"]["last_checked_at"] is None
    assert result["sources"]["construction"]["status"] == "stale"


def test_partial_source_only_reports_freshness_not_completeness():
    client, _ = transport("partial", "no_relevant")
    with client:
        result = check_backend("http://localhost:8000", ARRIVAL, client=client)
    assert result["both_sources_report_fresh"] is True
    assert result["sources"]["weather"]["forecast_present"] is False
    assert "complete" not in " ".join(result.keys())
    assert result["live_upstream_refresh_verified"] is False


@pytest.mark.parametrize("problem", ["redirect", "schema", "example", "arrival"])
def test_failed_contract_is_not_reported_as_success(problem):
    def alter(request, body, status):
        if request.url.path.endswith("/trip-alerts"):
            if problem == "redirect":
                return httpx.Response(302, headers={"Location":
                                      "https://unrequested.example.test/"})
            if problem == "schema":
                body["weather"]["status"] = "invented"
            elif problem == "example":
                body["is_example"] = True
            elif problem == "arrival":
                body["arrival_time"] = "2026-11-19T10:00:00-08:00"
        return httpx.Response(status, json=body)

    client, calls = transport(alter=alter)
    with client:
        result = check_backend("https://backend.example.test", ARRIVAL, client=client)
    assert result["api_contract_passed"] is False
    assert len(calls) == 3
    assert all(call.url.host == "backend.example.test" for call in calls)


def test_timeout_is_reported_without_exposing_provider_or_request_content():
    def fail(request):
        raise httpx.ReadTimeout("sensitive details must not be printed", request=request)

    with httpx.Client(transport=httpx.MockTransport(fail)) as client:
        result = check_backend("https://backend.example.test", ARRIVAL, client=client)
    assert result["api_contract_passed"] is False
    assert result["checks"]["health"]["error"] == "ReadTimeout"
    assert "sensitive details" not in json.dumps(result)


def test_missing_success_timestamp_cannot_claim_source_reports_fresh():
    def alter(request, body, status):
        if request.url.path.endswith("/trip-alerts"):
            body["weather"]["last_checked_at"] = None
        return httpx.Response(status, json=body)

    client, _ = transport(alter=alter)
    with client:
        result = check_backend("https://backend.example.test", ARRIVAL, client=client)
    assert result["api_contract_passed"]
    assert result["sources"]["weather"]["source_reports_fresh"] is False
    assert result["both_sources_report_fresh"] is False


def test_inconsistent_readiness_status_is_not_a_passed_contract():
    def alter(request, body, status):
        if request.url.path.endswith("/readiness"):
            body["status"] = "unavailable"
        return httpx.Response(status, json=body)

    client, _ = transport(alter=alter)
    with client:
        result = check_backend("https://backend.example.test", ARRIVAL, client=client)
    assert result["api_contract_passed"] is False
    assert result["backend_predictions_ready"] is False


def test_large_response_is_rejected_without_printing_its_body():
    def alter(request, body, status):
        if request.url.path.endswith("/health"):
            return httpx.Response(200, content=b"x" * (MAX_RESPONSE_BYTES + 1))
        return httpx.Response(status, json=body)

    client, _ = transport(alter=alter)
    with client:
        result = check_backend("https://backend.example.test", ARRIVAL, client=client)
    assert result["api_contract_passed"] is False
    assert result["checks"]["health"]["error"] == "response_too_large"


@pytest.mark.parametrize("url", [
    "http://backend.example.test", "https://user:secret@example.test",
    "https://example.test/?token=secret", "https://example.test/#secret",
    "file:///tmp/backend", "not a URL",
])
def test_invalid_or_credential_bearing_target_is_rejected(url):
    with pytest.raises(ValueError, match="without credentials"):
        normalize_base_url(url)


@pytest.mark.parametrize("url", ["http://localhost:8000/", "http://[::1]:8000/",
                                 "https://backend.example.test/api/"])
def test_explicit_safe_target_forms(url):
    assert normalize_base_url(url) == url.rstrip("/")


def test_arrival_requires_offset_and_default_is_future_utc():
    assert parse_arrival("2026-11-18T10:00:00-08:00") == ARRIVAL
    before = datetime.now(timezone.utc)
    default = parse_arrival()
    assert 3590 < (default - before).total_seconds() < 3610
    with pytest.raises(ValueError, match="explicit UTC offset"):
        parse_arrival("2026-11-18T10:00:00")


def test_cli_rejects_unsafe_target_without_logging_credentials(capsys):
    assert main(["--base-url", "https://user:secret@example.test"]) == 1
    assert "secret" not in capsys.readouterr().out


def test_smoke_rejects_other_dst_fold_with_same_local_clock():
    def wrong_fold(request, body, status):
        if request.url.path.endswith("/trip-alerts"):
            body["arrival_time"] = "2026-11-01T01:30:00-08:00"
        return httpx.Response(status, json=body)

    client, _ = transport(alter=wrong_fold)
    with client:
        result = check_backend(
            "http://localhost:8000", parse_arrival("2026-11-01T01:30:00-07:00"),
            client=client)
    assert result["checks"]["trip_alerts"]["schema_valid"]
    assert result["api_contract_passed"] is False


def test_cli_exit_zero_means_contract_pass_even_when_sources_fail(monkeypatch, capsys):
    client, _ = transport("unavailable", "unavailable", readiness=503)

    def use_mocked_transport(**kwargs):
        assert kwargs == {"follow_redirects": False, "trust_env": False}
        return client

    monkeypatch.setattr("scripts.check_trip_alerts.httpx.Client", use_mocked_transport)
    assert main(["--base-url", "http://localhost:8000",
                 "--arrival", "2026-11-18T10:00:00-08:00"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["api_contract_passed"]
    assert result["both_sources_report_fresh"] is False
    assert result["backend_predictions_ready"] is False
    assert result["aws_hosting_verified"] is False
