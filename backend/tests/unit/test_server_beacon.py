import asyncio
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
    async def test_fires_and_resets_fcc_id_timer(self):
        _arm_server(enabled=True)
        await _run_one_tick()
        assert not server._tx_queue.empty()
        item = server._tx_queue.get_nowait()
        assert item["_pre_formatted"] is True
        assert "monitoring" in item["text"]
        # Beacon counts as the FCC ID:
        assert server._has_transmitted is False
        assert server._last_id_time is not None
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
