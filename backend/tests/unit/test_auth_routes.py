"""Tests for backend.auth_routes — HTTP auth endpoints.

Strategy
--------
auth_routes uses module-level globals (_users_store, _token_store, _config)
populated by init().  We call init() in each test (or fixture) with MagicMock
objects, then mount the router on a bare FastAPI app and exercise it via
starlette TestClient.

We reset the module globals to None after each test to prevent state leakage.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient
from unittest.mock import MagicMock, patch

import backend.auth_routes as auth_routes_module
from backend.auth_routes import router


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app(users_store=None, token_store=None, config=None) -> TestClient:
    """Create a fresh FastAPI app with auth router and injected mocks."""
    app = FastAPI()
    app.include_router(router, prefix="/auth")
    auth_routes_module.init(users_store, token_store, config)
    return TestClient(app, raise_server_exceptions=False)


def _mock_user(
    user_id="user-1",
    display_name="Alice",
    is_admin=False,
    password_hash="hash",
    password_salt="salt",
    failed_attempts=0,
    locked_until=None,
) -> dict:
    return {
        "id": user_id,
        "display_name": display_name,
        "avatar_emoji": "👤",
        "operator_name": display_name,
        "callsign": "",
        "location": "",
        "password_hash": password_hash,
        "password_salt": password_salt,
        "is_admin": is_admin,
        "failed_attempts": failed_attempts,
        "locked_until": locked_until,
        "created_at": "2024-01-01T00:00:00+00:00",
        "prefs": {},
    }


def _safe_user(user: dict) -> dict:
    from backend.persistence.users import SENSITIVE_PROFILE_FIELDS
    return {k: v for k, v in user.items() if k not in SENSITIVE_PROFILE_FIELDS}


@pytest.fixture(autouse=True)
def reset_globals():
    """Ensure module globals are wiped after every test."""
    yield
    auth_routes_module.init(None, None, None)


# ---------------------------------------------------------------------------
# GET /auth/setup-status
# ---------------------------------------------------------------------------

class TestSetupStatus:
    def test_returns_503_when_not_initialised(self):
        client = _make_app()  # both stores left None after reset_globals
        # init called with None already in _make_app; but reset_globals runs
        # *after* the test body, so we manually set None here.
        auth_routes_module.init(None, None, None)
        r = client.get("/auth/setup-status")
        assert r.status_code == 503

    def test_setup_needed_true_when_store_empty(self):
        users = MagicMock()
        users.is_empty.return_value = True
        client = _make_app(users_store=users)
        r = client.get("/auth/setup-status")
        assert r.status_code == 200
        assert r.json() == {"setup_needed": True}

    def test_setup_needed_false_when_users_exist(self):
        users = MagicMock()
        users.is_empty.return_value = False
        client = _make_app(users_store=users)
        r = client.get("/auth/setup-status")
        assert r.status_code == 200
        assert r.json() == {"setup_needed": False}


# ---------------------------------------------------------------------------
# POST /auth/setup
# ---------------------------------------------------------------------------

class TestSetup:
    def test_returns_503_when_not_initialised(self):
        auth_routes_module.init(None, None, None)
        app = FastAPI()
        app.include_router(router, prefix="/auth")
        client = TestClient(app, raise_server_exceptions=False)
        r = client.post("/auth/setup", json={"display_name": "Admin", "password": "password123"})
        assert r.status_code == 503

    def test_returns_409_when_setup_already_done(self):
        users = MagicMock()
        users.is_empty.return_value = False
        tokens = MagicMock()
        client = _make_app(users_store=users, token_store=tokens)
        r = client.post("/auth/setup", json={"display_name": "Admin", "password": "password123"})
        assert r.status_code == 409

    def test_returns_422_when_display_name_blank(self):
        users = MagicMock()
        users.is_empty.return_value = True
        tokens = MagicMock()
        client = _make_app(users_store=users, token_store=tokens)
        r = client.post("/auth/setup", json={"display_name": "   ", "password": "password123"})
        assert r.status_code == 422

    def test_returns_422_when_password_too_short(self):
        users = MagicMock()
        users.is_empty.return_value = True
        tokens = MagicMock()
        client = _make_app(users_store=users, token_store=tokens)
        r = client.post("/auth/setup", json={"display_name": "Admin", "password": "short"})
        assert r.status_code == 422

    def test_successful_setup_returns_token_and_profile(self):
        user = _mock_user(user_id="admin", display_name="Admin", is_admin=True)
        users = MagicMock()
        users.is_empty.return_value = True
        users.create.return_value = user
        tokens = MagicMock()
        tokens.create.return_value = "tok-abc"
        client = _make_app(users_store=users, token_store=tokens)

        r = client.post("/auth/setup", json={"display_name": "Admin", "password": "password123"})

        assert r.status_code == 200
        body = r.json()
        assert body["token"] == "tok-abc"
        assert body["profile"]["display_name"] == "Admin"
        # Sensitive fields must be stripped
        assert "password_hash" not in body["profile"]
        assert "password_salt" not in body["profile"]

    def test_setup_strips_sensitive_fields(self):
        user = _mock_user(user_id="admin", display_name="Admin", is_admin=True)
        users = MagicMock()
        users.is_empty.return_value = True
        users.create.return_value = user
        tokens = MagicMock()
        tokens.create.return_value = "tok-xyz"
        client = _make_app(users_store=users, token_store=tokens)

        r = client.post("/auth/setup", json={"display_name": "Admin", "password": "password123"})
        body = r.json()
        for field in ("password_hash", "password_salt", "failed_attempts", "locked_until"):
            assert field not in body["profile"], f"{field!r} should be stripped from profile"

    def test_setup_saves_callsign_to_config(self):
        user = _mock_user(user_id="admin", display_name="Admin", is_admin=True)
        users = MagicMock()
        users.is_empty.return_value = True
        users.create.return_value = user
        tokens = MagicMock()
        tokens.create.return_value = "tok"
        config = MagicMock()
        config.__setitem__ = MagicMock()
        client = _make_app(users_store=users, token_store=tokens, config=config)

        client.post(
            "/auth/setup",
            json={"display_name": "Admin", "password": "password123", "callsign": "W1AW"},
        )
        config.save.assert_called_once()

    def test_setup_does_not_save_blank_callsign_to_config(self):
        user = _mock_user(user_id="admin", display_name="Admin", is_admin=True)
        users = MagicMock()
        users.is_empty.return_value = True
        users.create.return_value = user
        tokens = MagicMock()
        tokens.create.return_value = "tok"
        config = MagicMock()
        config.__setitem__ = MagicMock()
        # Use a dict-like config but track __setitem__ calls
        real_config: dict = {}
        config.__setitem__.side_effect = real_config.__setitem__
        client = _make_app(users_store=users, token_store=tokens, config=config)

        client.post(
            "/auth/setup",
            json={"display_name": "Admin", "password": "password123", "callsign": ""},
        )
        # save is still called (config exists), but callsign key not set
        assert "callsign" not in real_config


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------

class TestLogin:
    def test_returns_503_when_not_initialised(self):
        auth_routes_module.init(None, None, None)
        app = FastAPI()
        app.include_router(router, prefix="/auth")
        client = TestClient(app, raise_server_exceptions=False)
        r = client.post("/auth/login", json={"display_name": "Alice", "password": "pw"})
        assert r.status_code == 503

    def test_unknown_user_returns_401(self):
        users = MagicMock()
        users.get_all.return_value = []
        tokens = MagicMock()
        client = _make_app(users_store=users, token_store=tokens)
        r = client.post("/auth/login", json={"display_name": "Nobody", "password": "pw"})
        assert r.status_code == 401

    def test_locked_account_returns_423(self):
        user = _mock_user(display_name="Alice")
        users = MagicMock()
        users.get_all.return_value = [user]
        users.is_locked.return_value = True
        users.locked_until_str.return_value = "2099-01-01T00:00:00+00:00"
        tokens = MagicMock()
        client = _make_app(users_store=users, token_store=tokens)
        r = client.post("/auth/login", json={"display_name": "Alice", "password": "wrong"})
        assert r.status_code == 423

    def test_wrong_password_returns_401(self):
        user = _mock_user(display_name="Alice")
        users = MagicMock()
        users.get_all.return_value = [user]
        users.is_locked.return_value = False
        users.verify_password.return_value = False
        tokens = MagicMock()
        client = _make_app(users_store=users, token_store=tokens)
        r = client.post("/auth/login", json={"display_name": "Alice", "password": "bad"})
        assert r.status_code == 401

    def test_wrong_password_triggers_lockout_returns_423(self):
        """If verify_password returns False AND account becomes locked, return 423."""
        user = _mock_user(display_name="Alice")
        users = MagicMock()
        users.get_all.return_value = [user]
        # Not locked before the attempt, but locked after failed verify
        users.is_locked.side_effect = [False, True]
        users.verify_password.return_value = False
        users.locked_until_str.return_value = "2099-01-01T00:00:00+00:00"
        tokens = MagicMock()
        client = _make_app(users_store=users, token_store=tokens)
        r = client.post("/auth/login", json={"display_name": "Alice", "password": "bad"})
        assert r.status_code == 423

    def test_successful_login_returns_token_and_profile(self):
        user = _mock_user(display_name="Alice")
        users = MagicMock()
        users.get_all.return_value = [user]
        users.is_locked.return_value = False
        users.verify_password.return_value = True
        users.get.return_value = user
        tokens = MagicMock()
        tokens.create.return_value = "session-tok"
        client = _make_app(users_store=users, token_store=tokens)
        r = client.post("/auth/login", json={"display_name": "Alice", "password": "correct"})
        assert r.status_code == 200
        body = r.json()
        assert body["token"] == "session-tok"
        assert body["profile"]["display_name"] == "Alice"

    def test_login_strips_sensitive_fields(self):
        user = _mock_user(display_name="Alice")
        users = MagicMock()
        users.get_all.return_value = [user]
        users.is_locked.return_value = False
        users.verify_password.return_value = True
        users.get.return_value = user
        tokens = MagicMock()
        tokens.create.return_value = "tok"
        client = _make_app(users_store=users, token_store=tokens)
        r = client.post("/auth/login", json={"display_name": "Alice", "password": "correct"})
        body = r.json()
        for field in ("password_hash", "password_salt", "failed_attempts", "locked_until"):
            assert field not in body["profile"]

    def test_login_is_case_insensitive_on_display_name(self):
        user = _mock_user(display_name="Alice")
        users = MagicMock()
        users.get_all.return_value = [user]
        users.is_locked.return_value = False
        users.verify_password.return_value = True
        users.get.return_value = user
        tokens = MagicMock()
        tokens.create.return_value = "tok"
        client = _make_app(users_store=users, token_store=tokens)
        r = client.post("/auth/login", json={"display_name": "ALICE", "password": "correct"})
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------

class TestLogout:
    def test_logout_revokes_token(self):
        tokens = MagicMock()
        client = _make_app(token_store=tokens)
        r = client.post("/auth/logout", headers={"Authorization": "Bearer my-token"})
        assert r.status_code == 204
        tokens.revoke.assert_called_once_with("my-token")

    def test_logout_without_auth_header_returns_204(self):
        tokens = MagicMock()
        client = _make_app(token_store=tokens)
        r = client.post("/auth/logout")
        assert r.status_code == 204
        tokens.revoke.assert_not_called()

    def test_logout_with_non_bearer_header_returns_204(self):
        tokens = MagicMock()
        client = _make_app(token_store=tokens)
        r = client.post("/auth/logout", headers={"Authorization": "Basic dXNlcjpwYXNz"})
        assert r.status_code == 204
        tokens.revoke.assert_not_called()

    def test_logout_when_token_store_none_returns_204(self):
        auth_routes_module.init(None, None, None)
        app = FastAPI()
        app.include_router(router, prefix="/auth")
        client = TestClient(app, raise_server_exceptions=False)
        r = client.post("/auth/logout", headers={"Authorization": "Bearer some-tok"})
        assert r.status_code == 204


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------

class TestMe:
    def test_missing_authorization_returns_401(self):
        tokens = MagicMock()
        users = MagicMock()
        client = _make_app(users_store=users, token_store=tokens)
        r = client.get("/auth/me")
        assert r.status_code == 401

    def test_non_bearer_header_returns_401(self):
        tokens = MagicMock()
        users = MagicMock()
        client = _make_app(users_store=users, token_store=tokens)
        r = client.get("/auth/me", headers={"Authorization": "Basic abc"})
        assert r.status_code == 401

    def test_invalid_token_returns_401(self):
        tokens = MagicMock()
        tokens.validate.return_value = None
        users = MagicMock()
        client = _make_app(users_store=users, token_store=tokens)
        r = client.get("/auth/me", headers={"Authorization": "Bearer bad-token"})
        assert r.status_code == 401

    def test_valid_token_returns_profile(self):
        user = _mock_user(display_name="Alice")
        tokens = MagicMock()
        tokens.validate.return_value = "user-1"
        users = MagicMock()
        users.get.return_value = user
        client = _make_app(users_store=users, token_store=tokens)
        r = client.get("/auth/me", headers={"Authorization": "Bearer good-token"})
        assert r.status_code == 200
        assert r.json()["display_name"] == "Alice"

    def test_me_strips_sensitive_fields(self):
        user = _mock_user(display_name="Alice")
        tokens = MagicMock()
        tokens.validate.return_value = "user-1"
        users = MagicMock()
        users.get.return_value = user
        client = _make_app(users_store=users, token_store=tokens)
        r = client.get("/auth/me", headers={"Authorization": "Bearer good-token"})
        body = r.json()
        for field in ("password_hash", "password_salt", "failed_attempts", "locked_until"):
            assert field not in body

    def test_unknown_user_id_from_token_returns_404(self):
        tokens = MagicMock()
        tokens.validate.return_value = "ghost-user"
        users = MagicMock()
        users.get.return_value = None
        client = _make_app(users_store=users, token_store=tokens)
        r = client.get("/auth/me", headers={"Authorization": "Bearer valid-token"})
        assert r.status_code == 404

    def test_token_store_none_returns_503(self):
        # token_store=None triggers 503 in _require_token
        users = MagicMock()
        auth_routes_module.init(users, None, None)
        app = FastAPI()
        app.include_router(router, prefix="/auth")
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/auth/me", headers={"Authorization": "Bearer tok"})
        assert r.status_code == 503


# ---------------------------------------------------------------------------
# GET /auth/profiles
# ---------------------------------------------------------------------------

class TestProfiles:
    def test_returns_empty_list_when_store_none(self):
        auth_routes_module.init(None, None, None)
        app = FastAPI()
        app.include_router(router, prefix="/auth")
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/auth/profiles")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_public_profiles(self):
        public = [
            {"id": "user-1", "display_name": "Alice", "avatar_emoji": "👤"},
            {"id": "user-2", "display_name": "Bob", "avatar_emoji": "🎙️"},
        ]
        users = MagicMock()
        users.get_public.return_value = public
        client = _make_app(users_store=users)
        r = client.get("/auth/profiles")
        assert r.status_code == 200
        assert r.json() == public

    def test_delegates_to_get_public(self):
        users = MagicMock()
        users.get_public.return_value = []
        client = _make_app(users_store=users)
        client.get("/auth/profiles")
        users.get_public.assert_called_once()


# ---------------------------------------------------------------------------
# GET /auth/ws-ticket
# ---------------------------------------------------------------------------

class TestWsTicket:
    def _valid_client(self):
        tokens = MagicMock()
        tokens.validate.return_value = "user-1"
        tokens.create_ticket.return_value = "the-ticket"
        return _make_app(token_store=tokens), tokens

    def test_missing_auth_returns_401(self):
        tokens = MagicMock()
        tokens.validate.return_value = None
        client = _make_app(token_store=tokens)
        r = client.get("/auth/ws-ticket")
        assert r.status_code == 401

    def test_invalid_token_returns_401(self):
        tokens = MagicMock()
        tokens.validate.return_value = None
        client = _make_app(token_store=tokens)
        r = client.get("/auth/ws-ticket", headers={"Authorization": "Bearer bad"})
        assert r.status_code == 401

    def test_valid_token_returns_ticket(self):
        client, tokens = self._valid_client()
        r = client.get("/auth/ws-ticket", headers={"Authorization": "Bearer good"})
        assert r.status_code == 200
        assert r.json()["ticket"] == "the-ticket"

    def test_calls_create_ticket_with_user_id(self):
        client, tokens = self._valid_client()
        client.get("/auth/ws-ticket", headers={"Authorization": "Bearer good"})
        tokens.create_ticket.assert_called_once_with("user-1")

    def test_token_store_none_returns_503(self):
        client = _make_app(token_store=None)
        r = client.get("/auth/ws-ticket", headers={"Authorization": "Bearer x"})
        assert r.status_code == 503


# ---------------------------------------------------------------------------
# POST /auth/admin/revoke-user/{user_id}
# ---------------------------------------------------------------------------

class TestAdminRevokeUser:
    def _admin_client(self, target_exists=True, revoked_count=2):
        admin = _mock_user(user_id="admin-1", display_name="Admin", is_admin=True)
        target = _mock_user(user_id="target-1", display_name="Target")
        tokens = MagicMock()
        tokens.validate.return_value = "admin-1"
        tokens.revoke_all_for_user.return_value = revoked_count
        users = MagicMock()
        users.get.side_effect = lambda uid: (
            admin if uid == "admin-1" else (target if (uid == "target-1" and target_exists) else None)
        )
        return _make_app(users_store=users, token_store=tokens), tokens

    def test_non_admin_returns_403(self):
        non_admin = _mock_user(user_id="user-1", display_name="Alice", is_admin=False)
        tokens = MagicMock()
        tokens.validate.return_value = "user-1"
        users = MagicMock()
        users.get.return_value = non_admin
        client = _make_app(users_store=users, token_store=tokens)
        r = client.post("/auth/admin/revoke-user/target-1",
                        headers={"Authorization": "Bearer tok"})
        assert r.status_code == 403

    def test_missing_auth_returns_401(self):
        client, _ = self._admin_client()
        r = client.post("/auth/admin/revoke-user/target-1")
        assert r.status_code == 401

    def test_unknown_target_user_returns_404(self):
        client, _ = self._admin_client(target_exists=False)
        r = client.post("/auth/admin/revoke-user/no-such-user",
                        headers={"Authorization": "Bearer tok"})
        assert r.status_code == 404

    def test_success_returns_revoked_count(self):
        client, _ = self._admin_client(revoked_count=3)
        r = client.post("/auth/admin/revoke-user/target-1",
                        headers={"Authorization": "Bearer tok"})
        assert r.status_code == 200
        assert r.json()["revoked"] == 3

    def test_calls_revoke_all_for_user(self):
        client, tokens = self._admin_client()
        client.post("/auth/admin/revoke-user/target-1",
                    headers={"Authorization": "Bearer tok"})
        tokens.revoke_all_for_user.assert_called_once_with("target-1")

    def test_token_store_none_returns_503(self):
        client = _make_app(token_store=None)
        r = client.post("/auth/admin/revoke-user/x",
                        headers={"Authorization": "Bearer tok"})
        assert r.status_code == 503


# ---------------------------------------------------------------------------
# GET /auth/admin/audit
# ---------------------------------------------------------------------------

class TestAdminAudit:
    def _admin_client_with_audit(self, entries=None):
        admin = _mock_user(user_id="admin-1", display_name="Admin", is_admin=True)
        tokens = MagicMock()
        tokens.validate.return_value = "admin-1"
        users = MagicMock()
        users.get.return_value = admin
        audit = MagicMock()
        audit.tail.return_value = entries or []
        client = _make_app(users_store=users, token_store=tokens)
        import backend.auth_routes as m
        m._audit_log = audit
        return client, audit

    def test_non_admin_returns_403(self):
        non_admin = _mock_user(user_id="user-1", is_admin=False)
        tokens = MagicMock()
        tokens.validate.return_value = "user-1"
        users = MagicMock()
        users.get.return_value = non_admin
        client = _make_app(users_store=users, token_store=tokens)
        r = client.get("/auth/admin/audit", headers={"Authorization": "Bearer tok"})
        assert r.status_code == 403

    def test_missing_auth_returns_401(self):
        client, _ = self._admin_client_with_audit()
        r = client.get("/auth/admin/audit")
        assert r.status_code == 401

    def test_returns_audit_entries(self):
        entries = [{"event": "login_success", "user_id": "alice"}]
        client, _ = self._admin_client_with_audit(entries=entries)
        r = client.get("/auth/admin/audit", headers={"Authorization": "Bearer tok"})
        assert r.status_code == 200
        assert r.json() == entries

    def test_passes_limit_to_tail(self):
        client, audit = self._admin_client_with_audit()
        client.get("/auth/admin/audit?limit=50", headers={"Authorization": "Bearer tok"})
        audit.tail.assert_called_once_with(50)

    def test_limit_capped_at_1000(self):
        client, audit = self._admin_client_with_audit()
        client.get("/auth/admin/audit?limit=9999", headers={"Authorization": "Bearer tok"})
        audit.tail.assert_called_once_with(1000)

    def test_audit_log_none_returns_503(self):
        admin = _mock_user(user_id="admin-1", is_admin=True)
        tokens = MagicMock()
        tokens.validate.return_value = "admin-1"
        users = MagicMock()
        users.get.return_value = admin
        client = _make_app(users_store=users, token_store=tokens)
        import backend.auth_routes as m
        m._audit_log = None
        r = client.get("/auth/admin/audit", headers={"Authorization": "Bearer tok"})
        assert r.status_code == 503
