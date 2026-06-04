"""Unit tests for backend.persistence.contacts.ContactsStore."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.persistence.contacts import ContactsStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def store_path(tmp_path: Path) -> Path:
    """Return a path inside a fresh temp directory (file does not yet exist)."""
    return tmp_path / "contacts.json"


@pytest.fixture()
def empty_store(store_path: Path) -> ContactsStore:
    """ContactsStore backed by a non-existent file."""
    return ContactsStore(path=store_path)


# ---------------------------------------------------------------------------
# Tests: initial state
# ---------------------------------------------------------------------------

class TestInit:
    def test_get_all_returns_empty_list_when_file_absent(self, store_path: Path):
        store = ContactsStore(path=store_path)
        assert store.get_all() == []

    def test_get_all_returns_empty_list_when_file_malformed(self, store_path: Path):
        store_path.write_text("not valid json", encoding="utf-8")
        store = ContactsStore(path=store_path)
        assert store.get_all() == []

    def test_get_all_returns_empty_list_when_file_contains_non_list(self, store_path: Path):
        store_path.write_text('{"callsign": "W1AW"}', encoding="utf-8")
        store = ContactsStore(path=store_path)
        assert store.get_all() == []

    def test_loads_existing_contacts_on_init(self, store_path: Path):
        data = [{"callsign": "W1AW", "name": "Hiram Percy Maxim"}]
        store_path.write_text(json.dumps(data), encoding="utf-8")
        store = ContactsStore(path=store_path)
        assert store.get_all() == data


# ---------------------------------------------------------------------------
# Tests: add_contact
# ---------------------------------------------------------------------------

class TestAddContact:
    def test_creates_file_when_absent(self, store_path: Path, empty_store: ContactsStore):
        assert not store_path.exists()
        empty_store.add_contact({"callsign": "W1AW"})
        assert store_path.exists()

    def test_file_content_is_valid_json_list(self, store_path: Path, empty_store: ContactsStore):
        empty_store.add_contact({"callsign": "W1AW"})
        on_disk = json.loads(store_path.read_text(encoding="utf-8"))
        assert isinstance(on_disk, list)
        assert len(on_disk) == 1
        assert on_disk[0]["callsign"] == "W1AW"

    def test_returns_updated_list(self, empty_store: ContactsStore):
        result = empty_store.add_contact({"callsign": "W1AW"})
        assert isinstance(result, list)
        assert result[0]["callsign"] == "W1AW"

    def test_normalises_callsign_to_uppercase(self, empty_store: ContactsStore):
        empty_store.add_contact({"callsign": "w1aw"})
        assert empty_store.get_all()[0]["callsign"] == "W1AW"

    def test_strips_whitespace_from_callsign(self, empty_store: ContactsStore):
        empty_store.add_contact({"callsign": "  W1AW  "})
        assert empty_store.get_all()[0]["callsign"] == "W1AW"

    def test_same_callsign_different_name_keeps_both(self, store_path: Path, empty_store: ContactsStore):
        """GMRS family members share a callsign — both records must be kept."""
        empty_store.add_contact({"callsign": "W1AW", "name": "John Smith"})
        empty_store.add_contact({"callsign": "W1AW", "name": "Jane Smith"})
        contacts = empty_store.get_all()
        assert len(contacts) == 2
        names = {c["name"] for c in contacts}
        assert names == {"John Smith", "Jane Smith"}

    def test_same_callsign_same_name_deduplicates_last_write_wins(self, store_path: Path, empty_store: ContactsStore):
        """Exact duplicate (callsign + name) keeps only the last-written entry."""
        empty_store.add_contact({"callsign": "W1AW", "name": "John Smith", "location": "Old"})
        empty_store.add_contact({"callsign": "W1AW", "name": "John Smith", "location": "New"})
        contacts = empty_store.get_all()
        assert len(contacts) == 1
        assert contacts[0]["location"] == "New"

    def test_deduplication_is_case_insensitive(self, empty_store: ContactsStore):
        """Callsign case differences do not create a second record for the same person."""
        empty_store.add_contact({"callsign": "W1AW", "name": "John Smith"})
        empty_store.add_contact({"callsign": "w1aw", "name": "John Smith"})
        assert len(empty_store.get_all()) == 1

    def test_deduplication_persisted_to_disk(self, store_path: Path, empty_store: ContactsStore):
        empty_store.add_contact({"callsign": "W1AW", "name": "John Smith", "location": "Old"})
        empty_store.add_contact({"callsign": "W1AW", "name": "John Smith", "location": "New"})
        on_disk = json.loads(store_path.read_text(encoding="utf-8"))
        assert len(on_disk) == 1
        assert on_disk[0]["location"] == "New"

    def test_multiple_distinct_contacts_are_kept(self, empty_store: ContactsStore):
        empty_store.add_contact({"callsign": "W1AW"})
        empty_store.add_contact({"callsign": "K6MME"})
        assert len(empty_store.get_all()) == 2

    def test_raises_on_missing_callsign(self, empty_store: ContactsStore):
        with pytest.raises(ValueError):
            empty_store.add_contact({"name": "No Callsign"})

    def test_raises_on_empty_callsign(self, empty_store: ContactsStore):
        with pytest.raises(ValueError):
            empty_store.add_contact({"callsign": ""})


# ---------------------------------------------------------------------------
# Tests: update_contact
# ---------------------------------------------------------------------------

class TestUpdateContact:
    def test_modifies_existing_entry(self, empty_store: ContactsStore):
        empty_store.add_contact({"callsign": "W1AW", "name": "Old Name"})
        empty_store.update_contact("W1AW", {"name": "New Name"})
        assert empty_store.get_all()[0]["name"] == "New Name"

    def test_non_updated_fields_are_preserved(self, empty_store: ContactsStore):
        empty_store.add_contact({"callsign": "W1AW", "name": "Old", "location": "Hartford CT"})
        empty_store.update_contact("W1AW", {"name": "New"})
        assert empty_store.get_all()[0]["location"] == "Hartford CT"

    def test_update_is_persisted_to_disk(self, store_path: Path, empty_store: ContactsStore):
        empty_store.add_contact({"callsign": "W1AW", "name": "Old"})
        empty_store.update_contact("W1AW", {"name": "New"})
        on_disk = json.loads(store_path.read_text(encoding="utf-8"))
        assert on_disk[0]["name"] == "New"

    def test_update_is_case_insensitive_on_callsign(self, empty_store: ContactsStore):
        empty_store.add_contact({"callsign": "W1AW", "name": "Old"})
        empty_store.update_contact("w1aw", {"name": "New"})
        assert empty_store.get_all()[0]["name"] == "New"

    def test_returns_updated_list(self, empty_store: ContactsStore):
        empty_store.add_contact({"callsign": "W1AW"})
        result = empty_store.update_contact("W1AW", {"name": "Changed"})
        assert isinstance(result, list)
        assert result[0]["name"] == "Changed"

    def test_raises_keyerror_for_unknown_callsign(self, empty_store: ContactsStore):
        with pytest.raises(KeyError):
            empty_store.update_contact("UNKNOWN", {"name": "X"})

    def test_list_length_unchanged_after_update(self, empty_store: ContactsStore):
        empty_store.add_contact({"callsign": "W1AW"})
        empty_store.add_contact({"callsign": "K6MME"})
        empty_store.update_contact("W1AW", {"name": "Changed"})
        assert len(empty_store.get_all()) == 2


# ---------------------------------------------------------------------------
# Tests: get_all
# ---------------------------------------------------------------------------

class TestGetAll:
    def test_returns_in_memory_list_without_rereading_disk(self, store_path: Path):
        data = [{"callsign": "W1AW"}]
        store_path.write_text(json.dumps(data), encoding="utf-8")
        store = ContactsStore(path=store_path)

        # Corrupt the file on disk — get_all must NOT re-read it.
        store_path.write_text("[]", encoding="utf-8")

        assert store.get_all() == data

    def test_returns_copy_not_internal_reference(self, empty_store: ContactsStore):
        empty_store.add_contact({"callsign": "W1AW"})
        copy = empty_store.get_all()
        copy.clear()
        # Internal state must be unaffected.
        assert len(empty_store.get_all()) == 1
