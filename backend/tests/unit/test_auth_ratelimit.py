"""Unit tests for backend.auth_ratelimit."""
from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from backend.auth_ratelimit import LoginRateLimiter, _extract_ip, get_client_ip


# ---------------------------------------------------------------------------
# LoginRateLimiter
# ---------------------------------------------------------------------------

class TestLoginRateLimiter:
    def test_allows_up_to_max_attempts(self):
        rl = LoginRateLimiter(max_attempts=3, window_seconds=60)
        for _ in range(3):
            allowed, retry = rl.check("1.2.3.4")
            assert allowed is True
            assert retry == 0

    def test_blocks_on_max_plus_one(self):
        rl = LoginRateLimiter(max_attempts=3, window_seconds=60)
        for _ in range(3):
            rl.check("1.2.3.4")
        allowed, retry = rl.check("1.2.3.4")
        assert allowed is False
        assert retry > 0

    def test_retry_after_is_bounded(self):
        rl = LoginRateLimiter(max_attempts=1, window_seconds=60)
        rl.check("1.2.3.4")
        _, retry = rl.check("1.2.3.4")
        assert 0 < retry <= 61

    def test_blocked_attempt_not_recorded(self):
        """Blocked attempts must not push out the window (no self-extending ban)."""
        rl = LoginRateLimiter(max_attempts=2, window_seconds=60)
        rl.check("1.2.3.4")
        rl.check("1.2.3.4")
        # Now blocked — call many times
        for _ in range(10):
            rl.check("1.2.3.4")
        # Remaining hit count should still be 2 (the originals), not 12
        assert len(rl._hits["1.2.3.4"]) == 2

    def test_different_ips_are_independent(self):
        rl = LoginRateLimiter(max_attempts=1, window_seconds=60)
        rl.check("1.1.1.1")
        rl.check("1.1.1.1")  # 1.1.1.1 now blocked
        allowed, _ = rl.check("2.2.2.2")
        assert allowed is True

    def test_reset_clears_all_state(self):
        rl = LoginRateLimiter(max_attempts=1, window_seconds=60)
        rl.check("1.2.3.4")
        rl.check("1.2.3.4")  # blocked
        rl.reset()
        allowed, _ = rl.check("1.2.3.4")
        assert allowed is True

    def test_window_expiry_allows_new_attempts(self):
        rl = LoginRateLimiter(max_attempts=1, window_seconds=1)
        rl.check("1.2.3.4")
        allowed_before, _ = rl.check("1.2.3.4")
        assert allowed_before is False
        time.sleep(1.1)
        allowed_after, _ = rl.check("1.2.3.4")
        assert allowed_after is True

    def test_evicts_oldest_ip_at_cap(self):
        rl = LoginRateLimiter(max_attempts=5, window_seconds=60)
        # Simulate being over the cap by manually stuffing _hits
        for i in range(10_001):
            rl._hits[f"10.0.{i // 256}.{i % 256}"] = [time.monotonic()]
        # A new check should trigger eviction without raising
        rl.check("192.168.1.1")
        assert len(rl._hits) <= 10_001  # at most cap + the new IP before eviction


# ---------------------------------------------------------------------------
# _extract_ip
# ---------------------------------------------------------------------------

class TestExtractIp:
    def test_prefers_x_real_ip(self):
        headers = {"x-real-ip": "10.0.0.1", "x-forwarded-for": "9.9.9.9"}
        assert _extract_ip(headers, "127.0.0.1") == "10.0.0.1"

    def test_falls_back_to_x_forwarded_for(self):
        headers = {"x-forwarded-for": "10.0.0.2, 172.16.0.1"}
        assert _extract_ip(headers, "127.0.0.1") == "10.0.0.2"

    def test_x_forwarded_for_strips_whitespace(self):
        headers = {"x-forwarded-for": "  10.0.0.3  , 172.16.0.1"}
        assert _extract_ip(headers, "127.0.0.1") == "10.0.0.3"

    def test_falls_back_to_client_host(self):
        assert _extract_ip({}, "127.0.0.1") == "127.0.0.1"

    def test_default_client_host_is_unknown(self):
        assert _extract_ip({}) == "unknown"


# ---------------------------------------------------------------------------
# get_client_ip (FastAPI Request wrapper)
# ---------------------------------------------------------------------------

class TestGetClientIp:
    def _make_request(self, headers: dict, host: str | None = "127.0.0.1") -> MagicMock:
        req = MagicMock()
        req.headers = headers
        req.client = MagicMock()
        req.client.host = host
        return req

    def test_reads_x_real_ip_from_request(self):
        req = self._make_request({"x-real-ip": "10.10.10.10"})
        assert get_client_ip(req) == "10.10.10.10"

    def test_falls_back_to_client_host(self):
        req = self._make_request({})
        assert get_client_ip(req) == "127.0.0.1"

    def test_no_client_returns_unknown(self):
        req = MagicMock()
        req.headers = {}
        req.client = None
        assert get_client_ip(req) == "unknown"
