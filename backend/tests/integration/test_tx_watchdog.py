"""Integration tests for the TX kill-switch and transmit watchdog.

Covers:
- Synthesis timeout: TTS hangs → PTT never keyed, error broadcast, idle returned
- PTT max-duration watchdog: playback exceeds cap → PTT force-released
- Operator abort (tx_abort message): interrupts active playback
- Abort while idle: subsequent tx_message is NOT silently discarded

All tests use short timeout values (≤ 200 ms) so the suite runs quickly.
No real audio hardware or ML models are required; all I/O paths are mocked.

TX audio is played server-side (sd.play + sd.wait, run in an executor thread).
Tests patch backend.server._play_voice_blocking with a fake that blocks for the
audio's natural duration but returns early when sd.stop() is called — mirroring
how sd.stop() unblocks sd.wait() on abort/watchdog.

NOTE: test_server_ws.py fixtures do not include auth mocks and are currently
broken since the auth feature was added.  This file uses _auth_patches() to
bypass token/user validation for every test.
"""
from __future__ import annotations

import asyncio
import threading
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from starlette.testclient import TestClient

from backend.config import ServerConfig
from backend.server import app


# ---------------------------------------------------------------------------
# Config factory
# ---------------------------------------------------------------------------

def _cfg(tmp_path: Path, **overrides) -> ServerConfig:
    contacts_file = tmp_path / "contacts.json"
    contacts_file.write_text("[]")
    base = {
        "callsign": "W5TST",
        "name": "Test Op",
        "location": "Test City",
        "voice": "fake_voice",
        "contacts_file": str(contacts_file),
    }
    base.update(overrides)
    return ServerConfig(base)


# ---------------------------------------------------------------------------
# Auth mock helper
#
# The WS endpoint validates a session token; without this mock every connect
# is closed with code 4001 and all ws.receive_json() calls raise
# WebSocketDisconnect.  Patch the stores so any token is accepted.
# ---------------------------------------------------------------------------

@contextmanager
def _auth_patches():
    mock_users = MagicMock()
    mock_users.is_empty.return_value = False
    mock_users.get.return_value = {
        "id": "test-user",
        "display_name": "Test Operator",
        "is_admin": True,
        "prefs": {},
    }
    mock_users.get_public_one.return_value = {"display_name": "Test Operator"}

    mock_tokens = MagicMock()
    mock_tokens.validate.return_value = "test-user"
    mock_tokens.purge_expired.return_value = 0

    with (
        patch("backend.server.UsersStore", return_value=mock_users),
        patch("backend.server.TokenStore", return_value=mock_tokens),
        patch("backend.auth_routes.init"),
    ):
        yield


WS_URL = "/ws?token=test"


# ---------------------------------------------------------------------------
# Initial-message drain
#
# After a successful auth the server sends: status, user_profile, contacts,
# session_attendance, pending_stations, voices_list (and optionally
# online_status).  Drain until voices_list is seen so tests start clean.
# ---------------------------------------------------------------------------

def _drain_initial(ws, limit: int = 10) -> list[dict]:
    frames = []
    for _ in range(limit):
        msg = ws.receive_json()
        frames.append(msg)
        if msg.get("type") == "voices_list":
            break
    return frames


def _drain_until(ws, msg_type: str, limit: int = 15) -> list[dict]:
    """Collect frames until one matching msg_type arrives; return all collected."""
    collected = []
    for _ in range(limit):
        msg = ws.receive_json()
        collected.append(msg)
        if msg.get("type") == msg_type:
            break
    return collected


def _drain_until_idle(ws, limit: int = 25) -> list[dict]:
    """Collect frames until tx_status:idle arrives; return all collected.

    Use this (not _drain_until 'tx_status') in tests that need to see the
    error or idle that follow the initial tx_status:transmitting broadcast.
    """
    collected = []
    for _ in range(limit):
        msg = ws.receive_json()
        collected.append(msg)
        if msg.get("type") == "tx_status" and msg.get("status") == "idle":
            break
    return collected


# ---------------------------------------------------------------------------
# Shared mock factories
# ---------------------------------------------------------------------------

def _make_base_mocks():
    mock_stt = MagicMock()
    mock_stt.join = AsyncMock()
    mock_stt.channel_busy = MagicMock(is_set=MagicMock(return_value=False))
    mock_tts = MagicMock()
    return mock_stt, mock_tts


def _mock_ptt():
    ptt = MagicMock()
    ptt.lead_in_seconds = 0.0
    ptt.tail_seconds = 0.0
    return ptt


def _make_play_mocks():
    """Return (fake_play, stop_event, calls) emulating sd.play + sd.wait + sd.stop().

    fake_play blocks for the audio's natural duration but returns early when
    stop_event is set, mirroring sd.stop() interrupting sd.wait().  Patch
    backend.server.sd.stop with side_effect=stop_event.set so the server's
    abort/watchdog path unblocks the (threaded) playback.  Each call is recorded
    in `calls` as (sample_rate, output_device) for assertions.
    """
    stop_event = threading.Event()
    calls: list[tuple] = []

    def fake_play(audio, sample_rate, output_device):
        calls.append((sample_rate, output_device))
        if stop_event.wait(timeout=len(audio) / sample_rate):
            stop_event.clear()

    return fake_play, stop_event, calls


# ---------------------------------------------------------------------------
# Synthesis timeout — PTT must never be keyed when TTS hangs
# ---------------------------------------------------------------------------

class TestSynthesisTimeout:
    def test_error_broadcast_and_ptt_never_keyed(self, tmp_path):
        cfg = _cfg(tmp_path, tx_synthesis_timeout_seconds=0.1)
        mock_stt, mock_tts = _make_base_mocks()
        mock_ptt = _mock_ptt()

        async def _slow_synth(*_args, **_kwargs):
            await asyncio.sleep(10)  # longer than 0.1 s timeout
            return None, None

        mock_tts.synthesize_to_buffer = _slow_synth

        with _auth_patches():
            with (
                patch("backend.server.ServerConfig.load", return_value=cfg),
                patch("backend.server.STTWorker", return_value=mock_stt),
                patch("backend.server.TTSSynthesizer", return_value=mock_tts),
                patch("backend.server.make_ptt", return_value=mock_ptt),
                patch("backend.server._load_voice", return_value=MagicMock()),
            ):
                with TestClient(app) as tc:
                    with tc.websocket_connect(WS_URL) as ws:
                        _drain_initial(ws)
                        ws.send_json({"type": "tx_message", "callsign": "W5TST", "text": "hello"})
                        # Drain past the initial tx_status:transmitting frame;
                        # the synthesis timeout fires and produces an error then idle.
                        frames = _drain_until_idle(ws)

        types = [f["type"] for f in frames]
        assert "error" in types, f"Expected error broadcast on synthesis timeout; got: {types}"
        assert frames[-1] == {"type": "tx_status", "status": "idle"}
        mock_ptt.key.assert_not_called()

    def test_idle_always_broadcast_after_synthesis_timeout(self, tmp_path):
        cfg = _cfg(tmp_path, tx_synthesis_timeout_seconds=0.1)
        mock_stt, mock_tts = _make_base_mocks()
        mock_ptt = _mock_ptt()

        async def _slow_synth(*_args, **_kwargs):
            await asyncio.sleep(10)
            return None, None

        mock_tts.synthesize_to_buffer = _slow_synth

        with _auth_patches():
            with (
                patch("backend.server.ServerConfig.load", return_value=cfg),
                patch("backend.server.STTWorker", return_value=mock_stt),
                patch("backend.server.TTSSynthesizer", return_value=mock_tts),
                patch("backend.server.make_ptt", return_value=mock_ptt),
                patch("backend.server._load_voice", return_value=MagicMock()),
            ):
                with TestClient(app) as tc:
                    with tc.websocket_connect(WS_URL) as ws:
                        _drain_initial(ws)
                        ws.send_json({"type": "tx_message", "callsign": "W5TST", "text": "hello"})
                        frames = _drain_until_idle(ws)

        assert {"type": "tx_status", "status": "idle"} in frames


# ---------------------------------------------------------------------------
# PTT max-duration watchdog — PTT released when playback exceeds cap
# ---------------------------------------------------------------------------

class TestPttMaxDurationWatchdog:
    def test_ptt_released_and_error_broadcast_after_timeout(self, tmp_path):
        cfg = _cfg(tmp_path, tx_max_duration_seconds=0.15)
        mock_stt, mock_tts = _make_base_mocks()
        mock_ptt = _mock_ptt()
        fake_play, stop_event, _ = _make_play_mocks()

        # 5 s of audio; PTT cap is 150 ms so the watchdog fires first.
        long_audio = np.zeros(80000, dtype=np.int16)

        async def _synth(*_args, **_kwargs):
            return long_audio, 16000

        mock_tts.synthesize_to_buffer = _synth

        with _auth_patches():
            with (
                patch("backend.server.ServerConfig.load", return_value=cfg),
                patch("backend.server.STTWorker", return_value=mock_stt),
                patch("backend.server.TTSSynthesizer", return_value=mock_tts),
                patch("backend.server.make_ptt", return_value=mock_ptt),
                patch("backend.server._load_voice", return_value=MagicMock()),
                patch("backend.server._play_voice_blocking", fake_play),
                patch("backend.server.sd.stop", side_effect=stop_event.set),
            ):
                with TestClient(app) as tc:
                    with tc.websocket_connect(WS_URL) as ws:
                        _drain_initial(ws)
                        ws.send_json({"type": "tx_message", "callsign": "W5TST", "text": "test"})
                        # tx_status:transmitting arrives first; drain through error to idle.
                        frames = _drain_until_idle(ws)

        types = [f["type"] for f in frames]
        assert "error" in types, f"Expected timeout error; got: {types}"
        assert frames[-1] == {"type": "tx_status", "status": "idle"}
        mock_ptt.key.assert_called_once()
        mock_ptt.unkey.assert_called_once()

    def test_normal_short_tx_completes_without_error(self, tmp_path):
        """Watchdog must not fire for audio shorter than the cap; audio is played
        server-side out the configured output device."""
        cfg = _cfg(tmp_path, tx_max_duration_seconds=5, output_device=7)
        mock_stt, mock_tts = _make_base_mocks()
        mock_ptt = _mock_ptt()
        fake_play, stop_event, play_calls = _make_play_mocks()

        short_audio = np.zeros(160, dtype=np.int16)  # 10 ms

        async def _synth(*_args, **_kwargs):
            return short_audio, 16000

        mock_tts.synthesize_to_buffer = _synth

        with _auth_patches():
            with (
                patch("backend.server.ServerConfig.load", return_value=cfg),
                patch("backend.server.STTWorker", return_value=mock_stt),
                patch("backend.server.TTSSynthesizer", return_value=mock_tts),
                patch("backend.server.make_ptt", return_value=mock_ptt),
                patch("backend.server._load_voice", return_value=MagicMock()),
                patch("backend.server._play_voice_blocking", fake_play),
                patch("backend.server.sd.stop", side_effect=stop_event.set),
            ):
                with TestClient(app) as tc:
                    with tc.websocket_connect(WS_URL) as ws:
                        _drain_initial(ws)
                        ws.send_json({"type": "tx_message", "callsign": "W5TST", "text": "hi"})
                        frames = _drain_until_idle(ws)

        types = [f["type"] for f in frames]
        assert "error" not in types, f"Unexpected error for short TX: {types}"
        assert frames[-1] == {"type": "tx_status", "status": "idle"}
        mock_ptt.key.assert_called_once()
        mock_ptt.unkey.assert_called_once()
        # Audio was played server-side out the configured output device (7), not
        # broadcast to browsers.
        assert play_calls == [(16000, 7)], f"Expected one play to device 7; got {play_calls}"


# ---------------------------------------------------------------------------
# Operator abort — tx_abort interrupts active playback
# ---------------------------------------------------------------------------

class TestOperatorAbort:
    def test_tx_abort_interrupts_playback(self, tmp_path):
        cfg = _cfg(tmp_path, tx_max_duration_seconds=30)
        mock_stt, mock_tts = _make_base_mocks()
        mock_ptt = _mock_ptt()
        fake_play, stop_event, _ = _make_play_mocks()

        # 10 s audio; without abort the playback would last 10 s.
        long_audio = np.zeros(160000, dtype=np.int16)

        async def _synth(*_args, **_kwargs):
            return long_audio, 16000

        mock_tts.synthesize_to_buffer = _synth

        with _auth_patches():
            with (
                patch("backend.server.ServerConfig.load", return_value=cfg),
                patch("backend.server.STTWorker", return_value=mock_stt),
                patch("backend.server.TTSSynthesizer", return_value=mock_tts),
                patch("backend.server.make_ptt", return_value=mock_ptt),
                patch("backend.server._load_voice", return_value=MagicMock()),
                patch("backend.server._play_voice_blocking", fake_play),
                patch("backend.server.sd.stop", side_effect=stop_event.set),
            ):
                with TestClient(app) as tc:
                    with tc.websocket_connect(WS_URL) as ws:
                        _drain_initial(ws)
                        ws.send_json({"type": "tx_message", "callsign": "W5TST", "text": "long"})

                        # tx_echo is broadcast from inside _tx_pump after dequeue and
                        # before keying, so once we see it the abort can't be dropped
                        # by the top-of-loop guard.  PTT is now keyed and playing.
                        _drain_until(ws, "tx_echo", limit=10)
                        ws.send_json({"type": "tx_abort"})

                        # Should receive abort-related messages promptly (not 10 s later).
                        frames = _drain_until(ws, "tx_status", limit=10)

        idle_frames = [f for f in frames if f == {"type": "tx_status", "status": "idle"}]
        assert idle_frames, f"Expected tx_status:idle after abort; got: {[f['type'] for f in frames]}"
        mock_ptt.unkey.assert_called()

    def test_tx_abort_drains_queued_items(self, tmp_path):
        """Items queued before the abort must not be synthesized."""
        cfg = _cfg(tmp_path, tx_max_duration_seconds=30)
        mock_stt, mock_tts = _make_base_mocks()
        mock_ptt = _mock_ptt()
        fake_play, stop_event, _ = _make_play_mocks()

        long_audio = np.zeros(160000, dtype=np.int16)
        synth_calls: list[int] = []

        async def _synth(*_args, **_kwargs):
            synth_calls.append(1)
            return long_audio, 16000

        mock_tts.synthesize_to_buffer = _synth

        with _auth_patches():
            with (
                patch("backend.server.ServerConfig.load", return_value=cfg),
                patch("backend.server.STTWorker", return_value=mock_stt),
                patch("backend.server.TTSSynthesizer", return_value=mock_tts),
                patch("backend.server.make_ptt", return_value=mock_ptt),
                patch("backend.server._load_voice", return_value=MagicMock()),
                patch("backend.server._play_voice_blocking", fake_play),
                patch("backend.server.sd.stop", side_effect=stop_event.set),
            ):
                with TestClient(app) as tc:
                    with tc.websocket_connect(WS_URL) as ws:
                        _drain_initial(ws)
                        ws.send_json({"type": "tx_message", "callsign": "W5TST", "text": "msg 1"})
                        _drain_until(ws, "tx_echo", limit=10)
                        # Queue a second message while first is transmitting, then abort.
                        ws.send_json({"type": "tx_message", "callsign": "W5TST", "text": "msg 2"})
                        ws.send_json({"type": "tx_abort"})
                        _drain_until(ws, "tx_status", limit=10)

        assert len(synth_calls) == 1, f"Expected 1 synth call; got {len(synth_calls)}"


# ---------------------------------------------------------------------------
# Abort while idle — next tx_message must NOT be silently discarded
# ---------------------------------------------------------------------------

class TestAbortWhileIdle:
    def test_next_tx_after_idle_abort_is_not_dropped(self, tmp_path):
        """Regression: tx_abort while no TX active left _tx_abort_event set,
        causing the next tx_message to be discarded by the top-of-loop check."""
        cfg = _cfg(tmp_path)
        mock_stt, mock_tts = _make_base_mocks()
        mock_ptt = _mock_ptt()
        fake_play, stop_event, _ = _make_play_mocks()

        short_audio = np.zeros(160, dtype=np.int16)  # 10 ms

        async def _synth(*_args, **_kwargs):
            return short_audio, 16000

        mock_tts.synthesize_to_buffer = _synth

        with _auth_patches():
            with (
                patch("backend.server.ServerConfig.load", return_value=cfg),
                patch("backend.server.STTWorker", return_value=mock_stt),
                patch("backend.server.TTSSynthesizer", return_value=mock_tts),
                patch("backend.server.make_ptt", return_value=mock_ptt),
                patch("backend.server._load_voice", return_value=MagicMock()),
                patch("backend.server._play_voice_blocking", fake_play),
                patch("backend.server.sd.stop", side_effect=stop_event.set),
            ):
                with TestClient(app) as tc:
                    with tc.websocket_connect(WS_URL) as ws:
                        _drain_initial(ws)

                        # Abort while idle — server has nothing to interrupt.
                        ws.send_json({"type": "tx_abort"})
                        idle = ws.receive_json()
                        assert idle == {"type": "tx_status", "status": "idle"}

                        # The next tx_message must still transmit (not be silently dropped).
                        ws.send_json({"type": "tx_message", "callsign": "W5TST", "text": "after abort"})
                        transmitting = ws.receive_json()
                        assert transmitting == {"type": "tx_status", "status": "transmitting"}, (
                            "tx_message after idle abort was silently discarded"
                        )
