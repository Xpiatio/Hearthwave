"""Unit tests for backend.persistence.json_store (load_json, save_json)."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from backend.persistence.json_store import load_json, save_json


# ---------------------------------------------------------------------------
# Tests: load_json
# ---------------------------------------------------------------------------

class TestLoadJson:
    def test_returns_default_when_file_absent(self, tmp_path: Path):
        path = tmp_path / "missing.json"
        assert load_json(path, []) == []

    def test_returns_default_dict_when_file_absent(self, tmp_path: Path):
        path = tmp_path / "missing.json"
        assert load_json(path, {"default": True}) == {"default": True}

    def test_loads_list(self, tmp_path: Path):
        path = tmp_path / "data.json"
        path.write_text('[1, 2, 3]', encoding="utf-8")
        assert load_json(path, []) == [1, 2, 3]

    def test_loads_dict(self, tmp_path: Path):
        path = tmp_path / "data.json"
        path.write_text('{"key": "value"}', encoding="utf-8")
        assert load_json(path, {}) == {"key": "value"}

    def test_returns_default_on_invalid_json(self, tmp_path: Path):
        path = tmp_path / "bad.json"
        path.write_text("not valid json {{{{", encoding="utf-8")
        assert load_json(path, "DEFAULT") == "DEFAULT"

    def test_returns_default_on_empty_file(self, tmp_path: Path):
        path = tmp_path / "empty.json"
        path.write_text("", encoding="utf-8")
        assert load_json(path, None) is None

    def test_accepts_string_path(self, tmp_path: Path):
        path = tmp_path / "data.json"
        path.write_text("[42]", encoding="utf-8")
        assert load_json(str(path), []) == [42]

    def test_accepts_path_object(self, tmp_path: Path):
        path = tmp_path / "data.json"
        path.write_text("[42]", encoding="utf-8")
        assert load_json(path, []) == [42]

    def test_logs_warning_on_decode_error(self, tmp_path: Path, caplog):
        path = tmp_path / "bad.json"
        path.write_text("{bad", encoding="utf-8")
        with caplog.at_level(logging.WARNING, logger="backend.persistence.json_store"):
            load_json(path, {})
        assert any("Error decoding" in r.message for r in caplog.records)

    def test_unicode_content_preserved(self, tmp_path: Path):
        path = tmp_path / "data.json"
        payload = {"msg": "héllo 日本語"}
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        assert load_json(path, {}) == payload

    def test_null_json_value(self, tmp_path: Path):
        path = tmp_path / "data.json"
        path.write_text("null", encoding="utf-8")
        assert load_json(path, "fallback") is None

    def test_default_none(self, tmp_path: Path):
        path = tmp_path / "missing.json"
        assert load_json(path, None) is None

    def test_nested_structure(self, tmp_path: Path):
        path = tmp_path / "data.json"
        payload = {"users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]}
        path.write_text(json.dumps(payload), encoding="utf-8")
        assert load_json(path, {}) == payload


# ---------------------------------------------------------------------------
# Tests: save_json
# ---------------------------------------------------------------------------

class TestSaveJson:
    def test_creates_file(self, tmp_path: Path):
        path = tmp_path / "out.json"
        save_json(path, {"x": 1})
        assert path.exists()

    def test_content_is_valid_json(self, tmp_path: Path):
        path = tmp_path / "out.json"
        save_json(path, [1, 2, 3])
        assert json.loads(path.read_text(encoding="utf-8")) == [1, 2, 3]

    def test_overwrites_existing_file(self, tmp_path: Path):
        path = tmp_path / "out.json"
        path.write_text('{"old": 1}', encoding="utf-8")
        save_json(path, {"new": 2})
        assert json.loads(path.read_text(encoding="utf-8")) == {"new": 2}

    def test_pretty_printed(self, tmp_path: Path):
        path = tmp_path / "out.json"
        save_json(path, {"a": 1})
        text = path.read_text(encoding="utf-8")
        assert "\n" in text  # indent=4 produces multi-line output

    def test_unicode_preserved(self, tmp_path: Path):
        path = tmp_path / "out.json"
        save_json(path, {"msg": "héllo 日本語"})
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["msg"] == "héllo 日本語"

    def test_accepts_string_path(self, tmp_path: Path):
        path = tmp_path / "out.json"
        save_json(str(path), {"x": 99})
        assert json.loads(path.read_text(encoding="utf-8")) == {"x": 99}

    def test_saves_list(self, tmp_path: Path):
        path = tmp_path / "out.json"
        save_json(path, [{"id": 1}, {"id": 2}])
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data) == 2

    def test_raises_on_write_to_nonexistent_directory(self, tmp_path: Path):
        path = tmp_path / "no_such_dir" / "out.json"
        with pytest.raises(Exception):
            save_json(path, {"x": 1})

    def test_logs_error_on_failure(self, tmp_path: Path, caplog):
        path = tmp_path / "no_such_dir" / "out.json"
        with caplog.at_level(logging.ERROR, logger="backend.persistence.json_store"):
            with pytest.raises(Exception):
                save_json(path, {"x": 1})
        assert any("Error saving" in r.message for r in caplog.records)

    def test_roundtrip_with_load_json(self, tmp_path: Path):
        path = tmp_path / "data.json"
        original = {"callsign": "W1AW", "verified": True, "count": 7}
        save_json(path, original)
        from backend.persistence.json_store import load_json
        assert load_json(path, {}) == original
