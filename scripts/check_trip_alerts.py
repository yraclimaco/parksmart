"""Opt-in HTTP smoke check for a supplied ParkSmart backend; no deployment.

Only the known health, readiness and trip-alert paths are requested. A valid
response may explicitly report unavailable upstream sources; this check never
equates API reachability with a successful live provider refresh or AWS hosting.
"""

import argparse
import ipaddress
import json
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import httpx

from src.api.alert_schemas import TripAlertsRequest, TripAlertsResponse
from src.api.schemas import HealthResponse, ReadinessResponse

CONNECT_SECONDS = 1.0
READ_SECONDS = 8.0
REQUEST_SECONDS = 9.0
CHECK_SECONDS = 30.0
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
DEFAULT_PARKING_ID = "gilman-ps"
FRESH_STATUSES = {"available", "no_relevant", "partial"}


def normalize_base_url(value):
    """Validate an explicit backend base URL and return its normalized spelling.

    HTTPS is required except for HTTP loopback hosts. Optional deployment path
    prefixes are retained; credentials, query strings and fragments are rejected.
    Invalid input raises ValueError without echoing potentially secret text.
    """
    try:
        parts = urlsplit(value)
        address = httpx.URL(value)
        host = address.host
        loopback = host == "localhost"
        if not loopback:
            try:
                loopback = ipaddress.ip_address(host).is_loopback
            except ValueError:
                pass
        if (not host or parts.username is not None or parts.password is not None
                or "?" in value or "#" in value
                or address.scheme not in {"http", "https"}
                or (address.scheme == "http" and not loopback)):
            raise ValueError
        # Force validation of malformed ports before making any request.
        _ = address.port
    except (ValueError, httpx.InvalidURL) as error:
        raise ValueError("Use an HTTPS backend URL, or HTTP loopback URL, "
                         "without credentials, query or fragment") from error
    return str(address).rstrip("/")


def parse_arrival(value=None):
    """Return an aware trip arrival; default to one hour after current UTC time.

    Explicit input must be an ISO datetime with T and a UTC offset. The shared
    request schema converts it to America/Los_Angeles for matching.
    """
    if value is None:
        return datetime.now(timezone.utc) + timedelta(hours=1)
    try:
        if "T" not in value:
            raise ValueError
        arrival = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if arrival.tzinfo is None or arrival.utcoffset() is None:
            raise ValueError
        return arrival
    except ValueError as error:
        raise ValueError("arrival must be an ISO datetime with an explicit "
                         "UTC offset, for example 2026-11-18T10:00:00-08:00") from error


def _check_endpoint(client, base, path, model, root_deadline, payload=None):
    """Return a bounded endpoint check and a validated response or None."""
    check = {"reachable": False, "http_status": None, "schema_valid": False}
    deadline = min(root_deadline, time.monotonic() + REQUEST_SECONDS)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        check["error"] = "check_deadline_exceeded"
        return check, None
    timeout = httpx.Timeout(
        min(READ_SECONDS, remaining), connect=min(CONNECT_SECONDS, remaining),
        write=min(CONNECT_SECONDS, remaining), pool=min(CONNECT_SECONDS, remaining),
    )
    try:
        method = "POST" if payload is not None else "GET"
        with client.stream(method, base + path, json=payload,
                           timeout=timeout, follow_redirects=False) as response:
            check.update(reachable=True, http_status=response.status_code)
            allowed = {200, 503} if path == "/readiness" else {200}
            if response.status_code not in allowed:
                check["error"] = "unexpected_http_status"
                return check, None
            content = bytearray()
            for chunk in response.iter_bytes():
                if time.monotonic() >= deadline:
                    check["error"] = "check_deadline_exceeded"
                    return check, None
                content.extend(chunk)
                if len(content) > MAX_RESPONSE_BYTES:
                    check["error"] = "response_too_large"
                    return check, None
        parsed = model.model_validate(json.loads(content))
        check["schema_valid"] = True
        return check, parsed
    except httpx.HTTPError as error:
        check["error"] = type(error).__name__
    except (ValueError, UnicodeError):
        check["error"] = "invalid_response_schema_or_json"
    return check, None


def _source_summary(source):
    """Return source state/provenance without claiming a new upstream refresh."""
    checked = source.last_checked_at
    has_aware_check = checked is not None and checked.utcoffset() is not None
    return {
        "status": source.status,
        "source_reports_fresh": (
            source.status in FRESH_STATUSES and has_aware_check),
        "last_checked_at": checked.isoformat() if checked else None,
        "last_attempt_at": (source.last_attempt_at.isoformat()
                            if source.last_attempt_at else None),
        "alert_count": len(source.alerts),
        "forecast_present": source.forecast is not None,
    }


def check_backend(base_url, arrival=None, parking_location_id=DEFAULT_PARKING_ID,
                  client=None):
    """Check three fixed paths and return independent API/source result flags.

    Args:
        base_url: Explicit HTTPS or HTTP-loopback backend URL, optionally prefixed.
        arrival: Optional aware datetime; defaults to current UTC plus one hour.
        parking_location_id: Selected stable registry ID, default gilman-ps.
        client: Optional httpx.Client with a mocked transport for offline tests.
    Returns:
        JSON-compatible summary. api_contract_passed permits valid readiness 503
        and unavailable sources; backend_predictions_ready is reported separately.
        No credentials, resources or cloud verification are configured here.
    """
    base = normalize_base_url(base_url)
    arrival = arrival if arrival is not None else parse_arrival()
    if arrival.tzinfo is None or arrival.utcoffset() is None:
        raise ValueError("arrival must include an explicit UTC offset")
    request = TripAlertsRequest(arrival_time=arrival,
                                parking_location_id=parking_location_id)
    owned = client is None
    client = client or httpx.Client(follow_redirects=False, trust_env=False)
    deadline = time.monotonic() + CHECK_SECONDS
    try:
        health, _ = _check_endpoint(client, base, "/health", HealthResponse, deadline)
        readiness, ready = _check_endpoint(
            client, base, "/readiness", ReadinessResponse, deadline)
        alerts, response = _check_endpoint(
            client, base, "/trip-alerts", TripAlertsResponse, deadline,
            payload=request.model_dump(mode="json"))
    finally:
        if owned:
            client.close()
    ready_consistent = ready is not None and (
        (readiness["http_status"] == 200 and ready.status == "ready"
         and ready.catalog_ready and ready.predictions_ready)
        or (readiness["http_status"] == 503 and ready.status == "unavailable"
            and not (ready.catalog_ready and ready.predictions_ready)))
    alerts_consistent = response is not None and (
        not response.is_example
        and response.arrival_time.astimezone(timezone.utc)
        == request.arrival_time.astimezone(timezone.utc))
    sources = ({name: _source_summary(getattr(response, name))
                for name in ("weather", "construction")} if response else {})
    return {
        "base_url": base,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "arrival_time": request.arrival_time.isoformat(),
        "parking_location_id": request.parking_location_id,
        "checks": {"health": health, "readiness": readiness, "trip_alerts": alerts},
        "api_contract_passed": bool(
            health["schema_valid"] and ready_consistent and alerts_consistent),
        "backend_predictions_ready": bool(
            ready_consistent and readiness["http_status"] == 200),
        "sources": sources,
        "both_sources_report_fresh": bool(sources) and all(
            source["source_reports_fresh"] for source in sources.values()),
        "live_upstream_refresh_verified": False,
        "aws_hosting_verified": False,
        "limitations": [
            "API checks do not prove that this backend is hosted on AWS.",
            "Source responses may be cached; a new live refresh is not verified.",
            "Valid source unavailability is separate from a failed API contract.",
        ],
    }


def main(argv=None):
    """Parse an explicit target, print a summary and return the process exit code.

    Exit zero means the HTTP/schema contract passed, independently of upstream
    availability and parking-model readiness. Setup/contract failures return one.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--arrival", help="ISO datetime with an explicit UTC offset")
    parser.add_argument("--parking-location-id", default=DEFAULT_PARKING_ID)
    args = parser.parse_args(argv)
    try:
        summary = check_backend(args.base_url, parse_arrival(args.arrival),
                                args.parking_location_id)
    except ValueError:
        print(json.dumps({"api_contract_passed": False,
                          "error": "Invalid base URL, arrival or parking ID"}))
        return 1
    print(json.dumps(summary, indent=2))
    return 0 if summary["api_contract_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
