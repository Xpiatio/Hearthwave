"""Unit tests for backend.persistence._utils (atomic_json_write, atomic_text_write)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.persistence._utils import atomic_json_write, atomic_text_write


# ---------------------------------------------------------------------------
# Tests: atomic_json_write
# ---------------------------------------------------------------------------

class TestAtomicJsonWrite:
    def test_creates_file(self, tmp_path: Path):
        dest = tmp_path / "out.json"
        atomic_json_write(dest, {"key": "value"})
        assert dest.exists()

    def test_content_is_valid_json(self, tmp_path: Path):
        dest = tmp_path / "out.json"
        atomic_json_write(dest, [1, 2, 3])
        data = json.loads(dest.read_text(encoding="utf-8"))
        assert data == [1, 2, 3]

    def test_overwrites_existing_file(self, tmp_path: Path):
        dest = tmp_path / "out.json"
        dest.write_text('{"old": true}', encoding="utf-8")
        atomic_json_write(dest, {"new": True})
        data = json.loads(dest.read_text(encoding="utf-8"))
        assert data == {"new": True}

    def test_creates_parent_directories(self, tmp_path: Path):
        dest = tmp_path / "a" / "b" / "c" / "out.json"
        atomic_json_write(dest, {})
        assert dest.exists()

    def test_unicode_preserved(self, tmp_path: Path):
        dest = tmp_path / "out.json"
        atomic_json_write(dest, {"msg": "héllo wörld 日本語"})
        text = dest.read_text(encoding="utf-8")
        assert "héllo wörld 日本語" in text

    def test_ensure_ascii_false(self, tmp_path: Path):
        dest = tmp_path / "out.json"
        atomic_json_write(dest, {"x": "é"})
        raw = dest.read_bytes()
        # ensure_ascii=False means the character is stored as UTF-8, not escaped
        assert b"\\u" not in raw

    def test_no_tmp_file_left_on_success(self, tmp_path: Path):
        dest = tmp_path / "out.json"
        atomic_json_write(dest, {"x": 1})
        tmp_files = [f for f in tmp_path.iterdir() if f.suffix == ".tmp"]
        assert tmp_files == []

    def test_raises_on_non_serialisable_data(self, tmp_path: Path):
        dest = tmp_path / "out.json"
        with pytest.raises(TypeError):
            atomic_json_write(dest, object())

    def test_cleans_up_tmp_file_on_serialisation_error(self, tmp_path: Path):
        dest = tmp_path / "out.json"
        with pytest.raises(TypeError):
            atomic_json_write(dest, object())
        tmp_files = [f for f in tmp_path.iterdir() if f.suffix == ".tmp"]
        assert tmp_files == []

    def test_swallows_oserror_when_unlink_fails_during_cleanup(self, tmp_path: Path):
        """When cleanup os.unlink raises OSError it is silently ignored and original error re-raised."""
        dest = tmp_path / "out.json"

        def bad_replace(src, dst):
            raise OSError("disk full")

        def bad_unlink(path):
            raise OSError("unlink denied")

        with patch("backend.persistence._utils.os.replace", side_effect=bad_replace):
            with patch("backend.persistence._utils.os.unlink", side_effect=bad_unlink):
                with pytest.raises(OSError, match="disk full"):
                    atomic_json_write(dest, {"x": 1})

    def test_pretty_printed_output(self, tmp_path: Path):
        dest = tmp_path / "out.json"
        atomic_json_write(dest, {"a": 1})
        text = dest.read_text(encoding="utf-8")
        # indent=4 means newlines in the output
        assert "\n" in text

    def test_dict_roundtrip(self, tmp_path: Path):
        dest = tmp_path / "out.json"
        payload = {"callsign": "W1AW", "name": "Hiram Percy Maxim", "verified": True}
        atomic_json_write(dest, payload)
        assert json.loads(dest.read_text(encoding="utf-8")) == payload

    def test_list_roundtrip(self, tmp_path: Path):
        dest = tmp_path / "out.json"
        payload = [{"id": 1}, {"id": 2}]
        atomic_json_write(dest, payload)
        assert json.loads(dest.read_text(encoding="utf-8")) == payload

    def test_null_value(self, tmp_path: Path):
        dest = tmp_path / "out.json"
        atomic_json_write(dest, None)
        assert json.loads(dest.read_text(encoding="utf-8")) is None

    def test_empty_dict(self, tmp_path: Path):
        dest = tmp_path / "out.json"
        atomic_json_write(dest, {})
        assert json.loads(dest.read_text(encoding="utf-8")) == {}


# ---------------------------------------------------------------------------
# Tests: atomic_text_write
# ---------------------------------------------------------------------------

class TestAtomicTextWrite:
    def test_creates_file(self, tmp_path: Path):
        dest = tmp_path / "out.txt"
        atomic_text_write(dest, "hello")
        assert dest.exists()

    def test_content_matches(self, tmp_path: Path):
        dest = tmp_path / "out.txt"
        atomic_text_write(dest, "hello world")
        assert dest.read_text(encoding="utf-8") == "hello world"

    def test_overwrites_existing_file(self, tmp_path: Path):
        dest = tmp_path / "out.txt"
        dest.write_text("old", encoding="utf-8")
        atomic_text_write(dest, "new")
        assert dest.read_text(encoding="utf-8") == "new"

    def test_creates_parent_directories(self, tmp_path: Path):
        dest = tmp_path / "x" / "y" / "out.txt"
        atomic_text_write(dest, "data")
        assert dest.exists()

    def test_unicode_preserved(self, tmp_path: Path):
        dest = tmp_path / "out.txt"
        text = "àéîõü 中文 العربية"
        atomic_text_write(dest, text)
        assert dest.read_text(encoding="utf-8") == text

    def test_no_tmp_file_left_on_success(self, tmp_path: Path):
        dest = tmp_path / "out.txt"
        atomic_text_write(dest, "ok")
        tmp_files = [f for f in tmp_path.iterdir() if f.suffix == ".tmp"]
        assert tmp_files == []

    def test_empty_string(self, tmp_path: Path):
        dest = tmp_path / "out.txt"
        atomic_text_write(dest, "")
        assert dest.read_text(encoding="utf-8") == ""

    def test_multiline_text(self, tmp_path: Path):
        dest = tmp_path / "out.txt"
        text = "line1\nline2\nline3"
        atomic_text_write(dest, text)
        assert dest.read_text(encoding="utf-8") == text

    def test_raises_and_cleans_up_on_write_error(self, tmp_path: Path):
        """If writing fails mid-stream the tmp file is cleaned up."""
        dest = tmp_path / "out.txt"

        def bad_replace(src, dst):
            raise OSError("disk full")

        with patch("backend.persistence._utils.os.replace", side_effect=bad_replace):
            with pytest.raises(OSError):
                atomic_text_write(dest, "data")
        # The dest file was not created
        assert not dest.exists()

    def test_swallows_oserror_when_unlink_fails_during_cleanup(self, tmp_path: Path):
        """When the cleanup os.unlink itself raises OSError it is silently ignored."""
        dest = tmp_path / "out.txt"

        def bad_replace(src, dst):
            raise OSError("disk full")

        def bad_unlink(path):
            raise OSError("unlink denied")

        with patch("backend.persistence._utils.os.replace", side_effect=bad_replace):
            with patch("backend.persistence._utils.os.unlink", side_effect=bad_unlink):
                # The original OSError from os.replace must still propagate.
                with pytest.raises(OSError, match="disk full"):
                    atomic_text_write(dest, "data")
