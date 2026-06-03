"""Unit tests for backend.persistence.users.UsersStore."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.persistence.users import (
    DEFAULT_PREFS,
    LOCKOUT_DURATION_MINUTES,
    LOCKOUT_MAX_ATTEMPTS,
    SENSITIVE_PROFILE_FIELDS,
    UsersStore,
    _hash_password,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "users.json"


@pytest.fixture()
def store(store_path: Path) -> UsersStore:
    return UsersStore(path=store_path)


@pytest.fixture()
def alice(store: UsersStore) -> dict:
    return store.create(display_name="Alice", password="secret123")


@pytest.fixture()
def bob(store: UsersStore) -> dict:
    return store.create(display_name="Bob", password="hunter2")


# ---------------------------------------------------------------------------
# Tests: initialisation / loading
# ---------------------------------------------------------------------------

class TestInit:
    def test_is_empty_when_file_absent(self, store_path: Path):
        s = UsersStore(path=store_path)
        assert s.is_empty()

    def test_loads_existing_users(self, store_path: Path):
        # Pre-populate directly so we test _load, not create
        now = datetime.now(timezone.utc).isoformat()
        data = [{"id": "alice", "display_name": "Alice", "created_at": now}]
        store_path.write_text(json.dumps(data), encoding="utf-8")
        s = UsersStore(path=store_path)
        assert not s.is_empty()
        assert s.get("alice") is not None

    def test_empty_on_malformed_json(self, store_path: Path):
        store_path.write_text("not json", encoding="utf-8")
        s = UsersStore(path=store_path)
        assert s.is_empty()

    def test_empty_when_file_contains_dict(self, store_path: Path):
        store_path.write_text('{"key": "value"}', encoding="utf-8")
        s = UsersStore(path=store_path)
        assert s.is_empty()


# ---------------------------------------------------------------------------
# Tests: create
# ---------------------------------------------------------------------------

class TestCreate:
    def test_returns_profile_dict(self, store: UsersStore):
        profile = store.create(display_name="Alice", password="pw")
        assert isinstance(profile, dict)
        assert profile["display_name"] == "Alice"

    def test_persists_to_disk(self, store_path: Path, store: UsersStore):
        store.create(display_name="Alice", password="pw")
        on_disk = json.loads(store_path.read_text(encoding="utf-8"))
        assert isinstance(on_disk, list) and len(on_disk) == 1

    def test_id_derived_from_display_name(self, store: UsersStore):
        p = store.create(display_name="My Station", password="pw")
        assert p["id"] == "my-station"

    def test_id_is_unique_for_duplicates(self, store: UsersStore):
        p1 = store.create(display_name="Alice", password="pw1")
        p2 = store.create(display_name="Alice", password="pw2")
        assert p1["id"] != p2["id"]
        assert p2["id"] == "alice-2"

    def test_password_is_not_stored_in_plain_text(self, store: UsersStore):
        p = store.create(display_name="Alice", password="supersecret")
        assert "supersecret" not in json.dumps(p)

    def test_password_hash_and_salt_present(self, store: UsersStore):
        p = store.create(display_name="Alice", password="pw")
        assert "password_hash" in p and "password_salt" in p

    def test_is_admin_default_false(self, store: UsersStore):
        p = store.create(display_name="Alice", password="pw")
        assert p["is_admin"] is False

    def test_is_admin_can_be_set_true(self, store: UsersStore):
        p = store.create(display_name="Alice", password="pw", is_admin=True)
        assert p["is_admin"] is True

    def test_default_prefs_applied(self, store: UsersStore):
        p = store.create(display_name="Alice", password="pw")
        for k, v in DEFAULT_PREFS.items():
            assert p["prefs"][k] == v

    def test_custom_prefs_override_defaults(self, store: UsersStore):
        p = store.create(display_name="Alice", password="pw", prefs={"dark_mode": True})
        assert p["prefs"]["dark_mode"] is True
        # Other defaults still present
        assert p["prefs"]["filter_profanity"] is True

    def test_failed_attempts_initialised_to_zero(self, store: UsersStore):
        p = store.create(display_name="Alice", password="pw")
        assert p["failed_attempts"] == 0

    def test_locked_until_initialised_to_none(self, store: UsersStore):
        p = store.create(display_name="Alice", password="pw")
        assert p["locked_until"] is None

    def test_operator_name_defaults_to_display_name(self, store: UsersStore):
        p = store.create(display_name="Alice", password="pw")
        assert p["operator_name"] == "Alice"

    def test_operator_name_can_be_overridden(self, store: UsersStore):
        p = store.create(display_name="Alice", password="pw", operator_name="AK6XY")
        assert p["operator_name"] == "AK6XY"

    def test_optional_profile_fields(self, store: UsersStore):
        p = store.create(
            display_name="Alice",
            password="pw",
            callsign="W1AW",
            location="Hartford CT",
            avatar_emoji="📻",
        )
        assert p["callsign"] == "W1AW"
        assert p["location"] == "Hartford CT"
        assert p["avatar_emoji"] == "📻"

    def test_id_fallback_for_special_chars(self, store: UsersStore):
        p = store.create(display_name="!!!---", password="pw")
        # Should not raise; id should be non-empty
        assert len(p["id"]) > 0

    def test_created_at_is_iso_timestamp(self, store: UsersStore):
        p = store.create(display_name="Alice", password="pw")
        datetime.fromisoformat(p["created_at"])  # must not raise


# ---------------------------------------------------------------------------
# Tests: get / get_all / get_by_display_name / is_empty
# ---------------------------------------------------------------------------

class TestGet:
    def test_get_returns_none_for_unknown_id(self, store: UsersStore):
        assert store.get("nobody") is None

    def test_get_returns_copy(self, store: UsersStore, alice: dict):
        copy = store.get(alice["id"])
        copy["display_name"] = "MUTATED"
        assert store.get(alice["id"])["display_name"] == "Alice"

    def test_get_all_returns_list_copy(self, store: UsersStore, alice: dict):
        result = store.get_all()
        result.clear()
        assert len(store.get_all()) == 1

    def test_get_by_display_name_found(self, store: UsersStore, alice: dict):
        result = store.get_by_display_name("Alice")
        assert result is not None
        assert result["id"] == alice["id"]

    def test_get_by_display_name_not_found(self, store: UsersStore):
        assert store.get_by_display_name("Unknown") is None

    def test_is_empty_false_after_create(self, store: UsersStore, alice: dict):
        assert not store.is_empty()


# ---------------------------------------------------------------------------
# Tests: get_public / get_public_one
# ---------------------------------------------------------------------------

class TestGetPublic:
    def test_sensitive_fields_stripped(self, store: UsersStore, alice: dict):
        public = store.get_public()
        for profile in public:
            for field in SENSITIVE_PROFILE_FIELDS:
                assert field not in profile

    def test_non_sensitive_fields_present(self, store: UsersStore, alice: dict):
        public = store.get_public()
        assert public[0]["display_name"] == "Alice"

    def test_get_public_one_returns_none_for_unknown(self, store: UsersStore):
        assert store.get_public_one("nobody") is None

    def test_get_public_one_strips_sensitive(self, store: UsersStore, alice: dict):
        result = store.get_public_one(alice["id"])
        for field in SENSITIVE_PROFILE_FIELDS:
            assert field not in result

    def test_get_public_one_returns_correct_user(self, store: UsersStore, alice: dict, bob: dict):
        result = store.get_public_one(bob["id"])
        assert result["display_name"] == "Bob"


# ---------------------------------------------------------------------------
# Tests: verify_password
# ---------------------------------------------------------------------------

class TestVerifyPassword:
    def test_correct_password_returns_true(self, store: UsersStore, alice: dict):
        assert store.verify_password(alice["id"], "secret123")

    def test_wrong_password_returns_false(self, store: UsersStore, alice: dict):
        assert not store.verify_password(alice["id"], "wrongpass")

    def test_unknown_user_returns_false(self, store: UsersStore):
        assert not store.verify_password("ghost", "pw")

    def test_successful_verify_resets_failed_attempts(self, store: UsersStore, alice: dict):
        store.verify_password(alice["id"], "wrongpass")
        store.verify_password(alice["id"], "secret123")
        u = store.get(alice["id"])
        assert u["failed_attempts"] == 0

    def test_failed_verify_increments_attempt_counter(self, store: UsersStore, alice: dict):
        store.verify_password(alice["id"], "bad")
        u = store.get(alice["id"])
        assert u["failed_attempts"] == 1

    def test_lockout_after_max_attempts(self, store: UsersStore, alice: dict):
        for _ in range(LOCKOUT_MAX_ATTEMPTS):
            store.verify_password(alice["id"], "bad")
        assert store.is_locked(alice["id"])

    def test_locked_user_returns_false(self, store: UsersStore, alice: dict):
        for _ in range(LOCKOUT_MAX_ATTEMPTS):
            store.verify_password(alice["id"], "bad")
        assert not store.verify_password(alice["id"], "secret123")

    def test_locked_until_set_after_lockout(self, store: UsersStore, alice: dict):
        for _ in range(LOCKOUT_MAX_ATTEMPTS):
            store.verify_password(alice["id"], "bad")
        u = store.get(alice["id"])
        assert u["locked_until"] is not None


# ---------------------------------------------------------------------------
# Tests: is_locked / locked_until_str
# ---------------------------------------------------------------------------

class TestLockout:
    def test_not_locked_initially(self, store: UsersStore, alice: dict):
        assert not store.is_locked(alice["id"])

    def test_not_locked_for_unknown_user(self, store: UsersStore):
        assert not store.is_locked("ghost")

    def test_locked_until_str_none_when_not_locked(self, store: UsersStore, alice: dict):
        assert store.locked_until_str(alice["id"]) is None

    def test_locked_until_str_none_for_unknown(self, store: UsersStore):
        assert store.locked_until_str("ghost") is None

    def test_lock_expires_automatically(self, store: UsersStore, alice: dict):
        """Simulate an already-expired lockout stored in the record."""
        idx = store._find_index(alice["id"])
        past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        store._users[idx]["locked_until"] = past
        # is_locked should detect the expiry and clear it
        assert not store.is_locked(alice["id"])
        assert store.get(alice["id"])["locked_until"] is None

    def test_malformed_locked_until_treated_as_expired(self, store: UsersStore, alice: dict):
        idx = store._find_index(alice["id"])
        store._users[idx]["locked_until"] = "not-a-date"
        assert not store.is_locked(alice["id"])

    def test_locked_until_str_returns_iso_when_locked(self, store: UsersStore, alice: dict):
        for _ in range(LOCKOUT_MAX_ATTEMPTS):
            store.verify_password(alice["id"], "bad")
        result = store.locked_until_str(alice["id"])
        assert result is not None
        datetime.fromisoformat(result)  # must parse cleanly


# ---------------------------------------------------------------------------
# Tests: update_prefs
# ---------------------------------------------------------------------------

class TestUpdatePrefs:
    def test_merges_partial_prefs(self, store: UsersStore, alice: dict):
        updated = store.update_prefs(alice["id"], {"dark_mode": True})
        assert updated["prefs"]["dark_mode"] is True

    def test_other_prefs_preserved(self, store: UsersStore, alice: dict):
        store.update_prefs(alice["id"], {"dark_mode": True})
        u = store.get(alice["id"])
        assert u["prefs"]["filter_profanity"] is True

    def test_persists_to_disk(self, store_path: Path, store: UsersStore, alice: dict):
        store.update_prefs(alice["id"], {"dark_mode": True})
        on_disk = json.loads(store_path.read_text(encoding="utf-8"))
        assert on_disk[0]["prefs"]["dark_mode"] is True

    def test_raises_keyerror_for_unknown_user(self, store: UsersStore):
        with pytest.raises(KeyError):
            store.update_prefs("nobody", {"dark_mode": True})

    def test_returns_updated_profile(self, store: UsersStore, alice: dict):
        result = store.update_prefs(alice["id"], {"dark_mode": True})
        assert result["prefs"]["dark_mode"] is True


# ---------------------------------------------------------------------------
# Tests: update_profile
# ---------------------------------------------------------------------------

class TestUpdateProfile:
    def test_updates_display_name(self, store: UsersStore, alice: dict):
        store.update_profile(alice["id"], {"display_name": "Alicia"})
        assert store.get(alice["id"])["display_name"] == "Alicia"

    def test_updates_callsign(self, store: UsersStore, alice: dict):
        store.update_profile(alice["id"], {"callsign": "W1AW"})
        assert store.get(alice["id"])["callsign"] == "W1AW"

    def test_updates_is_admin(self, store: UsersStore, alice: dict):
        store.update_profile(alice["id"], {"is_admin": True})
        assert store.get(alice["id"])["is_admin"] is True

    def test_unknown_fields_ignored(self, store: UsersStore, alice: dict):
        store.update_profile(alice["id"], {"hacker_field": "evil"})
        assert "hacker_field" not in store.get(alice["id"])

    def test_persists_to_disk(self, store_path: Path, store: UsersStore, alice: dict):
        store.update_profile(alice["id"], {"location": "Hartford CT"})
        on_disk = json.loads(store_path.read_text(encoding="utf-8"))
        assert on_disk[0]["location"] == "Hartford CT"

    def test_raises_keyerror_for_unknown_user(self, store: UsersStore):
        with pytest.raises(KeyError):
            store.update_profile("nobody", {"display_name": "X"})

    def test_returns_updated_profile(self, store: UsersStore, alice: dict):
        result = store.update_profile(alice["id"], {"location": "NY"})
        assert result["location"] == "NY"


# ---------------------------------------------------------------------------
# Tests: change_password
# ---------------------------------------------------------------------------

class TestChangePassword:
    def test_new_password_works(self, store: UsersStore, alice: dict):
        store.change_password(alice["id"], "newpassword")
        assert store.verify_password(alice["id"], "newpassword")

    def test_old_password_no_longer_works(self, store: UsersStore, alice: dict):
        store.change_password(alice["id"], "newpassword")
        assert not store.verify_password(alice["id"], "secret123")

    def test_resets_failed_attempts(self, store: UsersStore, alice: dict):
        store.verify_password(alice["id"], "bad")
        store.change_password(alice["id"], "newpassword")
        assert store.get(alice["id"])["failed_attempts"] == 0

    def test_clears_lockout(self, store: UsersStore, alice: dict):
        for _ in range(LOCKOUT_MAX_ATTEMPTS):
            store.verify_password(alice["id"], "bad")
        store.change_password(alice["id"], "newpassword")
        assert store.get(alice["id"])["locked_until"] is None

    def test_persists_to_disk(self, store_path: Path, store: UsersStore, alice: dict):
        old_hash = store.get(alice["id"])["password_hash"]
        store.change_password(alice["id"], "newpassword")
        on_disk = json.loads(store_path.read_text(encoding="utf-8"))
        assert on_disk[0]["password_hash"] != old_hash

    def test_raises_keyerror_for_unknown_user(self, store: UsersStore):
        with pytest.raises(KeyError):
            store.change_password("nobody", "pw")


# ---------------------------------------------------------------------------
# Tests: delete
# ---------------------------------------------------------------------------

class TestDelete:
    def test_removes_user(self, store: UsersStore, alice: dict):
        store.delete(alice["id"])
        assert store.get(alice["id"]) is None

    def test_persists_deletion(self, store_path: Path, store: UsersStore, alice: dict):
        store.delete(alice["id"])
        on_disk = json.loads(store_path.read_text(encoding="utf-8"))
        assert on_disk == []

    def test_raises_keyerror_for_unknown(self, store: UsersStore):
        with pytest.raises(KeyError):
            store.delete("ghost")

    def test_only_target_user_removed(self, store: UsersStore, alice: dict, bob: dict):
        store.delete(alice["id"])
        assert store.get(bob["id"]) is not None
        assert len(store.get_all()) == 1


# ---------------------------------------------------------------------------
# Tests: reset_lockout
# ---------------------------------------------------------------------------

class TestResetLockout:
    def test_clears_failed_attempts(self, store: UsersStore, alice: dict):
        store.verify_password(alice["id"], "bad")
        store.reset_lockout(alice["id"])
        assert store.get(alice["id"])["failed_attempts"] == 0

    def test_clears_locked_until(self, store: UsersStore, alice: dict):
        for _ in range(LOCKOUT_MAX_ATTEMPTS):
            store.verify_password(alice["id"], "bad")
        store.reset_lockout(alice["id"])
        assert store.get(alice["id"])["locked_until"] is None

    def test_persists_to_disk(self, store_path: Path, store: UsersStore, alice: dict):
        for _ in range(LOCKOUT_MAX_ATTEMPTS):
            store.verify_password(alice["id"], "bad")
        store.reset_lockout(alice["id"])
        on_disk = json.loads(store_path.read_text(encoding="utf-8"))
        assert on_disk[0]["locked_until"] is None

    def test_raises_keyerror_for_unknown_user(self, store: UsersStore):
        with pytest.raises(KeyError):
            store.reset_lockout("ghost")


# ---------------------------------------------------------------------------
# Tests: _hash_password (private helper, but public enough to test directly)
# ---------------------------------------------------------------------------

class TestHashPassword:
    def test_same_inputs_produce_same_hash(self):
        import secrets
        salt = secrets.token_hex(32)
        h1 = _hash_password("password", salt)
        h2 = _hash_password("password", salt)
        assert h1 == h2

    def test_different_passwords_produce_different_hash(self):
        import secrets
        salt = secrets.token_hex(32)
        assert _hash_password("pw1", salt) != _hash_password("pw2", salt)

    def test_different_salts_produce_different_hash(self):
        import secrets
        h1 = _hash_password("pw", secrets.token_hex(32))
        h2 = _hash_password("pw", secrets.token_hex(32))
        assert h1 != h2

    def test_returns_hex_string(self):
        import secrets
        h = _hash_password("pw", secrets.token_hex(32))
        int(h, 16)  # must not raise
