"""Unit tests for backend.persistence.journal."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from backend.persistence.journal import (
    _fmt_date,
    delete_journal,
    load_journals,
    load_published_manifest,
    publish_journal,
    save_journal,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def journals_dir(tmp_path: Path) -> Path:
    d = tmp_path / "journals"
    d.mkdir()
    return d


def _write_journal(journals_dir: Path, filename: str, payload: dict) -> Path:
    """Helper: write a journal JSON file directly, bypassing save_journal."""
    path = journals_dir / filename
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Tests: _fmt_date
# ---------------------------------------------------------------------------

class TestFmtDate:
    def test_formats_utc_timestamp(self):
        result = _fmt_date("2025-06-15T10:30:00+00:00")
        assert result == "June 15, 2025"

    def test_handles_z_suffix(self):
        result = _fmt_date("2025-01-01T00:00:00Z")
        assert result == "January 1, 2025"

    def test_handles_naive_iso_date(self):
        result = _fmt_date("2025-12-25T00:00:00")
        assert result == "December 25, 2025"

    def test_returns_truncated_string_for_invalid_iso(self):
        result = _fmt_date("2025-06-15T!!bad")
        # Falls back to iso[:10]
        assert result == "2025-06-15"

    def test_returns_short_string_as_is_when_too_short(self):
        result = _fmt_date("bad")
        assert result == "bad"

    def test_handles_none_raises_type_error(self):
        # _fmt_date does not guard against None input; AttributeError/TypeError
        # is raised — document this as a known behaviour edge case.
        with pytest.raises((TypeError, AttributeError)):
            _fmt_date(None)  # type: ignore[arg-type]

    def test_month_name_is_full(self):
        result = _fmt_date("2025-03-07T08:00:00")
        assert result.startswith("March")

    def test_day_not_zero_padded(self):
        result = _fmt_date("2025-01-05T00:00:00")
        assert "5," in result
        assert "05," not in result


# ---------------------------------------------------------------------------
# Tests: save_journal
# ---------------------------------------------------------------------------

class TestSaveJournal:
    def test_returns_file_path_string(self, journals_dir: Path):
        result = save_journal("Title", "Summary", [], "transcript text", journals_dir)
        assert isinstance(result, str)
        assert Path(result).exists()

    def test_file_contains_valid_json(self, journals_dir: Path):
        path_str = save_journal("Title", "Summary", [], "tx", journals_dir)
        data = json.loads(Path(path_str).read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_title_stored(self, journals_dir: Path):
        path_str = save_journal("My Session", "Summary", [], "tx", journals_dir)
        data = json.loads(Path(path_str).read_text(encoding="utf-8"))
        assert data["title"] == "My Session"

    def test_summary_stored(self, journals_dir: Path):
        path_str = save_journal("Title", "Good session", [], "tx", journals_dir)
        data = json.loads(Path(path_str).read_text(encoding="utf-8"))
        assert data["summary"] == "Good session"

    def test_transcript_stored(self, journals_dir: Path):
        path_str = save_journal("T", "S", [], "HELLO WORLD", journals_dir)
        data = json.loads(Path(path_str).read_text(encoding="utf-8"))
        assert data["transcript"] == "HELLO WORLD"

    def test_callsigns_locations_stored(self, journals_dir: Path):
        cl = [{"callsign": "W1AW", "location": "Hartford CT"}]
        path_str = save_journal("T", "S", cl, "tx", journals_dir)
        data = json.loads(Path(path_str).read_text(encoding="utf-8"))
        assert data["callsigns_locations"] == cl

    def test_exported_at_present_and_parseable(self, journals_dir: Path):
        from datetime import datetime
        path_str = save_journal("T", "S", [], "tx", journals_dir)
        data = json.loads(Path(path_str).read_text(encoding="utf-8"))
        datetime.fromisoformat(data["exported_at"])  # must not raise

    def test_filename_matches_timestamp_pattern(self, journals_dir: Path):
        import re
        path_str = save_journal("T", "S", [], "tx", journals_dir)
        name = Path(path_str).name
        assert re.match(r"\d{8}_\d{6}\.json", name)

    def test_creates_journals_dir_if_absent(self, tmp_path: Path):
        missing = tmp_path / "new_journals"
        save_journal("T", "S", [], "tx", missing)
        assert missing.is_dir()


# ---------------------------------------------------------------------------
# Tests: load_journals
# ---------------------------------------------------------------------------

class TestLoadJournals:
    def test_returns_empty_list_when_dir_absent(self, tmp_path: Path):
        assert load_journals(tmp_path / "nonexistent") == []

    def test_returns_empty_list_for_empty_dir(self, journals_dir: Path):
        assert load_journals(journals_dir) == []

    def test_loads_single_entry(self, journals_dir: Path):
        _write_journal(journals_dir, "20250601_120000.json", {"title": "Entry1"})
        result = load_journals(journals_dir)
        assert len(result) == 1
        assert result[0]["title"] == "Entry1"

    def test_each_entry_has_file_key(self, journals_dir: Path):
        _write_journal(journals_dir, "20250601_120000.json", {"title": "E"})
        result = load_journals(journals_dir)
        assert "_file" in result[0]
        assert result[0]["_file"].endswith(".json")

    def test_sorted_newest_first(self, journals_dir: Path):
        _write_journal(journals_dir, "20250601_000000.json", {"title": "Old"})
        _write_journal(journals_dir, "20250602_000000.json", {"title": "New"})
        result = load_journals(journals_dir)
        assert result[0]["title"] == "New"
        assert result[1]["title"] == "Old"

    def test_skips_non_json_files(self, journals_dir: Path):
        (journals_dir / "notes.txt").write_text("not a journal")
        _write_journal(journals_dir, "20250601_000000.json", {"title": "E"})
        result = load_journals(journals_dir)
        assert len(result) == 1

    def test_skips_malformed_json_files(self, journals_dir: Path):
        (journals_dir / "20250601_000000.json").write_text("{{bad json")
        result = load_journals(journals_dir)
        assert result == []

    def test_multiple_entries_all_loaded(self, journals_dir: Path):
        for i in range(3):
            _write_journal(journals_dir, f"2025060{i+1}_000000.json", {"title": f"E{i}"})
        result = load_journals(journals_dir)
        assert len(result) == 3

    def test_roundtrip_with_save_journal(self, journals_dir: Path):
        save_journal("My Title", "Summary", [{"callsign": "W1AW", "location": "CT"}], "tx", journals_dir)
        result = load_journals(journals_dir)
        assert len(result) == 1
        assert result[0]["title"] == "My Title"


# ---------------------------------------------------------------------------
# Tests: delete_journal
# ---------------------------------------------------------------------------

class TestDeleteJournal:
    def test_deletes_existing_file(self, journals_dir: Path):
        path = _write_journal(journals_dir, "20250601_000000.json", {"title": "E"})
        delete_journal(str(path), journals_dir)
        assert not path.exists()

    def test_raises_value_error_for_path_outside_dir(self, journals_dir: Path, tmp_path: Path):
        outside = tmp_path / "secret.json"
        outside.write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError, match="outside journals directory"):
            delete_journal(str(outside), journals_dir)

    def test_raises_os_error_for_nonexistent_file(self, journals_dir: Path):
        with pytest.raises(OSError):
            delete_journal(str(journals_dir / "ghost.json"), journals_dir)

    def test_path_traversal_attempt_rejected(self, journals_dir: Path, tmp_path: Path):
        # Try to delete something above the journals dir via ../
        target = str(journals_dir / ".." / "something.json")
        with pytest.raises(ValueError):
            delete_journal(target, journals_dir)


# ---------------------------------------------------------------------------
# Tests: load_published_manifest
# ---------------------------------------------------------------------------

class TestLoadPublishedManifest:
    def test_returns_empty_list_when_no_manifest(self, journals_dir: Path):
        assert load_published_manifest(journals_dir) == []

    def test_returns_list_from_manifest(self, journals_dir: Path):
        pub_dir = journals_dir.parent / "public"
        pub_dir.mkdir()
        manifest = [{"title": "First"}]
        (pub_dir / "journal-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        result = load_published_manifest(journals_dir)
        assert result == manifest

    def test_returns_empty_list_on_malformed_manifest(self, journals_dir: Path):
        pub_dir = journals_dir.parent / "public"
        pub_dir.mkdir()
        (pub_dir / "journal-manifest.json").write_text("{{bad", encoding="utf-8")
        assert load_published_manifest(journals_dir) == []

    def test_returns_empty_list_when_manifest_is_not_list(self, journals_dir: Path):
        pub_dir = journals_dir.parent / "public"
        pub_dir.mkdir()
        (pub_dir / "journal-manifest.json").write_text('{"key": "value"}', encoding="utf-8")
        assert load_published_manifest(journals_dir) == []


# ---------------------------------------------------------------------------
# Tests: publish_journal
# ---------------------------------------------------------------------------

class TestPublishJournal:
    def _make_journal_file(self, journals_dir: Path, title: str = "Test") -> str:
        return save_journal(title, "Summary", [{"callsign": "W1AW", "location": "CT"}], "tx", journals_dir)

    def test_returns_manifest_entry(self, journals_dir: Path):
        path_str = self._make_journal_file(journals_dir)
        entry = publish_journal(path_str, "admin", journals_dir)
        assert entry["title"] == "Test"
        assert entry["published_by"] == "admin"

    def test_manifest_json_written(self, journals_dir: Path):
        path_str = self._make_journal_file(journals_dir)
        publish_journal(path_str, "admin", journals_dir)
        manifest = load_published_manifest(journals_dir)
        assert len(manifest) == 1
        assert manifest[0]["title"] == "Test"

    def test_html_file_written(self, journals_dir: Path):
        path_str = self._make_journal_file(journals_dir)
        publish_journal(path_str, "admin", journals_dir)
        html_path = journals_dir.parent / "public" / "journal.html"
        assert html_path.exists()

    def test_html_contains_title(self, journals_dir: Path):
        path_str = self._make_journal_file(journals_dir, title="GMRS Net June")
        publish_journal(path_str, "admin", journals_dir)
        html = (journals_dir.parent / "public" / "journal.html").read_text(encoding="utf-8")
        assert "GMRS Net June" in html

    def test_second_publish_prepended_to_manifest(self, journals_dir: Path):
        # Use distinct fixed filenames to avoid same-second collision in save_journal.
        p1 = str(_write_journal(journals_dir, "20250601_000000.json", {"title": "First", "summary": "", "callsigns_locations": [], "exported_at": "2025-06-01T00:00:00"}))
        p2 = str(_write_journal(journals_dir, "20250602_000000.json", {"title": "Second", "summary": "", "callsigns_locations": [], "exported_at": "2025-06-02T00:00:00"}))
        publish_journal(p1, "admin", journals_dir)
        publish_journal(p2, "admin", journals_dir)
        manifest = load_published_manifest(journals_dir)
        assert manifest[0]["title"] == "Second"
        assert manifest[1]["title"] == "First"

    def test_manifest_capped_at_max_published(self, journals_dir: Path):
        from backend.persistence.journal import _MAX_PUBLISHED
        for i in range(_MAX_PUBLISHED + 2):
            path_str = self._make_journal_file(journals_dir, title=f"Entry{i}")
            publish_journal(path_str, "admin", journals_dir)
        manifest = load_published_manifest(journals_dir)
        assert len(manifest) <= _MAX_PUBLISHED

    def test_raises_value_error_for_path_outside_journals_dir(self, journals_dir: Path, tmp_path: Path):
        outside = tmp_path / "evil.json"
        outside.write_text(json.dumps({"title": "evil"}), encoding="utf-8")
        with pytest.raises(ValueError, match="outside journals directory"):
            publish_journal(str(outside), "admin", journals_dir)

    def test_raises_value_error_for_missing_file(self, journals_dir: Path):
        with pytest.raises(ValueError, match="not found"):
            publish_journal(str(journals_dir / "ghost.json"), "admin", journals_dir)

    def test_entry_contains_source_file_name(self, journals_dir: Path):
        path_str = self._make_journal_file(journals_dir)
        entry = publish_journal(path_str, "admin", journals_dir)
        assert entry["source_file"] == Path(path_str).name

    def test_entry_exported_at_matches_source(self, journals_dir: Path):
        path_str = self._make_journal_file(journals_dir)
        source = json.loads(Path(path_str).read_text(encoding="utf-8"))
        entry = publish_journal(path_str, "admin", journals_dir)
        assert entry["exported_at"] == source.get("exported_at", "")

    def test_untitled_journal_gets_default_title(self, journals_dir: Path):
        path = _write_journal(journals_dir, "20250601_120000.json", {"title": "", "summary": ""})
        entry = publish_journal(str(path), "admin", journals_dir)
        assert entry["title"] == "(untitled)"

    def test_callsigns_locations_in_entry(self, journals_dir: Path):
        cl = [{"callsign": "W1AW", "location": "CT"}]
        path_str = save_journal("T", "S", cl, "tx", journals_dir)
        entry = publish_journal(path_str, "admin", journals_dir)
        assert entry["callsigns_locations"] == cl

    def test_html_renders_no_journals_placeholder_when_empty(self, journals_dir: Path):
        """Test _render_public_html path for no entries (via empty manifest write)."""
        # Write an empty manifest and call publish on a fresh file to trigger
        # the re-render path. We can test this by calling the internal renderer.
        from backend.persistence.journal import _render_public_html
        html = _render_public_html([])
        assert "No journals have been published yet" in html

    def test_html_renders_stations_section_when_callsigns_present(self, journals_dir: Path):
        cl = [{"callsign": "W1AW", "location": "Hartford CT"}]
        path_str = save_journal("Net Report", "Good net", cl, "tx", journals_dir)
        publish_journal(path_str, "admin", journals_dir)
        html = (journals_dir.parent / "public" / "journal.html").read_text(encoding="utf-8")
        assert "W1AW" in html
        assert "Hartford CT" in html

    def test_html_escapes_xss_in_title(self, journals_dir: Path):
        path = _write_journal(
            journals_dir, "20250601_120000.json",
            {"title": "<script>alert(1)</script>", "summary": "", "callsigns_locations": [], "exported_at": "2025-06-01T12:00:00"}
        )
        publish_journal(str(path), "admin", journals_dir)
        html = (journals_dir.parent / "public" / "journal.html").read_text(encoding="utf-8")
        assert "<script>" not in html

    def test_published_at_is_parseable_iso(self, journals_dir: Path):
        from datetime import datetime
        path_str = self._make_journal_file(journals_dir)
        entry = publish_journal(path_str, "admin", journals_dir)
        datetime.fromisoformat(entry["published_at"])  # must not raise
