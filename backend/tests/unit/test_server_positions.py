"""The host half of position reporting: backend.server._report_position.

Covers the bit a plugin can't cover for itself — deciding *when* a fix was
heard. Everything about validation and storage lives in the store's own tests.
"""
import asyncio
import contextlib
import sys
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

# backend.server transitively imports sounddevice (and other audio/ML deps) at
# module load time.  Stub them out so tests run in environments without audio hardware.
for _stub in ("sounddevice", "faster_whisper", "silero_vad", "piper"):
    sys.modules.setdefault(_stub, MagicMock())
_piper_config_stub = MagicMock()
_piper_config_stub.SynthesisConfig = MagicMock
sys.modules.setdefault("piper.config", _piper_config_stub)

import backend.server as server
from backend.positions.store import PositionStore


@pytest.fixture
def store(tmp_path, monkeypatch):
    store = PositionStore(tmp_path / "positions.json", ttl_minutes=60)
    monkeypatch.setattr(server, "_position_store", store)
    monkeypatch.setattr(server, "_positions_dirty", False)
    return store


def _only(store):
    return next(iter(store._records.values()))


# ---------------------------------------------------------------------------
# heard_at resolution
# ---------------------------------------------------------------------------

def test_no_heard_at_means_now():
    assert server._resolve_heard_at(None) is None


@pytest.mark.parametrize("raw", ["not-a-time", 0, -1, object()])
def test_a_useless_heard_at_means_now(raw):
    assert server._resolve_heard_at(raw) is None


def test_a_real_heard_at_is_kept():
    heard = time.time() - 3600
    assert server._resolve_heard_at(heard) == pytest.approx(heard)


def test_a_string_heard_at_is_coerced():
    heard = time.time() - 60
    assert server._resolve_heard_at(str(heard)) == pytest.approx(heard)


def test_a_future_heard_at_is_clamped_to_now():
    # Another radio's clock running fast would otherwise outlive its TTL.
    resolved = server._resolve_heard_at(time.time() + 86400)
    assert resolved <= time.time() + 1


def test_an_ancient_heard_at_is_kept_so_the_ttl_can_expire_it():
    # Honest and invisible beats fresh-looking and wrong.
    assert server._resolve_heard_at(1.0) == 1.0


# ---------------------------------------------------------------------------
# _report_position
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_report_stores_the_fix_and_marks_it_dirty(store):
    assert await server._report_position("aprs_rf", "W8ABC-9", 42.9, -85.8, label="Truck") is True
    assert _only(store).label == "Truck"
    assert server._positions_dirty is True


@pytest.mark.asyncio
async def test_a_node_db_row_ages_from_when_it_was_heard(store):
    # The whole point: reading a roster is not hearing a station.
    heard = time.time() - 7200
    await server._report_position("meshtastic", "!abcd", 42.9, -85.8, heard_at=heard)
    assert _only(store).heard_at == pytest.approx(heard)


@pytest.mark.asyncio
async def test_a_source_with_no_timestamp_is_stamped_on_arrival(store):
    await server._report_position("aprs_rf", "W8ABC-9", 42.9, -85.8)
    assert _only(store).heard_at == pytest.approx(time.time(), abs=5)


@pytest.mark.asyncio
async def test_heard_at_does_not_leak_into_the_display_metadata(store):
    await server._report_position("meshtastic", "!abcd", 42.9, -85.8,
                                  heard_at=time.time(), alt_m=240, snr="6.2 dB")
    record = _only(store)
    assert record.extra == {"snr": "6.2 dB"}
    assert record.alt_m == 240.0


@pytest.mark.asyncio
async def test_a_bad_fix_is_refused_without_raising(store):
    assert await server._report_position("meshtastic", "!abcd", 0.0, 0.0) is False
    assert len(store) == 0
    assert server._positions_dirty is False


@pytest.mark.asyncio
async def test_reporting_before_the_store_exists_is_a_no_op(monkeypatch):
    monkeypatch.setattr(server, "_position_store", None)
    assert await server._report_position("aprs_rf", "W8ABC-9", 42.9, -85.8) is False


# ---------------------------------------------------------------------------
# _positions_pump
# ---------------------------------------------------------------------------

@pytest.fixture
def pump(store, monkeypatch):
    """The pump with its sleep collapsed, plus a recording broadcast."""
    monkeypatch.setattr(server, "_POSITIONS_PUMP_INTERVAL_S", 0)
    monkeypatch.setattr(server, "_config", None)
    manager = MagicMock()
    manager.broadcast = AsyncMock()
    monkeypatch.setattr(server, "_manager", manager)
    return manager


async def _run_pump_briefly(seconds: float = 0.05):
    """Let the pump spin for a moment. Its interval is patched to 0, so this
    is many iterations, not one — enough for the refresh cadence to fire."""
    task = asyncio.create_task(server._positions_pump())
    await asyncio.sleep(seconds)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_pump_broadcasts_a_new_fix(pump, store):
    await server._report_position("aprs_rf", "W8ABC-9", 42.9, -85.8)
    await _run_pump_briefly()
    assert pump.broadcast.await_count >= 1
    assert pump.broadcast.await_args[0][0]["type"] == "positions"


@pytest.mark.asyncio
async def test_pump_stays_quiet_when_nothing_changed(pump, store, monkeypatch):
    # A hundred kiosks must not be woken every two seconds for no reason.
    monkeypatch.setattr(server, "_POSITIONS_REFRESH_S", 10_000)
    await server._report_position("aprs_rf", "W8ABC-9", 42.9, -85.8)
    await _run_pump_briefly()
    assert pump.broadcast.await_count == 1


@pytest.mark.asyncio
async def test_pump_refreshes_so_the_age_counters_keep_moving(pump, store, monkeypatch):
    # Age is resolved server-side, so silence must not freeze every station
    # at "Heard now".
    monkeypatch.setattr(server, "_POSITIONS_REFRESH_S", 0)
    await server._report_position("aprs_rf", "W8ABC-9", 42.9, -85.8)
    await _run_pump_briefly()
    assert pump.broadcast.await_count > 1


@pytest.mark.asyncio
async def test_pump_says_nothing_at_all_with_no_stations(pump, store, monkeypatch):
    monkeypatch.setattr(server, "_POSITIONS_REFRESH_S", 0)
    await _run_pump_briefly()
    pump.broadcast.assert_not_awaited()
