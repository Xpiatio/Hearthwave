"""Unit tests for backend.persistence.presence.PresenceStore."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.persistence.presence import PresenceStore


@pytest.fixture()
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "presence.json"


@pytest.fixture()
def store(store_path: Path) -> PresenceStore:
    return PresenceStore(path=store_path)


class TestInit:
    def test_empty_when_file_absent(self, store_path: Path):
        s = PresenceStore(path=store_path)
        assert s.all() == {}
        assert not store_path.exists()

    def test_get_unknown_user_returns_empty_shape(self, store: PresenceStore):
        assert store.get("nobody") == {
            "last_heard": None,
            "last_ok": None,
            "missed_checkin": False,
        }

    def test_loads_existing_data(self, store_path: Path):
        data = {"alice": {"last_heard": "2026-07-17T00:00:00+00:00", "last_ok": None, "missed_checkin": False}}
        store_path.write_text(json.dumps(data), encoding="utf-8")
        s = PresenceStore(path=store_path)
        assert s.get("alice")["last_heard"] == "2026-07-17T00:00:00+00:00"

    def test_malformed_json_starts_empty(self, store_path: Path):
        store_path.write_text("not json", encoding="utf-8")
        s = PresenceStore(path=store_path)
        assert s.all() == {}

    def test_non_dict_json_starts_empty(self, store_path: Path):
        store_path.write_text("[]", encoding="utf-8")
        s = PresenceStore(path=store_path)
        assert s.all() == {}


class TestTouchHeard:
    def test_sets_last_heard_only(self, store: PresenceStore):
        store.touch_heard("alice", "2026-07-17T10:00:00+00:00")
        entry = store.get("alice")
        assert entry["last_heard"] == "2026-07-17T10:00:00+00:00"
        assert entry["last_ok"] is None
        assert entry["missed_checkin"] is False

    def test_does_not_clear_missed_checkin(self, store: PresenceStore):
        store.set_missed("alice", True)
        store.touch_heard("alice", "2026-07-17T10:00:00+00:00")
        assert store.get("alice")["missed_checkin"] is True

    def test_persists_across_instances(self, store_path: Path):
        s1 = PresenceStore(path=store_path)
        s1.touch_heard("alice", "2026-07-17T10:00:00+00:00")
        s2 = PresenceStore(path=store_path)
        assert s2.get("alice")["last_heard"] == "2026-07-17T10:00:00+00:00"

    def test_updates_existing_entry(self, store: PresenceStore):
        store.touch_heard("alice", "2026-07-17T10:00:00+00:00")
        store.touch_heard("alice", "2026-07-17T11:00:00+00:00")
        assert store.get("alice")["last_heard"] == "2026-07-17T11:00:00+00:00"


class TestMarkOk:
    def test_sets_last_ok_and_last_heard(self, store: PresenceStore):
        store.mark_ok("alice", "2026-07-17T10:00:00+00:00")
        entry = store.get("alice")
        assert entry["last_ok"] == "2026-07-17T10:00:00+00:00"
        assert entry["last_heard"] == "2026-07-17T10:00:00+00:00"

    def test_clears_missed_checkin(self, store: PresenceStore):
        store.set_missed("alice", True)
        store.mark_ok("alice", "2026-07-17T10:00:00+00:00")
        assert store.get("alice")["missed_checkin"] is False

    def test_persists(self, store_path: Path):
        s1 = PresenceStore(path=store_path)
        s1.mark_ok("alice", "2026-07-17T10:00:00+00:00")
        s2 = PresenceStore(path=store_path)
        assert s2.get("alice")["last_ok"] == "2026-07-17T10:00:00+00:00"


class TestSetMissed:
    def test_returns_true_on_change(self, store: PresenceStore):
        assert store.set_missed("alice", True) is True

    def test_returns_false_when_unchanged(self, store: PresenceStore):
        assert store.set_missed("alice", False) is False  # already False by default

    def test_second_identical_call_returns_false(self, store: PresenceStore):
        store.set_missed("alice", True)
        assert store.set_missed("alice", True) is False

    def test_toggle_back_returns_true(self, store: PresenceStore):
        store.set_missed("alice", True)
        assert store.set_missed("alice", False) is True


class TestAll:
    def test_returns_all_entries(self, store: PresenceStore):
        store.touch_heard("alice", "2026-07-17T10:00:00+00:00")
        store.mark_ok("bob", "2026-07-17T11:00:00+00:00")
        all_entries = store.all()
        assert set(all_entries) == {"alice", "bob"}
        assert all_entries["bob"]["last_ok"] == "2026-07-17T11:00:00+00:00"

    def test_returned_dicts_are_copies(self, store: PresenceStore):
        store.touch_heard("alice", "2026-07-17T10:00:00+00:00")
        entry = store.get("alice")
        entry["last_heard"] = "tampered"
        assert store.get("alice")["last_heard"] == "2026-07-17T10:00:00+00:00"
