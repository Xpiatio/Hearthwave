"""Unit tests for backend.persistence.attendance."""
from __future__ import annotations

import pytest

from backend.persistence.attendance import AttendanceTracker, build_attendance_rows


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tracker() -> AttendanceTracker:
    return AttendanceTracker()


# ---------------------------------------------------------------------------
# Tests: AttendanceTracker.record
# ---------------------------------------------------------------------------

class TestRecord:
    def test_returns_true_on_first_record(self, tracker: AttendanceTracker):
        assert tracker.record("W1AW") is True

    def test_returns_false_on_duplicate(self, tracker: AttendanceTracker):
        tracker.record("W1AW")
        assert tracker.record("W1AW") is False

    def test_deduplication_is_case_insensitive(self, tracker: AttendanceTracker):
        tracker.record("w1aw")
        assert tracker.record("W1AW") is False

    def test_normalises_callsign_to_uppercase(self, tracker: AttendanceTracker):
        tracker.record("w1aw")
        assert "W1AW" in tracker

    def test_strips_whitespace(self, tracker: AttendanceTracker):
        tracker.record("  W1AW  ")
        assert "W1AW" in tracker

    def test_empty_string_returns_false(self, tracker: AttendanceTracker):
        assert tracker.record("") is False

    def test_whitespace_only_returns_false(self, tracker: AttendanceTracker):
        assert tracker.record("   ") is False

    def test_multiple_distinct_callsigns_recorded(self, tracker: AttendanceTracker):
        tracker.record("W1AW")
        tracker.record("K6MME")
        assert len(tracker) == 2

    def test_insertion_order_preserved(self, tracker: AttendanceTracker):
        tracker.record("K6MME")
        tracker.record("W1AW")
        tracker.record("N5XYZ")
        assert tracker.callsigns() == ["K6MME", "W1AW", "N5XYZ"]


# ---------------------------------------------------------------------------
# Tests: AttendanceTracker.remove
# ---------------------------------------------------------------------------

class TestRemove:
    def test_returns_true_when_present(self, tracker: AttendanceTracker):
        tracker.record("W1AW")
        assert tracker.remove("W1AW") is True

    def test_returns_false_when_absent(self, tracker: AttendanceTracker):
        assert tracker.remove("W1AW") is False

    def test_removes_from_callsigns(self, tracker: AttendanceTracker):
        tracker.record("W1AW")
        tracker.remove("W1AW")
        assert "W1AW" not in tracker

    def test_remove_is_case_insensitive(self, tracker: AttendanceTracker):
        tracker.record("W1AW")
        assert tracker.remove("w1aw") is True
        assert "W1AW" not in tracker

    def test_length_decreases_after_remove(self, tracker: AttendanceTracker):
        tracker.record("W1AW")
        tracker.record("K6MME")
        tracker.remove("W1AW")
        assert len(tracker) == 1

    def test_other_entries_unaffected(self, tracker: AttendanceTracker):
        tracker.record("W1AW")
        tracker.record("K6MME")
        tracker.remove("W1AW")
        assert "K6MME" in tracker

    def test_removed_callsign_can_be_re_added(self, tracker: AttendanceTracker):
        tracker.record("W1AW")
        tracker.remove("W1AW")
        result = tracker.record("W1AW")
        assert result is True
        assert "W1AW" in tracker


# ---------------------------------------------------------------------------
# Tests: AttendanceTracker.clear
# ---------------------------------------------------------------------------

class TestClear:
    def test_clears_all_entries(self, tracker: AttendanceTracker):
        tracker.record("W1AW")
        tracker.record("K6MME")
        tracker.clear()
        assert len(tracker) == 0

    def test_callsigns_empty_after_clear(self, tracker: AttendanceTracker):
        tracker.record("W1AW")
        tracker.clear()
        assert tracker.callsigns() == []

    def test_contains_false_after_clear(self, tracker: AttendanceTracker):
        tracker.record("W1AW")
        tracker.clear()
        assert "W1AW" not in tracker

    def test_clear_on_empty_tracker_is_noop(self, tracker: AttendanceTracker):
        tracker.clear()  # must not raise
        assert len(tracker) == 0

    def test_can_record_after_clear(self, tracker: AttendanceTracker):
        tracker.record("W1AW")
        tracker.clear()
        assert tracker.record("W1AW") is True


# ---------------------------------------------------------------------------
# Tests: AttendanceTracker.__contains__ and __len__
# ---------------------------------------------------------------------------

class TestContainsLen:
    def test_contains_true_for_recorded(self, tracker: AttendanceTracker):
        tracker.record("W1AW")
        assert "W1AW" in tracker

    def test_contains_false_for_unrecorded(self, tracker: AttendanceTracker):
        assert "W1AW" not in tracker

    def test_contains_case_insensitive(self, tracker: AttendanceTracker):
        tracker.record("W1AW")
        assert "w1aw" in tracker

    def test_len_zero_initially(self, tracker: AttendanceTracker):
        assert len(tracker) == 0

    def test_len_increments_on_record(self, tracker: AttendanceTracker):
        tracker.record("W1AW")
        assert len(tracker) == 1
        tracker.record("K6MME")
        assert len(tracker) == 2

    def test_len_unchanged_on_duplicate(self, tracker: AttendanceTracker):
        tracker.record("W1AW")
        tracker.record("W1AW")
        assert len(tracker) == 1

    def test_callsigns_returns_list_copy(self, tracker: AttendanceTracker):
        tracker.record("W1AW")
        copy = tracker.callsigns()
        copy.clear()
        assert len(tracker) == 1


# ---------------------------------------------------------------------------
# Tests: build_attendance_rows
# ---------------------------------------------------------------------------

class TestBuildAttendanceRows:
    def test_known_callsign_populated_from_contacts(self):
        contacts = [{"callsign": "W1AW", "name": "Hiram Maxim", "location": "Hartford CT"}]
        rows = build_attendance_rows(["W1AW"], contacts)
        assert len(rows) == 1
        assert rows[0]["name"] == "Hiram Maxim"
        assert rows[0]["location"] == "Hartford CT"

    def test_unknown_callsign_gets_blank_fields(self):
        rows = build_attendance_rows(["K9UNKNOWN"], [])
        assert len(rows) == 1
        assert rows[0]["callsign"] == "K9UNKNOWN"
        assert rows[0]["name"] == ""
        assert rows[0]["location"] == ""

    def test_empty_input_returns_empty_list(self):
        assert build_attendance_rows([], []) == []

    def test_row_includes_gmrs_and_ham_callsigns(self):
        contacts = [{
            "callsign": "W1AW",
            "name": "Test",
            "location": "",
            "gmrs_callsign": "WQXY123",
            "ham_callsign": "W1AW",
        }]
        rows = build_attendance_rows(["W1AW"], contacts)
        assert rows[0]["gmrs"] == "WQXY123"
        assert rows[0]["ham"] == "W1AW"

    def test_empty_callsigns_in_input_are_skipped(self):
        rows = build_attendance_rows(["", "  "], [])
        assert rows == []

    def test_normalises_callsign_in_input(self):
        contacts = [{"callsign": "W1AW", "name": "Test", "location": ""}]
        rows = build_attendance_rows(["w1aw"], contacts)
        assert rows[0]["callsign"] == "W1AW"
        assert rows[0]["name"] == "Test"

    def test_multiple_callsigns_mixed(self):
        contacts = [{"callsign": "W1AW", "name": "Alice", "location": "CT"}]
        rows = build_attendance_rows(["W1AW", "K9UNKNOWN"], contacts)
        assert len(rows) == 2
        assert rows[0]["name"] == "Alice"
        assert rows[1]["name"] == ""

    def test_uses_first_contact_match_when_multiple(self):
        contacts = [
            {"callsign": "W1AW", "name": "First", "location": "CT"},
            {"callsign": "W1AW", "name": "Second", "location": "MA"},
        ]
        rows = build_attendance_rows(["W1AW"], contacts)
        assert rows[0]["name"] == "First"

    def test_whitespace_stripped_from_name_and_location(self):
        contacts = [{"callsign": "W1AW", "name": "  Alice  ", "location": "  CT  "}]
        rows = build_attendance_rows(["W1AW"], contacts)
        assert rows[0]["name"] == "Alice"
        assert rows[0]["location"] == "CT"

    def test_none_name_becomes_empty_string(self):
        contacts = [{"callsign": "W1AW", "name": None, "location": None}]
        rows = build_attendance_rows(["W1AW"], contacts)
        assert rows[0]["name"] == ""
        assert rows[0]["location"] == ""

    def test_missing_gmrs_and_ham_fields_become_empty(self):
        contacts = [{"callsign": "W1AW", "name": "Alice", "location": ""}]
        rows = build_attendance_rows(["W1AW"], contacts)
        assert rows[0]["gmrs"] == ""
        assert rows[0]["ham"] == ""
