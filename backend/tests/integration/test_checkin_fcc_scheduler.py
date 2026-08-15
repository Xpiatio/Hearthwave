"""Direct-async tests for the check-in FCC lookup scheduler in backend.server.

These drive _schedule_checkin_fcc / _checkin_fcc_lookup against the module
globals directly (patched fresh per test) — the WebSocket integration tests
cover the wire path; this covers the scheduler's own races and cache rules,
which need a controllable-in-flight lookup that a TestClient can't provide.
"""
import asyncio
import threading
from unittest.mock import AsyncMock, patch

import backend.server as srv
from backend.fcc.crossref import VerificationResult
from backend.neighborhood.net import NeighborhoodNet


def _result(license_name, active=True):
    return VerificationResult(
        status="callsign_only", license_name=license_name, license_active=active
    )


def _patched(fake_verify):
    return (
        patch.object(srv, "verify_callsign", side_effect=fake_verify),
        patch.object(srv, "_neighborhood", NeighborhoodNet()),
        patch.object(srv._manager, "broadcast", new=AsyncMock()),
        patch.dict(srv._checkin_fcc_cache, clear=True),
        patch.dict(srv._checkin_fcc_tasks, clear=True),
        patch.object(srv, "is_online_cached", return_value=True),
    )


async def _wait_for_fcc(key, tries=200):
    for _ in range(tries):
        await asyncio.sleep(0.01)
        row = next(r for r in srv._neighborhood.roster() if r["user_id"] == key)
        if row.get("fcc_status"):
            return row
    raise AssertionError("fcc annotation never landed")


def test_recheckin_with_new_callsign_supersedes_inflight_lookup():
    # A re-check-in that changes the callsign while the old callsign's lookup
    # is still in flight must not leave the row annotated with the OLD
    # callsign's verdict.
    gate = threading.Event()
    results = {"WAAA111": _result("Old, Name", active=False),
               "WBBB222": _result("New, Name", active=True)}
    calls = []

    def fake_verify(cs, name):
        calls.append(cs)
        if cs == "WAAA111":
            gate.wait(timeout=5)
        return results[cs]

    async def scenario():
        srv._neighborhood.checkin("u1", "WAAA111", "Ann", "")
        srv._schedule_checkin_fcc("u1", "WAAA111", "Ann")
        await asyncio.sleep(0.05)  # first lookup is now blocked in its thread
        srv._neighborhood.checkin("u1", "WBBB222", "Ann", "")
        srv._schedule_checkin_fcc("u1", "WBBB222", "Ann")
        gate.set()
        return await _wait_for_fcc("u1")

    patches = _patched(fake_verify)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        row = asyncio.run(scenario())
    assert row["fcc_license_name"] == "New, Name"
    assert row["fcc_status"] == "active"


def test_cache_key_is_normalized_callsign():
    # An account profile can hold a lowercase callsign; the radio form
    # normalizes to uppercase. Both spellings are one license and must share
    # one cache entry — i.e. one HTTP lookup, not two.
    calls = []

    def fake_verify(cs, name):
        calls.append(cs)
        return _result("Zomberg, Benjamin J")

    async def scenario():
        srv._neighborhood.checkin("u1", "wslz233", "Ben", "")
        srv._schedule_checkin_fcc("u1", "wslz233", "Ben")
        await _wait_for_fcc("u1")
        srv._neighborhood.checkin("u2", "WSLZ233", "Eliza", "")
        srv._schedule_checkin_fcc("u2", "WSLZ233", "Eliza")
        return await _wait_for_fcc("u2")

    patches = _patched(fake_verify)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        asyncio.run(scenario())
    assert len(calls) == 1
