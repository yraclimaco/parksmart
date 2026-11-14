"""Isolate two optional data providers from parking and prediction resources."""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import asdict
from threading import BoundedSemaphore

from .cache import CachedJSON
from .contracts import ProviderResult
from .http import JSONHTTP, SOURCE_BUDGET_SECONDS, SOCKET_TIMEOUT_SECONDS

LOGGER = logging.getLogger(__name__)
SOURCE_WORKERS = 2
# Includes the largest possible in-progress socket wait beyond the read deadline.
ALERT_REQUEST_BUDGET_SECONDS = SOURCE_BUDGET_SECONDS + SOCKET_TIMEOUT_SECONDS + 0.5
SOURCE_LABELS = {
    "weather": ("Open-Meteo", "https://open-meteo.com/"),
    "construction": (
        "UCSD published construction notices",
        "https://admin-enterprise-gis.ucsd.edu/server/rest/services/"
        "Construction/Construction_Alert_Approved/MapServer",
    ),
}
COMMON_LIMITATIONS = [
    "Trip alerts are informational and do not change parking availability or ranking.",
    "Construction notices do not establish whole-lot closure or route avoidance.",
]


def unavailable_source(name, message):
    """Return an attributed unavailable result without inventing retrieval times."""
    title, url = SOURCE_LABELS[name]
    return ProviderResult("unavailable", title, url, limitations=[message])


class TripAlertService:
    """Once-created providers, cache, pool and independent bounded source work.

    Args:
        weather: Optional injectable provider with get(arrival, targets).
        construction: Optional injectable provider using the same interface.
        enabled: False disables all external calls with explicit source states.
    """

    def __init__(self, weather=None, construction=None, enabled=True):
        from .construction import ConstructionProvider
        from .weather import WeatherProvider

        self.http = JSONHTTP()
        cache = CachedJSON()
        self.providers = {
            "weather": weather or WeatherProvider(self.http, cache),
            "construction": construction or ConstructionProvider(self.http, cache),
        }
        self.enabled = enabled
        self._pool = ThreadPoolExecutor(max_workers=SOURCE_WORKERS,
                                        thread_name_prefix="trip-alert")
        self._slots = BoundedSemaphore(SOURCE_WORKERS)

    def _get_source(self, name, arrival, targets):
        """Contain provider failures; never turn them into successful empty data."""
        try:
            result = self.providers[name].get(arrival, targets)
            if not isinstance(result, ProviderResult):
                raise TypeError("Alert provider returned an invalid result type")
            return result
        except Exception:
            LOGGER.exception("Trip alert source %s failed", name)
            return unavailable_source(name, "Source information is unavailable.")

    def get(self, arrival, targets):
        """Return weather/construction dictionaries for aware arrival and points.

        At most two source jobs exist per process; saturation returns unavailable
        immediately rather than queuing unbounded jobs. Both providers share a
        response deadline and remain independent of recommendation handlers.
        """
        deadline = time.monotonic() + ALERT_REQUEST_BUDGET_SECONDS
        futures, results = {}, {}
        for name in self.providers:
            if not self.enabled:
                results[name] = unavailable_source(name, "Trip alerts are disabled.")
            elif not self._slots.acquire(blocking=False):
                results[name] = unavailable_source(
                    name, "Source refresh capacity is busy; retry shortly.")
            else:
                try:
                    future = self._pool.submit(self._get_source, name, arrival, targets)
                except RuntimeError:
                    self._slots.release()
                    results[name] = unavailable_source(name, "Trip alerts are stopping.")
                else:
                    future.add_done_callback(lambda _: self._slots.release())
                    futures[name] = future
        for name, future in futures.items():
            try:
                results[name] = future.result(timeout=max(0, deadline - time.monotonic()))
            except TimeoutError:
                results[name] = unavailable_source(
                    name, "Source response budget expired; information is unavailable.")
        return {name: asdict(result) for name, result in results.items()}

    def close(self):
        """Stop accepting source jobs and close sockets on backend shutdown."""
        self._pool.shutdown(wait=False, cancel_futures=True)
        self.http.close()
