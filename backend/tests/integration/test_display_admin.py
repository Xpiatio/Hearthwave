"""Admin device-token management + household quick-messages config.

Covers Task 3's three new admin-only WS handlers (device_token_create/list/
revoke) backed by the real (tmp_path-backed) DeviceTokenStore from Task 1,
plus the display_quick_messages config field threaded through
set_admin_config / _build_status.

Fixture idiom mirrors test_server_ws.py (TestClient built with mocked
STT/TTS/UsersStore/TokenStore) and test_display_ws.py (DeviceTokenStore is a
real tmp_path-backed instance rather than a mock, so create()/list_all()/
revoke() exercise real behavior end to end).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from backend.config import ServerConfig
from backend.persistence.device_tokens import DeviceTokenStore
from backend.server import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

WS_URL = "/ws?token=test"


def _minimal_cfg(tmp_path: Path) -> ServerConfig:
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
    })


def _make_mocks():
    mock_stt = MagicMock()
    mock_stt.join = AsyncMock()
    mock_stt.channel_busy = MagicMock(is_set=MagicMock(return_value=False))
    mock_tts = MagicMock()
    mock_tts.synthesize_to_buffer = AsyncMock(return_value=(None, None))
    return mock_stt, mock_tts


def _make_auth_mocks(*, is_admin: bool = True):
    role = "admin" if is_admin else "adult"
    mock_users = MagicMock()
    mock_users.is_empty.return_value = False
    mock_users.get.return_value = {
        "id": "test-user",
        "display_name": "Test Operator",
        "is_admin": is_admin,
        "role": role,
        "prefs": {},
    }
    mock_users.get_public_one.return_value = {"display_name": "Test Operator"}

    mock_tokens = MagicMock()
    mock_tokens.validate.return_value = "test-user"
    mock_tokens.purge_expired.return_value = 0
    return mock_users, mock_tokens


def _next_of_type(ws, msg_type: str, limit: int = 15) -> dict | None:
    """Receive frames until one matching msg_type arrives; return it (or None)."""
    for _ in range(limit):
        msg = ws.receive_json()
        if msg.get("type") == msg_type:
            return msg
    return None


def _drain_initial(ws, limit: int = 12) -> list[dict]:
    """Drain the burst of initial frames every new connection receives."""
    frames = []
    for _ in range(limit):
        msg = ws.receive_json()
        frames.append(msg)
        if msg.get("type") == "chat_history":
            break
    return frames


def _drain_display_snapshots(ws, limit: int = 8) -> list[dict]:
    """Drain the display snapshot burst; stop once chat_history is seen."""
    frames = []
    for _ in range(limit):
        msg = ws.receive_json()
        frames.append(msg)
        if msg.get("type") == "chat_history":
            break
    return frames


@pytest.fixture
def device_store(tmp_path):
    """Real (tmp_path-backed) DeviceTokenStore — not a mock — so
    create/revoke/validate exercise Task 1's actual behavior."""
    return DeviceTokenStore(path=tmp_path / "device_tokens.json")


@pytest.fixture
def client(tmp_path, device_store):
    cfg = _minimal_cfg(tmp_path)
    cfg.save = MagicMock()
    mock_stt, mock_tts = _make_mocks()
    mock_users, mock_tokens = _make_auth_mocks(is_admin=True)
    with (
        patch("backend.server.ServerConfig.load", return_value=cfg),
        patch("backend.server.STTWorker", return_value=mock_stt),
        patch("backend.server.TTSSynthesizer", return_value=mock_tts),
        patch("backend.server.UsersStore", return_value=mock_users),
        patch("backend.server.TokenStore", return_value=mock_tokens),
        patch("backend.server.DeviceTokenStore", return_value=device_store),
        patch("backend.auth_routes.init"),
    ):
        with TestClient(app) as tc:
            yield tc


@pytest.fixture
def non_admin_client(tmp_path, device_store):
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
        patch("backend.server.DeviceTokenStore", return_value=device_store),
        patch("backend.auth_routes.init"),
    ):
        with TestClient(app) as tc:
            yield tc


@pytest.fixture
def admin_ws(client):
    with client.websocket_connect(WS_URL) as ws:
        _drain_initial(ws)
        yield ws


@pytest.fixture
def user_ws(non_admin_client):
    with non_admin_client.websocket_connect(WS_URL) as ws:
        _drain_initial(ws)
        yield ws


# ---------------------------------------------------------------------------
# Device token admin
# ---------------------------------------------------------------------------

class TestDeviceTokenAdmin:
    def test_create_returns_full_token_once(self, admin_ws):
        admin_ws.send_json({"type": "device_token_create", "label": "Kitchen"})
        msg = _next_of_type(admin_ws, "device_token_created")
        assert msg is not None
        assert msg["record"]["label"] == "Kitchen"
        assert len(msg["record"]["token"]) >= 32

    def test_create_followed_by_device_tokens_list(self, admin_ws):
        admin_ws.send_json({"type": "device_token_create", "label": "Kitchen"})
        _next_of_type(admin_ws, "device_token_created")
        msg = _next_of_type(admin_ws, "device_tokens")
        assert msg is not None
        assert msg["tokens"][0]["label"] == "Kitchen"

    def test_list_omits_token_field(self, admin_ws):
        admin_ws.send_json({"type": "device_token_create", "label": "Kitchen"})
        _next_of_type(admin_ws, "device_token_created")
        admin_ws.send_json({"type": "device_token_list"})
        msg = _next_of_type(admin_ws, "device_tokens")
        assert msg["tokens"] and "token" not in msg["tokens"][0]
        assert set(msg["tokens"][0].keys()) == {"id", "label", "created_at", "last_seen", "eink"}

    def test_create_invalid_label_returns_error(self, admin_ws):
        admin_ws.send_json({"type": "device_token_create", "label": ""})
        msg = _next_of_type(admin_ws, "error")
        assert msg is not None

    def test_revoke_disconnects_live_display(self, admin_ws, client):
        admin_ws.send_json({"type": "device_token_create", "label": "Kitchen"})
        rec = _next_of_type(admin_ws, "device_token_created")["record"]
        _next_of_type(admin_ws, "device_tokens")  # drain create's follow-up list refresh
        with client.websocket_connect(f"/ws?device_token={rec['token']}") as dws:
            _drain_display_snapshots(dws)
            admin_ws.send_json({"type": "device_token_revoke", "id": rec["id"]})
            msg = _next_of_type(admin_ws, "device_tokens")
            assert msg is not None
            assert msg["tokens"] == []
            # display socket should now be closed (receive raises)
            with pytest.raises(Exception):
                while True:
                    dws.receive_json()

    def test_non_admin_rejected(self, user_ws):
        user_ws.send_json({"type": "device_token_create", "label": "Kitchen"})
        msg = _next_of_type(user_ws, "error")
        assert msg is not None
        assert "admin" in msg["detail"].lower()

    def test_non_admin_list_rejected(self, user_ws):
        user_ws.send_json({"type": "device_token_list"})
        msg = _next_of_type(user_ws, "error")
        assert msg is not None
        assert "admin" in msg["detail"].lower()

    def test_non_admin_revoke_rejected(self, user_ws):
        user_ws.send_json({"type": "device_token_revoke", "id": "whatever"})
        msg = _next_of_type(user_ws, "error")
        assert msg is not None
        assert "admin" in msg["detail"].lower()


# ---------------------------------------------------------------------------
# Household quick messages config
# ---------------------------------------------------------------------------

class TestDisplayQuickMessagesConfig:
    def test_default_empty(self, admin_ws):
        admin_ws.send_json({"type": "set_admin_config", "name": "New Station Name"})
        msg = _next_of_type(admin_ws, "status")
        assert msg["display_quick_messages"] == []

    def test_admin_can_set_and_status_carries_it(self, admin_ws):
        admin_ws.send_json({"type": "set_admin_config",
                            "display_quick_messages": ["Dinner is ready", "Come home please"]})
        msg = _next_of_type(admin_ws, "status")
        assert msg["display_quick_messages"] == ["Dinner is ready", "Come home please"]

    def test_empty_list_allowed(self, admin_ws):
        admin_ws.send_json({"type": "set_admin_config",
                            "display_quick_messages": ["Dinner is ready"]})
        _next_of_type(admin_ws, "status")
        admin_ws.send_json({"type": "set_admin_config", "display_quick_messages": []})
        msg = _next_of_type(admin_ws, "status")
        assert msg["display_quick_messages"] == []

    def test_invalid_entries_rejected(self, admin_ws):
        admin_ws.send_json({"type": "set_admin_config",
                            "display_quick_messages": ["ok", "x" * 300]})
        msg = _next_of_type(admin_ws, "error")
        assert msg is not None
        assert "quick message" in msg["detail"].lower()

    def test_invalid_quick_messages_does_not_block_other_fields(self, admin_ws):
        """A mixed payload with an invalid display_quick_messages alongside a
        valid unrelated admin field should still apply the valid field (per-field
        validation, matching the skip-only-this-field idiom used by neighboring
        set_admin_config legs like neighborhood_net_day/tts_length_scale/rx_mode),
        while still reporting the display_quick_messages error."""
        admin_ws.send_json({"type": "set_admin_config",
                            "name": "New Station Name",
                            "display_quick_messages": ["ok", "x" * 300]})
        err = _next_of_type(admin_ws, "error")
        assert err is not None
        assert "quick message" in err["detail"].lower()
        status = _next_of_type(admin_ws, "status")
        assert status is not None
        assert status["station_name"] == "New Station Name"
        assert status["display_quick_messages"] == []
