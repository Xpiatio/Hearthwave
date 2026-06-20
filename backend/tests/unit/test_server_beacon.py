import asyncio
import contextlib
import datetime
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# backend.server transitively imports sounddevice (and other audio/ML deps) at
# module load time.  Stub them out so tests run in environments without audio hardware.
for _stub in ("sounddevice", "faster_whisper", "silero_vad", "piper"):
    sys.modules.setdefault(_stub, MagicMock())
_piper_config_stub = MagicMock()
_piper_config_stub.SynthesisConfig = MagicMock
sys.modules.setdefault("piper.config", _piper_config_stub)

import backend.server as server
from backend.config import ServerConfig


def _arm_server(*, enabled=True, ncs_active=False, channel_clear=True):
    cfg = ServerConfig()
    cfg.update({
        "monitoring_beacon_enabled": enabled,
        "monitoring_beacon_interval": 900,
        "callsign": "WSLZ233",
    })
    server._config = cfg
    server._tx_queue = asyncio.Queue()
    server._manager = MagicMock()
    server._manager.broadcast = AsyncMock()
    server._channel_clear = channel_clear
    server._last_beacon_time = None
    server._last_id_time = None
    server._has_transmitted = True
    if ncs_active:
        ncs = MagicMock()
        ncs.is_active.return_value = True
        server._ncs_plugin = ncs
    else:
        server._ncs_plugin = None


async def _run_one_tick():
    """Drive the pump through exactly one loop body, then break via CancelledError."""
    calls = 0

    async def fake_sleep(_):
        nonlocal calls
        calls += 1
        if calls >= 2:
            raise asyncio.CancelledError()

    with patch("asyncio.sleep", side_effect=fake_sleep):
        await server._monitoring_beacon_pump()


class TestMonitoringBeaconPump:
    async def test_fires_enqueues_beacon_marker_without_touching_id_state(self):
        _arm_server(enabled=True)
        server._has_transmitted = True          # simulate a prior real TX awaiting ID
        server._last_id_time = None
        await _run_one_tick()
        assert not server._tx_queue.empty()
        item = server._tx_queue.get_nowait()
        assert item["_pre_formatted"] is True
        assert item["_beacon"] is True
        assert "monitoring" in item["text"]
        # Pump must NOT reset the FCC ID timer — that happens on confirmed air.
        assert server._has_transmitted is True
        assert server._last_id_time is None
        # Its own cadence timer DID advance.
        assert server._last_beacon_time is not None

    async def test_skips_when_disabled(self):
        _arm_server(enabled=False)
        await _run_one_tick()
        assert server._tx_queue.empty()

    async def test_skips_when_ncs_active(self):
        _arm_server(enabled=True, ncs_active=True)
        await _run_one_tick()
        assert server._tx_queue.empty()

    async def test_skips_when_channel_busy(self):
        _arm_server(enabled=True, channel_clear=False)
        await _run_one_tick()
        assert server._tx_queue.empty()


def _arm_tx_pump(*, channel_busy: bool):
    """Arm backend.server globals so _tx_pump can process one beacon payload."""
    cfg = ServerConfig()
    cfg.update({"voice": "/fake/voice.onnx", "callsign": "WSLZ233"})
    server._config = cfg
    server._tx_queue = asyncio.Queue()
    server._tx_abort_event = asyncio.Event()
    server._tts_event_queue = asyncio.Queue()
    server._manager = MagicMock()
    server._manager.broadcast = AsyncMock()
    server._manager.broadcast_to_user = AsyncMock()
    server._audit_log = None
    server._stt_listening = False               # skip the resume/sleep tail
    server._synthesizer = MagicMock()
    # synthesize_to_buffer is awaited via asyncio.wait_for → AsyncMock returning a tuple.
    server._synthesizer.synthesize_to_buffer = AsyncMock(return_value=(b"\x00\x00", 22050))
    stt = MagicMock()
    stt.channel_busy.is_set.return_value = channel_busy
    server._stt_worker = stt
    server._last_id_time = None
    server._has_transmitted = True              # a prior real TX is awaiting its ID


class _StubPtt:
    lead_in_seconds = 0.0
    tail_seconds = 0.0
    def key(self): pass
    def unkey(self): pass


async def _drive_tx_pump_once():
    """Run _tx_pump, let it process exactly the queued payload(s), then cancel."""
    task = asyncio.ensure_future(server._tx_pump())
    try:
        for _ in range(200):
            await asyncio.sleep(0)
            if server._tx_queue.empty():
                # give the in-flight body time to finish its awaits
                for _ in range(50):
                    await asyncio.sleep(0)
                break
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


class TestTxPumpBeaconIdReset:
    async def test_aired_beacon_resets_id_timer(self):
        _arm_tx_pump(channel_busy=False)
        with patch.object(server, "make_ptt", return_value=_StubPtt()), \
             patch.object(server, "_load_voice", return_value=object()), \
             patch.object(server, "_play_voice_blocking", return_value=None):
            await server._tx_queue.put({"text": "WSLZ 2 3 3 base, monitoring.",
                                        "_pre_formatted": True, "_beacon": True})
            await _drive_tx_pump_once()
        assert server._last_id_time is not None
        assert server._has_transmitted is False

    async def test_discarded_beacon_does_not_reset_id_timer(self):
        _arm_tx_pump(channel_busy=True)   # squelch open → discarded before air
        with patch.object(server, "make_ptt", return_value=_StubPtt()), \
             patch.object(server, "_load_voice", return_value=object()), \
             patch.object(server, "_play_voice_blocking", return_value=None):
            await server._tx_queue.put({"text": "WSLZ 2 3 3 base, monitoring.",
                                        "_pre_formatted": True, "_beacon": True})
            await _drive_tx_pump_once()
        # Beacon never aired → ID pump must stay armed.
        assert server._last_id_time is None
        assert server._has_transmitted is True
