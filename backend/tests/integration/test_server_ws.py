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


def _make_auth_mocks(*, listen_only: bool = False, is_admin: bool = True):
    mock_users = MagicMock()
    mock_users.is_empty.return_value = False
    mock_users.get.return_value = {
        "id": "test-user",
        "display_name": "Test Operator",
        "is_admin": is_admin,
        "prefs": {"listen_only": listen_only} if listen_only else {},
    }
    mock_users.get_public_one.return_value = {"display_name": "Test Operator"}

    mock_tokens = MagicMock()
    mock_tokens.validate.return_value = "test-user"
    mock_tokens.purge_expired.return_value = 0
    return mock_users, mock_tokens


WS_URL = "/ws?token=test"


@contextmanager
def _ws_server(tmp_path, *, is_admin: bool = True):
    """Spin up the app with mocked deps and yield (TestClient, cfg).

    cfg.save is stubbed so handlers that persist config don't touch the real
    config file, and sd.query_devices is stubbed so device enumeration is
    deterministic without audio hardware.
    """
    cfg = _minimal_cfg(tmp_path)
    cfg.save = MagicMock()
    mock_stt, mock_tts = _make_mocks()
    mock_users, mock_tokens = _make_auth_mocks(is_admin=is_admin)
    fake_devices = [
        {"name": "Built-in Output", "max_input_channels": 0, "max_output_channels": 2},
        {"name": "USB CODEC", "max_input_channels": 1, "max_output_channels": 2},
    ]
    with (
        patch("backend.server.ServerConfig.load", return_value=cfg),
        patch("backend.server.STTWorker", return_value=mock_stt),
        patch("backend.server.TTSSynthesizer", return_value=mock_tts),
        patch("backend.server.UsersStore", return_value=mock_users),
        patch("backend.server.TokenStore", return_value=mock_tokens),
        patch("backend.auth_routes.init"),
        patch("backend.server.sd.query_devices", return_value=fake_devices),
    ):
        with TestClient(app) as tc:
            yield tc, cfg


def _next_of_type(ws, msg_type: str, limit: int = 15) -> dict | None:
    """Receive frames until one matching msg_type arrives; return it (or None)."""
    for _ in range(limit):
        msg = ws.receive_json()
        if msg.get("type") == msg_type:
            return msg
    return None


@pytest.fixture
def non_admin_client(tmp_path):
    cfg = _minimal_cfg(tmp_path)
    cfg.save = MagicMock()
    mock_stt, mock_tts = _make_mocks()
    mock_users, mock_tokens = _make_auth_mocks(is_admin=False)
    with (
        patch("backend.server.ServerConfig.load", return_value=cfg),
        patch("backend.server.STTWorker", return_value=mock_stt),
        patch("backend.server.TTSSynthesizer", return_value=mock_tts),
        patch("backend.server.UsersStore", return_value=mock_users),
        patch("backend.server.TokenStore", return_value=mock_tokens),
        patch("backend.auth_routes.init"),
    ):
        with TestClient(app) as tc:
            yield tc, cfg


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

    def test_operator_tx_transmits_even_when_channel_busy(self, tmp_path):
        """An operator-initiated tx_message overrides the channel-busy squelch
        guard (consistent with the voice-test path): the operator decides when
        to key. Auto station-ID still respects a busy channel — covered
        separately."""
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_stt.channel_busy = MagicMock(is_set=MagicMock(return_value=True))
        synth_called = threading.Event()

        async def _synth(*_args, **_kwargs):
            synth_called.set()
            return None, None

        mock_tts.synthesize_to_buffer = _synth
        mock_users, mock_tokens = _make_auth_mocks()
        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
            patch("backend.server.make_ptt", return_value=MagicMock()),
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    ws.send_json({"type": "tx_message", "callsign": "W5TST", "text": "hello"})
                    frames = _drain_until_idle(ws)
        types = [f["type"] for f in frames]
        assert "tx_echo" in types, "operator TX was discarded despite channel-busy override"
        assert synth_called.is_set(), "synthesis never ran — TX was discarded"

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


# ---------------------------------------------------------------------------
# set_server_config — saved_phrases
# ---------------------------------------------------------------------------

class TestSetServerConfigSavedPhrases:
    """Validate saved_phrases handling in set_server_config.

    _config.save() is patched throughout because /data is not writable in the
    test environment.
    """

    def _send_and_get_status(self, ws, phrases):
        with patch("backend.config.ServerConfig.save"):
            ws.send_json({"type": "set_server_config", "saved_phrases": phrases})
            return ws.receive_json()

    def test_valid_phrases_reflected_in_status(self, client):
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            msg = self._send_and_get_status(ws, ["roger that", "QSL"])
            assert msg["type"] == "status"
            assert msg["saved_phrases"] == ["roger that", "QSL"]

    def test_whitespace_only_entries_filtered_out(self, client):
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            msg = self._send_and_get_status(ws, ["  ", "over", ""])
            assert msg["saved_phrases"] == ["over"]

    def test_phrases_trimmed(self, client):
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            msg = self._send_and_get_status(ws, ["  roger that  "])
            assert msg["saved_phrases"] == ["roger that"]

    def test_non_list_payload_ignored(self, client):
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            initial = self._send_and_get_status(ws, ["baseline"])
            assert initial["saved_phrases"] == ["baseline"]
            # Send non-list — should be silently ignored
            with patch("backend.config.ServerConfig.save"):
                ws.send_json({"type": "set_server_config", "saved_phrases": "not a list"})
                msg = ws.receive_json()
            assert msg["saved_phrases"] == ["baseline"]

    def test_list_with_non_string_entries_ignored(self, client):
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            initial = self._send_and_get_status(ws, ["baseline"])
            assert initial["saved_phrases"] == ["baseline"]
            with patch("backend.config.ServerConfig.save"):
                ws.send_json({"type": "set_server_config", "saved_phrases": [1, 2, 3]})
                msg = ws.receive_json()
            assert msg["saved_phrases"] == ["baseline"]

    def test_list_capped_at_fifty(self, client):
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            sixty = [f"phrase {i}" for i in range(60)]
            msg = self._send_and_get_status(ws, sixty)
            assert len(msg["saved_phrases"]) == 50
            assert msg["saved_phrases"] == [f"phrase {i}" for i in range(50)]

    def test_phrase_truncated_at_120_chars(self, client):
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            long_phrase = "x" * 200
            msg = self._send_and_get_status(ws, [long_phrase])
            assert msg["saved_phrases"] == ["x" * 120]


# ---------------------------------------------------------------------------
# Audio output device (drives the radio) — listing, setting, admin gating
# ---------------------------------------------------------------------------

class TestOutputDevice:
    def test_list_output_devices_returns_output_capable_devices(self, tmp_path):
        with _ws_server(tmp_path) as (tc, _cfg):
            with tc.websocket_connect(WS_URL) as ws:
                _drain_initial(ws)
                ws.send_json({"type": "list_output_devices"})
                msg = _next_of_type(ws, "output_devices")
        assert msg is not None, "no output_devices reply received"
        labels = [d["label"] for d in msg["devices"]]
        # System Default plus the two output-capable devices from the stub.
        assert labels == ["System Default (speaker)", "Built-in Output", "USB CODEC"]
        assert msg["current_output_device"] == -1

    def test_set_output_device_updates_config_and_status(self, tmp_path):
        with _ws_server(tmp_path) as (tc, cfg):
            with tc.websocket_connect(WS_URL) as ws:
                _drain_initial(ws)
                ws.send_json({"type": "set_output_device", "output_device": 1})
                status = _next_of_type(ws, "status")
        assert cfg["output_device"] == 1
        assert cfg.save.called
        assert status is not None and status["output_device"] == 1

    def test_set_output_device_rejected_for_non_admin(self, non_admin_client):
        tc, cfg = non_admin_client
        with tc.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "set_output_device", "output_device": 1})
            err = _next_of_type(ws, "error")
        assert err is not None and "admin" in err["detail"].lower()
        assert "output_device" not in cfg
        assert not cfg.save.called

    def test_set_input_device_rejected_for_non_admin(self, non_admin_client):
        tc, cfg = non_admin_client
        with tc.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "set_input_device", "input_device": 2})
            err = _next_of_type(ws, "error")
        assert err is not None and "admin" in err["detail"].lower()
        assert cfg.get("input_device", -1) == -1
        assert not cfg.save.called


class TestListJournals:
    """Regression coverage for the journals handler.

    `Path` was referenced in the list_journals handler but never imported at
    module scope (only locally, under the alias `_Path`, in a different
    function).  With >=1 journal present the handler raised
    NameError('Path'), which propagated out of the WS receive loop and closed
    the connection — and the frontend sends list_journals on connect, so the
    socket died in a reconnect loop and never processed tx_message (TTS).
    """

    def test_list_journals_with_entry_does_not_crash_connection(self, tmp_path):
        from backend.persistence.journal import save_journal
        from starlette.websockets import WebSocketDisconnect

        msg = None
        with _ws_server(tmp_path) as (tc, cfg):
            cfg["journals_dir"] = str(tmp_path / "journals")
            save_journal("Net Title", "summary", [], "transcript", cfg.journals_dir)
            with tc.websocket_connect(WS_URL) as ws:
                _drain_initial(ws)
                ws.send_json({"type": "list_journals"})
                try:
                    msg = _next_of_type(ws, "journals")
                except WebSocketDisconnect:
                    pytest.fail(
                        "WS connection crashed handling list_journals "
                        "(NameError: name 'Path' is not defined?)"
                    )
        assert msg is not None, "connection died before sending journals (NameError?)"
        assert len(msg["journals"]) == 1
        assert msg["journals"][0]["published"] is False


# ---------------------------------------------------------------------------
# _resolve_tx_voice — map a display name to that user's (voice, length_scale)
# ---------------------------------------------------------------------------

class TestResolveTxVoice:
    @staticmethod
    def _store(profile):
        store = MagicMock()
        store.get_by_display_name.return_value = profile
        return store

    def test_resolves_named_user_prefs(self):
        import backend.server as srv
        store = self._store({"prefs": {"tts_voice": "alice.onnx", "tts_length_scale": 1.3}})
        with patch.object(srv, "_users_store", store):
            assert srv._resolve_tx_voice("Alice") == ("alice.onnx", 1.3)
        store.get_by_display_name.assert_called_once_with("Alice")

    def test_unknown_name_returns_none(self):
        import backend.server as srv
        with patch.object(srv, "_users_store", self._store(None)):
            assert srv._resolve_tx_voice("Nobody") == (None, None)

    def test_sentinel_prefs_fall_through_to_none(self):
        # tts_voice="" and tts_length_scale=0 are the DEFAULT_PREFS "inherit
        # station default" sentinels — they must resolve to (None, None).
        import backend.server as srv
        store = self._store({"prefs": {"tts_voice": "", "tts_length_scale": 0}})
        with patch.object(srv, "_users_store", store):
            assert srv._resolve_tx_voice("Alice") == (None, None)

    def test_no_store_returns_none(self):
        import backend.server as srv
        with patch.object(srv, "_users_store", None):
            assert srv._resolve_tx_voice("Alice") == (None, None)


# ---------------------------------------------------------------------------
# chat_message — chat-only path (broadcast to log, never keyed over the radio)
# ---------------------------------------------------------------------------

class TestChatMessage:
    def test_chat_message_broadcasts_chat_echo_to_all(self, client):
        with (
            client.websocket_connect(WS_URL) as ws1,
            client.websocket_connect(WS_URL) as ws2,
        ):
            _drain_initial(ws1)
            _drain_initial(ws2)
            ws1.send_json({"type": "chat_message", "text": "meet at noon",
                           "callsign": "W5TST", "operator": "Op"})
            m1 = _next_of_type(ws1, "chat_echo")
            m2 = _next_of_type(ws2, "chat_echo")
        assert m1 is not None and m1["text"] == "meet at noon"
        assert m2 is not None and m2["text"] == "meet at noon"

    def test_empty_chat_message_ignored(self, client):
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "chat_message", "text": "   ",
                          "callsign": "W5TST", "operator": "Op"})
            ws.send_json({"type": "chat_message", "text": "real",
                          "callsign": "W5TST", "operator": "Op"})
            msg = _next_of_type(ws, "chat_echo")
        # The whitespace-only message must produce no chat_echo, so the first
        # echo we see is the second ("real") message.
        assert msg is not None and msg["text"] == "real"

    def test_chat_message_does_not_synthesize_or_key_ptt(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()
        mock_ptt = MagicMock()
        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
            patch("backend.server.make_ptt", return_value=mock_ptt),
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    ws.send_json({"type": "chat_message", "text": "hello",
                                  "callsign": "W5TST", "operator": "Op"})
                    msg = _next_of_type(ws, "chat_echo")
        assert msg is not None
        mock_tts.synthesize_to_buffer.assert_not_called()
        mock_ptt.key.assert_not_called()

    def test_chat_profanity_masked_for_filtering_recipient(self, client):
        # Default profile prefs -> filter_profanity True.
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "chat_message", "text": "oh shit",
                          "callsign": "W5TST", "operator": "Op"})
            msg = _next_of_type(ws, "chat_echo")
        assert msg is not None and msg["text"] == "oh s***"

    def test_chat_raw_when_filter_disabled(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()
        mock_users.get.return_value = {
            "id": "test-user", "display_name": "Test Operator",
            "is_admin": True, "prefs": {"filter_profanity": False},
        }
        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    ws.send_json({"type": "chat_message", "text": "oh shit",
                                  "callsign": "W5TST", "operator": "Op"})
                    msg = _next_of_type(ws, "chat_echo")
        assert msg is not None and msg["text"] == "oh shit"

    def test_listen_only_rejects_chat(self, listen_only_client):
        with listen_only_client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "chat_message", "text": "hello",
                          "callsign": "W5TST", "operator": "Op"})
            msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "listen" in msg["detail"].lower()


# ---------------------------------------------------------------------------
# tx_message + voice_as — voice as the *named* user, not the sender
# ---------------------------------------------------------------------------

class TestTxMessageVoiceAs:
    @staticmethod
    def _run(cfg, mock_users, voice_as):
        mock_stt, mock_tts = _make_mocks()
        _, mock_tokens = _make_auth_mocks()
        loaded: list[str] = []
        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
            patch("backend.server.make_ptt", return_value=MagicMock()),
            patch("backend.server._load_voice",
                  side_effect=lambda v: loaded.append(v) or MagicMock()),
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    ws.send_json({"type": "tx_message", "callsign": "W5TST",
                                  "text": "hello", "voice_as": voice_as})
                    _drain_until_idle(ws)
        return loaded

    def test_voice_as_uses_named_user_voice(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_users, _ = _make_auth_mocks()
        mock_users.get_by_display_name.return_value = {
            "display_name": "Alice",
            "prefs": {"tts_voice": "alice.onnx", "tts_length_scale": 1.5},
        }
        loaded = self._run(cfg, mock_users, "Alice")
        assert "alice.onnx" in loaded

    def test_voice_as_unknown_falls_back_to_station_voice(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)  # cfg.voice == "fake_voice"
        mock_users, _ = _make_auth_mocks()
        mock_users.get_by_display_name.return_value = None
        loaded = self._run(cfg, mock_users, "Ghost")
        assert "fake_voice" in loaded
