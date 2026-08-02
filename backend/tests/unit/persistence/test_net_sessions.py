"""Unit tests for backend.persistence.net_sessions."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from backend.persistence.net_sessions import (
    NET_TYPE_NCS,
    NET_TYPE_NEIGHBORHOOD,
    _iso,
    delete_session,
    load_session,
    load_session_summaries,
    normalize_roster,
    save_session,
)


@pytest.fixture()
def sessions_dir(tmp_path: Path) -> Path:
    d = tmp_path / "net_sessions"
    d.mkdir()
    return d


class TestNormalizeRoster:
    def test_ncs_row_keeps_traffic_and_converts_unix_time(self):
        rows = [{
            "callsign": "kd8abc", "status": "CheckedIn", "traffic": "Priority",
            "name": "Maria", "location": "Holland", "checkin_time": 1_700_000_000.0,
            "verified": True, "called": True,
        }]
        result = normalize_roster(rows)
        assert result[0]["callsign"] == "KD8ABC"
        assert result[0]["traffic"] == "Priority"
        assert result[0]["checkin_time"].startswith("2023-11-14T")
        assert result[0]["verified"] is True
        assert "called" not in result[0]

    def test_neighborhood_row_maps_status_and_nulls_traffic(self):
        rows = [{
            "user_id": "u1", "callsign": "WRAB123", "name": "Sam",
            "location": "Zeeland", "status": "checked_in",
            "checkin_time": "2026-08-01T19:30:00Z", "called": False,
        }]
        result = normalize_roster(rows)
        assert result[0]["status"] == "CheckedIn"
        assert result[0]["traffic"] is None
        # I4: checkin_time is an ISO string too, so it goes through the same
        # _iso() normalization as started_at/ended_at — the "Z" the
        # neighborhood net wrote it with converges to the canonical
        # "+00:00" encoding, matching what an NCS-sourced row would produce.
        assert result[0]["checkin_time"] == "2026-08-01T19:30:00+00:00"

    def test_standby_and_checked_out_map(self):
        rows = [{"status": "standby"}, {"status": "checked_out"}]
        assert [r["status"] for r in normalize_roster(rows)] == ["Standby", "CheckedOut"]

    def test_unknown_status_passes_through(self):
        assert normalize_roster([{"status": "Weird"}])[0]["status"] == "Weird"


class TestIso:
    """I4: NCS's ``Z``-suffixed strings and the neighborhood net's
    ``+00:00``-suffixed strings must converge to one on-disk encoding."""

    def test_z_suffix_and_offset_suffix_converge(self):
        assert _iso("2026-08-01T19:30:00Z") == _iso("2026-08-01T19:30:00+00:00")

    def test_unix_timestamp_matches_equivalent_iso_string(self):
        assert _iso(1_700_000_000.0) == _iso("2023-11-14T22:13:20Z")

    def test_blank_and_none_pass_through_as_empty_string(self):
        assert _iso("") == ""
        assert _iso(None) == ""

    def test_unparsable_string_passes_through_unchanged(self):
        assert _iso("not a timestamp") == "not a timestamp"


class TestSaveSession:
    def test_writes_file_and_returns_path(self, sessions_dir: Path):
        path = save_session(
            net_type=NET_TYPE_NCS,
            started_at="2026-08-01T19:00:00Z",
            ended_at="2026-08-01T19:52:00Z",
            duration_seconds=3120,
            roster=[{"callsign": "KD8ABC", "status": "CheckedIn", "name": "Maria"}],
            transcript="KD8ABC: nothing to report",
            sessions_dir=sessions_dir,
        )
        assert Path(path).exists()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        assert data["net_type"] == "ncs"
        assert data["duration_seconds"] == 3120
        assert data["id"].endswith("_ncs")
        assert data["roster"][0]["callsign"] == "KD8ABC"
        assert data["transcript"] == "KD8ABC: nothing to report"

    def test_normalizes_z_and_offset_suffixes_to_the_same_encoding(self, sessions_dir: Path):
        # I4: NCS passes "...Z"; the neighborhood net passes "...+00:00" (via
        # datetime.isoformat()). Both must land on disk in the same form.
        path_a = save_session(
            net_type=NET_TYPE_NCS, started_at="2026-08-01T19:00:00Z",
            ended_at="2026-08-01T19:52:00Z", duration_seconds=0,
            roster=[], transcript="", sessions_dir=sessions_dir,
        )
        path_b = save_session(
            net_type=NET_TYPE_NEIGHBORHOOD, started_at="2026-08-01T19:00:00+00:00",
            ended_at="2026-08-01T19:52:00+00:00", duration_seconds=0,
            roster=[], transcript="", sessions_dir=sessions_dir,
        )
        data_a = json.loads(Path(path_a).read_text(encoding="utf-8"))
        data_b = json.loads(Path(path_b).read_text(encoding="utf-8"))
        assert data_a["started_at"] == data_b["started_at"]
        assert data_a["ended_at"] == data_b["ended_at"]

    def test_creates_directory_when_missing(self, tmp_path: Path):
        target = tmp_path / "nested" / "sessions"
        save_session(
            net_type=NET_TYPE_NEIGHBORHOOD, started_at="", ended_at="",
            duration_seconds=0, roster=[], transcript="", sessions_dir=target,
        )
        assert target.is_dir()
        assert len(list(target.glob("*.json"))) == 1


class TestLoadSessionSummaries:
    def test_returns_newest_first_without_transcripts(self, sessions_dir: Path):
        for name in ("20260801_190000_ncs.json", "20260802_190000_neighborhood.json"):
            (sessions_dir / name).write_text(json.dumps({
                "id": name[:-5], "net_type": "ncs", "started_at": "2026-08-01T19:00:00Z",
                "ended_at": "", "duration_seconds": 60,
                "roster": [{"callsign": "KD8ABC", "name": "Maria"}],
                "transcript": "a very long transcript",
            }), encoding="utf-8")
        summaries = load_session_summaries(sessions_dir)
        assert [s["id"] for s in summaries] == [
            "20260802_190000_neighborhood", "20260801_190000_ncs",
        ]
        assert "transcript" not in summaries[0]
        assert summaries[0]["checkin_count"] == 1
        assert summaries[0]["stations"] == [{"callsign": "KD8ABC", "name": "Maria"}]

    def test_missing_directory_returns_empty(self, tmp_path: Path):
        assert load_session_summaries(tmp_path / "nope") == []

    def test_skips_corrupt_file(self, sessions_dir: Path):
        (sessions_dir / "20260801_190000_ncs.json").write_text("{not json", encoding="utf-8")
        assert load_session_summaries(sessions_dir) == []

    def test_logs_corrupt_file_instead_of_swallowing_silently(self, sessions_dir: Path, caplog):
        (sessions_dir / "20260801_190000_ncs.json").write_text("{not json", encoding="utf-8")
        with caplog.at_level(logging.WARNING):
            load_session_summaries(sessions_dir)
        assert "20260801_190000_ncs.json" in caplog.text


class TestLoadSession:
    def test_returns_full_entry(self, sessions_dir: Path):
        path = save_session(
            net_type=NET_TYPE_NCS, started_at="", ended_at="", duration_seconds=0,
            roster=[], transcript="hello", sessions_dir=sessions_dir,
        )
        session_id = Path(path).stem
        assert load_session(session_id, sessions_dir)["transcript"] == "hello"

    def test_missing_returns_none(self, sessions_dir: Path):
        assert load_session("20260801_190000_ncs", sessions_dir) is None

    def test_rejects_path_traversal(self, sessions_dir: Path):
        assert load_session("../../etc/passwd", sessions_dir) is None

    def test_logs_unreadable_file_instead_of_swallowing_silently(self, sessions_dir: Path, caplog):
        (sessions_dir / "20260801_190000_ncs.json").write_text("{not json", encoding="utf-8")
        with caplog.at_level(logging.WARNING):
            assert load_session("20260801_190000_ncs", sessions_dir) is None
        assert "20260801_190000_ncs" in caplog.text


class TestDeleteSession:
    def test_removes_file(self, sessions_dir: Path):
        path = save_session(
            net_type=NET_TYPE_NCS, started_at="", ended_at="", duration_seconds=0,
            roster=[], transcript="", sessions_dir=sessions_dir,
        )
        delete_session(Path(path).stem, sessions_dir)
        assert not Path(path).exists()

    def test_rejects_path_traversal(self, sessions_dir: Path):
        with pytest.raises(ValueError):
            delete_session("../secrets", sessions_dir)


def test_normalize_roster_carries_the_radio_marker():
    rows = normalize_roster([
        {"callsign": "wrab123", "name": "Maria", "location": "Maple St",
         "status": "checked_in", "checkin_time": "2026-08-01T19:30:00Z",
         "via": "radio"},
    ])
    assert rows[0]["via"] == "radio"


def test_normalize_roster_defaults_via_to_blank():
    # Account rows and NCS rows have no `via` key at all; a stored record
    # should still have the column so a reader never has to guess.
    rows = normalize_roster([
        {"callsign": "WRAA111", "name": "Ann", "location": "1st St",
         "status": "checked_in", "checkin_time": "2026-08-01T19:30:00Z"},
    ])
    assert rows[0]["via"] == ""


def test_normalize_roster_carries_no_answer_defaulting_false():
    rows = [
        {"callsign": "wraa111", "name": "Ann", "no_answer": True},
        {"callsign": "wrab222", "name": "Bea"},  # pre-flag record / NCS row
    ]
    result = normalize_roster(rows)
    assert result[0]["no_answer"] is True
    assert result[1]["no_answer"] is False
