"""Tests for roster-based callsign rewrite in _rx_pump.

Finals only, gated on BOTH fuzzy_callsign and fuzzy_callsign_rewrite, and
applied BEFORE mask_profanity — so broadcast, stream history, TTS read-aloud,
plugins, and attendance all see the corrected text.
"""
import asyncio
import collections
import sys
from unittest.mock import AsyncMock, MagicMock

# backend.server transitively imports sounddevice (and other audio/ML deps) at
# module load time.  Stub them out so tests run in environments without audio hardware.
for _stub in ("sounddevice", "faster_whisper", "silero_vad", "piper"):
    sys.modules.setdefault(_stub, MagicMock())
_piper_config_stub = MagicMock()
_piper_config_stub.SynthesisConfig = MagicMock
sys.modules.setdefault("piper.config", _piper_config_stub)

import backend.server as server
from backend.config import ServerConfig
from backend.text.profanity import mask_profanity


def _arm_server(*, fuzzy=True, rewrite=True, contacts=({"callsign": "WSLZ233"},)):
    server._config = ServerConfig({
        "fuzzy_callsign": fuzzy,
        "fuzzy_callsign_rewrite": rewrite,
    })
    server._stt_out_queue = asyncio.Queue()
    server._utterance_partial_texts = {}
    server._recent_finals = collections.deque(maxlen=2)
    server._pending_stations = {}
    server._manager = MagicMock()
    server._manager.broadcast_rx = AsyncMock()
    server._manager.broadcast = AsyncMock()
    server._stream_history = MagicMock()
    server._contacts_store = MagicMock()
    server._contacts_store.get_all.return_value = list(contacts)
    server._attendance = MagicMock()
    server._attendance.record.return_value = False
    server._synthesize_rx_audio = AsyncMock()
    server.plugin_registry = MagicMock()
    server.plugin_registry.dispatch_rx_final = AsyncMock()


async def _pump_one(result: dict) -> dict:
    """Run _rx_pump through one queue item and return broadcast_rx's call."""
    await server._stt_out_queue.put(result)
    task = asyncio.get_running_loop().create_task(server._rx_pump())
    for _ in range(200):
        if server._manager.broadcast_rx.await_count:
            break
        await asyncio.sleep(0.01)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert server._manager.broadcast_rx.await_count == 1
    call = server._manager.broadcast_rx.await_args
    return {"msg": call.args[0], **call.kwargs}


class TestRxPumpCallsignRewrite:
    async def test_final_rewritten_and_marked_before_profanity_mask(self):
        _arm_server()
        out = await _pump_one({
            "utterance_id": "1", "partial": False,
            "text": "WSLZ235 that shit band is open",
        })
        assert out["raw_text"] == "WSLZ233 that shit band is open"
        # mask ran on the REWRITTEN text — proves rewrite-before-mask ordering
        assert out["filtered_text"] == mask_profanity("WSLZ233 that shit band is open")
        assert out["msg"]["callsign_spans"] == [[0, 7, "WSLZ233", "WSLZ235"]]

    async def test_exact_hit_not_marked(self):
        _arm_server()
        out = await _pump_one({
            "utterance_id": "1", "partial": False, "text": "WSLZ233 radio check",
        })
        assert out["raw_text"] == "WSLZ233 radio check"
        assert out["msg"]["callsign_spans"] == [[0, 7, "WSLZ233", None]]

    async def test_rewrite_off_keeps_label_correction_only(self):
        _arm_server(rewrite=False)
        out = await _pump_one({
            "utterance_id": "1", "partial": False, "text": "WSLZ235 radio check",
        })
        # text untouched; span label still fuzzy-corrected (existing behavior)
        assert out["raw_text"] == "WSLZ235 radio check"
        assert out["msg"]["callsign_spans"] == [[0, 7, "WSLZ233"]]

    async def test_fuzzy_off_disables_rewrite_even_when_rewrite_on(self):
        _arm_server(fuzzy=False, rewrite=True)
        out = await _pump_one({
            "utterance_id": "1", "partial": False, "text": "WSLZ235 radio check",
        })
        assert out["raw_text"] == "WSLZ235 radio check"
        assert out["msg"]["callsign_spans"] == [[0, 7, "WSLZ235"]]

    async def test_partials_never_rewritten(self):
        _arm_server()
        out = await _pump_one({
            "utterance_id": "1", "partial": True, "text": "WSLZ235 radio",
        })
        assert out["raw_text"] == "WSLZ235 radio"
        assert out["msg"]["callsign_spans"] == [[0, 7, "WSLZ235"]]

    async def test_rewritten_text_reaches_tts_and_plugins(self):
        _arm_server()
        await _pump_one({
            "utterance_id": "1", "partial": False, "text": "WSLZ235 radio check",
        })
        server._synthesize_rx_audio.assert_called_once_with("WSLZ233 radio check")
        server.plugin_registry.dispatch_rx_final.assert_called_once_with("WSLZ233 radio check")

    async def test_rewritten_text_recorded_in_stream_history(self):
        _arm_server()
        await _pump_one({
            "utterance_id": "1", "partial": False, "text": "WSLZ235 radio check",
        })
        args = server._stream_history.record_rx.call_args.args
        assert args[1] == "WSLZ233 radio check"
