"""Per-request-class rate limiting with optional adaptive load awareness.

Different LUX requests have very different cost profiles:

* fetching a single document is cheap and can be done as fast as the network
  allows;
* a simple search hits a search index and is mildly expensive;
* a relationship search walks the graph and is much more expensive.

This module provides a small token-bucket-style limiter (really: a minimum
sleep between consecutive requests of a given category) plus an optional
"load endpoint" hook. If LUX exposes a `/load` (or similar) endpoint that
reports how busy it is, luxy will multiply its base interval by the
reported load factor before sleeping.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger(__name__)


REQUEST_DOCUMENT = "document"
REQUEST_SIMPLE = "simple"
REQUEST_RELATIONSHIP = "relationship"

DEFAULT_INTERVALS = {
    REQUEST_DOCUMENT: 0.0,
    REQUEST_SIMPLE: 1.0,
    REQUEST_RELATIONSHIP: 3.0,
}


@dataclass
class RateLimiter:
    """Thread-safe minimum-interval rate limiter, keyed by request category.

    Parameters
    ----------
    intervals:
        Mapping of request category to the minimum number of seconds that
        must elapse between two consecutive calls of that category.
    load_callback:
        Optional callable returning a non-negative float load factor. When
        set, `acquire()` multiplies the configured interval by this factor.
        A factor of ``1.0`` is a no-op. Anything that raises is treated as
        ``1.0``.
    """

    intervals: dict = field(default_factory=lambda: dict(DEFAULT_INTERVALS))
    load_callback: Optional[Callable[[], float]] = None
    _last_call: dict = field(default_factory=dict, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def set_interval(self, category: str, seconds: Optional[float]) -> None:
        """Set/clear the minimum interval for a request category.

        Pass ``seconds=None`` or ``0`` to remove the limit (used for
        documents by default).
        """
        with self._lock:
            self.intervals[category] = float(seconds) if seconds else 0.0

    def _current_load(self) -> float:
        if not self.load_callback:
            return 1.0
        try:
            value = float(self.load_callback())
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("load_callback raised %s; ignoring", exc)
            return 1.0
        return max(value, 0.0) or 1.0

    def acquire(self, category: str = REQUEST_SIMPLE) -> float:
        """Block until the next call of ``category`` is allowed.

        Returns the number of seconds actually slept (0 if no wait needed).
        Unknown categories are treated as :data:`REQUEST_SIMPLE`.
        """
        base = self.intervals.get(category, self.intervals.get(REQUEST_SIMPLE, 0.0))
        if base <= 0:
            with self._lock:
                self._last_call[category] = time.monotonic()
            return 0.0

        interval = base * self._current_load()
        slept = 0.0
        with self._lock:
            now = time.monotonic()
            last = self._last_call.get(category, 0.0)
            wait = (last + interval) - now
            if wait > 0:
                slept = wait
            self._last_call[category] = now + max(slept, 0.0)
        if slept > 0:
            logger.debug("Rate limiter sleeping %.3fs for %s", slept, category)
            time.sleep(slept)
        return slept


def make_load_callback(
    url: str,
    *,
    session=None,
    cache_ttl: float = 5.0,
    timeout: float = 2.0,
) -> Callable[[], float]:
    """Build a load callback that polls ``url`` and caches the result.

    The endpoint is expected to return JSON with a ``load`` (or ``factor``)
    numeric field, e.g. ``{"load": 1.4}``. If the endpoint is missing or
    returns nothing parseable, the callback yields ``1.0`` so the limiter
    falls back to its base interval.
    """
    import requests

    sess = session or requests.Session()
    state = {"value": 1.0, "ts": 0.0}

    def _callback() -> float:
        now = time.monotonic()
        if now - state["ts"] < cache_ttl:
            return state["value"]
        try:
            resp = sess.get(url, timeout=timeout)
            if resp.status_code != 200:
                state["value"] = 1.0
            else:
                payload = resp.json()
                value = payload.get("load", payload.get("factor", 1.0))
                state["value"] = max(float(value), 0.0) or 1.0
        except Exception as exc:  # pragma: no cover - depends on network
            logger.debug("Failed to read load from %s: %s", url, exc)
            state["value"] = 1.0
        state["ts"] = now
        return state["value"]

    return _callback


_default_limiter: Optional[RateLimiter] = None


def get_default_rate_limiter() -> RateLimiter:
    """Return (lazily creating) the process-wide default rate limiter."""
    global _default_limiter
    if _default_limiter is None:
        _default_limiter = RateLimiter()
    return _default_limiter


def set_rate_limits(
    *,
    document: Optional[float] = None,
    simple: Optional[float] = None,
    relationship: Optional[float] = None,
) -> RateLimiter:
    """Tweak the default limiter from a single call.

    ``None`` leaves a category unchanged; ``0`` disables the limit.
    """
    limiter = get_default_rate_limiter()
    if document is not None:
        limiter.set_interval(REQUEST_DOCUMENT, document)
    if simple is not None:
        limiter.set_interval(REQUEST_SIMPLE, simple)
    if relationship is not None:
        limiter.set_interval(REQUEST_RELATIONSHIP, relationship)
    return limiter


__all__ = [
    "DEFAULT_INTERVALS",
    "REQUEST_DOCUMENT",
    "REQUEST_RELATIONSHIP",
    "REQUEST_SIMPLE",
    "RateLimiter",
    "get_default_rate_limiter",
    "make_load_callback",
    "set_rate_limits",
]
