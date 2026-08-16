"""Direct-async tests for the check-in FCC lookup scheduler in backend.server.

These drive _schedule_checkin_fcc / _checkin_fcc_lookup against the module
globals directly (patched fresh per test) — the WebSocket integration tests
cover the wire path; this covers the scheduler's own races and cache rules,
which need a controllable-in-flight lookup that a TestClient can't provide.
"""
import asyncio
import threading
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import backend.server as srv
from backend.fcc.crossref import VerificationResult
from backend.neighborhood.net import NeighborhoodNet
from backend.positions.store import PositionStore


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


# ---------------------------------------------------------------------------
# License-city fallback pins
# ---------------------------------------------------------------------------

class FakeContacts:
    def __init__(self, contacts):
        self._contacts = contacts

    def get_all(self):
        return list(self._contacts)


def _located_result(city="Jenison, MI"):
    return VerificationResult(
        status="callsign_only",
        license_name="Zomberg, Benjamin J",
        license_active=True,
        license_location=city,
    )


def _pin_patched(contacts, store, result=None, coords=(42.9053, -85.7936)):
    verdict = result if result is not None else _located_result()
    return (
        *_patched(lambda cs, name: verdict),
        patch.object(srv, "_contacts_store", FakeContacts(contacts)),
        patch.object(srv, "_position_store", store),
        patch.object(srv, "geocode_city", return_value=coords),
    )


def _run_checkin(patches, key="u1", callsign="WSLZ233", name="Ben"):
    async def scenario():
        srv._neighborhood.checkin(key, callsign, name, "")
        srv._schedule_checkin_fcc(key, callsign, name)
        await _wait_for_fcc(key)
        await asyncio.sleep(0.05)  # let the pin hop settle after the verdict

    with ExitStack() as stack:
        for patch_ctx in patches:
            stack.enter_context(patch_ctx)
        asyncio.run(scenario())


def test_license_city_pin_is_created_for_an_opted_in_contact(tmp_path):
    store = PositionStore(tmp_path / "p.json", ttl_minutes=60)
    _run_checkin(_pin_patched([{"callsign": "WSLZ233", "map_pin": True}], store))

    pins = [rec for rec in store.active() if rec.source == "fcc"]
    assert len(pins) == 1
    assert pins[0].node_id == "WSLZ233"
    assert pins[0].extra["approx"] == "license"
    # Scattered off the raw centroid so two stations in one city stay distinct.
    assert (pins[0].lat, pins[0].lon) != (42.9053, -85.7936)
    assert abs(pins[0].lat - 42.9053) < 0.01


def test_no_pin_when_the_contact_has_not_opted_in(tmp_path):
    store = PositionStore(tmp_path / "p.json", ttl_minutes=60)
    _run_checkin(_pin_patched([{"callsign": "WSLZ233"}], store))
    assert store.active() == []


def test_no_pin_when_the_callsign_has_no_contact(tmp_path):
    store = PositionStore(tmp_path / "p.json", ttl_minutes=60)
    _run_checkin(_pin_patched([{"callsign": "WRZM714", "map_pin": True}], store))
    assert store.active() == []


def test_no_pin_when_the_station_already_has_a_real_fix(tmp_path):
    store = PositionStore(tmp_path / "p.json", ttl_minutes=60)
    store.upsert("aprs_rf", "WSLZ233-9", 42.5, -85.5)
    _run_checkin(_pin_patched([{"callsign": "WSLZ233", "map_pin": True}], store))
    assert [rec.source for rec in store.active()] == ["aprs_rf"]


def test_no_pin_when_the_license_has_no_city(tmp_path):
    store = PositionStore(tmp_path / "p.json", ttl_minutes=60)
    _run_checkin(
        _pin_patched(
            [{"callsign": "WSLZ233", "map_pin": True}], store, result=_located_result("")
        )
    )
    assert store.active() == []


def test_no_pin_when_a_real_fix_arrives_during_the_geocode(tmp_path):
    # The geocode is a network round-trip, so a station can start the check-in
    # with no position and be heard over the air before the pin is written.
    # The real fix still has to win.
    store = PositionStore(tmp_path / "p.json", ttl_minutes=60)
    entered = threading.Event()
    release = threading.Event()

    def slow_geocode(location):
        entered.set()
        release.wait(timeout=5)
        return (42.9053, -85.7936)

    patches = (
        *_patched(lambda cs, name: _located_result()),
        patch.object(srv, "_contacts_store",
                     FakeContacts([{"callsign": "WSLZ233", "map_pin": True}])),
        patch.object(srv, "_position_store", store),
        patch.object(srv, "geocode_city", side_effect=slow_geocode),
    )

    async def scenario():
        srv._neighborhood.checkin("u1", "WSLZ233", "Ben", "")
        srv._schedule_checkin_fcc("u1", "WSLZ233", "Ben")
        for _ in range(200):
            await asyncio.sleep(0.01)
            if entered.is_set():
                break
        assert entered.is_set(), "geocode never started"
        store.upsert("aprs_rf", "WSLZ233-9", 42.5, -85.5)
        release.set()
        await _wait_for_fcc("u1")
        await asyncio.sleep(0.05)

    with ExitStack() as stack:
        for patch_ctx in patches:
            stack.enter_context(patch_ctx)
        asyncio.run(scenario())

    assert [rec.source for rec in store.active()] == ["aprs_rf"]


def test_pin_honours_the_opt_in_on_either_callsign_field(tmp_path):
    # A contact can carry a GMRS and a ham callsign in separate fields; the
    # one they checked in with is the one that has to match.
    for field in ("gmrs_callsign", "ham_callsign"):
        store = PositionStore(tmp_path / f"p-{field}.json", ttl_minutes=60)
        _run_checkin(_pin_patched([{"name": "Ben", field: "WSLZ233", "map_pin": True}],
                                  store))
        assert [rec.source for rec in store.active()] == ["fcc"], field
