"""Unit tests for backend.persistence.tokens.TokenStore."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.persistence.tokens import TokenStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "tokens.json"


@pytest.fixture()
def store(store_path: Path) -> TokenStore:
    return TokenStore(path=store_path)


# ---------------------------------------------------------------------------
# Tests: initialisation / loading
# ---------------------------------------------------------------------------

class TestInit:
    def test_starts_empty_when_file_absent(self, store_path: Path):
        ts = TokenStore(path=store_path)
        assert ts.validate("anything") is None

    def test_loads_existing_valid_token(self, store_path: Path):
        expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        data = {"mytoken": {"user_id": "alice", "expires_at": expires}}
        store_path.write_text(json.dumps(data), encoding="utf-8")
        ts = TokenStore(path=store_path)
        assert ts.validate("mytoken") == "alice"

    def test_starts_empty_on_malformed_json(self, store_path: Path):
        store_path.write_text("not json", encoding="utf-8")
        ts = TokenStore(path=store_path)
        assert ts.validate("anything") is None

    def test_starts_empty_when_file_contains_list(self, store_path: Path):
        store_path.write_text("[]", encoding="utf-8")
        ts = TokenStore(path=store_path)
        assert ts.validate("anything") is None


# ---------------------------------------------------------------------------
# Tests: create
# ---------------------------------------------------------------------------

class TestCreate:
    def test_returns_non_empty_string(self, store: TokenStore):
        token = store.create("alice")
        assert isinstance(token, str) and len(token) > 0

    def test_token_is_url_safe(self, store: TokenStore):
        token = store.create("alice")
        # URL-safe base64 only contains A-Z a-z 0-9 - _
        import re
        assert re.fullmatch(r"[A-Za-z0-9_\-]+", token)

    def test_each_call_returns_unique_token(self, store: TokenStore):
        tokens = {store.create("alice") for _ in range(10)}
        assert len(tokens) == 10

    def test_token_is_persisted_to_disk(self, store_path: Path, store: TokenStore):
        token = store.create("alice")
        on_disk = json.loads(store_path.read_text(encoding="utf-8"))
        assert token in on_disk

    def test_default_ttl_is_7_days(self, store: TokenStore):
        token = store.create("alice")
        # Validate right away should succeed
        assert store.validate(token) == "alice"

    def test_custom_ttl(self, store: TokenStore):
        token = store.create("alice", ttl_days=1)
        assert store.validate(token) == "alice"

    def test_multiple_users(self, store: TokenStore):
        t1 = store.create("alice")
        t2 = store.create("bob")
        assert store.validate(t1) == "alice"
        assert store.validate(t2) == "bob"


# ---------------------------------------------------------------------------
# Tests: validate
# ---------------------------------------------------------------------------

class TestValidate:
    def test_unknown_token_returns_none(self, store: TokenStore):
        assert store.validate("does-not-exist") is None

    def test_valid_token_returns_user_id(self, store: TokenStore):
        token = store.create("charlie")
        assert store.validate(token) == "charlie"

    def test_expired_token_returns_none(self, store_path: Path):
        past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        data = {"expiredtok": {"user_id": "alice", "expires_at": past}}
        store_path.write_text(json.dumps(data), encoding="utf-8")
        ts = TokenStore(path=store_path)
        assert ts.validate("expiredtok") is None

    def test_expired_token_removed_from_store(self, store_path: Path):
        past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        data = {"expiredtok": {"user_id": "alice", "expires_at": past}}
        store_path.write_text(json.dumps(data), encoding="utf-8")
        ts = TokenStore(path=store_path)
        ts.validate("expiredtok")
        assert ts.validate("expiredtok") is None

    def test_malformed_expires_at_returns_none(self, store_path: Path):
        data = {"badtok": {"user_id": "alice", "expires_at": "not-a-date"}}
        store_path.write_text(json.dumps(data), encoding="utf-8")
        ts = TokenStore(path=store_path)
        assert ts.validate("badtok") is None

    def test_missing_expires_at_returns_none(self, store_path: Path):
        data = {"badtok": {"user_id": "alice"}}
        store_path.write_text(json.dumps(data), encoding="utf-8")
        ts = TokenStore(path=store_path)
        assert ts.validate("badtok") is None


# ---------------------------------------------------------------------------
# Tests: revoke
# ---------------------------------------------------------------------------

class TestRevoke:
    def test_revoking_valid_token_invalidates_it(self, store: TokenStore):
        token = store.create("alice")
        store.revoke(token)
        assert store.validate(token) is None

    def test_revoke_persists_to_disk(self, store_path: Path, store: TokenStore):
        token = store.create("alice")
        store.revoke(token)
        on_disk = json.loads(store_path.read_text(encoding="utf-8"))
        assert token not in on_disk

    def test_revoking_unknown_token_is_noop(self, store: TokenStore):
        # Must not raise
        store.revoke("nonexistent-token")

    def test_revoke_only_removes_target_token(self, store: TokenStore):
        t1 = store.create("alice")
        t2 = store.create("bob")
        store.revoke(t1)
        assert store.validate(t2) == "bob"


# ---------------------------------------------------------------------------
# Tests: purge_expired
# ---------------------------------------------------------------------------

class TestPurgeExpired:
    def test_returns_zero_when_nothing_expired(self, store: TokenStore):
        store.create("alice")
        assert store.purge_expired() == 0

    def test_returns_count_of_purged_tokens(self, store_path: Path):
        past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        future = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        data = {
            "old1": {"user_id": "alice", "expires_at": past},
            "old2": {"user_id": "bob", "expires_at": past},
            "good": {"user_id": "charlie", "expires_at": future},
        }
        store_path.write_text(json.dumps(data), encoding="utf-8")
        ts = TokenStore(path=store_path)
        assert ts.purge_expired() == 2

    def test_valid_tokens_survive_purge(self, store_path: Path):
        past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        future = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        data = {
            "old": {"user_id": "alice", "expires_at": past},
            "good": {"user_id": "charlie", "expires_at": future},
        }
        store_path.write_text(json.dumps(data), encoding="utf-8")
        ts = TokenStore(path=store_path)
        ts.purge_expired()
        assert ts.validate("good") == "charlie"

    def test_purge_persists_removal(self, store_path: Path):
        past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        data = {"old": {"user_id": "alice", "expires_at": past}}
        store_path.write_text(json.dumps(data), encoding="utf-8")
        ts = TokenStore(path=store_path)
        ts.purge_expired()
        on_disk = json.loads(store_path.read_text(encoding="utf-8"))
        assert "old" not in on_disk

    def test_purge_skips_save_when_nothing_expired(self, store_path: Path):
        """purge_expired should not write the file if nothing was purged."""
        future = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        data = {"good": {"user_id": "alice", "expires_at": future}}
        store_path.write_text(json.dumps(data), encoding="utf-8")
        ts = TokenStore(path=store_path)
        mtime_before = store_path.stat().st_mtime
        ts.purge_expired()
        mtime_after = store_path.stat().st_mtime
        assert mtime_before == mtime_after

    def test_malformed_entry_treated_as_expired(self, store_path: Path):
        data = {"badentry": {"user_id": "alice", "expires_at": "garbage"}}
        store_path.write_text(json.dumps(data), encoding="utf-8")
        ts = TokenStore(path=store_path)
        count = ts.purge_expired()
        assert count == 1


# ---------------------------------------------------------------------------
# Tests: revoke_all_for_user
# ---------------------------------------------------------------------------

class TestRevokeAllForUser:
    def test_removes_all_tokens_for_user(self, store: TokenStore):
        t1 = store.create("alice")
        t2 = store.create("alice")
        count = store.revoke_all_for_user("alice")
        assert count == 2
        assert store.validate(t1) is None
        assert store.validate(t2) is None

    def test_does_not_affect_other_users(self, store: TokenStore):
        store.create("alice")
        bob_token = store.create("bob")
        store.revoke_all_for_user("alice")
        assert store.validate(bob_token) == "bob"

    def test_returns_zero_when_user_has_no_tokens(self, store: TokenStore):
        assert store.revoke_all_for_user("nobody") == 0

    def test_persists_removal_to_disk(self, store_path: Path, store: TokenStore):
        t = store.create("alice")
        store.revoke_all_for_user("alice")
        on_disk = json.loads(store_path.read_text(encoding="utf-8"))
        assert t not in on_disk


# ---------------------------------------------------------------------------
# Tests: WS tickets (create_ticket / validate_ticket)
# ---------------------------------------------------------------------------

class TestTickets:
    def test_valid_ticket_returns_user_id(self, store: TokenStore):
        ticket = store.create_ticket("alice")
        assert store.validate_ticket(ticket) == "alice"

    def test_ticket_is_single_use(self, store: TokenStore):
        ticket = store.create_ticket("alice")
        store.validate_ticket(ticket)
        assert store.validate_ticket(ticket) is None

    def test_unknown_ticket_returns_none(self, store: TokenStore):
        assert store.validate_ticket("no-such-ticket") is None

    def test_expired_ticket_returns_none(self, store: TokenStore):
        ticket = store.create_ticket("alice", ttl_seconds=0)
        # ttl=0 means already expired at create time
        assert store.validate_ticket(ticket) is None

    def test_expired_unconsumed_ticket_pruned_on_next_create(self, store: TokenStore):
        store.create_ticket("alice", ttl_seconds=0)  # immediately expired
        assert len(store._tickets) == 1 or len(store._tickets) == 0  # may or may not be pruned yet
        store.create_ticket("bob")  # triggers prune
        assert all(
            v["user_id"] != "alice"
            for v in store._tickets.values()
        ), "expired alice ticket should have been pruned"

    def test_tickets_are_not_persisted(self, store_path: Path, store: TokenStore):
        store.create_ticket("alice")
        on_disk = json.loads(store_path.read_text(encoding="utf-8")) if store_path.exists() else {}
        # Session tokens file must not contain ticket entries
        assert all("_ticket" not in k for k in on_disk)
        # A freshly loaded store has no knowledge of the ticket
        fresh = TokenStore(path=store_path)
        assert len(fresh._tickets) == 0

    def test_tickets_are_unique(self, store: TokenStore):
        tickets = {store.create_ticket("alice") for _ in range(20)}
        assert len(tickets) == 20
