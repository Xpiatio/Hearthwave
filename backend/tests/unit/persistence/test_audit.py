"""Unit tests for backend.persistence.audit.AuditLog."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.persistence.audit import AuditLog


@pytest.fixture()
def log_path(tmp_path: Path) -> Path:
    return tmp_path / "audit.log"


@pytest.fixture()
def audit(log_path: Path) -> AuditLog:
    return AuditLog(path=log_path)


# ---------------------------------------------------------------------------
# log()
# ---------------------------------------------------------------------------

class TestLog:
    def test_creates_file_on_first_write(self, audit: AuditLog, log_path: Path):
        audit.log("test_event")
        assert log_path.exists()

    def test_entry_is_valid_json(self, audit: AuditLog, log_path: Path):
        audit.log("login_success", user_id="alice", ip="1.2.3.4", detail="ok")
        line = log_path.read_text().strip()
        entry = json.loads(line)
        assert entry["event"] == "login_success"
        assert entry["user_id"] == "alice"
        assert entry["ip"] == "1.2.3.4"
        assert entry["detail"] == "ok"
        assert "ts" in entry

    def test_multiple_entries_one_per_line(self, audit: AuditLog, log_path: Path):
        audit.log("a")
        audit.log("b")
        lines = [l for l in log_path.read_text().splitlines() if l.strip()]
        assert len(lines) == 2
        assert json.loads(lines[0])["event"] == "a"
        assert json.loads(lines[1])["event"] == "b"

    def test_special_chars_in_detail_are_json_safe(self, audit: AuditLog, log_path: Path):
        audit.log("tx", detail='text="hello\nworld"')
        line = log_path.read_text().strip()
        entry = json.loads(line)
        assert "hello" in entry["detail"]

    def test_write_failure_does_not_raise(self, tmp_path: Path):
        bad = AuditLog(path=tmp_path / "no_dir" / "audit.log")
        bad.log("event")  # should not raise; warning is logged internally


# ---------------------------------------------------------------------------
# tail()
# ---------------------------------------------------------------------------

class TestTail:
    def test_empty_file_returns_empty_list(self, audit: AuditLog, log_path: Path):
        log_path.write_text("")
        assert audit.tail() == []

    def test_missing_file_returns_empty_list(self, log_path: Path):
        audit = AuditLog(path=log_path)  # file never created
        assert audit.tail() == []

    def test_returns_all_entries_when_under_limit(self, audit: AuditLog):
        for i in range(5):
            audit.log(f"event_{i}")
        result = audit.tail(limit=10)
        assert len(result) == 5
        assert result[0]["event"] == "event_0"
        assert result[-1]["event"] == "event_4"

    def test_limit_is_respected(self, audit: AuditLog):
        for i in range(10):
            audit.log(f"event_{i}")
        result = audit.tail(limit=3)
        assert len(result) == 3
        # Should be the LAST 3 entries
        assert result[-1]["event"] == "event_9"
        assert result[0]["event"] == "event_7"

    def test_malformed_line_is_skipped(self, audit: AuditLog, log_path: Path):
        audit.log("good_before")
        with open(log_path, "a") as fh:
            fh.write("NOT JSON\n")
        audit.log("good_after")
        result = audit.tail()
        events = [e["event"] for e in result]
        assert "good_before" in events
        assert "good_after" in events
        assert len(result) == 2  # malformed line silently skipped

    def test_blank_lines_are_skipped(self, audit: AuditLog, log_path: Path):
        audit.log("event_a")
        with open(log_path, "a") as fh:
            fh.write("\n\n")
        audit.log("event_b")
        result = audit.tail()
        assert len(result) == 2

    def test_large_log_tail_returns_correct_entries(self, audit: AuditLog):
        for i in range(500):
            audit.log(f"event_{i}", detail="x" * 50)
        result = audit.tail(limit=10)
        assert len(result) == 10
        assert result[-1]["event"] == "event_499"
