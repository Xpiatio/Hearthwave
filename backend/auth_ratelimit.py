"""IP-based sliding-window rate limiter for auth endpoints.

No external dependencies — uses only stdlib time and collections.

Usage:
    limiter = LoginRateLimiter()
    allowed, retry_after = limiter.check(ip)
    if not allowed:
        raise HTTPException(429, headers={"Retry-After": str(retry_after)})
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Mapping

from fastapi import Request

_WINDOW_SECONDS = 300   # 5-minute sliding window
_MAX_ATTEMPTS   = 10    # attempts allowed per window per IP
_MAX_TRACKED_IPS = 10_000  # evict oldest IPs beyond this to bound memory


class LoginRateLimiter:
    def __init__(self, max_attempts: int = _MAX_ATTEMPTS, window_seconds: int = _WINDOW_SECONDS) -> None:
        self._max    = max_attempts
        self._window = window_seconds
        # Maps IP → list of monotonic timestamps within the current window
        self._hits: dict[str, list[float]] = defaultdict(list)

    def reset(self) -> None:
        """Clear all tracked attempts (e.g. on server startup / test teardown)."""
        self._hits.clear()

    def check(self, ip: str) -> tuple[bool, int]:
        """Record an attempt from *ip*.

        Returns (True, 0) if allowed, or (False, retry_after_seconds) if the
        window is exhausted.  The attempt is NOT recorded when blocked so that
        a flooded IP doesn't keep pushing out its own window.
        """
        now    = time.monotonic()
        cutoff = now - self._window
        hits   = [t for t in self._hits[ip] if t > cutoff]
        self._hits[ip] = hits

        if len(hits) >= self._max:
            # Time until the oldest recorded hit falls outside the window.
            retry_after = int(min(hits) + self._window - now) + 1
            return False, retry_after

        hits.append(now)
        self._hits[ip] = hits

        # Evict oldest entries if the table grows too large (e.g. scanner flood).
        if len(self._hits) > _MAX_TRACKED_IPS:
            oldest_ip = min(self._hits, key=lambda k: min(self._hits[k], default=0))
            del self._hits[oldest_ip]

        return True, 0


def _extract_ip(headers: Mapping[str, str], client_host: str = "unknown") -> str:
    """Extract real client IP from proxy headers, with fallback to direct host."""
    real_ip = headers.get("x-real-ip")
    if real_ip:
        return real_ip
    forwarded_for = headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return client_host


def get_client_ip(request: Request) -> str:
    """Return the real client IP from a FastAPI Request, honouring nginx headers."""
    client_host = request.client.host if request.client else "unknown"
    return _extract_ip(request.headers, client_host)
