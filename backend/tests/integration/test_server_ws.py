"""Integration tests for the Hearthwave WebSocket server.

Uses Starlette's in-process TestClient — no audio hardware or real ML models
required.  STTWorker and TTSSynthesizer are mocked so the suite covers the
WebSocket protocol and server orchestration logic only.

Running:
    cd /mnt/storage/Repos/Radio-TTY
    python -m pytest backend/tests/integration/ -v
"""
from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from backend.config import ServerConfig
from backend.server import app, StreamHistory


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
        "presence_file": str(tmp_path / "presence.json"),
        "family_file": str(tmp_path / "family.json"),
        "incidents_file": str(tmp_path / "incidents.json"),
        "listen_only": listen_only,
    })


def _make_mocks():
    mock_stt = MagicMock()
    mock_stt.join = AsyncMock()
    mock_stt.channel_busy = MagicMock(is_set=MagicMock(return_value=False))
    mock_tts = MagicMock()
    mock_tts.synthesize_to_buffer = AsyncMock(return_value=(None, None))
    return mock_stt, mock_tts


def _make_auth_mocks(*, listen_only: bool = False, is_admin: bool = True, role: str | None = None,
                      coordinator: bool = False):
    if role is None:
        role = "admin" if is_admin else "adult"
    prefs: dict = {}
    if listen_only:
        prefs["listen_only"] = listen_only
    if coordinator:
        prefs["neighborhood_coordinator"] = True
    mock_users = MagicMock()
    mock_users.is_empty.return_value = False
    mock_users.get.return_value = {
        "id": "test-user",
        "display_name": "Test Operator",
        "is_admin": is_admin,
        "role": role,
        "prefs": prefs,
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


@pytest.fixture
def kid_client(tmp_path):
    """Connected as a role="kid" user — server-enforced pref locks apply."""
    cfg = _minimal_cfg(tmp_path)
    mock_stt, mock_tts = _make_mocks()
    mock_users, mock_tokens = _make_auth_mocks(is_admin=False, role="kid")
    mock_users.get.return_value["prefs"] = {"quick_messages": ["I'm home"]}
    mock_users.update_prefs.return_value = {
        "id": "test-user",
        "display_name": "Test Operator",
        "is_admin": False,
        "role": "kid",
        "prefs": {
            "dark_mode": True,
            "filter_profanity": True,
            "ui_level": "simple",
            "listen_only": False,
        },
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
            yield tc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _drain_initial(ws, limit: int = 12) -> list[dict]:
    """Drain the burst of initial frames every new connection receives.

    The server sends: status, user_profile, contacts, session_attendance,
    pending_stations, family_presence, family_reminders (non-kid),
    neighborhood_state, neighborhood_incidents, voices_list, chat_history
    (and optionally online_status). Stop when chat_history is seen so tests
    start from a clean slate.
    """
    frames = []
    for _ in range(limit):
        msg = ws.receive_json()
        frames.append(msg)
        if msg.get("type") == "chat_history":
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
        body = resp.json()
        assert body["ok"] is True
        assert "version" in body

    def test_health_reports_version(self, client):
        """/health returns ok plus the backend package version."""
        import backend

        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["version"] == backend.__version__
        assert isinstance(backend.__version__, str) and body["version"]


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
# save_user_prefs — aac_grid validation
# ---------------------------------------------------------------------------

class TestSaveUserPrefsAacGrid:
    def test_aac_grid_oversized_returns_error(self, client):
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            huge = {"version": 1, "categories": [
                {"id": f"c{i}", "name": "x" * 200, "emoji": "⭐", "buttons": []}
                for i in range(400)
            ]}
            ws.send_json({"type": "save_user_prefs", "prefs": {"aac_grid": huge}})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "aac_grid" in msg["detail"]

    def test_aac_grid_non_dict_returns_error(self, client):
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "save_user_prefs", "prefs": {"aac_grid": ["not", "a", "dict"]}})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "aac_grid" in msg["detail"]


# ---------------------------------------------------------------------------
# save_user_prefs — ui_level / font_scale / high_contrast validation
# ---------------------------------------------------------------------------

class TestSaveUserPrefsUiLevelAndA11y:
    def test_valid_values_saved_and_reflected(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()
        mock_users.update_prefs.return_value = {
            "id": "test-user",
            "display_name": "Test Operator",
            "is_admin": True,
            "prefs": {"ui_level": "operator", "font_scale": 1.5, "high_contrast": True},
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
                    ws.send_json({"type": "save_user_prefs",
                                  "prefs": {"ui_level": "operator", "font_scale": 1.5, "high_contrast": True}})
                    msg = _next_of_type(ws, "user_profile")
        assert msg is not None
        assert msg["profile"]["prefs"]["ui_level"] == "operator"
        assert msg["profile"]["prefs"]["font_scale"] == 1.5
        assert msg["profile"]["prefs"]["high_contrast"] is True
        mock_users.update_prefs.assert_called_once_with(
            "test-user",
            {"ui_level": "operator", "font_scale": 1.5, "high_contrast": True},
        )

    def test_rejects_bad_values_but_valid_key_still_applied(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()
        mock_users.update_prefs.return_value = {
            "id": "test-user",
            "display_name": "Test Operator",
            "is_admin": True,
            "prefs": {"ui_level": "operator", "font_scale": 1},
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
                    # Invalid values -> silently dropped; nothing valid left,
                    # so this request produces no reply at all.
                    ws.send_json({"type": "save_user_prefs",
                                  "prefs": {"ui_level": "root", "font_scale": 9}})
                    # A subsequent request with a valid value still goes through.
                    ws.send_json({"type": "save_user_prefs", "prefs": {"ui_level": "operator"}})
                    msg = _next_of_type(ws, "user_profile")
        assert msg is not None
        assert msg["profile"]["prefs"]["ui_level"] == "operator"
        assert msg["profile"]["prefs"]["font_scale"] == 1  # unchanged default
        # update_prefs is only ever called once, with the valid key alone —
        # proving the invalid request never reached the store.
        mock_users.update_prefs.assert_called_once_with("test-user", {"ui_level": "operator"})

    def test_high_contrast_rejects_non_bool(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()
        mock_users.update_prefs.return_value = {
            "id": "test-user",
            "display_name": "Test Operator",
            "is_admin": True,
            "prefs": {"dark_mode": True},
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
                    ws.send_json({"type": "save_user_prefs",
                                  "prefs": {"high_contrast": "yes", "dark_mode": True}})
                    msg = _next_of_type(ws, "user_profile")
        assert msg is not None
        assert msg["profile"]["prefs"]["dark_mode"] is True
        mock_users.update_prefs.assert_called_once_with("test-user", {"dark_mode": True})


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
# set_server_config — MeshCore settings sanitization
# ---------------------------------------------------------------------------

@pytest.fixture
def demo_plugin():
    """Register a fake plugin with a config schema, then clean it up. Lets the
    generic plugin-config save path (coercion/clamping/namespace) be exercised."""
    from backend.plugins.base import BasePlugin, ConfigField, PluginManifest
    from backend.plugins.registry import plugin_registry

    plugin = BasePlugin()
    plugin.manifest = PluginManifest(
        id="demo", name="Demo", description="x",
        config_schema=(
            ConfigField("serial_port", "Port", "text", "/dev/ttyUSB0"),
            ConfigField("baud", "Baud", "number", 115200, minimum=1),
            ConfigField("max_packet_length", "Max", "number", 140, minimum=1),
            ConfigField("channel_idx", "Channel", "number", 0, minimum=0),
            ConfigField("prefix_separator", "Sep", "text", ": "),
        ),
    )
    plugin_registry.register(plugin)
    try:
        yield "demo"
    finally:
        plugin_registry._plugins = tuple(p for p in plugin_registry._plugins if p is not plugin)


class TestSetServerConfigPlugins:
    """The generic, namespaced plugin-config save path in set_server_config.

    The frontend sends data["plugins"][id] = {enabled, ...fields}; the backend
    coerces each value against the plugin's declared schema, clamps numbers,
    ignores unknown keys, and reflects the result in the status broadcast.
    """

    def _send(self, ws, plugins):
        with patch("backend.config.ServerConfig.save"):
            ws.send_json({"type": "set_server_config", "plugins": plugins})
            return ws.receive_json()

    def _entry(self, msg, plugin_id="demo"):
        return next(p for p in msg["plugins"] if p["id"] == plugin_id)

    def test_values_stored_and_reflected(self, client, demo_plugin):
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            msg = self._send(ws, {"demo": {
                "serial_port": "/dev/ttyACM0", "baud": 9600,
                "max_packet_length": 200, "channel_idx": 3, "prefix_separator": " > ",
            }})
            cfg = self._entry(msg)["config"]
            assert cfg["serial_port"] == "/dev/ttyACM0"
            assert cfg["baud"] == 9600
            assert cfg["max_packet_length"] == 200
            assert cfg["channel_idx"] == 3
            assert cfg["prefix_separator"] == " > "

    def test_non_numeric_number_ignored(self, client, demo_plugin):
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            self._send(ws, {"demo": {"baud": 9600}})
            msg = self._send(ws, {"demo": {"baud": "not-a-number"}})
            assert self._entry(msg)["config"]["baud"] == 9600  # unchanged

    def test_number_clamped_to_minimum(self, client, demo_plugin):
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            assert self._entry(self._send(ws, {"demo": {"max_packet_length": 0}}))["config"]["max_packet_length"] == 1
            assert self._entry(self._send(ws, {"demo": {"channel_idx": -2}}))["config"]["channel_idx"] == 0

    def test_unknown_key_ignored(self, client, demo_plugin):
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            msg = self._send(ws, {"demo": {"evil": "haxx"}})
            assert "evil" not in self._entry(msg)["config"]

    def test_enabled_flag_reflected(self, client, demo_plugin):
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            assert self._entry(self._send(ws, {"demo": {"enabled": True}}))["enabled"] is True
            assert self._entry(self._send(ws, {"demo": {"enabled": False}}))["enabled"] is False


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


class TestChatHistory:
    def test_history_empty_on_first_connect(self, client):
        with client.websocket_connect(WS_URL) as ws:
            frames = _drain_initial(ws)
        hist = next(f for f in frames if f["type"] == "chat_history")
        assert hist["messages"] == []

    def test_later_client_receives_prior_chat(self, client):
        with client.websocket_connect(WS_URL) as ws1:
            _drain_initial(ws1)
            ws1.send_json({"type": "chat_message", "text": "meet at noon",
                           "callsign": "W5TST", "operator": "Op"})
            assert _next_of_type(ws1, "chat_echo") is not None
            # A client connecting afterwards gets the message in its backfill.
            with client.websocket_connect(WS_URL) as ws2:
                frames = _drain_initial(ws2)
        hist = next(f for f in frames if f["type"] == "chat_history")
        chat = [m for m in hist["messages"] if m["type"] == "chat_echo"]
        assert any(m["text"] == "meet at noon" for m in chat)

    def test_history_masks_profanity_for_filtering_client(self, client):
        # Default prefs -> filter_profanity True, so the backfill is masked too.
        with client.websocket_connect(WS_URL) as ws1:
            _drain_initial(ws1)
            ws1.send_json({"type": "chat_message", "text": "oh shit",
                           "callsign": "W5TST", "operator": "Op"})
            assert _next_of_type(ws1, "chat_echo") is not None
            with client.websocket_connect(WS_URL) as ws2:
                frames = _drain_initial(ws2)
        hist = next(f for f in frames if f["type"] == "chat_history")
        chat = [m for m in hist["messages"] if m["type"] == "chat_echo"]
        assert chat and chat[-1]["text"] == "oh s***"

    def test_admin_clear_broadcasts_and_empties_history(self, client):
        with (
            client.websocket_connect(WS_URL) as ws1,
            client.websocket_connect(WS_URL) as ws2,
        ):
            _drain_initial(ws1)
            _drain_initial(ws2)
            ws1.send_json({"type": "chat_message", "text": "hello there",
                           "callsign": "W5TST", "operator": "Op"})
            assert _next_of_type(ws1, "chat_echo") is not None
            assert _next_of_type(ws2, "chat_echo") is not None
            # Admin clears: both clients get chat_cleared.
            ws1.send_json({"type": "clear_chat"})
            assert _next_of_type(ws1, "chat_cleared") is not None
            assert _next_of_type(ws2, "chat_cleared") is not None
            # A new client now gets an empty backfill.
            with client.websocket_connect(WS_URL) as ws3:
                frames = _drain_initial(ws3)
        hist = next(f for f in frames if f["type"] == "chat_history")
        assert hist["messages"] == []

    def test_non_admin_clear_rejected_and_history_kept(self, non_admin_client):
        tc, _cfg = non_admin_client
        with tc.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "chat_message", "text": "keep me",
                          "callsign": "W5TST", "operator": "Op"})
            assert _next_of_type(ws, "chat_echo") is not None
            ws.send_json({"type": "clear_chat"})
            err = _next_of_type(ws, "error")
            assert err is not None and "admin" in err["detail"].lower()
            # History survived: a fresh connection still sees the message.
            with tc.websocket_connect(WS_URL) as ws2:
                frames = _drain_initial(ws2)
        hist = next(f for f in frames if f["type"] == "chat_history")
        assert any(m.get("text") == "keep me" for m in hist["messages"])

    def test_history_raw_for_non_filtering_client(self, tmp_path):
        # A client with filter_profanity disabled gets unmasked backfill text.
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
                with tc.websocket_connect(WS_URL) as ws1:
                    _drain_initial(ws1)
                    ws1.send_json({"type": "chat_message", "text": "oh shit",
                                   "callsign": "W5TST", "operator": "Op"})
                    assert _next_of_type(ws1, "chat_echo") is not None
                    with tc.websocket_connect(WS_URL) as ws2:
                        frames = _drain_initial(ws2)
        hist = next(f for f in frames if f["type"] == "chat_history")
        chat = [m for m in hist["messages"] if m["type"] == "chat_echo"]
        assert chat and chat[-1]["text"] == "oh shit"


class TestStreamHistoryUnit:
    """Unit tests for the StreamHistory buffer (no server/WS involved)."""

    def test_render_resolves_text_per_filter_pref(self):
        h = StreamHistory()
        h.record_rx({"type": "chat_echo", "ts": "t"}, "oh shit", "oh s***")
        assert h.render_for(filter_profanity=True)[0]["text"] == "oh s***"
        assert h.render_for(filter_profanity=False)[0]["text"] == "oh shit"

    def test_record_plain_round_trips_tx_echo(self):
        h = StreamHistory()
        tx = {"type": "tx_echo", "ts": "t", "callsign": "W5TST",
              "operator": "Op", "text": "going mobile", "target_call": "ALL"}
        h.record_plain(tx)
        out = h.render_for(filter_profanity=True)
        assert out == [tx]  # verbatim, unaffected by filter pref

    def test_record_plain_does_not_alias_caller_dict(self):
        h = StreamHistory()
        tx = {"type": "tx_echo", "text": "orig"}
        h.record_plain(tx)
        tx["text"] = "mutated after record"
        assert h.render_for(filter_profanity=True)[0]["text"] == "orig"

    def test_patch_updates_callsign_spans_of_matching_entry(self):
        h = StreamHistory()
        h.record_rx({"type": "rx_message", "utterance_id": "u1",
                     "callsign_spans": []}, "raw", "raw")
        h.patch("u1", [[0, 5, "W5TST"]])
        assert h.render_for(True)[0]["callsign_spans"] == [[0, 5, "W5TST"]]

    def test_patch_unknown_utterance_is_noop(self):
        h = StreamHistory()
        h.record_rx({"type": "rx_message", "utterance_id": "u1"}, "raw", "raw")
        h.patch("does-not-exist", [[0, 1, "X"]])  # must not raise
        assert "callsign_spans" not in h.render_for(True)[0]

    def test_clear_empties_buffer(self):
        h = StreamHistory()
        h.record_rx({"type": "chat_echo"}, "a", "a")
        h.clear()
        assert h.render_for(True) == []

    def test_cap_evicts_oldest_entries(self):
        h = StreamHistory(max_entries=3)
        for i in range(5):
            h.record_plain({"type": "tx_echo", "text": f"m{i}"})
        out = h.render_for(True)
        assert [m["text"] for m in out] == ["m2", "m3", "m4"]


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


# ---------------------------------------------------------------------------
# rescan_vocabulary — WS handler response
# ---------------------------------------------------------------------------

class TestRescanVocabulary:
    def test_response_includes_term_and_callsign_counts(self, tmp_path):
        """rescan_vocabulary must reply with vocabulary_rescanned carrying
        term_count and callsign_count that reflect the current contacts and
        config.  We add two contacts first, then trigger the rescan."""
        with _ws_server(tmp_path) as (tc, cfg):
            with tc.websocket_connect(WS_URL) as ws:
                _drain_initial(ws)
                # Add two contacts so the callsign_count is non-trivial.
                ws.send_json({"type": "add_contact", "callsign": "W9AAA", "name": "Alpha"})
                _next_of_type(ws, "contacts")
                ws.send_json({"type": "add_contact", "callsign": "W9BBB", "name": "Bravo"})
                _next_of_type(ws, "contacts")
                # Now request a vocabulary rescan.
                ws.send_json({"type": "rescan_vocabulary"})
                reply = _next_of_type(ws, "vocabulary_rescanned")
        assert reply is not None, "no vocabulary_rescanned reply received"
        assert reply["type"] == "vocabulary_rescanned"
        # Two callsigns were added; both are within the default cap of 15.
        assert reply["callsign_count"] == 2
        # term_count must be at least the two callsigns plus CURATED (40 terms).
        assert reply["term_count"] >= 2 + 40

    def test_callsign_count_capped_at_max_callsigns(self, tmp_path):
        """callsign_count must never exceed stt_vocab_max_callsigns."""
        with _ws_server(tmp_path) as (tc, cfg):
            cfg["stt_vocab_max_callsigns"] = 1
            with tc.websocket_connect(WS_URL) as ws:
                _drain_initial(ws)
                ws.send_json({"type": "add_contact", "callsign": "W9AAA", "name": "Alpha"})
                _next_of_type(ws, "contacts")
                ws.send_json({"type": "add_contact", "callsign": "W9BBB", "name": "Bravo"})
                _next_of_type(ws, "contacts")
                ws.send_json({"type": "rescan_vocabulary"})
                reply = _next_of_type(ws, "vocabulary_rescanned")
        assert reply is not None
        assert reply["callsign_count"] == 1


# ---------------------------------------------------------------------------
# Contact mutations trigger _rebuild_stt_vocabulary
# ---------------------------------------------------------------------------

class TestContactMutationTriggersVocabRebuild:
    """add_contact and delete_contact must each cause _rebuild_stt_vocabulary
    to fire, which in turn calls update_phrases on the STT worker.  The
    observable effect is that the mock worker's update_phrases receives the
    new (or reduced) callsign in the phrase list."""

    @staticmethod
    def _run_with_mock_stt(tmp_path):
        """Spin up the app with an instrumented STT mock and return it alongside
        a factory for making WS sessions.  Returns (TestClient, mock_stt)."""
        cfg = _minimal_cfg(tmp_path)
        cfg.save = MagicMock()
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()
        return cfg, mock_stt, mock_tts, mock_users, mock_tokens

    def test_add_contact_triggers_rebuild(self, tmp_path):
        """After add_contact the STT worker's update_phrases is called with the
        new callsign included in the phrase list."""
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = self._run_with_mock_stt(tmp_path)
        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
            patch("backend.server.sd.query_devices", return_value=[]),
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    ws.send_json({"type": "add_contact", "callsign": "KE8ZZZ", "name": "Test"})
                    _next_of_type(ws, "contacts")
        # update_phrases must have been called at least once after add_contact.
        # The last call must include the new callsign.
        assert mock_stt.update_phrases.called, "update_phrases was never called after add_contact"
        last_phrases = mock_stt.update_phrases.call_args[0][0]
        assert "KE8ZZZ" in last_phrases, f"KE8ZZZ missing from final phrase list: {last_phrases}"

    def test_delete_contact_triggers_rebuild(self, tmp_path):
        """After delete_contact the STT worker's update_phrases is called and
        the removed callsign is no longer present in the phrase list."""
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = self._run_with_mock_stt(tmp_path)
        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
            patch("backend.server.sd.query_devices", return_value=[]),
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    # Add then immediately remove a contact.
                    ws.send_json({"type": "add_contact", "callsign": "KE8YYY", "name": "Del"})
                    _next_of_type(ws, "contacts")
                    mock_stt.update_phrases.reset_mock()
                    ws.send_json({"type": "delete_contact", "callsign": "KE8YYY"})
                    _next_of_type(ws, "contacts")
        assert mock_stt.update_phrases.called, "update_phrases not called after delete_contact"
        last_phrases = mock_stt.update_phrases.call_args[0][0]
        assert "KE8YYY" not in last_phrases, f"KE8YYY still in phrase list after delete: {last_phrases}"


# ---------------------------------------------------------------------------
# set_server_config — stt_gain_mode
# ---------------------------------------------------------------------------

class TestSetServerConfigSttGainMode:
    """Validate stt_gain_mode handling in set_server_config.

    A valid new mode must be persisted and trigger an STT restart; an invalid
    mode must be silently ignored; a repeated same-mode must not trigger a
    restart.  STTWorker.stop/join/start are mocked throughout so the test does
    not require audio hardware.
    """

    def _send_and_get_status(self, ws, data):
        with patch("backend.config.ServerConfig.save"):
            ws.send_json({"type": "set_server_config", **data})
            return ws.receive_json()

    def test_valid_new_mode_persisted_and_triggers_restart(self, tmp_path):
        """A valid mode change (agc→rms) is written to config and restarts the STT worker."""
        with _ws_server(tmp_path) as (tc, cfg):
            cfg["stt_gain_mode"] = "agc"
            with tc.websocket_connect(WS_URL) as ws:
                _drain_initial(ws)
                with (
                    patch("backend.server._stt_listening", True),
                    patch("backend.server._make_stt_worker") as mock_make,
                    patch("backend.config.ServerConfig.save"),
                ):
                    mock_make.return_value = MagicMock(start=MagicMock(), join=AsyncMock())
                    ws.send_json({"type": "set_server_config", "stt_gain_mode": "rms"})
                    ws.receive_json()  # status broadcast
                assert cfg["stt_gain_mode"] == "rms"

    def test_invalid_mode_is_noop(self, tmp_path):
        """An unrecognized mode must not be written to config."""
        with _ws_server(tmp_path) as (tc, cfg):
            cfg["stt_gain_mode"] = "agc"
            with tc.websocket_connect(WS_URL) as ws:
                _drain_initial(ws)
                msg = self._send_and_get_status(ws, {"stt_gain_mode": "loud"})
                assert msg["type"] == "status"
            assert cfg.get("stt_gain_mode") == "agc"

    def test_unchanged_mode_does_not_trigger_restart(self, tmp_path):
        """Sending the same mode as current must not set stt_restart_needed."""
        with _ws_server(tmp_path) as (tc, cfg):
            cfg["stt_gain_mode"] = "rms"
            with tc.websocket_connect(WS_URL) as ws:
                _drain_initial(ws)
                with (
                    patch("backend.server._stt_listening", True),
                    patch("backend.server._make_stt_worker") as mock_make,
                    patch("backend.config.ServerConfig.save"),
                ):
                    ws.send_json({"type": "set_server_config", "stt_gain_mode": "rms"})
                    ws.receive_json()  # status broadcast
                    mock_make.assert_not_called()


# ---------------------------------------------------------------------------
# set_server_config — whisper_model_final "auto" / large-v3-turbo
# ---------------------------------------------------------------------------

class TestSetServerConfigFinalModelAuto:
    """"auto" and "large-v3-turbo" are valid FINAL model values; turbo must
    NOT be accepted as the fast (streaming) model. Status carries the
    configured value plus a read-only whisper_model_final_resolved."""

    def _set_and_status(self, ws, data):
        with (
            patch("backend.server._stt_listening", False),
            patch("backend.config.ServerConfig.save"),
        ):
            ws.send_json({"type": "set_server_config", **data})
            return ws.receive_json()

    def test_auto_accepted_as_final_model(self, tmp_path):
        with _ws_server(tmp_path) as (tc, cfg):
            cfg["whisper_model_final"] = ""
            with tc.websocket_connect(WS_URL) as ws:
                _drain_initial(ws)
                msg = self._set_and_status(ws, {"whisper_model_final": "auto"})
                assert cfg["whisper_model_final"] == "auto"
                assert msg["whisper_model_final"] == "auto"

    def test_turbo_accepted_as_final_model(self, tmp_path):
        with _ws_server(tmp_path) as (tc, cfg):
            cfg["whisper_model_final"] = ""
            with tc.websocket_connect(WS_URL) as ws:
                _drain_initial(ws)
                self._set_and_status(ws, {"whisper_model_final": "large-v3-turbo"})
                assert cfg["whisper_model_final"] == "large-v3-turbo"

    def test_invalid_final_model_rejected(self, tmp_path):
        with _ws_server(tmp_path) as (tc, cfg):
            cfg["whisper_model_final"] = ""
            with tc.websocket_connect(WS_URL) as ws:
                _drain_initial(ws)
                self._set_and_status(ws, {"whisper_model_final": "bogus-model"})
                assert cfg["whisper_model_final"] == ""

    def test_turbo_rejected_as_fast_model(self, tmp_path):
        with _ws_server(tmp_path) as (tc, cfg):
            cfg["whisper_model"] = "small.en"
            with tc.websocket_connect(WS_URL) as ws:
                _drain_initial(ws)
                self._set_and_status(ws, {"whisper_model": "large-v3-turbo"})
                assert cfg["whisper_model"] == "small.en"

    def test_status_includes_resolved_final_model(self, tmp_path):
        with _ws_server(tmp_path) as (tc, cfg):
            with tc.websocket_connect(WS_URL) as ws:
                _drain_initial(ws)
                worker = MagicMock()
                worker.whisper_model_final = "distil-large-v3"
                with patch("backend.server._stt_worker", worker):
                    msg = self._set_and_status(ws, {})
                assert msg["whisper_model_final_resolved"] == "distil-large-v3"

    def test_resolved_empty_without_worker(self, tmp_path):
        with _ws_server(tmp_path) as (tc, cfg):
            with tc.websocket_connect(WS_URL) as ws:
                _drain_initial(ws)
                with patch("backend.server._stt_worker", None):
                    msg = self._set_and_status(ws, {})
                assert msg["whisper_model_final_resolved"] == ""


# ---------------------------------------------------------------------------
# set_config — fuzzy_callsign_rewrite
# ---------------------------------------------------------------------------

class TestSetConfigFuzzyCallsignRewrite:
    """fuzzy_callsign_rewrite rides the lighter set_config path (station-wide,
    no STT restart) beside fuzzy_callsign, and shows up in the status
    broadcast so the UI toggle round-trips."""

    def test_toggle_persisted_and_broadcast(self, tmp_path):
        with _ws_server(tmp_path) as (tc, cfg):
            with tc.websocket_connect(WS_URL) as ws:
                _drain_initial(ws)
                with patch("backend.config.ServerConfig.save"):
                    ws.send_json({"type": "set_config", "fuzzy_callsign_rewrite": True})
                    msg = ws.receive_json()
                assert cfg["fuzzy_callsign_rewrite"] is True
                assert msg["fuzzy_callsign_rewrite"] is True

    def test_status_defaults_to_false(self, tmp_path):
        with _ws_server(tmp_path) as (tc, cfg):
            with tc.websocket_connect(WS_URL) as ws:
                _drain_initial(ws)
                with patch("backend.config.ServerConfig.save"):
                    ws.send_json({"type": "set_config", "fuzzy_callsign": True})
                    msg = ws.receive_json()
                assert msg["fuzzy_callsign_rewrite"] is False


# ---------------------------------------------------------------------------
# set_server_config — stt_noise_profile
# ---------------------------------------------------------------------------

class TestSetServerConfigNoiseProfile:
    """stt_noise_profile is a worker-construction knob: toggling it must be
    persisted and restart a listening STT worker; a repeated same value must
    not trigger a restart; the status broadcast must carry the current value.
    """

    def test_toggle_persisted_and_triggers_restart(self, tmp_path):
        with _ws_server(tmp_path) as (tc, cfg):
            with tc.websocket_connect(WS_URL) as ws:
                _drain_initial(ws)
                with (
                    patch("backend.server._stt_listening", True),
                    patch("backend.server._make_stt_worker") as mock_make,
                    patch("backend.config.ServerConfig.save"),
                ):
                    mock_make.return_value = MagicMock(start=MagicMock(), join=AsyncMock())
                    ws.send_json({"type": "set_server_config", "stt_noise_profile": True})
                    msg = ws.receive_json()  # status broadcast
                assert cfg["stt_noise_profile"] is True
                assert msg["stt_noise_profile"] is True

    def test_unchanged_value_does_not_trigger_restart(self, tmp_path):
        with _ws_server(tmp_path) as (tc, cfg):
            cfg["stt_noise_profile"] = True
            with tc.websocket_connect(WS_URL) as ws:
                _drain_initial(ws)
                with (
                    patch("backend.server._stt_listening", True),
                    patch("backend.server._make_stt_worker") as mock_make,
                    patch("backend.config.ServerConfig.save"),
                ):
                    ws.send_json({"type": "set_server_config", "stt_noise_profile": True})
                    ws.receive_json()  # status broadcast
                    mock_make.assert_not_called()

    def test_status_defaults_to_false(self, tmp_path):
        with _ws_server(tmp_path) as (tc, cfg):
            with tc.websocket_connect(WS_URL) as ws:
                _drain_initial(ws)
                with patch("backend.config.ServerConfig.save"):
                    ws.send_json({"type": "set_server_config"})
                    msg = ws.receive_json()
                assert msg["stt_noise_profile"] is False


# ---------------------------------------------------------------------------
# set_server_config — vox priming word
# ---------------------------------------------------------------------------

class TestSetServerConfigVoxPrimerWord:
    def _send_and_get_status(self, ws, data):
        with patch("backend.config.ServerConfig.save"):
            ws.send_json({"type": "set_server_config", **data})
            return ws.receive_json()

    def test_word_and_enabled_reflected_in_status(self, client):
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            msg = self._send_and_get_status(
                ws, {"vox_primer_word_enabled": True, "vox_primer_word": "break"}
            )
            assert msg["type"] == "status"
            assert msg["vox_primer_word_enabled"] is True
            assert msg["vox_primer_word"] == "break"

    def test_word_is_trimmed(self, client):
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            msg = self._send_and_get_status(ws, {"vox_primer_word": "  transmit  "})
            assert msg["vox_primer_word"] == "transmit"

    def test_word_capped_at_64_chars(self, client):
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            msg = self._send_and_get_status(ws, {"vox_primer_word": "x" * 100})
            assert msg["vox_primer_word"] == "x" * 64

    def test_status_default_word_is_transmit(self, client):
        with client.websocket_connect(WS_URL) as ws:
            frames = _drain_initial(ws)
            status = next(f for f in frames if f["type"] == "status")
            assert status["vox_primer_word"] == "transmit"
            assert status["vox_primer_word_enabled"] is False

    def test_non_string_word_ignored(self, client):
        # JSON null / numbers must not overwrite the word (str(None) would
        # otherwise make the radio speak the literal "None").
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            for bad in (None, 123, ["transmit"]):
                msg = self._send_and_get_status(ws, {"vox_primer_word": bad})
                assert msg["vox_primer_word"] == "transmit"


class TestTxAppliesPrimerWord:
    def test_enabled_prepends_word_to_synth_text(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        cfg["vox_primer_word_enabled"] = True
        cfg["vox_primer_word"] = "transmit"
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()
        captured: dict[str, str] = {}
        synth_done = threading.Event()

        async def _capture_synth(_voice, text, *_args, **_kwargs):
            captured["text"] = text
            synth_done.set()
            return None, None

        mock_tts.synthesize_to_buffer = _capture_synth

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
                synth_done.wait(timeout=2.0)

        assert "text" in captured, "synthesize_to_buffer was never called"
        assert captured["text"].startswith("transmit. "), captured["text"]

    def test_disabled_does_not_prepend(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)  # word primer off by default
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()
        captured: dict[str, str] = {}
        synth_done = threading.Event()

        async def _capture_synth(_voice, text, *_args, **_kwargs):
            captured["text"] = text
            synth_done.set()
            return None, None

        mock_tts.synthesize_to_buffer = _capture_synth

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
                synth_done.wait(timeout=2.0)

        assert "text" in captured, "synthesize_to_buffer was never called"
        assert not captured["text"].startswith("transmit. "), captured["text"]


# ---------------------------------------------------------------------------
# STT calibration wizard
# ---------------------------------------------------------------------------

class TestCalibrationGetText:
    def test_admin_receives_preamble_text(self, tmp_path):
        with _ws_server(tmp_path) as (tc, cfg):
            with tc.websocket_connect(WS_URL) as ws:
                _drain_initial(ws)
                ws.send_json({"type": "calibration_get_text"})
                msg = ws.receive_json()
                assert msg["type"] == "calibration_text"
                assert "human events" in msg["text"]

    def test_non_admin_rejected(self, non_admin_client):
        tc, cfg = non_admin_client
        with tc.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "calibration_get_text"})
            msg = ws.receive_json()
            assert msg["type"] == "error"


class TestCalibrationStart:
    def test_requires_listening_worker(self, tmp_path):
        with _ws_server(tmp_path) as (tc, cfg):
            with tc.websocket_connect(WS_URL) as ws:
                _drain_initial(ws)
                with patch("backend.server._stt_listening", False):
                    ws.send_json({"type": "calibration_start"})
                    msg = ws.receive_json()
                assert msg["type"] == "calibration_error"

    def test_replies_started_when_listening(self, tmp_path):
        with _ws_server(tmp_path) as (tc, cfg):
            with tc.websocket_connect(WS_URL) as ws:
                _drain_initial(ws)
                with patch("backend.server._stt_listening", True):
                    ws.send_json({"type": "calibration_start"})
                    msg = ws.receive_json()
                assert msg["type"] == "calibration_started"

    def test_non_admin_rejected(self, non_admin_client):
        tc, cfg = non_admin_client
        with tc.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "calibration_start"})
            msg = ws.receive_json()
            assert msg["type"] == "error"


class TestCalibrationStop:
    def test_stop_without_start_errors(self, tmp_path):
        with _ws_server(tmp_path) as (tc, cfg):
            with tc.websocket_connect(WS_URL) as ws:
                _drain_initial(ws)
                ws.send_json({"type": "calibration_stop"})
                msg = ws.receive_json()
                assert msg["type"] == "calibration_error"

    def test_stop_with_too_little_audio_errors(self, tmp_path):
        with _ws_server(tmp_path) as (tc, cfg):
            with tc.websocket_connect(WS_URL) as ws:
                _drain_initial(ws)
                with patch("backend.server._stt_listening", True):
                    ws.send_json({"type": "calibration_start"})
                    ws.receive_json()  # calibration_started
                ws.send_json({"type": "calibration_stop"})
                msg = ws.receive_json()
                assert msg["type"] == "calibration_error"

    def test_stop_with_enough_audio_runs_sweep_and_streams_result(self, tmp_path):
        import numpy as np
        import backend.server as srv

        with _ws_server(tmp_path) as (tc, cfg):
            with tc.websocket_connect(WS_URL) as ws:
                _drain_initial(ws)
                with patch("backend.server._stt_listening", True):
                    ws.send_json({"type": "calibration_start"})
                    ws.receive_json()  # calibration_started
                # Feed >2s of audio directly into the module-level capture.
                # (backend.server.STTWorker is mocked in this fixture, so use
                # the real sample rate literal rather than STTWorker.SAMPLE_RATE.)
                srv._calibration_capture.feed_raw(np.zeros(16000 * 3, dtype=np.float32))
                with (
                    patch("backend.server.load_vad_model", return_value=object()),
                    patch("backend.server.WhisperTranscriber"),
                    patch("backend.server.run_sweep", return_value=[
                        {"model": "small.en", "gain_mode": "agc", "noise_profile": False,
                         "wer": 0.1, "hypothesis": "x"},
                    ]) as mock_sweep,
                ):
                    ws.send_json({"type": "calibration_stop"})
                    msg = _next_of_type(ws, "calibration_result")
                assert msg is not None
                assert msg["recommended"]["model"] == "small.en"
                assert msg["results"][0]["wer"] == 0.1
                mock_sweep.assert_called_once()

    def test_sweep_only_includes_models_staged_on_disk(self, tmp_path):
        import numpy as np
        import backend.server as srv

        models_dir = tmp_path / "Models" / "STT"
        (models_dir / "small.en").mkdir(parents=True)
        (models_dir / "distil-large-v3").mkdir()
        with _ws_server(tmp_path) as (tc, cfg):
            with tc.websocket_connect(WS_URL) as ws:
                _drain_initial(ws)
                with patch("backend.server._stt_listening", True):
                    ws.send_json({"type": "calibration_start"})
                    ws.receive_json()  # calibration_started
                srv._calibration_capture.feed_raw(np.zeros(16000 * 3, dtype=np.float32))
                with (
                    patch("backend.server.STTWorker._MODELS_DIR", models_dir),
                    patch("backend.server.load_vad_model", return_value=object()),
                    patch("backend.server.WhisperTranscriber"),
                    patch("backend.server.run_sweep", return_value=[]) as mock_sweep,
                ):
                    ws.send_json({"type": "calibration_stop"})
                    _next_of_type(ws, "calibration_result")
                assert mock_sweep.call_args.kwargs["models"] == [
                    "distil-large-v3", "small.en",
                ]

    def test_no_staged_models_errors_instead_of_hf_download(self, tmp_path):
        import numpy as np
        import backend.server as srv

        models_dir = tmp_path / "Models" / "STT"
        models_dir.mkdir(parents=True)  # exists but empty: nothing staged
        with _ws_server(tmp_path) as (tc, cfg):
            with tc.websocket_connect(WS_URL) as ws:
                _drain_initial(ws)
                with patch("backend.server._stt_listening", True):
                    ws.send_json({"type": "calibration_start"})
                    ws.receive_json()  # calibration_started
                srv._calibration_capture.feed_raw(np.zeros(16000 * 3, dtype=np.float32))
                with (
                    patch("backend.server.STTWorker._MODELS_DIR", models_dir),
                    patch("backend.server.run_sweep") as mock_sweep,
                ):
                    ws.send_json({"type": "calibration_stop"})
                    msg = _next_of_type(ws, "calibration_error")
                assert msg is not None
                assert "bootstrap_models" in msg["detail"]
                mock_sweep.assert_not_called()

    def test_non_admin_rejected(self, non_admin_client):
        tc, cfg = non_admin_client
        with tc.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "calibration_stop"})
            msg = ws.receive_json()
            assert msg["type"] == "error"


class TestCalibrationApply:
    def test_apply_delegates_to_set_server_config(self, tmp_path):
        with _ws_server(tmp_path) as (tc, cfg):
            with tc.websocket_connect(WS_URL) as ws:
                _drain_initial(ws)
                with (
                    patch("backend.server._stt_listening", False),
                    patch("backend.config.ServerConfig.save"),
                ):
                    ws.send_json({
                        "type": "calibration_apply",
                        "whisper_model": "medium.en",
                        "gain_mode": "rms",
                        "noise_profile": True,
                    })
                    _next_of_type(ws, "status")
                    msg = _next_of_type(ws, "calibration_applied")
                assert msg is not None
                assert cfg["whisper_model"] == "medium.en"
                assert cfg["stt_gain_mode"] == "rms"
                assert cfg["stt_noise_profile"] is True

    def test_non_admin_rejected(self, non_admin_client):
        tc, cfg = non_admin_client
        with tc.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "calibration_apply", "whisper_model": "medium.en"})
            msg = ws.receive_json()
            assert msg["type"] == "error"


# ---------------------------------------------------------------------------
# Role management (admin|adult|kid) — set_role handler + kid pref locking
# ---------------------------------------------------------------------------

class TestRoleHandlers:
    def test_set_role_requires_admin(self, non_admin_client):
        tc, _cfg = non_admin_client
        with tc.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "set_role", "user_id": "other", "role": "kid"})
            msg = _next_of_type(ws, "error")
        assert msg is not None
        assert "admin" in msg["detail"].lower()

    def test_set_role_broadcasts_profiles(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()
        mock_users.set_role.return_value = {"id": "other", "role": "kid", "is_admin": False}
        # Demoting "other" into kid clears their quick_messages (I2 fix) —
        # give update_prefs a well-formed return so _sync_live_state_for_user
        # (which re-derives effective_prefs from it) doesn't choke on a bare
        # MagicMock.
        mock_users.update_prefs.return_value = {
            "id": "other", "role": "kid", "is_admin": False, "prefs": {"quick_messages": []},
        }
        mock_users.get_public.return_value = [
            {"id": "test-user", "role": "admin", "is_admin": True},
            {"id": "other", "role": "kid", "is_admin": False},
        ]
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
                    ws.send_json({"type": "set_role", "user_id": "other", "role": "kid"})
                    msg = _next_of_type(ws, "profiles")
        assert msg is not None
        assert any(p.get("role") == "kid" for p in msg["profiles"])
        mock_users.set_role.assert_called_once_with("other", "kid")

    # -- Phase 3 Task 1 review, Finding 1(a): demoting to kid must also
    #    clear neighborhood_coordinator, not just quick_messages --

    def test_set_role_demote_clears_neighborhood_coordinator(self, tmp_path):
        """A coordinator-adult demoted to kid must have neighborhood_coordinator
        cleared alongside quick_messages — both the update_prefs merge call
        and every read surface fed by the resulting profiles broadcast /
        get_public must show coordinator False."""
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()
        mock_users.set_role.return_value = {"id": "other", "role": "kid", "is_admin": False}
        mock_users.update_prefs.return_value = {
            "id": "other", "role": "kid", "is_admin": False,
            "prefs": {"quick_messages": [], "neighborhood_coordinator": False},
        }
        mock_users.get_public.return_value = [
            {"id": "test-user", "role": "admin", "is_admin": True, "prefs": {}},
            {"id": "other", "role": "kid", "is_admin": False,
             "prefs": {"quick_messages": [], "neighborhood_coordinator": False}},
        ]
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
                    ws.send_json({"type": "set_role", "user_id": "other", "role": "kid"})
                    msg = _next_of_type(ws, "profiles")
        assert msg is not None
        mock_users.update_prefs.assert_called_once_with(
            "other", {"quick_messages": [], "neighborhood_coordinator": False}
        )
        target = next(p for p in msg["profiles"] if p["id"] == "other")
        assert target["prefs"]["neighborhood_coordinator"] is False

    def test_set_role_unknown_role_returns_error(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()
        mock_users.set_role.side_effect = ValueError("unknown role: superuser")
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
                    ws.send_json({"type": "set_role", "user_id": "other", "role": "superuser"})
                    msg = _next_of_type(ws, "error")
        assert msg is not None

    def test_kid_prefs_locked(self, kid_client):
        with kid_client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "save_user_prefs",
                          "prefs": {"filter_profanity": False, "ui_level": "operator",
                                    "listen_only": True, "dark_mode": True}})
            msg = _next_of_type(ws, "user_profile")
        assert msg is not None
        prefs = msg["profile"]["prefs"]
        assert prefs["filter_profanity"] is True
        assert prefs["ui_level"] == "simple"
        assert prefs["dark_mode"] is True      # allowed key applied
        assert prefs["listen_only"] is False   # disallowed key dropped/locked

    def test_kid_connection_prefs_locked_on_connect(self, tmp_path):
        """A kid profile with subverted saved prefs still connects locked."""
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks(is_admin=False, role="kid")
        mock_users.get.return_value["prefs"] = {
            "filter_profanity": False,
            "ui_level": "operator",
            "listen_only": True,
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
                    frames = _drain_initial(ws)
        profile_msg = next(f for f in frames if f.get("type") == "user_profile")
        prefs = profile_msg["profile"]["prefs"]
        assert prefs["filter_profanity"] is True
        assert prefs["ui_level"] == "simple"
        assert prefs["listen_only"] is False

    # -- Finding 2: set_role must not allow an admin to demote themselves --

    def test_set_role_rejects_self_demotion(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()  # admin, id="test-user"
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
                    ws.send_json({"type": "set_role", "user_id": "test-user", "role": "adult"})
                    msg = _next_of_type(ws, "error")
        assert msg is not None
        assert "own" in msg["detail"].lower()
        mock_users.set_role.assert_not_called()

    def test_set_role_allows_admin_to_change_others(self, tmp_path):
        """Sanity check: the self-demotion guard doesn't block changing OTHER users."""
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()  # admin, id="test-user"
        mock_users.set_role.return_value = {"id": "other", "role": "adult", "is_admin": False}
        mock_users.get_public.return_value = []
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
                    ws.send_json({"type": "set_role", "user_id": "other", "role": "adult"})
                    msg = _next_of_type(ws, "profiles")
        assert msg is not None
        mock_users.set_role.assert_called_once_with("other", "adult")

    # -- Finding 1: update_profile must sync role when is_admin changes,
    #    and reject granting is_admin to a kid --

    def test_update_profile_is_admin_rejection_returns_error(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()  # admin caller
        mock_users.update_profile.side_effect = ValueError(
            "Cannot grant admin to a kid profile directly; promote via set_role."
        )
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
                    ws.send_json({"type": "update_profile", "user_id": "kid-1", "is_admin": True})
                    msg = _next_of_type(ws, "error")
        assert msg is not None
        assert "kid" in msg["detail"].lower()

    # -- Phase 2 re-review Finding A: update_profile must not allow an admin
    #    to demote themselves via is_admin: false (would reopen the
    #    sole-admin lockout that set_role's self-demotion guard closed) --

    def test_update_profile_rejects_self_demotion(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()  # admin, id="test-user"
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
                    ws.send_json({"type": "update_profile", "is_admin": False})
                    msg = _next_of_type(ws, "error")
        assert msg is not None
        assert "own" in msg["detail"].lower()
        mock_users.update_profile.assert_not_called()

    def test_update_profile_rejects_self_demotion_with_explicit_user_id(self, tmp_path):
        """Same guard when the admin targets their own id explicitly rather than omitting user_id."""
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()  # admin, id="test-user"
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
                    ws.send_json({"type": "update_profile", "user_id": "test-user", "is_admin": False})
                    msg = _next_of_type(ws, "error")
        assert msg is not None
        assert "own" in msg["detail"].lower()
        mock_users.update_profile.assert_not_called()

    def test_update_profile_allows_self_edit_of_non_role_fields(self, tmp_path):
        """Sanity check: the self-demotion guard doesn't block editing your own other fields."""
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()  # admin, id="test-user"
        mock_users.update_profile.return_value = {
            "id": "test-user", "display_name": "New Name", "is_admin": True, "role": "admin", "prefs": {},
        }
        mock_users.get_public.return_value = []
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
                    ws.send_json({"type": "update_profile", "display_name": "New Name"})
                    msg = _next_of_type(ws, "user_profile")
        assert msg is not None
        mock_users.update_profile.assert_called_once_with("test-user", {"display_name": "New Name"})

    def test_update_profile_allows_demoting_others(self, tmp_path):
        """Sanity check: the self-demotion guard doesn't block demoting OTHER users."""
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()  # admin, id="test-user"
        mock_users.update_profile.return_value = {
            "id": "other", "display_name": "Other", "is_admin": False, "role": "adult", "prefs": {},
        }
        mock_users.get_public.return_value = []
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
                    ws.send_json({"type": "update_profile", "user_id": "other", "is_admin": False})
                    msg = _next_of_type(ws, "profiles")
        assert msg is not None
        mock_users.update_profile.assert_called_once_with("other", {"is_admin": False})

    # -- Finding 4: create_profile with an invalid role must error, not silently drop it --

    def test_create_profile_invalid_role_returns_error(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()  # admin caller
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
                    ws.send_json({
                        "type": "create_profile",
                        "display_name": "New Kid",
                        "password": "pw12345678",
                        "role": "superuser",
                    })
                    msg = _next_of_type(ws, "error")
        assert msg is not None
        mock_users.create.assert_not_called()


# ---------------------------------------------------------------------------
# set_neighborhood_coordinator — admin-only pref grant, kid-target rejection,
# live-sync to an already-connected target socket (Phase 3 Task 1)
# ---------------------------------------------------------------------------

class TestNeighborhoodCoordinator:
    def test_requires_admin(self, non_admin_client):
        tc, _cfg = non_admin_client
        with tc.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "set_neighborhood_coordinator", "user_id": "other", "coordinator": True})
            msg = _next_of_type(ws, "error")
        assert msg is not None
        assert "admin" in msg["detail"].lower()

    def test_admin_sets_coordinator_on_adult(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()  # admin, id="test-user"

        def get_side_effect(user_id):
            if user_id == "adult-1":
                return {"id": "adult-1", "role": "adult", "is_admin": False, "prefs": {}}
            return {"id": "test-user", "display_name": "Test Operator",
                    "is_admin": True, "role": "admin", "prefs": {}}
        mock_users.get.side_effect = get_side_effect
        mock_users.update_prefs.return_value = {
            "id": "adult-1", "role": "adult", "is_admin": False,
            "prefs": {"neighborhood_coordinator": True},
        }
        mock_users.get_public.return_value = [
            {"id": "adult-1", "role": "adult", "is_admin": False,
             "prefs": {"neighborhood_coordinator": True}},
        ]
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
                    ws.send_json({"type": "set_neighborhood_coordinator",
                                  "user_id": "adult-1", "coordinator": True})
                    msg = _next_of_type(ws, "profiles")
        assert msg is not None
        target = next(p for p in msg["profiles"] if p["id"] == "adult-1")
        assert target["prefs"]["neighborhood_coordinator"] is True
        mock_users.update_prefs.assert_called_once_with("adult-1", {"neighborhood_coordinator": True})

    def test_target_kid_rejected(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()  # admin, id="test-user"

        def get_side_effect(user_id):
            if user_id == "kid-1":
                return {"id": "kid-1", "role": "kid", "is_admin": False, "prefs": {}}
            return {"id": "test-user", "display_name": "Test Operator",
                    "is_admin": True, "role": "admin", "prefs": {}}
        mock_users.get.side_effect = get_side_effect
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
                    ws.send_json({"type": "set_neighborhood_coordinator",
                                  "user_id": "kid-1", "coordinator": True})
                    msg = _next_of_type(ws, "error")
        assert msg is not None
        assert msg["detail"] == "Kid accounts cannot be coordinators"
        mock_users.update_prefs.assert_not_called()

    def test_live_sync_updates_connected_target_without_reconnect(self, tmp_path):
        """Mirrors TestLiveRoleAndPresetSync: an admin grant must reach the
        target's already-open socket's ConnectionState immediately (via
        _sync_live_state_for_user), not only the persisted profile — that's
        what lets a Task 3 coordinator-gated handler work without a reconnect."""
        from backend.server import _manager

        target_id = "target-1"
        with _two_user_server(tmp_path, target_id=target_id, target_role="adult") as (tc, mock_users):
            mock_users.update_prefs.return_value = {
                "id": target_id, "role": "adult", "is_admin": False,
                "prefs": {"neighborhood_coordinator": True},
            }
            with (
                tc.websocket_connect("/ws?token=target-token") as ws_target,
                tc.websocket_connect("/ws?token=admin-token") as ws_admin,
            ):
                _drain_initial(ws_target)
                _drain_initial(ws_admin)

                ws_admin.send_json({"type": "set_neighborhood_coordinator",
                                     "user_id": target_id, "coordinator": True})
                assert _next_of_type(ws_admin, "profiles") is not None

                live_states = _manager.states_for_user(target_id)
                assert live_states
                assert live_states[0].prefs.get("neighborhood_coordinator") is True

    # -- Phase 3 Task 1 review, Finding 3: a revoke must reach the target's
    #    already-open socket just as reliably as a grant does --

    def test_live_sync_revoke_updates_connected_target_without_reconnect(self, tmp_path):
        """Mirrors test_live_sync_updates_connected_target_without_reconnect,
        but grant-then-revoke: after the admin flips coordinator back to
        False, the target's live ConnectionState.prefs must flip too,
        without a reconnect."""
        from backend.server import _manager

        target_id = "target-1"
        with _two_user_server(
            tmp_path, target_id=target_id, target_role="adult",
            target_prefs={"neighborhood_coordinator": True},
        ) as (tc, mock_users):
            mock_users.update_prefs.return_value = {
                "id": target_id, "role": "adult", "is_admin": False,
                "prefs": {"neighborhood_coordinator": False},
            }
            with (
                tc.websocket_connect("/ws?token=target-token") as ws_target,
                tc.websocket_connect("/ws?token=admin-token") as ws_admin,
            ):
                _drain_initial(ws_target)
                _drain_initial(ws_admin)

                ws_admin.send_json({"type": "set_neighborhood_coordinator",
                                     "user_id": target_id, "coordinator": False})
                assert _next_of_type(ws_admin, "profiles") is not None

                live_states = _manager.states_for_user(target_id)
                assert live_states
                assert live_states[0].prefs.get("neighborhood_coordinator") is False


# ---------------------------------------------------------------------------
# quick_messages pref — validation, save, and admin-set path
# ---------------------------------------------------------------------------

class TestValidateQuickMessages:
    """Unit coverage for the shared _validate_quick_messages() sanitizer."""

    def test_valid_list_stripped(self):
        from backend.server import _validate_quick_messages
        assert _validate_quick_messages([" Standing by ", "QSL"]) == ["Standing by", "QSL"]

    def test_rejects_non_list(self):
        from backend.server import _validate_quick_messages
        assert _validate_quick_messages("Standing by") is None

    def test_rejects_empty_list(self):
        from backend.server import _validate_quick_messages
        assert _validate_quick_messages([]) is None

    def test_rejects_too_many_items(self):
        from backend.server import _validate_quick_messages
        assert _validate_quick_messages([f"msg {i}" for i in range(21)]) is None

    def test_accepts_twenty_items(self):
        from backend.server import _validate_quick_messages
        assert _validate_quick_messages([f"msg {i}" for i in range(20)]) is not None

    def test_rejects_non_string_item(self):
        from backend.server import _validate_quick_messages
        assert _validate_quick_messages(["ok", 42]) is None

    def test_rejects_empty_string_item(self):
        from backend.server import _validate_quick_messages
        assert _validate_quick_messages(["ok", "   "]) is None

    def test_rejects_item_over_200_chars(self):
        from backend.server import _validate_quick_messages
        assert _validate_quick_messages(["x" * 201]) is None

    def test_rejects_control_chars(self):
        from backend.server import _validate_quick_messages
        assert _validate_quick_messages(["bad\x00text"]) is None


class TestQuickMessagesPref:
    def test_save_valid_list(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()
        mock_users.update_prefs.return_value = {
            "id": "test-user",
            "display_name": "Test Operator",
            "is_admin": True,
            "prefs": {"quick_messages": ["Standing by", "QSL"]},
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
                    ws.send_json({"type": "save_user_prefs",
                                  "prefs": {"quick_messages": ["Standing by", "QSL"]}})
                    msg = _next_of_type(ws, "user_profile")
        assert msg is not None
        assert msg["profile"]["prefs"]["quick_messages"] == ["Standing by", "QSL"]
        mock_users.update_prefs.assert_called_once_with(
            "test-user", {"quick_messages": ["Standing by", "QSL"]}
        )

    def test_reject_bad_shapes_but_sibling_key_still_applied(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()
        mock_users.update_prefs.return_value = {
            "id": "test-user",
            "display_name": "Test Operator",
            "is_admin": True,
            "prefs": {"dark_mode": True},
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
                    ws.send_json({"type": "save_user_prefs",
                                  "prefs": {"quick_messages": ["ok", 42], "dark_mode": True}})
                    msg = _next_of_type(ws, "user_profile")
        assert msg is not None
        assert "quick_messages" not in msg["profile"]["prefs"]
        assert msg["profile"]["prefs"]["dark_mode"] is True
        # Invalid key silently dropped before reaching the store — only the
        # valid sibling key is persisted.
        mock_users.update_prefs.assert_called_once_with("test-user", {"dark_mode": True})

    def test_kid_cannot_save_own_quick_messages(self, kid_client):
        """quick_messages is intentionally absent from KID_ALLOWED_PREF_KEYS —
        kids cannot edit their own preset allowlist."""
        with kid_client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "save_user_prefs",
                          "prefs": {"quick_messages": ["anything"], "dark_mode": True}})
            msg = _next_of_type(ws, "user_profile")
        assert msg is not None
        assert msg["profile"]["prefs"].get("quick_messages") != ["anything"]
        assert msg["profile"]["prefs"]["dark_mode"] is True


# ---------------------------------------------------------------------------
# I4: keys in KID_ALLOWED_PREF_KEYS (aac_mode, aac_grid, ...) must actually
# reach update_prefs and come back on the user_profile message for a kid —
# not just survive the filter with no persistence.
# ---------------------------------------------------------------------------

class TestKidSaveUserPrefsAllowedKeys:
    def test_kid_aac_mode_persists(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks(is_admin=False, role="kid")
        mock_users.update_prefs.return_value = {
            "id": "test-user", "display_name": "Test Operator", "is_admin": False,
            "role": "kid", "prefs": {"aac_mode": False},
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
                    ws.send_json({"type": "save_user_prefs", "prefs": {"aac_mode": False}})
                    msg = _next_of_type(ws, "user_profile")
        assert msg is not None
        assert msg["profile"]["prefs"]["aac_mode"] is False
        mock_users.update_prefs.assert_called_once_with("test-user", {"aac_mode": False})

    def test_kid_aac_grid_passthrough(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks(is_admin=False, role="kid")
        grid = {"version": 1, "categories": []}
        mock_users.update_prefs.return_value = {
            "id": "test-user", "display_name": "Test Operator", "is_admin": False,
            "role": "kid", "prefs": {"aac_grid": grid},
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
                    ws.send_json({"type": "save_user_prefs", "prefs": {"aac_grid": grid}})
                    msg = _next_of_type(ws, "user_profile")
        assert msg is not None
        assert msg["profile"]["prefs"]["aac_grid"] == grid
        mock_users.update_prefs.assert_called_once_with("test-user", {"aac_grid": grid})

    def test_kid_cannot_self_grant_neighborhood_coordinator(self, tmp_path):
        """neighborhood_coordinator is admin-only (see TestNeighborhoodCoordinator);
        it must be silently dropped from a self-serve save_user_prefs, not just
        for kids but this specifically proves the kid path drops it too.

        Phase 3 Task 1 fix, Finding 1(b): effective_prefs now forces this key
        to False for every kid profile (a belt-and-braces lock), so a kid's
        prefs always carry it as False rather than leaving it absent."""
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks(is_admin=False, role="kid")
        mock_users.update_prefs.return_value = {
            "id": "test-user", "display_name": "Test Operator", "is_admin": False,
            "role": "kid", "prefs": {"dark_mode": True},
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
                    ws.send_json({"type": "save_user_prefs",
                                  "prefs": {"neighborhood_coordinator": True, "dark_mode": True}})
                    msg = _next_of_type(ws, "user_profile")
        assert msg is not None
        assert msg["profile"]["prefs"]["neighborhood_coordinator"] is False
        mock_users.update_prefs.assert_called_once_with("test-user", {"dark_mode": True})


class TestSetUserQuickMessages:
    def test_admin_sets_kid_presets(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()  # admin, id="test-user"
        mock_users.update_prefs.return_value = {
            "id": "kid-1", "role": "kid", "is_admin": False,
            "prefs": {"quick_messages": ["I'm home", "Call me"]},
        }
        mock_users.get_public.return_value = [
            {"id": "kid-1", "role": "kid", "is_admin": False,
             "prefs": {"quick_messages": ["I'm home", "Call me"]}},
        ]
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
                    ws.send_json({"type": "set_user_quick_messages", "user_id": "kid-1",
                                  "quick_messages": ["I'm home", "Call me"]})
                    msg = _next_of_type(ws, "profiles")
        assert msg is not None
        target = next(p for p in msg["profiles"] if p["id"] == "kid-1")
        assert target["prefs"]["quick_messages"] == ["I'm home", "Call me"]
        mock_users.update_prefs.assert_called_once_with(
            "kid-1", {"quick_messages": ["I'm home", "Call me"]}
        )

    def test_requires_admin(self, non_admin_client):
        tc, _cfg = non_admin_client
        with tc.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "set_user_quick_messages", "user_id": "kid-1",
                          "quick_messages": ["I'm home"]})
            msg = _next_of_type(ws, "error")
        assert msg is not None
        assert "admin" in msg["detail"].lower()

    def test_rejects_invalid_shape(self, tmp_path):
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
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    ws.send_json({"type": "set_user_quick_messages", "user_id": "kid-1",
                                  "quick_messages": ["ok", 42]})
                    msg = _next_of_type(ws, "error")
        assert msg is not None
        mock_users.update_prefs.assert_not_called()

    def test_rejects_placeholder_preset_for_kid(self, tmp_path):
        """A kid preset containing a {Token} placeholder is permanently
        untransmittable (the kid TX gate matches raw preset text, but the
        client's resend after prompt_token carries resolved text, which no
        longer matches any preset).  Reject at write time instead."""
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()  # admin, id="test-user"

        def get_side_effect(user_id):
            if user_id == "kid-1":
                return {"id": "kid-1", "role": "kid", "is_admin": False, "prefs": {}}
            return {"id": "test-user", "display_name": "Test Operator",
                    "is_admin": True, "role": "admin", "prefs": {}}
        mock_users.get.side_effect = get_side_effect

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
                    ws.send_json({"type": "set_user_quick_messages", "user_id": "kid-1",
                                  "quick_messages": ["Home by {Time}"]})
                    msg = _next_of_type(ws, "error")
        assert msg is not None
        assert msg["detail"] == "Kid presets cannot contain placeholders"
        mock_users.update_prefs.assert_not_called()

    def test_allows_placeholder_preset_for_adult(self, tmp_path):
        """Regression guard: adult/admin presets legitimately use {N}
        placeholders (resolved client-side before TX) and must not be
        blocked by the kid-only placeholder rule."""
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()  # admin, id="test-user"

        def get_side_effect(user_id):
            if user_id == "adult-1":
                return {"id": "adult-1", "role": "adult", "is_admin": False, "prefs": {}}
            return {"id": "test-user", "display_name": "Test Operator",
                    "is_admin": True, "role": "admin", "prefs": {}}
        mock_users.get.side_effect = get_side_effect
        mock_users.update_prefs.return_value = {
            "id": "adult-1", "role": "adult", "is_admin": False,
            "prefs": {"quick_messages": ["Home by {Time}"]},
        }
        mock_users.get_public.return_value = [
            {"id": "adult-1", "role": "adult", "is_admin": False,
             "prefs": {"quick_messages": ["Home by {Time}"]}},
        ]

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
                    ws.send_json({"type": "set_user_quick_messages", "user_id": "adult-1",
                                  "quick_messages": ["Home by {Time}"]})
                    msg = _next_of_type(ws, "profiles")
        assert msg is not None
        target = next(p for p in msg["profiles"] if p["id"] == "adult-1")
        assert target["prefs"]["quick_messages"] == ["Home by {Time}"]
        mock_users.update_prefs.assert_called_once_with(
            "adult-1", {"quick_messages": ["Home by {Time}"]}
        )

    def test_unknown_user_returns_error(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()
        mock_users.update_prefs.side_effect = KeyError("no such user")
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
                    ws.send_json({"type": "set_user_quick_messages", "user_id": "no-such-user",
                                  "quick_messages": ["I'm home"]})
                    msg = _next_of_type(ws, "error")
        assert msg is not None
        assert "unknown" in msg["detail"].lower()


# ---------------------------------------------------------------------------
# I2: role/preset admin actions must reach an already-connected target's
# *live* ConnectionState immediately — not only on their next reconnect.
# ---------------------------------------------------------------------------

@contextmanager
def _two_user_server(tmp_path, *, target_id: str = "target-1",
                      target_role: str = "adult", target_prefs: dict | None = None):
    """Two distinct authenticated identities on one TestClient: an admin
    (token "admin-token", user_id "test-user") and a second user (token
    "target-token", user_id target_id) — so a test can hold both sockets
    open at once and prove an admin action reaches the target's socket
    without a reconnect."""
    cfg = _minimal_cfg(tmp_path)
    mock_stt, mock_tts = _make_mocks()
    mock_users = MagicMock()
    mock_users.is_empty.return_value = False
    profiles = {
        "test-user": {"id": "test-user", "display_name": "Admin", "is_admin": True,
                       "role": "admin", "prefs": {}},
        target_id: {"id": target_id, "display_name": "Target", "is_admin": False,
                    "role": target_role, "prefs": dict(target_prefs or {})},
    }
    mock_users.get.side_effect = lambda uid: profiles.get(uid)
    mock_users.get_public_one.side_effect = lambda uid: (
        None if profiles.get(uid) is None
        else {k: v for k, v in profiles[uid].items() if k != "prefs"}
    )
    mock_users.get_public.return_value = list(profiles.values())
    mock_tokens = MagicMock()
    mock_tokens.validate.side_effect = {
        "admin-token": "test-user", "target-token": target_id,
    }.get
    mock_tokens.purge_expired.return_value = 0
    with (
        patch("backend.server.ServerConfig.load", return_value=cfg),
        patch("backend.server.STTWorker", return_value=mock_stt),
        patch("backend.server.TTSSynthesizer", return_value=mock_tts),
        patch("backend.server.UsersStore", return_value=mock_users),
        patch("backend.server.TokenStore", return_value=mock_tokens),
        patch("backend.auth_routes.init"),
    ):
        with TestClient(app) as tc:
            yield tc, mock_users


class TestLiveRoleAndPresetSync:
    def test_demote_to_kid_gates_tx_on_the_open_socket(self, tmp_path):
        target_id = "target-1"
        with _two_user_server(tmp_path, target_id=target_id, target_role="adult") as (tc, mock_users):
            mock_users.set_role.return_value = {"id": target_id, "role": "kid", "is_admin": False}
            mock_users.update_prefs.return_value = {
                "id": target_id, "role": "kid", "is_admin": False, "prefs": {"quick_messages": []},
            }
            with (
                tc.websocket_connect("/ws?token=target-token") as ws_target,
                tc.websocket_connect("/ws?token=admin-token") as ws_admin,
            ):
                _drain_initial(ws_target)
                _drain_initial(ws_admin)

                # Sanity: still an adult — free text transmits fine.
                ws_target.send_json({"type": "tx_message", "callsign": "W5TST", "text": "arbitrary words"})
                frames = _drain_until_idle(ws_target)
                assert frames[0] == {"type": "tx_status", "status": "transmitting"}

                # Admin demotes the target to kid.
                ws_admin.send_json({"type": "set_role", "user_id": target_id, "role": "kid"})
                assert _next_of_type(ws_admin, "profiles") is not None

                # Same socket, no reconnect: free text is now rejected.
                ws_target.send_json({"type": "tx_message", "callsign": "W5TST", "text": "arbitrary words"})
                msg = _next_of_type(ws_target, "error")
        assert msg is not None
        assert "not allowed" in msg["detail"].lower()

    def test_preset_edit_reaches_open_socket_and_notifies_target(self, tmp_path):
        target_id = "kid-1"
        with _two_user_server(
            tmp_path, target_id=target_id, target_role="kid",
            target_prefs={"quick_messages": ["Old preset"]},
        ) as (tc, mock_users):
            mock_users.update_prefs.return_value = {
                "id": target_id, "role": "kid", "is_admin": False,
                "prefs": {"quick_messages": ["New preset"]},
            }
            with (
                tc.websocket_connect("/ws?token=target-token") as ws_target,
                tc.websocket_connect("/ws?token=admin-token") as ws_admin,
            ):
                _drain_initial(ws_target)
                _drain_initial(ws_admin)

                # Sanity: the old preset transmits before the edit.
                ws_target.send_json({"type": "tx_message", "callsign": "W5TST", "text": "Old preset"})
                frames = _drain_until_idle(ws_target)
                assert frames[0] == {"type": "tx_status", "status": "transmitting"}

                # Admin replaces the target's preset list.
                ws_admin.send_json({"type": "set_user_quick_messages", "user_id": target_id,
                                     "quick_messages": ["New preset"]})
                assert _next_of_type(ws_admin, "profiles") is not None

                # Target's already-open socket gets the update pushed to it...
                profile_msg = _next_of_type(ws_target, "user_profile")
                assert profile_msg is not None
                assert profile_msg["profile"]["prefs"]["quick_messages"] == ["New preset"]
                # ...followed by the target's own copy of the final "profiles"
                # broadcast (it's a connected client too) — drain it before
                # moving on so it doesn't get mistaken for the next tx_status.
                assert _next_of_type(ws_target, "profiles") is not None

                # ...the new preset transmits, no reconnect required...
                ws_target.send_json({"type": "tx_message", "callsign": "W5TST", "text": "New preset"})
                frames = _drain_until_idle(ws_target)
                assert frames[0] == {"type": "tx_status", "status": "transmitting"}

                # ...and the removed preset is now rejected.
                ws_target.send_json({"type": "tx_message", "callsign": "W5TST", "text": "Old preset"})
                msg = _next_of_type(ws_target, "error")
        assert msg is not None
        assert "not allowed" in msg["detail"].lower()


# ---------------------------------------------------------------------------
# Kid TX allowlist gate — kids may only transmit an admin-curated preset
# ---------------------------------------------------------------------------

class TestKidTxGate:
    def test_kid_tx_preset_allowed(self, kid_client):
        """kid_client's profile prefs include quick_messages == ["I'm home"];
        sending that exact text (strip-compared) transmits normally."""
        with kid_client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "tx_message", "callsign": "WRXB123", "text": "I'm home"})
            frames = _drain_until_idle(ws)
        types = [f["type"] for f in frames]
        assert "tx_status" in types
        assert frames[0] == {"type": "tx_status", "status": "transmitting"}
        assert frames[-1] == {"type": "tx_status", "status": "idle"}

    def test_kid_tx_preset_allowed_with_surrounding_whitespace(self, kid_client):
        """Preset match is strip-compared, not exact-byte."""
        with kid_client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "tx_message", "callsign": "WRXB123", "text": "  I'm home  "})
            frames = _drain_until_idle(ws)
        assert frames[0] == {"type": "tx_status", "status": "transmitting"}

    def test_kid_tx_freetext_rejected(self, kid_client):
        with kid_client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "tx_message", "callsign": "WRXB123", "text": "arbitrary words"})
            msg = _next_of_type(ws, "error")
        assert msg is not None
        assert "not allowed" in msg["detail"].lower()

    def test_kid_tx_with_no_presets_rejects_everything(self, tmp_path):
        """Edge case: a kid profile with no configured presets rejects all TX,
        including a text that happens to be an empty string."""
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks(is_admin=False, role="kid")
        # No quick_messages set — prefs stay at the {} default from _make_auth_mocks.
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
                    ws.send_json({"type": "tx_message", "callsign": "WRXB123", "text": ""})
                    msg = _next_of_type(ws, "error")
        assert msg is not None
        assert "not allowed" in msg["detail"].lower()

    def test_kid_chat_message_stays_ungated(self, kid_client):
        """chat_message is never gated by the TX allowlist, even for kids —
        only on-air tx_message is restricted to presets."""
        with kid_client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "chat_message", "text": "arbitrary chat text",
                          "callsign": "WRXB123", "operator": "Kid"})
            msg = _next_of_type(ws, "chat_echo")
        assert msg is not None

    def test_adult_tx_unaffected_by_gate(self, client):
        """Sanity check: the kid gate must not affect non-kid roles."""
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "tx_message", "callsign": "W5TST", "text": "arbitrary words"})
            frames = _drain_until_idle(ws)
        assert frames[0] == {"type": "tx_status", "status": "transmitting"}


# ---------------------------------------------------------------------------
# C1: voice PTT — a kid must not be able to transmit arbitrary recorded
# speech (only text presets are gated by TestKidTxGate above).
# ---------------------------------------------------------------------------

class TestKidVoiceTxGate:
    def test_kid_voice_tx_start_rejected(self, kid_client):
        with kid_client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "voice_tx_start", "callsign": "WRXB123"})
            msg = _next_of_type(ws, "error")
        assert msg is not None
        assert "not allowed" in msg["detail"].lower()

    def test_kid_voice_tx_end_rejected(self, kid_client):
        """Belt-and-suspenders: even sent alone (no prior voice_tx_start),
        voice_tx_end must reject a kid rather than fall through."""
        with kid_client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "voice_tx_end"})
            msg = _next_of_type(ws, "error")
        assert msg is not None
        assert "not allowed" in msg["detail"].lower()

    def test_adult_voice_tx_start_unaffected(self, client):
        """Sanity check: the kid gate must not affect non-kid roles."""
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "voice_tx_start", "callsign": "W5TST"})
            msg = ws.receive_json()
        assert msg == {"type": "voice_tx_ack"}


# ---------------------------------------------------------------------------
# I1a: standalone_id ("This is") speaks client-supplied operator/location on
# air — must be gated like any other TX, not just listen-only.
# ---------------------------------------------------------------------------

class TestKidStandaloneIdGate:
    def test_kid_standalone_id_rejected(self, kid_client):
        with kid_client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "standalone_id", "operator": "Kid", "callsign": "WRXB123"})
            msg = _next_of_type(ws, "error")
        assert msg is not None
        assert "not allowed" in msg["detail"].lower()

    def test_adult_standalone_id_unaffected(self, client):
        """Sanity check: the kid gate must not affect non-kid roles."""
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "standalone_id", "operator": "Test Op", "callsign": "W5TST"})
            frames = _drain_until_idle(ws)
        assert frames[0] == {"type": "tx_status", "status": "transmitting"}


# ---------------------------------------------------------------------------
# I5: set_listen_only ungated let a kid defeat the server-enforced
# listen_only lock by simply flipping it back off themselves.
# ---------------------------------------------------------------------------

class TestKidListenOnlyGate:
    def test_kid_set_listen_only_rejected(self, kid_client):
        with kid_client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "set_listen_only", "listen_only": True})
            msg = _next_of_type(ws, "error")
        assert msg is not None
        assert "adult" in msg["detail"].lower()

    def test_adult_set_listen_only_unaffected(self, tmp_path):
        """Sanity check: the kid gate must not affect non-kid roles."""
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()  # admin, id="test-user"
        mock_users.update_prefs.return_value = {
            "id": "test-user", "display_name": "Test Operator", "is_admin": True,
            "role": "admin", "prefs": {"listen_only": True},
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
                    ws.send_json({"type": "set_listen_only", "listen_only": True})
                    msg = _next_of_type(ws, "user_profile")
        assert msg is not None
        assert msg["profile"]["prefs"]["listen_only"] is True


# ---------------------------------------------------------------------------
# N1: set_config's filter_profanity leg was ungated for kids — a kid could
# flip their own profanity filter off via set_config, defeating the
# kid-safety filter save_user_prefs enforces via KID_ALLOWED_PREF_KEYS.
# fuzzy_callsign / fuzzy_callsign_rewrite are station-wide and untouched.
# ---------------------------------------------------------------------------

class TestKidProfanityFilterGate:
    def test_kid_set_config_filter_profanity_rejected(self, kid_client):
        with kid_client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "set_config", "filter_profanity": False})
            msg = _next_of_type(ws, "error")
        assert msg is not None
        assert "adult" in msg["detail"].lower()

    def test_kid_set_config_filter_profanity_prefs_unchanged(self, tmp_path):
        """Sanity check: the rejected leg must not mutate state.prefs or
        reach the store."""
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks(is_admin=False, role="kid")
        mock_users.get.return_value["prefs"] = {"filter_profanity": True}
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
                    ws.send_json({"type": "set_config", "filter_profanity": False})
                    msg = _next_of_type(ws, "error")
        assert msg is not None
        mock_users.update_prefs.assert_not_called()

    def test_adult_set_config_filter_profanity_unaffected(self, tmp_path):
        """Sanity check: the kid gate must not affect non-kid roles."""
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()  # admin, id="test-user"
        mock_users.update_prefs.return_value = {
            "id": "test-user", "display_name": "Test Operator", "is_admin": True,
            "role": "admin", "prefs": {"filter_profanity": False},
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
                    ws.send_json({"type": "set_config", "filter_profanity": False})
                    msg = _next_of_type(ws, "user_profile")
        assert msg is not None
        assert msg["profile"]["prefs"]["filter_profanity"] is False


# ---------------------------------------------------------------------------
# I6: a kid could self-rename (display_name/operator_name/callsign) and then
# use family_status ("I'm OK") — which speaks operator_name on air ungated —
# to transmit arbitrary text under the new identity.
# ---------------------------------------------------------------------------

class TestKidProfileIdentityGate:
    def test_kid_self_edit_of_identity_field_rejected(self, kid_client):
        with kid_client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "update_profile", "operator_name": "New Name"})
            msg = _next_of_type(ws, "error")
        assert msg is not None
        assert "ask an adult" in msg["detail"].lower()

    def test_kid_self_edit_of_callsign_rejected(self, kid_client):
        with kid_client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "update_profile", "callsign": "W1AW"})
            msg = _next_of_type(ws, "error")
        assert msg is not None
        assert "ask an adult" in msg["detail"].lower()

    def test_kid_self_edit_of_non_identity_field_allowed(self, tmp_path):
        """Sanity check: the identity-field gate must not block a kid editing
        their other own profile fields (e.g. avatar_emoji)."""
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks(is_admin=False, role="kid")
        mock_users.update_profile.return_value = {
            "id": "test-user", "display_name": "Test Operator", "avatar_emoji": "🐸",
            "is_admin": False, "role": "kid", "prefs": {},
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
                    ws.send_json({"type": "update_profile", "avatar_emoji": "🐸"})
                    msg = _next_of_type(ws, "user_profile")
        assert msg is not None

    def test_admin_can_still_edit_a_kids_identity_fields(self, tmp_path):
        """Sanity check: the gate only restricts a kid's SELF-edit — an admin
        editing another user's (including a kid's) identity fields via the
        admin path (target_id != state.user_id) must be unaffected."""
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()  # admin, id="test-user"
        mock_users.update_profile.return_value = {
            "id": "kid-1", "display_name": "Kid", "operator_name": "New Name",
            "is_admin": False, "role": "kid", "prefs": {},
        }
        mock_users.get_public.return_value = []
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
                    ws.send_json({"type": "update_profile", "user_id": "kid-1",
                                  "operator_name": "New Name"})
                    msg = _next_of_type(ws, "profiles")
        assert msg is not None
        mock_users.update_profile.assert_called_once_with("kid-1", {"operator_name": "New Name"})


# ---------------------------------------------------------------------------
# family_status ("I'm OK") — presence + chat + TTS fan-out
# ---------------------------------------------------------------------------

def _family_status_auth_mocks(*, is_admin: bool = True, role: str | None = None, listen_only: bool = False):
    """_make_auth_mocks() plus get_public() wired.

    _build_family_presence_msg() joins presence onto *every* known profile via
    get_public() (unlike get()/get_public_one(), which are keyed to the
    connecting user) — so family_presence assertions need it configured.
    """
    mock_users, mock_tokens = _make_auth_mocks(is_admin=is_admin, role=role, listen_only=listen_only)
    mock_users.get_public.return_value = [
        {"id": "test-user", "display_name": "Test Operator", "avatar_emoji": "👤"},
    ]
    return mock_users, mock_tokens


class TestFamilyStatus:
    def test_im_ok_fans_out_presence_chat_and_tts(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        captured: dict[str, str] = {}

        async def _capture_synth(_voice, text, *_args, **_kwargs):
            captured["text"] = text
            return None, None

        mock_tts.synthesize_to_buffer = _capture_synth
        mock_users, mock_tokens = _family_status_auth_mocks()
        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
            patch("piper.PiperVoice"),
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    ws.send_json({"type": "family_status", "status": "ok"})

                    chat = _next_of_type(ws, "chat_echo")
                    assert chat is not None
                    assert chat["text"] == "Family status: Test Operator is okay."

                    presence = _next_of_type(ws, "family_presence")
                    assert presence is not None
                    me = next(e for e in presence["entries"] if e["user_id"] == "test-user")
                    assert me["last_ok"] is not None
                    assert me["missed_checkin"] is False

                    _drain_until_idle(ws)  # blocks until the TTS leg has actually run

        assert captured.get("text") == "Family status: Test Operator is okay."

    def test_listen_only_skips_tts_leg_but_still_chats_and_marks_ok(self, tmp_path):
        cfg = _minimal_cfg(tmp_path, listen_only=True)
        mock_stt, mock_tts = _make_mocks()
        captured: dict[str, str] = {}

        async def _capture_synth(_voice, text, *_args, **_kwargs):
            captured["text"] = text
            return None, None

        mock_tts.synthesize_to_buffer = _capture_synth
        mock_users, mock_tokens = _family_status_auth_mocks(listen_only=True)
        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
            patch("piper.PiperVoice"),
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    ws.send_json({"type": "family_status", "status": "ok"})

                    chat = _next_of_type(ws, "chat_echo")
                    assert chat is not None

                    presence = _next_of_type(ws, "family_presence")
                    me = next(e for e in presence["entries"] if e["user_id"] == "test-user")
                    assert me["last_ok"] is not None
                    assert me["missed_checkin"] is False

        assert "text" not in captured, "listen-only family_status must not enqueue TTS"

    def test_kid_can_send_family_status(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _family_status_auth_mocks(is_admin=False, role="kid")
        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
            patch("piper.PiperVoice"),
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    ws.send_json({"type": "family_status", "status": "ok"})
                    assert _next_of_type(ws, "family_presence") is not None

    def test_unknown_status_value_returns_error(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _family_status_auth_mocks()
        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
            patch("piper.PiperVoice"),
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    ws.send_json({"type": "family_status", "status": "not-ok"})
                    err = _next_of_type(ws, "error")
        assert err is not None
        assert err["detail"] == "Unknown family status"

    def test_family_presence_sent_on_connect(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _family_status_auth_mocks()
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
                    frames = _drain_initial(ws)
        presence_frames = [f for f in frames if f["type"] == "family_presence"]
        assert len(presence_frames) == 1
        me = next(e for e in presence_frames[0]["entries"] if e["user_id"] == "test-user")
        assert me == {
            "user_id": "test-user",
            "display_name": "Test Operator",
            "avatar_emoji": "👤",
            "last_heard": None,
            "last_ok": None,
            "missed_checkin": False,
        }


class TestFamilyStatusVoice:
    """M4: family_status ("I'm OK") TTS must speak in the sender's own
    configured voice, mirroring tx_message's voice resolution — not just
    whatever the station default happens to be."""

    def test_im_ok_uses_senders_voice_prefs(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        loaded: list[str] = []
        captured: dict = {}

        async def _capture_synth(_voice, text, *args, **kwargs):
            captured["length_scale"] = kwargs.get("length_scale")
            return None, None

        mock_tts.synthesize_to_buffer = _capture_synth
        mock_users, mock_tokens = _family_status_auth_mocks()
        mock_users.get.return_value["prefs"] = {
            "tts_voice": "grandpa.onnx", "tts_length_scale": 1.3,
        }
        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
            patch("backend.server._load_voice",
                  side_effect=lambda v: loaded.append(v) or MagicMock()),
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    ws.send_json({"type": "family_status", "status": "ok"})
                    _drain_until_idle(ws)
        assert "grandpa.onnx" in loaded
        assert captured.get("length_scale") == 1.3


class TestTxMessageTouchesPresence:
    def test_tx_message_touches_last_heard(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _family_status_auth_mocks()
        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
            patch("piper.PiperVoice"),
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    ws.send_json({"type": "tx_message", "callsign": "WRXB123", "text": "hello net"})
                    presence = _next_of_type(ws, "family_presence")
        assert presence is not None
        me = next(e for e in presence["entries"] if e["user_id"] == "test-user")
        assert me["last_heard"] is not None


# ---------------------------------------------------------------------------
# Check-in reminders: set_family_reminder / get_family_reminders
# ---------------------------------------------------------------------------

class TestFamilyReminders:
    def test_admin_set_reminder_broadcasts_family_reminders(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _family_status_auth_mocks()
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
                    ws.send_json({
                        "type": "set_family_reminder",
                        "user_id": "test-user",
                        "time": "09:00",
                        "enabled": True,
                    })
                    msg = _next_of_type(ws, "family_reminders")
        assert msg is not None
        assert msg["reminders"] == {"test-user": {"time": "09:00", "enabled": True}}

    def test_non_admin_set_reminder_rejected(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _family_status_auth_mocks(is_admin=False, role="adult")
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
                    ws.send_json({
                        "type": "set_family_reminder",
                        "user_id": "test-user",
                        "time": "09:00",
                        "enabled": True,
                    })
                    err = _next_of_type(ws, "error")
        assert err is not None
        assert err["detail"] == "Admin access required."

    def test_set_reminder_bad_time_returns_error(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _family_status_auth_mocks()
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
                    ws.send_json({
                        "type": "set_family_reminder",
                        "user_id": "test-user",
                        "time": "25:99",
                        "enabled": True,
                    })
                    err = _next_of_type(ws, "error")
        assert err is not None

    def test_set_reminder_none_time_deletes(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _family_status_auth_mocks()
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
                    ws.send_json({
                        "type": "set_family_reminder",
                        "user_id": "test-user",
                        "time": "09:00",
                        "enabled": True,
                    })
                    _next_of_type(ws, "family_reminders")
                    ws.send_json({
                        "type": "set_family_reminder",
                        "user_id": "test-user",
                        "time": None,
                        "enabled": True,
                    })
                    msg = _next_of_type(ws, "family_reminders")
        assert msg["reminders"] == {}

    def test_kid_get_reminders_rejected(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _family_status_auth_mocks(is_admin=False, role="kid")
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
                    ws.send_json({"type": "get_family_reminders"})
                    err = _next_of_type(ws, "error")
        assert err is not None
        assert err["detail"] == "Check-in reminders not available for this account."

    def test_adult_get_reminders_returns_msg(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _family_status_auth_mocks(is_admin=False, role="adult")
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
                    ws.send_json({"type": "get_family_reminders"})
                    msg = _next_of_type(ws, "family_reminders")
        assert msg is not None
        assert msg["reminders"] == {}

    def test_family_reminders_sent_on_connect_for_adult(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _family_status_auth_mocks(is_admin=False, role="adult")
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
                    frames = _drain_initial(ws)
        reminder_frames = [f for f in frames if f["type"] == "family_reminders"]
        assert len(reminder_frames) == 1

    def test_family_reminders_not_sent_on_connect_for_kid(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _family_status_auth_mocks(is_admin=False, role="kid")
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
                    frames = _drain_initial(ws)
        reminder_frames = [f for f in frames if f["type"] == "family_reminders"]
        assert reminder_frames == []


class TestDeleteProfileCleansUpFamilyData:
    """M2: delete_profile must not orphan the deleted user's check-in
    reminder or presence entry — both would otherwise linger forever on
    the Family board for a user_id that no longer exists."""

    def test_delete_profile_removes_reminder_and_presence(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        Path(cfg.family_file).write_text(
            json.dumps({"other": {"time": "09:00", "enabled": True}}), encoding="utf-8"
        )
        Path(cfg.presence_file).write_text(
            json.dumps({"other": {"last_heard": "2026-07-17T10:00:00+00:00",
                                   "last_ok": None, "missed_checkin": False}}),
            encoding="utf-8",
        )
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _family_status_auth_mocks()  # admin, id="test-user"
        mock_users.get_public.return_value = []
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
                    ws.send_json({"type": "delete_profile", "user_id": "other"})
                    reminders_msg = _next_of_type(ws, "family_reminders")
                    presence_msg = _next_of_type(ws, "family_presence")
        assert reminders_msg is not None
        assert "other" not in reminders_msg["reminders"]
        assert presence_msg is not None
        assert all(e["user_id"] != "other" for e in presence_msg["entries"])


# ---------------------------------------------------------------------------
# Phase 3 Task 2 — neighborhood net: state, check-ins, round-table
# ---------------------------------------------------------------------------

def _neighborhood_server(tmp_path, *, role: str = "adult", is_admin: bool = False,
                          coordinator: bool = False, mock_tts=None, profile: dict | None = None,
                          journals: bool = False, listen_only: bool = False):
    """Context manager yielding (TestClient, cfg) wired for neighborhood-net tests."""
    cfg = _minimal_cfg(tmp_path, listen_only=listen_only)
    if journals:
        cfg["journals_dir"] = str(tmp_path / "journals")
    mock_stt, default_tts = _make_mocks()
    tts = mock_tts if mock_tts is not None else default_tts
    mock_users, mock_tokens = _make_auth_mocks(
        is_admin=is_admin, role=role, coordinator=coordinator, listen_only=listen_only,
    )
    if profile is not None:
        mock_users.get_public_one.return_value = profile
    return cfg, mock_stt, tts, mock_users, mock_tokens


class TestNeighborhoodNetHandlers:
    def test_get_state_sent_on_connect(self, tmp_path):
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_server(tmp_path)
        cfg["neighborhood_net_day"] = "Saturday"
        cfg["neighborhood_net_time"] = "09:00"
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
                    frames = _drain_initial(ws)
        state_msgs = [f for f in frames if f.get("type") == "neighborhood_state"]
        assert len(state_msgs) == 1
        msg = state_msgs[0]
        assert msg == {
            "type": "neighborhood_state",
            "active": False,
            "roster": [],
            "current_call": None,
            "net_day": "Saturday",
            "net_time": "09:00",
        }

    def test_get_state_request_returns_current_state(self, tmp_path):
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_server(tmp_path)
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
                    ws.send_json({"type": "neighborhood_get_state"})
                    msg = _next_of_type(ws, "neighborhood_state")
        assert msg is not None and msg["active"] is False

    def test_checkin_any_role_incl_kid_broadcasts_state_from_connection_profile(self, tmp_path):
        """Checkin transmits nothing and works for a kid; identity comes from
        the CONNECTION's own profile — client-supplied fields are ignored
        (same kid-rename protection precedent as update_profile)."""
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_server(
            tmp_path, role="kid",
            profile={
                "display_name": "Kiddo", "operator_name": "Kiddo Op",
                "callsign": "W5KID", "location": "Back Yard",
            },
        )
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
                    ws.send_json({
                        "type": "neighborhood_checkin",
                        "callsign": "FAKE", "name": "Not Real", "location": "Nowhere",
                    })
                    msg = _next_of_type(ws, "neighborhood_state")
        assert msg is not None
        assert len(msg["roster"]) == 1
        row = msg["roster"][0]
        assert row["callsign"] == "W5KID"
        assert row["name"] == "Kiddo Op"
        assert row["location"] == "Back Yard"
        assert row["status"] == "checked_in"

    def test_start_rejected_for_adult_without_coordinator_pref(self, tmp_path):
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_server(tmp_path)
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
                    ws.send_json({"type": "neighborhood_start"})
                    err = _next_of_type(ws, "error")
        assert err is not None
        assert err["detail"] == "Coordinator access required"

    def test_start_activates_for_coordinator(self, tmp_path):
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_server(
            tmp_path, coordinator=True,
        )
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
                    ws.send_json({"type": "neighborhood_start"})
                    msg = _next_of_type(ws, "neighborhood_state")
        assert msg is not None and msg["active"] is True

    @pytest.mark.parametrize("msg_type", [
        "neighborhood_start", "neighborhood_end", "neighborhood_call_next", "neighborhood_call_reset",
    ])
    def test_coordinator_only_handlers_reject_plain_adult(self, tmp_path, msg_type):
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_server(tmp_path)
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
                    ws.send_json({"type": msg_type})
                    err = _next_of_type(ws, "error")
        assert err is not None
        assert err["detail"] == "Coordinator access required"

    def test_status_change_for_other_user_requires_coordinator(self, tmp_path):
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_server(tmp_path)
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
                    ws.send_json({"type": "neighborhood_status", "user_id": "other-user", "status": "standby"})
                    err = _next_of_type(ws, "error")
        assert err is not None
        assert err["detail"] == "Coordinator access required"

    def test_status_change_for_own_user_allowed_without_coordinator(self, tmp_path):
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_server(tmp_path)
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
                    ws.send_json({"type": "neighborhood_checkin"})
                    _next_of_type(ws, "neighborhood_state")
                    ws.send_json({"type": "neighborhood_status", "status": "standby"})
                    msg = _next_of_type(ws, "neighborhood_state")
        assert msg is not None
        assert msg["roster"][0]["status"] == "standby"

    def test_call_next_enqueues_tx_and_broadcasts_current_call(self, tmp_path):
        captured: dict[str, str] = {}

        async def _capture_synth(_voice, text, *_args, **_kwargs):
            captured["text"] = text
            return None, None

        mock_stt, mock_tts = _make_mocks()
        mock_tts.synthesize_to_buffer = _capture_synth
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_server(
            tmp_path, coordinator=True, mock_tts=mock_tts,
            profile={"display_name": "Coord Op", "callsign": "W5CRD", "location": "Front St"},
        )
        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
            patch("piper.PiperVoice"),
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    ws.send_json({"type": "neighborhood_start"})
                    _next_of_type(ws, "neighborhood_state")
                    ws.send_json({"type": "neighborhood_checkin"})
                    _next_of_type(ws, "neighborhood_state")
                    ws.send_json({"type": "neighborhood_call_next"})
                    frames = _drain_until_idle(ws)
        state_msgs = [f for f in frames if f.get("type") == "neighborhood_state"]
        idle_msgs = [f for f in frames if f.get("type") == "tx_status" and f.get("status") == "idle"]
        assert state_msgs, "expected a neighborhood_state broadcast after call_next"
        assert idle_msgs, "expected the TX pump to run the queued call to completion"
        assert state_msgs[-1]["current_call"] == "test-user"
        assert state_msgs[-1]["roster"][0]["called"] is True
        assert captured.get("text") == "Coord Op, you're up. Anything to report? W5TST."

    def test_call_next_round_complete_returns_none_and_clears_current_call(self, tmp_path):
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_server(
            tmp_path, coordinator=True,
            profile={"display_name": "Coord Op", "callsign": "W5CRD", "location": ""},
        )
        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
            patch("piper.PiperVoice"),
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    ws.send_json({"type": "neighborhood_start"})
                    _next_of_type(ws, "neighborhood_state")
                    ws.send_json({"type": "neighborhood_checkin"})
                    _next_of_type(ws, "neighborhood_state")
                    ws.send_json({"type": "neighborhood_call_next"})
                    _drain_until_idle(ws)
                    # Second call_next: round already complete (only one
                    # checked-in station, already called) — no TX, current
                    # call cleared, so no tx_status:idle will follow.
                    ws.send_json({"type": "neighborhood_call_next"})
                    msg = _next_of_type(ws, "neighborhood_state")
        assert msg is not None
        assert msg["current_call"] is None

    def test_call_reset_clears_called_flags(self, tmp_path):
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_server(
            tmp_path, coordinator=True,
            profile={"display_name": "Coord Op", "callsign": "W5CRD", "location": ""},
        )
        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
            patch("piper.PiperVoice"),
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    ws.send_json({"type": "neighborhood_start"})
                    _next_of_type(ws, "neighborhood_state")
                    ws.send_json({"type": "neighborhood_checkin"})
                    _next_of_type(ws, "neighborhood_state")
                    ws.send_json({"type": "neighborhood_call_next"})
                    _drain_until_idle(ws)
                    ws.send_json({"type": "neighborhood_call_reset"})
                    msg = _next_of_type(ws, "neighborhood_state")
        assert msg is not None
        assert msg["current_call"] is None
        assert msg["roster"][0]["called"] is False

    def test_end_with_nonempty_roster_saves_journal(self, tmp_path):
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_server(
            tmp_path, coordinator=True, journals=True,
            profile={"display_name": "Coord Op", "callsign": "W5CRD", "location": "Front St"},
        )
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
                    ws.send_json({"type": "neighborhood_start"})
                    _next_of_type(ws, "neighborhood_state")
                    ws.send_json({"type": "neighborhood_checkin"})
                    _next_of_type(ws, "neighborhood_state")
                    ws.send_json({"type": "neighborhood_end"})
                    saved = _next_of_type(ws, "neighborhood_journal_saved")
        assert saved is not None
        journal_files = list((tmp_path / "journals").glob("*.json"))
        assert len(journal_files) == 1
        entry = json.loads(journal_files[0].read_text())
        assert entry["title"].startswith("Neighborhood net ")
        assert entry["callsigns_locations"] == [{"callsign": "W5CRD", "location": "Front St"}]

    def test_end_with_empty_roster_does_not_save_journal(self, tmp_path):
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_server(
            tmp_path, coordinator=True, journals=True,
        )
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
                    ws.send_json({"type": "neighborhood_start"})
                    _next_of_type(ws, "neighborhood_state")
                    ws.send_json({"type": "neighborhood_end"})
                    msg = _next_of_type(ws, "neighborhood_state")
        assert msg is not None and msg["active"] is False


# ---------------------------------------------------------------------------
# Phase 3 Task 6 review fix — set_admin_config must rebroadcast
# neighborhood_state when it touches the net schedule, else already-connected
# clients keep showing a stale next-net day/time until they reconnect.
# ---------------------------------------------------------------------------

class TestSetAdminConfigNeighborhoodBroadcast:
    def test_net_schedule_change_reaches_second_client_without_reconnect(self, tmp_path):
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_server(
            tmp_path, is_admin=True,
        )
        cfg.save = MagicMock()
        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
        ):
            with TestClient(app) as tc:
                with (
                    tc.websocket_connect(WS_URL) as ws1,
                    tc.websocket_connect(WS_URL) as ws2,
                ):
                    _drain_initial(ws1)
                    _drain_initial(ws2)
                    ws1.send_json({
                        "type": "set_admin_config",
                        "neighborhood_net_day": "Wednesday",
                        "neighborhood_net_time": "19:30",
                    })
                    msg = _next_of_type(ws2, "neighborhood_state")
        assert msg is not None, "second client never got a neighborhood_state rebroadcast"
        assert msg["net_day"] == "Wednesday"
        assert msg["net_time"] == "19:30"

    def test_unrelated_admin_config_save_does_not_broadcast_neighborhood_state(self, tmp_path):
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_server(
            tmp_path, is_admin=True,
        )
        cfg.save = MagicMock()
        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
        ):
            with TestClient(app) as tc:
                with (
                    tc.websocket_connect(WS_URL) as ws1,
                    tc.websocket_connect(WS_URL) as ws2,
                ):
                    _drain_initial(ws1)
                    _drain_initial(ws2)
                    ws1.send_json({"type": "set_admin_config", "name": "New Station Name"})
                    # Only the status broadcast should follow — nothing neighborhood-related.
                    msg = ws2.receive_json()
        assert msg["type"] == "status"


# ---------------------------------------------------------------------------
# Phase 3 Task 3 — incident reports + street alert
# ---------------------------------------------------------------------------

def _valid_incident_payload(**overrides) -> dict:
    payload = {
        "type": "neighborhood_incident_report",
        "category": "hazard",
        "description": "Tree down blocking the road",
        "location": "5th and Main",
    }
    payload.update(overrides)
    return payload


class TestNeighborhoodIncidentReport:
    def test_kid_report_rejected(self, tmp_path):
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_server(tmp_path, role="kid")
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
                    ws.send_json(_valid_incident_payload())
                    msg = _next_of_type(ws, "error")
        assert msg is not None
        assert msg["detail"] == "TX not allowed for this account"

    def test_invalid_payload_returns_incident_error(self, tmp_path):
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_server(tmp_path)
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
                    ws.send_json(_valid_incident_payload(category="not-a-category"))
                    msg = _next_of_type(ws, "neighborhood_incident_error")
        assert msg is not None
        assert msg["detail"]

    def test_valid_report_transmits_logs_and_broadcasts(self, tmp_path):
        captured: dict[str, str] = {}

        async def _capture_synth(_voice, text, *_args, **_kwargs):
            captured["text"] = text
            return None, None

        mock_stt, mock_tts = _make_mocks()
        mock_tts.synthesize_to_buffer = _capture_synth
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_server(
            tmp_path, mock_tts=mock_tts,
            profile={"display_name": "Ann Adult", "callsign": "W5ANN", "location": "Home"},
        )
        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
            patch("piper.PiperVoice"),
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    ws.send_json(_valid_incident_payload())
                    frames = _drain_until_idle(ws)
        tx_echo = next(f for f in frames if f.get("type") == "tx_echo")
        incidents_msgs = [f for f in frames if f.get("type") == "neighborhood_incidents"]
        sent_msg = next(f for f in frames if f.get("type") == "neighborhood_incident_sent")
        assert incidents_msgs, "expected a neighborhood_incidents broadcast"
        assert tx_echo["display_name"] == "NEIGHBORHOOD"
        assert tx_echo["callsign"] == "W5ANN"
        assert tx_echo["text"].startswith("NEIGHBORHOOD HAZARD. TREE DOWN BLOCKING THE ROAD. ")
        assert captured["text"] == tx_echo["text"] == sent_msg["text"]
        assert sent_msg["ts"]
        entries = incidents_msgs[-1]["incidents"]
        assert len(entries) == 1
        assert entries[0]["category"] == "hazard"
        assert entries[0]["reporter"] == "Ann Adult"
        assert entries[0]["location"] == "5th and Main"

    def test_incidents_sent_on_connect(self, tmp_path):
        (tmp_path / "incidents.json").write_text(json.dumps([
            {"id": "abc123", "category": "hazard", "description": "x", "location": "y",
             "reporter": "Ann", "ts": "2026-07-17T09:00:00Z"},
        ]))
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_server(tmp_path)
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
                    frames = _drain_initial(ws)
        incidents_msgs = [f for f in frames if f.get("type") == "neighborhood_incidents"]
        assert len(incidents_msgs) == 1
        assert incidents_msgs[0]["incidents"][0]["id"] == "abc123"

    def test_list_incidents_any_role_returns_current_list(self, tmp_path):
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_server(tmp_path, role="kid")
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
                    ws.send_json({"type": "neighborhood_list_incidents"})
                    msg = _next_of_type(ws, "neighborhood_incidents")
        assert msg is not None
        assert msg["incidents"] == []


def _neighborhood_alert_two_user_server(tmp_path):
    """A coordinator adult ('coord-1') and a kid ('kid-1') on one TestClient,
    mirroring _two_user_server, so a test can prove a street alert broadcast
    reaches an already-connected kid socket."""
    cfg = _minimal_cfg(tmp_path)
    mock_stt, mock_tts = _make_mocks()
    mock_users = MagicMock()
    mock_users.is_empty.return_value = False
    profiles = {
        "coord-1": {"id": "coord-1", "display_name": "Coord Op", "is_admin": False,
                    "role": "adult", "prefs": {"neighborhood_coordinator": True}},
        "kid-1": {"id": "kid-1", "display_name": "Kiddo", "is_admin": False,
                  "role": "kid", "prefs": {}},
    }
    mock_users.get.side_effect = lambda uid: profiles.get(uid)
    mock_users.get_public_one.side_effect = lambda uid: (
        None if profiles.get(uid) is None
        else {k: v for k, v in profiles[uid].items() if k != "prefs"}
    )
    mock_tokens = MagicMock()
    mock_tokens.validate.side_effect = {"coord-token": "coord-1", "kid-token": "kid-1"}.get
    mock_tokens.purge_expired.return_value = 0
    return cfg, mock_stt, mock_tts, mock_users, mock_tokens


class TestNeighborhoodStreetAlert:
    def test_non_coordinator_rejected(self, tmp_path):
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_server(tmp_path)
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
                    ws.send_json({"type": "neighborhood_street_alert", "message": "Water main break on Elm"})
                    msg = _next_of_type(ws, "error")
        assert msg is not None
        assert msg["detail"] == "Coordinator access required"

    def test_empty_message_rejected(self, tmp_path):
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_server(tmp_path, coordinator=True)
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
                    ws.send_json({"type": "neighborhood_street_alert", "message": "   "})
                    msg = _next_of_type(ws, "error")
        assert msg is not None

    def test_coordinator_alert_transmits_and_broadcasts(self, tmp_path):
        captured: dict[str, str] = {}

        async def _capture_synth(_voice, text, *_args, **_kwargs):
            captured["text"] = text
            return None, None

        mock_stt, mock_tts = _make_mocks()
        mock_tts.synthesize_to_buffer = _capture_synth
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_server(
            tmp_path, coordinator=True, mock_tts=mock_tts,
            profile={"display_name": "Coord Op", "callsign": "W5CRD", "location": ""},
        )
        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
            patch("piper.PiperVoice"),
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    ws.send_json({"type": "neighborhood_street_alert", "message": "  Water main break on Elm  "})
                    frames = _drain_until_idle(ws)
        alert_msg = next(f for f in frames if f.get("type") == "neighborhood_alert")
        tx_echo = next(f for f in frames if f.get("type") == "tx_echo")
        assert alert_msg["message"] == "Water main break on Elm"
        assert alert_msg["issued_by"] == "Coord Op"
        assert alert_msg["id"]
        assert alert_msg["ts"]
        assert captured["text"] == "NEIGHBORHOOD ALERT. Water main break on Elm. W5TST."
        assert tx_echo["text"] == captured["text"]
        assert tx_echo["display_name"] == "NEIGHBORHOOD"

    def test_alert_reaches_kid_client(self, tmp_path):
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_alert_two_user_server(tmp_path)
        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
            patch("piper.PiperVoice"),
        ):
            with TestClient(app) as tc:
                with (
                    tc.websocket_connect("/ws?token=kid-token") as ws_kid,
                    tc.websocket_connect("/ws?token=coord-token") as ws_coord,
                ):
                    _drain_initial(ws_kid)
                    _drain_initial(ws_coord)
                    ws_coord.send_json({"type": "neighborhood_street_alert", "message": "Boil water advisory"})
                    _drain_until_idle(ws_coord)
                    msg = _next_of_type(ws_kid, "neighborhood_alert")
        assert msg is not None
        assert msg["message"] == "Boil water advisory"

    def test_listen_only_coordinator_alert_skips_tts_but_broadcasts(self, tmp_path):
        captured: dict[str, str] = {}

        async def _capture_synth(_voice, text, *_args, **_kwargs):
            captured["text"] = text
            return None, None

        mock_stt, mock_tts = _make_mocks()
        mock_tts.synthesize_to_buffer = _capture_synth
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_server(
            tmp_path, coordinator=True, mock_tts=mock_tts, listen_only=True,
            profile={"display_name": "Coord Op", "callsign": "W5CRD", "location": ""},
        )
        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
            patch("piper.PiperVoice"),
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    ws.send_json({"type": "neighborhood_street_alert", "message": "Boil water advisory"})
                    msg = _next_of_type(ws, "neighborhood_alert")
        assert msg is not None
        assert msg["message"] == "Boil water advisory"
        assert "text" not in captured
        journals_dir = tmp_path / "journals"
        assert not journals_dir.exists() or not list(journals_dir.glob("*.json"))
