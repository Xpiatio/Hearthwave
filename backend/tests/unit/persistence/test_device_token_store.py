"""Tests for DeviceTokenStore — admin-issued device tokens for /display kiosk."""
import json
import pytest

from backend.persistence.device_tokens import DeviceTokenStore


def _store(tmp_path):
    return DeviceTokenStore(path=tmp_path / "device_tokens.json")


class TestCreate:
    def test_create_returns_record_with_token(self, tmp_path):
        s = _store(tmp_path)
        rec = s.create("Kitchen tablet")
        assert rec["label"] == "Kitchen tablet"
        assert len(rec["token"]) >= 32
        assert rec["id"] and rec["created_at"]
        assert rec["last_seen"] is None

    def test_create_persists_to_disk(self, tmp_path):
        s = _store(tmp_path)
        rec = s.create("Kitchen tablet")
        data = json.loads((tmp_path / "device_tokens.json").read_text())
        assert data["tokens"][0]["token"] == rec["token"]

    def test_create_rejects_blank_label(self, tmp_path):
        with pytest.raises(ValueError):
            _store(tmp_path).create("   ")

    def test_create_rejects_long_label(self, tmp_path):
        with pytest.raises(ValueError):
            _store(tmp_path).create("x" * 81)

    def test_create_accepts_max_length_label(self, tmp_path):
        """Label of exactly MAX_LABEL_LEN (80) characters is accepted."""
        s = _store(tmp_path)
        rec = s.create("x" * 80)
        assert rec["label"] == "x" * 80


class TestValidate:
    def test_validate_good_token_returns_record_and_stamps_last_seen(self, tmp_path):
        s = _store(tmp_path)
        rec = s.create("Kitchen tablet")
        got = s.validate(rec["token"])
        assert got["id"] == rec["id"]
        assert got["last_seen"] is not None

    def test_validate_unknown_token_returns_none(self, tmp_path):
        assert _store(tmp_path).validate("nope") is None

    def test_validate_non_ascii_token_returns_none_without_raising(self, tmp_path):
        """secrets.compare_digest raises TypeError on non-ASCII str input;
        validate() must encode both sides to bytes first so a hostile/garbled
        token from the WS handshake can't crash the connection before accept."""
        s = _store(tmp_path)
        s.create("Kitchen tablet")
        assert s.validate("ü" * 8) is None

    def test_validate_survives_reload(self, tmp_path):
        s = _store(tmp_path)
        rec = s.create("Kitchen tablet")
        s2 = _store(tmp_path)
        assert s2.validate(rec["token"])["id"] == rec["id"]


class TestRevoke:
    def test_revoke_removes_token(self, tmp_path):
        s = _store(tmp_path)
        rec = s.create("Kitchen tablet")
        assert s.revoke(rec["id"]) is True
        assert s.validate(rec["token"]) is None

    def test_revoke_unknown_id_returns_false(self, tmp_path):
        assert _store(tmp_path).revoke("nope") is False


class TestSetEink:
    def test_create_defaults_eink_off(self, tmp_path):
        assert _store(tmp_path).create("Kitchen")["eink"] is False

    def test_set_eink_toggles_and_persists(self, tmp_path):
        s = _store(tmp_path)
        rec = s.create("Kitchen")
        assert s.set_eink(rec["id"], True) is True
        assert _store(tmp_path).list_all()[0]["eink"] is True

    def test_set_eink_unknown_id_returns_false(self, tmp_path):
        assert _store(tmp_path).set_eink("nope", True) is False

    def test_legacy_record_without_eink_key_loads(self, tmp_path):
        """Pre-e-ink records lack the key — must load and read as off, not crash."""
        path = tmp_path / "device_tokens.json"
        path.write_text(json.dumps({"tokens": [
            {"id": "abc", "token": "t" * 32, "label": "Old", "created_at": "x", "last_seen": None},
        ]}))
        rec = DeviceTokenStore(path=path).list_all()[0]
        assert rec.get("eink", False) is False


class TestLoad:
    def test_load_corrupted_json_yields_empty_store(self, tmp_path):
        """Corrupted device_tokens.json is handled gracefully, yielding empty store."""
        path = tmp_path / "device_tokens.json"
        # Write literal garbage (not valid JSON) to the file
        path.write_text("{ invalid json garbage }")
        # Loading should not raise, should yield empty store
        s = DeviceTokenStore(path=path)
        assert s.list_all() == []
