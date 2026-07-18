"""Unit tests for backend.persistence.family.FamilyStore."""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.persistence.family import FamilyStore


def test_set_get_delete_reminder(tmp_path):
    s = FamilyStore(str(tmp_path / "family.json"))
    s.set_reminder("u1", "09:00", True)
    assert s.get_reminders() == {"u1": {"time": "09:00", "enabled": True}}
    s.set_reminder("u1", None, False)
    assert s.get_reminders() == {}


def test_persists(tmp_path):
    path = str(tmp_path / "family.json")
    FamilyStore(path).set_reminder("u1", "21:30", True)
    assert FamilyStore(path).get_reminders()["u1"]["time"] == "21:30"


def test_rejects_bad_time(tmp_path):
    with pytest.raises(ValueError):
        FamilyStore(str(tmp_path / "family.json")).set_reminder("u1", "25:99", True)


def test_empty_when_file_absent(tmp_path):
    path = tmp_path / "family.json"
    s = FamilyStore(str(path))
    assert s.get_reminders() == {}
    assert not path.exists()


def test_disabled_reminder_roundtrips(tmp_path):
    s = FamilyStore(str(tmp_path / "family.json"))
    s.set_reminder("u1", "08:00", False)
    assert s.get_reminders() == {"u1": {"time": "08:00", "enabled": False}}


def test_delete_unknown_user_is_noop(tmp_path):
    s = FamilyStore(str(tmp_path / "family.json"))
    s.set_reminder("nobody", None, False)
    assert s.get_reminders() == {}


def test_returned_dict_is_a_copy(tmp_path):
    s = FamilyStore(str(tmp_path / "family.json"))
    s.set_reminder("u1", "09:00", True)
    reminders = s.get_reminders()
    reminders["u1"]["time"] = "tampered"
    assert s.get_reminders()["u1"]["time"] == "09:00"


def test_malformed_json_starts_empty(tmp_path):
    path = tmp_path / "family.json"
    path.write_text("not json", encoding="utf-8")
    s = FamilyStore(str(path))
    assert s.get_reminders() == {}


def test_set_reminder_updates_existing(tmp_path):
    s = FamilyStore(str(tmp_path / "family.json"))
    s.set_reminder("u1", "09:00", True)
    s.set_reminder("u1", "10:00", False)
    assert s.get_reminders() == {"u1": {"time": "10:00", "enabled": False}}


def test_delete_removes_reminder(tmp_path):
    s = FamilyStore(str(tmp_path / "family.json"))
    s.set_reminder("u1", "09:00", True)
    s.delete("u1")
    assert s.get_reminders() == {}


def test_delete_method_on_unknown_user_is_noop(tmp_path):
    s = FamilyStore(str(tmp_path / "family.json"))
    s.set_reminder("u1", "09:00", True)
    s.delete("nobody")
    assert s.get_reminders() == {"u1": {"time": "09:00", "enabled": True}}


def test_delete_only_removes_target_user(tmp_path):
    s = FamilyStore(str(tmp_path / "family.json"))
    s.set_reminder("u1", "09:00", True)
    s.set_reminder("u2", "21:00", True)
    s.delete("u1")
    assert s.get_reminders() == {"u2": {"time": "21:00", "enabled": True}}


def test_delete_persists(tmp_path):
    path = str(tmp_path / "family.json")
    s = FamilyStore(path)
    s.set_reminder("u1", "09:00", True)
    s.delete("u1")
    assert FamilyStore(path).get_reminders() == {}
