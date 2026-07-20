"""Display (kiosk) WebSocket auth + scope gating.

Covers device-token auth on /ws (separate identity class from session-token
users) and the display scope gate: a wall-display connection may only send
_DISPLAY_ALLOWED_MSGS; everything else is rejected with an error frame
before it ever reaches plugin dispatch or the generic message handlers.

Fixture idiom mirrors test_server_ws.py (TestClient built with mocked
STT/TTS/UsersStore/TokenStore; DeviceTokenStore is a real tmp_path-backed
instance rather than a mock, so create()/revoke()/validate() exercise real
behavior end to end).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.config import ServerConfig
from backend.persistence.device_tokens import DeviceTokenStore
from backend.server import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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


def _make_auth_mocks():
    mock_users = MagicMock()
    mock_users.is_empty.return_value = False
    mock_users.get.return_value = {
        "id": "test-user",
        "display_name": "Test Operator",
        "is_admin": True,
        "role": "admin",
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


def _drain_snapshots(ws, limit: int = 8) -> list[dict]:
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
def display_token(device_store):
    """A valid device token, seeded with label 'Kitchen' (Task 4's tests rely
    on this label)."""
    rec = device_store.create("Kitchen")
    return rec["token"]


@pytest.fixture
def client(tmp_path, device_store):
    cfg = _minimal_cfg(tmp_path)
    mock_stt, mock_tts = _make_mocks()
    mock_users, mock_tokens = _make_auth_mocks()
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


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class TestDisplayAuth:
    def test_valid_device_token_connects_and_gets_snapshots(self, client, display_token):
        with client.websocket_connect(f"/ws?device_token={display_token}") as ws:
            types = [ws.receive_json()["type"] for _ in range(5)]
        assert "status" in types
        assert "display_config" in types
        assert "family_presence" in types
        assert "neighborhood_state" in types
        assert "chat_history" in types

    def test_display_snapshot_excludes_user_only_payloads(self, client, display_token):
        with client.websocket_connect(f"/ws?device_token={display_token}") as ws:
            types = [ws.receive_json()["type"] for _ in range(4)]
        assert "user_profile" not in types
        assert "contacts" not in types

    def test_bad_device_token_closes_4001(self, client):
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/ws?device_token=bogus-token") as ws:
                ws.receive_json()
        assert exc_info.value.code == 4001

    def test_revoked_token_cannot_connect(self, client, display_token, device_store):
        rec = device_store.list_all()[0]
        device_store.revoke(rec["id"])
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/ws?device_token={display_token}") as ws:
                ws.receive_json()
        assert exc_info.value.code == 4001


# ---------------------------------------------------------------------------
# Scope gate
# ---------------------------------------------------------------------------

class TestDisplayScope:
    def test_display_cannot_send_tx_message(self, client, display_token):
        with client.websocket_connect(f"/ws?device_token={display_token}") as ws:
            _drain_snapshots(ws)
            ws.send_json({"type": "tx_message", "callsign": "WABC123", "text": "hi"})
            msg = _next_of_type(ws, "error")
        assert msg is not None
        assert "wall display" in msg["detail"].lower()

    def test_display_cannot_use_admin_messages(self, client, display_token):
        with client.websocket_connect(f"/ws?device_token={display_token}") as ws:
            _drain_snapshots(ws)
            ws.send_json({"type": "device_token_list"})
            msg = _next_of_type(ws, "error")
        assert msg is not None
        assert "wall display" in msg["detail"].lower()
