"""Display interaction handlers: display_im_ok, display_quick_message.

Task 4 of the kiosk WS work. Covers:
- display_im_ok: kitchen-tablet proxy for the family_status "I'm OK"
  check-in. The wall display has no user identity of its own, so the
  tapped family member is named explicitly in the message; the server
  only validates that the user exists (household trust model). Fan-out
  mirrors family_status (server.py ~2639): TTS enqueue + chat broadcast +
  presence mark + presence broadcast.
- display_quick_message: text must exactly match an entry in the admin's
  configured config.display_quick_messages allowlist (kid-gate precedent
  — no free text); fan-out is TTS enqueue + chat echo carrying the
  device's own label (not a user's display_name).

Fixture idiom mirrors test_display_ws.py / test_display_admin.py (TestClient
with mocked STT/TTS/UsersStore/TokenStore; DeviceTokenStore is a real
tmp_path-backed instance) plus test_server_ws.py's family_status fan-out
idiom (mock_users.get_public wired for _build_family_presence_msg's join
across every known profile).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from backend.config import ServerConfig
from backend.persistence.device_tokens import DeviceTokenStore
from backend.server import app

WS_URL = "/ws?token=test"

SEEDED_USER = {
    "id": "fam-1",
    "display_name": "Riley",
    "operator_name": "",
    "avatar_emoji": "🧒",
}


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
    """UsersStore mock wired for both the admin session-token connection
    (test-user) and display_im_ok's lookup of an arbitrary family member
    (SEEDED_USER) — plus get_public() for _build_family_presence_msg's
    join across every known profile."""
    mock_users = MagicMock()
    mock_users.is_empty.return_value = False
    mock_users.get.return_value = {
        "id": "test-user",
        "display_name": "Test Operator",
        "is_admin": True,
        "role": "admin",
        "prefs": {},
    }

    def _get_public_one(user_id):
        if user_id == SEEDED_USER["id"]:
            return dict(SEEDED_USER)
        if user_id == "test-user":
            return {"display_name": "Test Operator"}
        return None

    mock_users.get_public_one.side_effect = _get_public_one
    mock_users.get_public.return_value = [
        {"id": "test-user", "display_name": "Test Operator", "avatar_emoji": "👤"},
        dict(SEEDED_USER),
    ]

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


def _drain_display_snapshots(ws, limit: int = 8) -> list[dict]:
    """Drain the display snapshot burst; stop once chat_history is seen."""
    frames = []
    for _ in range(limit):
        msg = ws.receive_json()
        frames.append(msg)
        if msg.get("type") == "chat_history":
            break
    return frames


def _drain_initial(ws, limit: int = 12) -> list[dict]:
    """Drain a regular (session-token) connection's initial snapshot burst."""
    frames = []
    for _ in range(limit):
        msg = ws.receive_json()
        frames.append(msg)
        if msg.get("type") == "chat_history":
            break
    return frames


@pytest.fixture
def seeded_user():
    return dict(SEEDED_USER)


@pytest.fixture
def device_store(tmp_path):
    """Real (tmp_path-backed) DeviceTokenStore — not a mock — so
    create/revoke/validate exercise Task 1's actual behavior."""
    return DeviceTokenStore(path=tmp_path / "device_tokens.json")


@pytest.fixture
def display_token(device_store):
    """A valid device token, seeded with label 'Kitchen' (chat_echo
    display_name assertions rely on this exact label)."""
    rec = device_store.create("Kitchen")
    return rec["token"]


@pytest.fixture
def client(tmp_path, device_store):
    cfg = _minimal_cfg(tmp_path)
    cfg.save = MagicMock()
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
        patch("piper.PiperVoice"),
    ):
        with TestClient(app) as tc:
            yield tc


@pytest.fixture
def admin_ws(client):
    """A connected, authenticated admin session-token socket used to drive
    set_admin_config (display_quick_messages) ahead of a display connecting."""
    with client.websocket_connect(WS_URL) as ws:
        _drain_initial(ws)
        yield ws


# ---------------------------------------------------------------------------
# display_im_ok
# ---------------------------------------------------------------------------

class TestDisplayImOk:
    def test_im_ok_marks_presence_and_broadcasts(self, client, display_token, seeded_user):
        with client.websocket_connect(f"/ws?device_token={display_token}") as ws:
            _drain_display_snapshots(ws)
            ws.send_json({"type": "display_im_ok", "user_id": seeded_user["id"]})
            msg = _next_of_type(ws, "family_presence")
            assert msg is not None
            entry = next(e for e in msg["entries"] if e["user_id"] == seeded_user["id"])
            assert entry["last_ok"] is not None

    def test_im_ok_unknown_user_errors(self, client, display_token):
        with client.websocket_connect(f"/ws?device_token={display_token}") as ws:
            _drain_display_snapshots(ws)
            ws.send_json({"type": "display_im_ok", "user_id": "nope"})
            msg = _next_of_type(ws, "error")
            assert msg is not None
            assert "unknown" in msg["detail"].lower()

    def test_im_ok_posts_chat_line_with_member_name(self, client, display_token, seeded_user):
        with client.websocket_connect(f"/ws?device_token={display_token}") as ws:
            _drain_display_snapshots(ws)
            ws.send_json({"type": "display_im_ok", "user_id": seeded_user["id"]})
            msg = _next_of_type(ws, "chat_echo")
            assert msg is not None
            assert "is okay" in msg["text"]

    def test_im_ok_acks(self, client, display_token, seeded_user):
        with client.websocket_connect(f"/ws?device_token={display_token}") as ws:
            _drain_display_snapshots(ws)
            ws.send_json({"type": "display_im_ok", "user_id": seeded_user["id"]})
            msg = _next_of_type(ws, "display_ack")
            assert msg is not None
            assert msg["action"] == "im_ok"


# ---------------------------------------------------------------------------
# display_quick_message
# ---------------------------------------------------------------------------

class TestDisplayQuickMessage:
    def test_configured_message_is_accepted(self, client, display_token, admin_ws):
        admin_ws.send_json({"type": "set_admin_config",
                            "display_quick_messages": ["Dinner is ready"]})
        _next_of_type(admin_ws, "status")
        with client.websocket_connect(f"/ws?device_token={display_token}") as ws:
            _drain_display_snapshots(ws)
            ws.send_json({"type": "display_quick_message", "text": "Dinner is ready"})
            msg = _next_of_type(ws, "display_ack")
            assert msg is not None
            assert msg["action"] == "quick_message"

    def test_unlisted_text_rejected(self, client, display_token):
        with client.websocket_connect(f"/ws?device_token={display_token}") as ws:
            _drain_display_snapshots(ws)
            ws.send_json({"type": "display_quick_message", "text": "arbitrary free text"})
            msg = _next_of_type(ws, "error")
            assert msg is not None
            assert "not allowed" in msg["detail"].lower()

    def test_chat_echo_uses_device_label(self, client, display_token, admin_ws):
        admin_ws.send_json({"type": "set_admin_config",
                            "display_quick_messages": ["Dinner is ready"]})
        _next_of_type(admin_ws, "status")
        with client.websocket_connect(f"/ws?device_token={display_token}") as ws:
            _drain_display_snapshots(ws)
            ws.send_json({"type": "display_quick_message", "text": "Dinner is ready"})
            msg = _next_of_type(ws, "chat_echo")
            assert msg is not None
            assert msg["display_name"] == "Kitchen"  # fixture label
