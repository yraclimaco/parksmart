"""Bounded read-only JSON access to the two configured public alert sources."""

import json
import time

import httpx

from .cache import SourceError

SOURCE_BUDGET_SECONDS = 4.0
# UCSD geometry queries can exceed a one-second read on a healthy connection.
# Keep each socket wait bounded within the separate four-second refresh budget.
SOCKET_TIMEOUT_SECONDS = 2.0
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
ALLOWED_HOSTS = {"api.open-meteo.com", "admin-enterprise-gis.ucsd.edu"}


class JSONHTTP:
    """Shared small HTTP pool, with no redirects, retries or credential lookup.

    Args:
        client: Optional httpx.Client for tests. Otherwise creates a client with
            four connections, bounded pool/socket waits and trust_env=False.
    """

    def __init__(self, client=None):
        self.client = client or httpx.Client(
            follow_redirects=False, trust_env=False,
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
            timeout=httpx.Timeout(SOCKET_TIMEOUT_SECONDS, pool=0.1),
            headers={"User-Agent": "ParkSmart-trip-alerts/0.1"},
        )

    def get_json(self, url, params=None, deadline=None):
        """Return bounded decoded JSON from an allowed HTTPS source.

        Args:
            url: Fixed provider URL, never supplied by an HTTP request body.
            params: Scalar public query parameters.
            deadline: Optional shared monotonic deadline across paginated calls.
        Raises:
            SourceError: timeout, transport/status/JSON failure or oversized body.
        """
        address = httpx.URL(url)
        if address.scheme != "https" or address.host not in ALLOWED_HOSTS:
            raise SourceError("Alert source URL is not allowed.")
        deadline = deadline or time.monotonic() + SOURCE_BUDGET_SECONDS
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise SourceError("Alert source request budget expired.")
        timeout = httpx.Timeout(min(SOCKET_TIMEOUT_SECONDS, remaining), pool=0.1)
        try:
            with self.client.stream("GET", url, params=params, timeout=timeout) as response:
                response.raise_for_status()
                content = bytearray()
                for chunk in response.iter_bytes():
                    if time.monotonic() >= deadline:
                        raise SourceError("Alert source request budget expired.")
                    content.extend(chunk)
                    if len(content) > MAX_RESPONSE_BYTES:
                        raise SourceError("Alert source response is too large.")
            return json.loads(content)
        except (httpx.HTTPError, ValueError, UnicodeError) as error:
            raise SourceError("Alert source response is unavailable.") from error

    def close(self):
        """Close the shared pool on application shutdown; return None."""
        self.client.close()
