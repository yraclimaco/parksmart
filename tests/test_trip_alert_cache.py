"""Freshness, failure provenance, bounded transport and cache concurrency."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event

import httpx
import pytest

from src.trip_alerts.cache import CachedJSON, SourceError
from src.trip_alerts.http import JSONHTTP, MAX_RESPONSE_BYTES


class Clock:
    """Deterministic duration and wall clocks; no sleeping in cache tests."""

    def __init__(self):
        self.elapsed = 0
        self.origin = datetime(2026, 11, 13, tzinfo=timezone.utc)

    def monotonic(self):
        return self.elapsed

    def utcnow(self):
        return self.origin + timedelta(seconds=self.elapsed)


def test_cache_hits_backoff_and_stale_expiry_keep_success_timestamp():
    clock = Clock()
    cache = CachedJSON(monotonic=clock.monotonic, utcnow=clock.utcnow)
    calls = []

    def fetch():
        calls.append(clock.elapsed)
        if len(calls) > 1:
            raise SourceError("offline")
        return {"value": 3}

    fresh = cache.get("weather", fetch, 10, 60)
    clock.elapsed = 5
    assert cache.get("weather", fetch, 10, 60).state == "fresh"
    assert len(calls) == 1
    clock.elapsed = 11
    stale = cache.get("weather", fetch, 10, 60)
    assert stale.state == "stale" and stale.data == {"value": 3}
    assert stale.last_checked_at == fresh.last_checked_at
    assert stale.last_attempt_at == clock.utcnow()
    clock.elapsed = 12
    assert cache.get("weather", fetch, 10, 60).last_attempt_at == stale.last_attempt_at
    assert len(calls) == 2
    clock.elapsed = 61
    expired = cache.get("weather", fetch, 10, 60)
    assert expired.state == "unavailable" and expired.data is None
    assert expired.last_checked_at == fresh.last_checked_at


def test_cold_failures_are_not_cached_as_empty_success():
    cache = CachedJSON()

    def fail():
        raise SourceError("bad JSON")

    result = cache.get("construction", fail, 10, 60)
    assert result.state == "unavailable"
    assert result.data is None and result.last_checked_at is None
    assert result.last_attempt_at is not None


def test_lru_capacity_evicts_oldest_key():
    cache = CachedJSON(max_entries=2)
    calls = []

    def fetch():
        calls.append(1)
        return {"ok": True}

    for key in ("first", "second", "third", "first"):
        cache.get(key, fetch, 10, 60)
    assert len(calls) == 4
    assert len(cache._entries) == 2


def test_refresh_single_flight_returns_busy_without_waiting():
    cache = CachedJSON()
    started, release = Event(), Event()

    def fetch():
        started.set()
        assert release.wait(timeout=3)
        return {"ok": True}

    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(cache.get, "same", fetch, 10, 60)
        assert started.wait(timeout=3)
        try:
            result = cache.get("same", lambda: pytest.fail("duplicate refresh"), 10, 60)
            assert result.state == "unavailable"
            assert "progress" in result.error
        finally:
            release.set()
        assert pending.result(timeout=3).state == "fresh"


@pytest.mark.parametrize("response", [
    httpx.Response(500), httpx.Response(302, headers={"location": "https://evil.test"}),
    httpx.Response(200, text="not json"),
    httpx.Response(200, content=b"x" * (MAX_RESPONSE_BYTES + 1)),
])
def test_transport_rejects_status_redirect_malformed_and_oversized(response):
    client = httpx.Client(transport=httpx.MockTransport(lambda request: response))
    transport = JSONHTTP(client)
    with pytest.raises(SourceError):
        transport.get_json("https://api.open-meteo.com/v1/forecast")
    transport.close()


def test_transport_json_success_and_fixed_source_allowlist():
    calls = []

    def serve(request):
        calls.append(request)
        return httpx.Response(200, json={"hourly": {}})

    transport = JSONHTTP(httpx.Client(transport=httpx.MockTransport(serve)))
    assert transport.get_json("https://api.open-meteo.com/v1/forecast") == {"hourly": {}}
    for url in ("http://api.open-meteo.com", "https://localhost/", "https://evil.test/"):
        with pytest.raises(SourceError):
            transport.get_json(url)
    assert len(calls) == 1
    transport.close()


def test_transport_timeout_is_a_source_failure():
    def timeout(request):
        raise httpx.ReadTimeout("bounded", request=request)

    transport = JSONHTTP(httpx.Client(transport=httpx.MockTransport(timeout)))
    with pytest.raises(SourceError):
        transport.get_json("https://api.open-meteo.com/v1/forecast")
    transport.close()
