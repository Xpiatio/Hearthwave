"""Tests for backend.server._make_stt_worker — the single construction point
for STTWorker. A miswired config key fails silently (wrong value, not an
exception), so assert each new key reaches the worker constructor.
"""
from unittest.mock import patch

import backend.server as server
from backend.config import ServerConfig


def _capture_worker_kwargs(cfg: ServerConfig) -> dict:
    captured = {}

    def fake_worker(**kwargs):
        captured.update(kwargs)
        return object()

    with patch.object(server, "_config", cfg), \
         patch.object(server, "STTWorker", fake_worker):
        server._make_stt_worker()
    return captured


def test_passes_stt_accuracy_config_keys():
    cfg = ServerConfig({
        "squelch_open_threshold": 0.02,
        "squelch_adaptive": True,
        "stt_pre_roll_s": 2.0,
        "stt_min_speech_s": 0.25,
        "whisper_model_final": "distil-large-v3",
        "stt_final_max_s": 45.0,
        "stt_debug_capture": True,
        "stt_debug_dir": "/tmp/dbg",
        "stt_gain_mode": "rms",
        "stt_noise_profile": True,
    })
    kw = _capture_worker_kwargs(cfg)

    assert kw["squelch_open_threshold"] == 0.02
    assert kw["squelch_adaptive"] is True
    assert kw["pre_roll_s"] == 2.0
    assert kw["min_speech_s"] == 0.25
    assert kw["whisper_model_final"] == "distil-large-v3"
    assert kw["final_max_s"] == 45.0
    assert kw["debug_capture"] is True
    assert kw["debug_dir"] == "/tmp/dbg"
    assert kw["gain_mode"] == "rms"
    assert kw["noise_profile"] is True


def test_defaults_when_keys_absent():
    kw = _capture_worker_kwargs(ServerConfig({}))

    assert kw["squelch_open_threshold"] == 0.05
    assert kw["squelch_adaptive"] is False
    assert kw["pre_roll_s"] == 1.0
    assert kw["min_speech_s"] == 0.4
    # New installs default to auto-resolving the final-pass model;
    # persisted "" (explicit off) is deliberately not migrated.
    assert kw["whisper_model_final"] == "auto"
    assert kw["debug_capture"] is False
    assert kw["gain_mode"] == "agc"
    assert kw["noise_profile"] is False


def test_sentinel_input_device_normalized_to_none():
    # -1 is the "no explicit device" sentinel; the worker expects None.
    kw = _capture_worker_kwargs(ServerConfig({"input_device": -1}))
    assert kw["input_device"] is None
