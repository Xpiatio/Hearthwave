import json
import os
import tempfile
from pathlib import Path

import pytest

from backend.config import ServerConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_config(**kwargs) -> ServerConfig:
    """Return a ServerConfig pre-populated with *kwargs*."""
    cfg = ServerConfig()
    cfg.update(kwargs)
    return cfg


# ---------------------------------------------------------------------------
# Station identity
# ---------------------------------------------------------------------------

class TestStationIdentityDefaults:
    def test_callsign_default(self):
        assert ServerConfig().callsign == "N0CALL"

    def test_name_default(self):
        assert ServerConfig().name == ""

    def test_location_default(self):
        assert ServerConfig().location == ""


class TestStationIdentityOverrides:
    def test_callsign_override(self):
        assert make_config(callsign="WSLZ233").callsign == "WSLZ233"

    def test_name_override(self):
        assert make_config(name="Bob").name == "Bob"

    def test_location_override(self):
        assert make_config(location="Jenison, MI").location == "Jenison, MI"


# ---------------------------------------------------------------------------
# Audio / STT
# ---------------------------------------------------------------------------

class TestAudioDefaults:
    def test_input_device_default(self):
        assert ServerConfig().input_device == -1

    def test_output_device_default(self):
        assert ServerConfig().output_device == -1

    def test_monitor_enabled_default(self):
        assert ServerConfig().monitor_enabled is False

    def test_monitor_passthrough_default(self):
        assert ServerConfig().monitor_passthrough is False

    def test_whisper_model_default(self):
        assert ServerConfig().whisper_model == "small.en"

    def test_vad_threshold_default(self):
        assert ServerConfig().vad_threshold == pytest.approx(0.5)

    def test_system_monitor_sink_default(self):
        assert ServerConfig().system_monitor_sink == ""


class TestAudioOverrides:
    def test_vad_threshold_stored_as_string_coerced_to_float(self):
        assert make_config(vad_threshold="0.7").vad_threshold == pytest.approx(0.7)

    def test_monitor_enabled_truthy_int(self):
        assert make_config(monitor_enabled=1).monitor_enabled is True

    def test_system_monitor_sink_stripped(self):
        assert make_config(system_monitor_sink="  pulse  ").system_monitor_sink == "pulse"

    def test_system_monitor_sink_none_is_empty_string(self):
        assert make_config(system_monitor_sink=None).system_monitor_sink == ""


# ---------------------------------------------------------------------------
# TTS
# ---------------------------------------------------------------------------

class TestTTSDefaults:
    def test_voice_default(self):
        assert ServerConfig().voice == ""

    def test_tts_length_scale_default(self):
        assert ServerConfig().tts_length_scale == pytest.approx(1.0)

    def test_voices_dir_default_when_no_voice(self):
        assert ServerConfig().voices_dir == Path("/app/Voices")


class TestTTSOverrides:
    def test_voices_dir_explicit(self):
        assert make_config(voices_dir="/custom/voices").voices_dir == Path("/custom/voices")

    def test_voices_dir_derived_from_voice_path(self):
        cfg = make_config(voice="/app/Voices/en/myvoice.onnx")
        # voices_dir not set explicitly → falls back to voice parent
        assert cfg.voices_dir == Path("/app/Voices/en")

    def test_voices_dir_explicit_beats_voice_path(self):
        cfg = make_config(voice="/app/Voices/en/myvoice.onnx", voices_dir="/custom")
        assert cfg.voices_dir == Path("/custom")

    def test_tts_length_scale_string_coerced(self):
        assert make_config(tts_length_scale="1.2").tts_length_scale == pytest.approx(1.2)


# ---------------------------------------------------------------------------
# Text / content
# ---------------------------------------------------------------------------

class TestTextDefaults:
    def test_filter_profanity_default_true(self):
        assert ServerConfig().filter_profanity is True

    def test_fuzzy_callsign_default_false(self):
        assert ServerConfig().fuzzy_callsign is False

    def test_saved_phrases_default_is_list(self):
        assert isinstance(ServerConfig().saved_phrases, list)

    def test_saved_phrases_default_contains_expected_phrases(self):
        phrases = ServerConfig().saved_phrases
        assert "break break" in phrases
        assert "copy that" in phrases
        assert "over" in phrases

    def test_saved_phrases_default_has_ten_entries(self):
        assert len(ServerConfig().saved_phrases) == 10


class TestTextOverrides:
    def test_filter_profanity_can_be_disabled(self):
        assert make_config(filter_profanity=False).filter_profanity is False

    def test_fuzzy_callsign_can_be_enabled(self):
        assert make_config(fuzzy_callsign=True).fuzzy_callsign is True

    def test_saved_phrases_can_be_overridden(self):
        assert make_config(saved_phrases=["roger that", "QSL"]).saved_phrases == [
            "roger that", "QSL"
        ]

    def test_saved_phrases_returns_copy(self):
        cfg = ServerConfig()
        cfg.saved_phrases.clear()  # mutating the returned list must not affect the next call
        assert len(cfg.saved_phrases) == 10


# ---------------------------------------------------------------------------
# Radio / service
# ---------------------------------------------------------------------------

class TestRadioDefaults:
    def test_radio_service_default(self):
        assert ServerConfig().radio_service == ""

    def test_listen_only_default(self):
        assert ServerConfig().listen_only is False


# ---------------------------------------------------------------------------
# PTT
# ---------------------------------------------------------------------------

class TestPTTDefaults:
    def test_ptt_mode_default(self):
        assert ServerConfig().ptt_mode == "manual"

    def test_ptt_serial_port_default(self):
        assert ServerConfig().ptt_serial_port == ""

    def test_ptt_serial_line_default(self):
        assert ServerConfig().ptt_serial_line == "RTS"


class TestPTTOverrides:
    def test_ptt_serial_port_stripped(self):
        assert make_config(ptt_serial_port="  /dev/ttyUSB0  ").ptt_serial_port == "/dev/ttyUSB0"

    def test_ptt_serial_port_none_is_empty_string(self):
        assert make_config(ptt_serial_port=None).ptt_serial_port == ""


# ---------------------------------------------------------------------------
# RX mode
# ---------------------------------------------------------------------------

class TestRXModeDefault:
    def test_rx_mode_default_voice(self):
        assert ServerConfig().rx_mode == "voice"

    def test_rx_mode_override_cw(self):
        assert make_config(rx_mode="cw").rx_mode == "cw"


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------

class TestAttendanceDefaults:
    def test_attendance_disabled_by_default(self):
        assert ServerConfig().attendance_enabled is False

    def test_attendance_enabled_via_nested_dict(self):
        cfg = make_config(attendance={"enabled": True})
        assert cfg.attendance_enabled is True

    def test_attendance_disabled_via_nested_dict(self):
        cfg = make_config(attendance={"enabled": False})
        assert cfg.attendance_enabled is False


class TestAttendanceSetter:
    def test_setter_enables_attendance(self):
        cfg = ServerConfig()
        cfg.attendance_enabled = True
        assert cfg.attendance_enabled is True

    def test_setter_preserves_existing_attendance_keys(self):
        cfg = make_config(attendance={"enabled": False, "extra": "value"})
        cfg.attendance_enabled = True
        assert cfg["attendance"]["extra"] == "value"

    def test_setter_disables_attendance(self):
        cfg = make_config(attendance={"enabled": True})
        cfg.attendance_enabled = False
        assert cfg.attendance_enabled is False

    def test_setter_on_empty_config(self):
        cfg = ServerConfig()
        cfg.attendance_enabled = True
        assert cfg["attendance"] == {"enabled": True}


# ---------------------------------------------------------------------------
# AI / journals
# ---------------------------------------------------------------------------

class TestAIDefaults:
    def test_gemini_api_key_default(self):
        assert ServerConfig().gemini_api_key == ""

    def test_journals_dir_default(self):
        assert ServerConfig().journals_dir == Path("/data/journals")


class TestAIOverrides:
    def test_journals_dir_override(self):
        assert make_config(journals_dir="/custom/journals").journals_dir == Path("/custom/journals")


# ---------------------------------------------------------------------------
# Spectrogram
# ---------------------------------------------------------------------------

class TestSpectrogramDefaults:
    def test_spectro_colormap_default(self):
        assert ServerConfig().spectro_colormap == "viridis"

    def test_spectro_freq_range_default(self):
        assert ServerConfig().spectro_freq_range == "full"

    def test_spectro_time_window_default(self):
        assert ServerConfig().spectro_time_window_s == 30


class TestSpectrogramOverrides:
    def test_spectro_time_window_string_coerced(self):
        assert make_config(spectro_time_window_s="60").spectro_time_window_s == 60


# ---------------------------------------------------------------------------
# Persistence paths
# ---------------------------------------------------------------------------

class TestPersistenceDefaults:
    def test_contacts_file_default(self):
        assert ServerConfig().contacts_file == Path("/data/contacts.json")

    def test_users_file_default(self):
        assert ServerConfig().users_file == Path("/data/users.json")

    def test_tokens_file_default(self):
        assert ServerConfig().tokens_file == Path("/data/tokens.json")


class TestPersistenceOverrides:
    def test_contacts_file_override(self):
        assert make_config(contacts_file="/tmp/c.json").contacts_file == Path("/tmp/c.json")

    def test_users_file_override(self):
        assert make_config(users_file="/tmp/u.json").users_file == Path("/tmp/u.json")

    def test_tokens_file_override(self):
        assert make_config(tokens_file="/tmp/t.json").tokens_file == Path("/tmp/t.json")


# ---------------------------------------------------------------------------
# NCS / Net Control Station
# ---------------------------------------------------------------------------

class TestNCSDefaults:
    def test_ncs_zone_default_empty(self):
        assert ServerConfig().ncs_zone == ""

    def test_ncs_announcement_interval_default(self):
        assert ServerConfig().ncs_announcement_interval == 600


class TestNCSOverrides:
    def test_ncs_zone_uppercased_and_stripped(self):
        assert make_config(ncs_zone="  miz025  ").ncs_zone == "MIZ025"

    def test_ncs_zone_none_is_empty_string(self):
        assert make_config(ncs_zone=None).ncs_zone == ""

    def test_ncs_announcement_interval_string_coerced(self):
        assert make_config(ncs_announcement_interval="300").ncs_announcement_interval == 300


# ---------------------------------------------------------------------------
# Server host / port
# ---------------------------------------------------------------------------

class TestServerDefaults:
    def test_host_default(self):
        assert ServerConfig().host == "0.0.0.0"

    def test_port_default(self):
        assert ServerConfig().port == 8765


class TestServerOverrides:
    def test_host_override(self):
        assert make_config(host="127.0.0.1").host == "127.0.0.1"

    def test_port_override(self):
        assert make_config(port=9000).port == 9000

    def test_port_string_coerced(self):
        assert make_config(port="9000").port == 9000


# ---------------------------------------------------------------------------
# dict subclass behaviour
# ---------------------------------------------------------------------------

class TestDictSubclass:
    def test_is_a_dict(self):
        assert isinstance(ServerConfig(), dict)

    def test_can_be_updated_with_dict_merge(self):
        cfg = ServerConfig()
        cfg.update({"callsign": "K1ABC"})
        assert cfg.callsign == "K1ABC"

    def test_key_access_works(self):
        cfg = make_config(callsign="K1ABC")
        assert cfg["callsign"] == "K1ABC"


# ---------------------------------------------------------------------------
# ServerConfig.load
# ---------------------------------------------------------------------------

class TestLoad:
    def test_load_nonexistent_file_returns_empty_config(self, tmp_path):
        cfg = ServerConfig.load(tmp_path / "nonexistent.json")
        assert isinstance(cfg, ServerConfig)
        assert cfg.callsign == "N0CALL"

    def test_load_valid_json_populates_config(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"callsign": "W1AW", "port": 9999}))
        cfg = ServerConfig.load(config_file)
        assert cfg.callsign == "W1AW"
        assert cfg.port == 9999

    def test_load_invalid_json_returns_defaults(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text("not valid json {{{{")
        cfg = ServerConfig.load(config_file)
        assert cfg.callsign == "N0CALL"

    def test_load_json_array_at_top_level_returns_defaults(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps([1, 2, 3]))
        cfg = ServerConfig.load(config_file)
        assert cfg.callsign == "N0CALL"

    def test_load_returns_server_config_instance(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"callsign": "K1ABC"}))
        cfg = ServerConfig.load(config_file)
        assert isinstance(cfg, ServerConfig)


# ---------------------------------------------------------------------------
# ServerConfig.save
# ---------------------------------------------------------------------------

class TestSave:
    def test_save_creates_file(self, tmp_path):
        cfg = make_config(callsign="W1AW")
        config_file = tmp_path / "config.json"
        cfg.save(config_file)
        assert config_file.exists()

    def test_save_roundtrip(self, tmp_path):
        config_file = tmp_path / "config.json"
        cfg = make_config(callsign="W1AW", port=9000)
        cfg.save(config_file)
        loaded = ServerConfig.load(config_file)
        assert loaded.callsign == "W1AW"
        assert loaded.port == 9000

    def test_save_creates_parent_dirs(self, tmp_path):
        config_file = tmp_path / "subdir" / "nested" / "config.json"
        cfg = make_config(callsign="K1ABC")
        cfg.save(config_file)
        assert config_file.exists()

    def test_save_produces_valid_json(self, tmp_path):
        config_file = tmp_path / "config.json"
        cfg = make_config(callsign="W1AW", name="Test")
        cfg.save(config_file)
        data = json.loads(config_file.read_text())
        assert data["callsign"] == "W1AW"
        assert data["name"] == "Test"

    def test_save_unicode_preserved(self, tmp_path):
        config_file = tmp_path / "config.json"
        cfg = make_config(name="Ångström")
        cfg.save(config_file)
        data = json.loads(config_file.read_text(encoding="utf-8"))
        assert data["name"] == "Ångström"


# ---------------------------------------------------------------------------
# CONFIG_FILE env var (module-level resolution)
# ---------------------------------------------------------------------------

class TestConfigFileEnvVar:
    def test_load_uses_provided_path_not_env_default(self, tmp_path, monkeypatch):
        # Ensure the explicit path argument takes priority regardless of env
        monkeypatch.setenv("RADIO_TTY_CONFIG", str(tmp_path / "ignored.json"))
        config_file = tmp_path / "explicit.json"
        config_file.write_text(json.dumps({"callsign": "N0ENV"}))
        cfg = ServerConfig.load(config_file)
        assert cfg.callsign == "N0ENV"


# ---------------------------------------------------------------------------
# PTT Lead-in
# ---------------------------------------------------------------------------

class TestPttLeadInMs:
    def test_default_is_350(self):
        cfg = ServerConfig()
        assert cfg.ptt_lead_in_ms == 350

    def test_reads_from_dict(self):
        cfg = ServerConfig({"ptt_lead_in_ms": 400})
        assert cfg.ptt_lead_in_ms == 400

    def test_returns_int(self):
        cfg = ServerConfig({"ptt_lead_in_ms": "500"})
        assert isinstance(cfg.ptt_lead_in_ms, int)
        assert cfg.ptt_lead_in_ms == 500
