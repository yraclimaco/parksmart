"""Bounded per-process source caches with single-flight refresh and backoff."""

import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Optional

MAX_CACHE_ENTRIES = 64
FAILURE_RETRY_SECONDS = 30


class SourceError(Exception):
    """An external source failed or returned an unusable response."""


@dataclass(frozen=True)
class CachedPayload:
    """Cached source data and provenance; state is fresh, stale or unavailable.

    data is None when no usable snapshot exists. last_checked_at always retains
    the successful snapshot time; failed attempts never refresh that timestamp.
    """

    data: Any
    state: str
    last_checked_at: Optional[datetime]
    last_attempt_at: Optional[datetime]
    error: Optional[str] = None


@dataclass
class _Entry:
    data: Any = None
    checked: Optional[datetime] = None
    attempted: Optional[datetime] = None
    stored_at: float = float("-inf")
    retry_after: float = 0
    error: Optional[str] = None


class CachedJSON:
    """Keep at most max_entries source responses, with injectable test clocks.

    Args:
        max_entries: Positive LRU capacity; in-flight work is bounded likewise.
        monotonic: Duration clock, independent of wall-clock corrections.
        utcnow: Aware UTC clock for user-facing provenance only.
    """

    def __init__(self, max_entries=MAX_CACHE_ENTRIES, monotonic=time.monotonic,
                 utcnow=None):
        if max_entries < 1:
            raise ValueError("Cache capacity must be positive")
        self.max_entries = max_entries
        self.monotonic = monotonic
        self.utcnow = utcnow or (lambda: datetime.now(timezone.utc))
        self._entries = OrderedDict()
        self._inflight = set()
        self._lock = Lock()

    def _snapshot(self, entry, max_age, error=None):
        """Return a stale snapshot if within max_age, otherwise no source data."""
        usable = (entry.data is not None
                  and self.monotonic() - entry.stored_at < max_age)
        return CachedPayload(
            entry.data if usable else None,
            "stale" if usable else "unavailable",
            entry.checked, entry.attempted, error or entry.error,
        )

    def get(self, key, loader, ttl_seconds, max_stale_seconds):
        """Return cached/fetched JSON without waiting on another in-flight refresh.

        Args:
            key: Hashable source/coordinate key; arrival times need not be keys.
            loader: Zero-argument bounded loader, raising SourceError on failure.
            ttl_seconds: Fresh duration from successful retrieval, in seconds.
            max_stale_seconds: Maximum total snapshot age that may be served.
        Returns:
            CachedPayload. Failure retries back off for 30 seconds; stale values
            retain their original retrieval time and are always marked stale.
        """
        if ttl_seconds <= 0 or max_stale_seconds < ttl_seconds:
            raise ValueError("Cache ages must be positive and stale age >= TTL")
        with self._lock:
            entry = self._entries.setdefault(key, _Entry())
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)
            now = self.monotonic()
            if entry.data is not None and now - entry.stored_at < ttl_seconds:
                return CachedPayload(entry.data, "fresh", entry.checked,
                                     entry.attempted)
            if key in self._inflight:
                return self._snapshot(entry, max_stale_seconds,
                                      "Source refresh is in progress.")
            if now < entry.retry_after:
                return self._snapshot(entry, max_stale_seconds)
            if len(self._inflight) >= self.max_entries:
                return self._snapshot(entry, max_stale_seconds,
                                      "Source refresh capacity is busy.")
            self._inflight.add(key)
            entry.attempted = self.utcnow()
        try:
            data = loader()
            if data is None:
                raise SourceError("Source returned no JSON data.")
        except SourceError:
            with self._lock:
                entry.error = "Source refresh failed; no new data was retrieved."
                entry.retry_after = self.monotonic() + FAILURE_RETRY_SECONDS
                return self._snapshot(entry, max_stale_seconds)
        else:
            with self._lock:
                entry.data, entry.checked = data, self.utcnow()
                entry.stored_at = self.monotonic()
                entry.error = None
                entry.retry_after = 0
                # A concurrent LRU eviction cannot publish a mixed entry.
                self._entries[key] = entry
                self._entries.move_to_end(key)
                while len(self._entries) > self.max_entries:
                    self._entries.popitem(last=False)
                return CachedPayload(data, "fresh", entry.checked, entry.attempted)
        finally:
            with self._lock:
                self._inflight.discard(key)
