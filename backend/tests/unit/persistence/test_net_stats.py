"""Unit tests for backend.persistence.net_stats."""
from __future__ import annotations

from backend.persistence.net_stats import compute_attendance_stats


def _session(session_id: str, started_at: str, *stations) -> dict:
    """Build a summary like load_session_summaries returns."""
    return {
        "id": session_id,
        "net_type": "neighborhood",
        "started_at": started_at,
        "ended_at": "",
        "duration_seconds": 600,
        "checkin_count": len(stations),
        "stations": [{"callsign": cs, "name": name} for cs, name in stations],
    }


# Newest-first, as the store returns them.
SUMMARIES = [
    _session("s3", "2026-08-15T19:00:00Z", ("KD8ABC", "Maria"), ("WRAB123", "Sam")),
    _session("s2", "2026-08-08T19:00:00Z", ("KD8ABC", "Maria")),
    _session("s1", "2026-08-01T19:00:00Z", ("KD8ABC", "Maria"), ("WRAB123", "Sam")),
]


class TestComputeAttendanceStats:
    def test_counts_total_nets(self):
        rows = {r["callsign"]: r for r in compute_attendance_stats(SUMMARIES)}
        assert rows["KD8ABC"]["total_nets"] == 3
        assert rows["WRAB123"]["total_nets"] == 2

    def test_streak_counts_consecutive_most_recent_nets(self):
        rows = {r["callsign"]: r for r in compute_attendance_stats(SUMMARIES)}
        # Maria attended all three, most recent included.
        assert rows["KD8ABC"]["current_streak"] == 3
        # Sam attended the newest net but missed the one before it.
        assert rows["WRAB123"]["current_streak"] == 1

    def test_recent_window_caps_at_ten_sessions(self):
        many = [_session(f"s{i}", "2026-01-01T00:00:00Z", ("KD8ABC", "Maria")) for i in range(14)]
        row = compute_attendance_stats(many)[0]
        assert row["recent_window"] == 10
        assert row["attended_of_recent"] == 10
        assert row["total_nets"] == 14

    def test_last_seen_is_most_recent_session_start(self):
        rows = {r["callsign"]: r for r in compute_attendance_stats(SUMMARIES)}
        assert rows["WRAB123"]["last_seen"] == "2026-08-15T19:00:00Z"

    def test_sorted_by_total_desc_then_callsign(self):
        rows = compute_attendance_stats(SUMMARIES)
        assert [r["callsign"] for r in rows] == ["KD8ABC", "WRAB123"]

    def test_name_falls_back_to_contacts(self):
        summaries = [_session("s1", "2026-08-01T19:00:00Z", ("KD8ABC", ""))]
        contacts = [{"callsign": "KD8ABC", "name": "Maria from contacts", "location": "Holland"}]
        assert compute_attendance_stats(summaries, contacts)[0]["name"] == "Maria from contacts"

    def test_empty_input_returns_empty(self):
        assert compute_attendance_stats([]) == []

    def test_blank_callsigns_ignored(self):
        summaries = [_session("s1", "2026-08-01T19:00:00Z", ("", "Anonymous"))]
        assert compute_attendance_stats(summaries) == []
