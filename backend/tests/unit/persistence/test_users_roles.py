"""Unit tests for role field, migration, and admin role management on UsersStore."""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.persistence.users import ROLES, UsersStore


@pytest.fixture()
def store(tmp_path: Path) -> UsersStore:
    return UsersStore(path=tmp_path / "users.json")


class TestRoleField:
    def test_create_defaults_to_adult(self, store: UsersStore):
        u = store.create(display_name="Kid Sis", password="pw12345678")
        assert u["role"] == "adult"

    def test_create_admin_gets_admin_role(self, store: UsersStore):
        u = store.create(display_name="Dad", password="pw12345678", is_admin=True)
        assert u["role"] == "admin"

    def test_create_explicit_role_overrides_is_admin_derivation(self, store: UsersStore):
        u = store.create(display_name="Kid", password="pw12345678", role="kid")
        assert u["role"] == "kid"
        assert u["is_admin"] is False

    def test_create_explicit_admin_role_sets_is_admin(self, store: UsersStore):
        u = store.create(display_name="Mom", password="pw12345678", role="admin")
        assert u["is_admin"] is True

    def test_create_rejects_unknown_role(self, store: UsersStore):
        with pytest.raises(ValueError):
            store.create(display_name="X", password="pw12345678", role="superuser")

    def test_set_role_kid(self, store: UsersStore):
        u = store.create(display_name="Kid", password="pw12345678")
        out = store.set_role(u["id"], "kid")
        assert out["role"] == "kid"
        assert out["is_admin"] is False

    def test_set_role_admin_syncs_is_admin(self, store: UsersStore):
        u = store.create(display_name="Mom", password="pw12345678")
        out = store.set_role(u["id"], "admin")
        assert out["is_admin"] is True

    def test_set_role_away_from_admin_clears_is_admin(self, store: UsersStore):
        u = store.create(display_name="Dad", password="pw12345678", is_admin=True)
        out = store.set_role(u["id"], "adult")
        assert out["role"] == "adult"
        assert out["is_admin"] is False

    def test_set_role_rejects_unknown(self, store: UsersStore):
        u = store.create(display_name="X", password="pw12345678")
        with pytest.raises(ValueError):
            store.set_role(u["id"], "superuser")

    def test_set_role_unknown_user_returns_none(self, store: UsersStore):
        assert store.set_role("nobody", "kid") is None

    def test_legacy_user_without_role_migrates_on_load(self, store: UsersStore, tmp_path: Path):
        u = store.create(display_name="Old", password="pw12345678", is_admin=True)
        # Simulate pre-role data written by an older server version.
        for rec in store._users:
            rec.pop("role", None)
        store._save()
        reloaded = UsersStore(path=tmp_path / "users.json")
        assert reloaded.get(u["id"])["role"] == "admin"

    def test_legacy_non_admin_user_migrates_to_adult(self, store: UsersStore, tmp_path: Path):
        u = store.create(display_name="Old Non Admin", password="pw12345678")
        for rec in store._users:
            rec.pop("role", None)
        store._save()
        reloaded = UsersStore(path=tmp_path / "users.json")
        assert reloaded.get(u["id"])["role"] == "adult"

    def test_role_survives_get_public(self, store: UsersStore):
        u = store.create(display_name="Kid", password="pw12345678", role="kid")
        public = store.get_public()
        assert public[0]["role"] == "kid"

    def test_roles_constant_matches_spec(self):
        assert set(ROLES) == {"admin", "adult", "kid"}


class TestUpdateProfileRoleSync:
    """update_profile must keep role == 'admin' <=> is_admin in sync (Finding 1)."""

    def test_is_admin_true_syncs_role_to_admin(self, store: UsersStore):
        u = store.create(display_name="Adult", password="pw12345678")
        assert u["role"] == "adult"
        out = store.update_profile(u["id"], {"is_admin": True})
        assert out["is_admin"] is True
        assert out["role"] == "admin"

    def test_is_admin_false_on_admin_syncs_role_to_adult(self, store: UsersStore):
        u = store.create(display_name="Admin", password="pw12345678", is_admin=True)
        out = store.update_profile(u["id"], {"is_admin": False})
        assert out["is_admin"] is False
        assert out["role"] == "adult"

    def test_is_admin_true_on_kid_is_rejected(self, store: UsersStore):
        u = store.create(display_name="Kid", password="pw12345678", role="kid")
        with pytest.raises(ValueError):
            store.update_profile(u["id"], {"is_admin": True})
        after = store.get(u["id"])
        assert after["role"] == "kid"
        assert after["is_admin"] is False

    def test_is_admin_false_on_non_admin_leaves_role_unchanged(self, store: UsersStore):
        u = store.create(display_name="Adult", password="pw12345678")
        out = store.update_profile(u["id"], {"is_admin": False})
        assert out["is_admin"] is False
        assert out["role"] == "adult"
