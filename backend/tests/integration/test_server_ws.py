"""Integration tests for the Radio-TTY WebSocket server.

Uses Starlette's in-process TestClient — no audio hardware or real ML models
required.  STTWorker and TTSSynthesizer are mocked so the suite covers the
WebSocket protocol and server orchestration logic only.

Running:
    cd /mnt/storage/Repos/Radio-TTY
    python -m pytest backend/tests/integration/ -v
"""
from __future__ import annotations

import threading
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from backend.config import ServerConfig
from backend.server import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _minimal_cfg(tmp_path: Path, *, listen_only: bool = False) -> ServerConfig:
    contacts_file = tmp_path / "contacts.json"
    contacts_file.write_text("[]")
    return ServerConfig({
        "callsign": "W5TST",
        "name": "Test Op",
        "location": "Test City",
        "voice": "fake_voice",
        "contacts_file": str(contacts_file),
        "listen_only": listen_only,
    })


def _make_mocks():
    mock_stt = MagicMock()
    mock_stt.join = AsyncMock()
    mock_stt.channel_busy = MagicMock(is_set=MagicMock(return_value=False))
    mock_tts = MagicMock()
    mock_tts.synthesize_to_buffer = AsyncMock(return_value=(None, None))
    return mock_stt, mock_tts


def _make_auth_mocks(*, listen_only: bool = False):
    mock_users = MagicMock()
    mock_users.is_empty.return_value = False
    mock_users.get.return_value = {
        "id": "test-user",
        "display_name": "Test Operator",
        "is_admin": True,
        "prefs": {"listen_only": listen_only} if listen_only else {},
    }
    mock_users.get_public_one.return_value = {"display_name": "Test Operator"}

    mock_tokens = MagicMock()
    mock_tokens.validate.return_value = "test-user"
    mock_tokens.purge_expired.return_value = 0
    return mock_users, mock_tokens


WS_URL = "/ws?token=test"


@pytest.fixture
def client(tmp_path):
    cfg = _minimal_cfg(tmp_path)
    mock_stt, mock_tts = _make_mocks()
    mock_users, mock_tokens = _make_auth_mocks()
    with (
        patch("backend.server.ServerConfig.load", return_value=cfg),
        patch("backend.server.STTWorker", return_value=mock_stt),
        patch("backend.server.TTSSynthesizer", return_value=mock_tts),
        patch("backend.server.UsersStore", return_value=mock_users),
        patch("backend.server.TokenStore", return_value=mock_tokens),
        patch("backend.auth_routes.init"),
    ):
        with TestClient(app) as tc:
            yield tc


@pytest.fixture
def listen_only_client(tmp_path):
    cfg = _minimal_cfg(tmp_path, listen_only=True)
    mock_stt, mock_tts = _make_mocks()
    mock_users, mock_tokens = _make_auth_mocks(listen_only=True)
    with (
        patch("backend.server.ServerConfig.load", return_value=cfg),
        patch("backend.server.STTWorker", return_value=mock_stt),
        patch("backend.server.TTSSynthesizer", return_value=mock_tts),
        patch("backend.server.UsersStore", return_value=mock_users),
        patch("backend.server.TokenStore", return_value=mock_tokens),
        patch("backend.auth_routes.init"),
    ):
        with TestClient(app) as tc:
            yield tc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _drain_initial(ws, limit: int = 10) -> list[dict]:
    """Drain the burst of initial frames every new connection receives.

    The server sends: status, user_profile, contacts, session_attendance,
    pending_stations, voices_list (and optionally online_status).  Stop when
    voices_list is seen so tests start from a clean slate.
    """
    frames = []
    for _ in range(limit):
        msg = ws.receive_json()
        frames.append(msg)
        if msg.get("type") == "voices_list":
            break
    return frames


def _drain_until_idle(ws, limit: int = 25) -> list[dict]:
    """Collect frames until tx_status:idle arrives; return all collected."""
    collected = []
    for _ in range(limit):
        msg = ws.receive_json()
        collected.append(msg)
        if msg.get("type") == "tx_status" and msg.get("status") == "idle":
            break
    return collected


# ---------------------------------------------------------------------------
# HTTP health endpoint
# ---------------------------------------------------------------------------

class TestHealth:
    def test_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}


# ---------------------------------------------------------------------------
# WebSocket — initial connection frames
# ---------------------------------------------------------------------------

class TestWebSocketConnection:
    def test_initial_message_is_status(self, client):
        with client.websocket_connect(WS_URL) as ws:
            msg = ws.receive_json()
            assert msg["type"] == "status"
            assert "radio_connected" in msg
            assert "channel_clear" in msg
            assert "volume_ok" in msg
            assert "monitor_enabled" in msg

    def test_radio_connected_reflects_mock_stt_healthy(self, client):
        with client.websocket_connect(WS_URL) as ws:
            msg = ws.receive_json()
            # STTWorker is running (mock, no error) → connected = True
            assert msg["radio_connected"] is True

    def test_second_message_is_user_profile(self, client):
        with client.websocket_connect(WS_URL) as ws:
            ws.receive_json()  # status
            msg = ws.receive_json()
            assert msg["type"] == "user_profile"

    def test_contacts_message_is_sent_on_connect(self, client):
        with client.websocket_connect(WS_URL) as ws:
            frames = _drain_initial(ws)
            types = [f["type"] for f in frames]
            assert "contacts" in types

    def test_initial_contacts_list_is_empty(self, client):
        with client.websocket_connect(WS_URL) as ws:
            frames = _drain_initial(ws)
            contacts_frame = next(f for f in frames if f["type"] == "contacts")
            assert contacts_frame["contacts"] == []


# ---------------------------------------------------------------------------
# tx_message — validation
# ---------------------------------------------------------------------------

class TestTxMessageValidation:
    def test_missing_callsign_field_returns_error(self, client):
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "tx_message", "text": "hello"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "callsign" in msg["detail"].lower()

    def test_whitespace_only_callsign_returns_error(self, client):
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "tx_message", "callsign": "   ", "text": "hello"})
            msg = ws.receive_json()
            assert msg["type"] == "error"

    def test_listen_only_mode_rejects_tx(self, listen_only_client):
        with listen_only_client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "tx_message", "callsign": "W5TST", "text": "hello"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "listen" in msg["detail"].lower()


# ---------------------------------------------------------------------------
# tx_message — happy path
# ---------------------------------------------------------------------------

class TestTxMessageFlow:
    def test_valid_tx_broadcasts_transmitting_then_idle(self, client):
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "tx_message", "callsign": "W5TST", "text": "hello"})
            # tx_status:transmitting arrives from the WS handler immediately;
            # tx_echo arrives from the pump before synthesis; tx_status:idle
            # arrives from the finally block after synthesis completes.
            frames = _drain_until_idle(ws)
            types = [f["type"] for f in frames]
            assert "tx_status" in types
            assert frames[0] == {"type": "tx_status", "status": "transmitting"}
            assert frames[-1] == {"type": "tx_status", "status": "idle"}

    def test_stt_worker_paused_during_tx_and_resumed_after(self, tmp_path):
        """STTWorker.pause() must be called before synthesis and .resume()
        after, so the radio receiver doesn't transcribe TTS audio that bleeds
        back through the radio while transmitting."""
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()
        pause_order: list[str] = []
        resume_event = threading.Event()

        mock_stt.pause.side_effect = lambda: pause_order.append("pause")

        def _on_resume():
            pause_order.append("resume")
            resume_event.set()

        mock_stt.resume.side_effect = _on_resume

        async def _synth_with_order(*_args, **_kwargs):
            pause_order.append("synth")
            return None, None

        mock_tts.synthesize_to_buffer = _synth_with_order

        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
            patch("backend.server.make_ptt", return_value=MagicMock()),
            patch("piper.PiperVoice"),
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    ws.send_json({"type": "tx_message", "callsign": "W5TST", "text": "hello"})
                    _drain_until_idle(ws)
                # WS closed; wait for the server's 0.2 s post-TX sleep then resume().
                # resume_event is set by _on_resume() inside the background event loop.
                resume_event.wait(timeout=2.0)

        assert "pause" in pause_order, "pause() was never called"
        assert "synth" in pause_order, "synthesize_to_buffer was never called"
        assert "resume" in pause_order, "resume() was never called"
        assert pause_order.index("pause") < pause_order.index("synth")
        assert pause_order.index("synth") < pause_order.index("resume")

    def test_tx_broadcast_reaches_second_client(self, client):
        with (
            client.websocket_connect(WS_URL) as ws1,
            client.websocket_connect(WS_URL) as ws2,
        ):
            _drain_initial(ws1)
            _drain_initial(ws2)
            ws1.send_json({"type": "tx_message", "callsign": "W5TST", "text": "hello"})
            # Both clients should see the transmitting broadcast.
            msg1 = ws1.receive_json()
            msg2 = ws2.receive_json()
            assert msg1["type"] == "tx_status"
            assert msg1["status"] == "transmitting"
            assert msg2["type"] == "tx_status"
            assert msg2["status"] == "transmitting"


# ---------------------------------------------------------------------------
# add_contact
# ---------------------------------------------------------------------------

class TestAddContact:
    def test_valid_contact_is_broadcast_to_client(self, client):
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({
                "type": "add_contact",
                "callsign": "W9FOO",
                "name": "Foo Operator",
            })
            msg = ws.receive_json()
            assert msg["type"] == "contacts"
            callsigns = [c["callsign"] for c in msg["contacts"]]
            assert "W9FOO" in callsigns

    def test_callsign_is_uppercased_in_store(self, client):
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "add_contact", "callsign": "w9foo", "name": "Lower"})
            msg = ws.receive_json()
            assert msg["type"] == "contacts"
            callsigns = [c["callsign"] for c in msg["contacts"]]
            assert "W9FOO" in callsigns

    def test_add_contact_without_callsign_returns_error(self, client):
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "add_contact", "name": "No Callsign"})
            msg = ws.receive_json()
            assert msg["type"] == "error"

    def test_add_contact_broadcast_reaches_second_client(self, client):
        with (
            client.websocket_connect(WS_URL) as ws1,
            client.websocket_connect(WS_URL) as ws2,
        ):
            _drain_initial(ws1)
            _drain_initial(ws2)
            ws1.send_json({"type": "add_contact", "callsign": "W9BAR", "name": "Bar"})
            msg1 = ws1.receive_json()
            msg2 = ws2.receive_json()
            assert msg1["type"] == "contacts"
            assert msg2["type"] == "contacts"
            assert any(c["callsign"] == "W9BAR" for c in msg1["contacts"])
            assert any(c["callsign"] == "W9BAR" for c in msg2["contacts"])
