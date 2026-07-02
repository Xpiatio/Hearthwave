"""Tests for whisper_model_final="auto" — resolve the best final-pass model
actually staged under Models/STT at worker construction, or silently run
single-pass when nothing suitable is staged.

Follows the tmp_path _MODELS_DIR monkeypatch pattern of
test_final_backend_select.py; no models or audio hardware load.
"""
import asyncio

import backend.stt.worker as worker_mod
from backend.stt.worker import STTWorker


def _worker(tmp_path, monkeypatch, *, staged=(), configured="auto",
            fast_model="small.en", device="auto"):
    models = tmp_path / "Models" / "STT"
    models.mkdir(parents=True, exist_ok=True)
    for name in staged:
        (models / name).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(STTWorker, "_MODELS_DIR", models)
    errors = []
    w = STTWorker(
        out_queue=asyncio.Queue(),
        whisper_model=fast_model,
        whisper_model_final=configured,
        stt_final_device=device,
        on_error=errors.append,
    )
    w._test_errors = errors
    return w


class TestAutoResolution:
    def test_nothing_staged_resolves_off_without_error(self, tmp_path, monkeypatch):
        w = _worker(tmp_path, monkeypatch)
        assert w.whisper_model_final == ""
        assert w._final_q is None
        assert w._test_errors == []

    def test_models_dir_absent_resolves_off(self, tmp_path, monkeypatch):
        monkeypatch.setattr(STTWorker, "_MODELS_DIR", tmp_path / "nope" / "STT")
        w = STTWorker(out_queue=asyncio.Queue(), whisper_model_final="auto")
        assert w.whisper_model_final == ""
        assert w._final_q is None

    def test_distil_staged_resolves(self, tmp_path, monkeypatch):
        w = _worker(tmp_path, monkeypatch, staged=("distil-large-v3",))
        assert w.whisper_model_final == "distil-large-v3"
        assert w._final_q is not None

    def test_preference_order_turbo_wins(self, tmp_path, monkeypatch):
        w = _worker(
            tmp_path, monkeypatch,
            staged=("large-v3", "distil-large-v3", "large-v3-turbo"),
        )
        assert w.whisper_model_final == "large-v3-turbo"

    def test_fast_model_excluded_from_candidates(self, tmp_path, monkeypatch):
        # distil staged as BOTH fast and only final candidate → auto must not
        # pick the fast model for the second pass.
        w = _worker(
            tmp_path, monkeypatch,
            staged=("distil-large-v3",), fast_model="distil-large-v3",
        )
        assert w.whisper_model_final == ""

    def test_device_cpu_ignores_hf_only_staging(self, tmp_path, monkeypatch):
        w = _worker(
            tmp_path, monkeypatch, staged=("distil-large-v3-hf",), device="cpu",
        )
        assert w.whisper_model_final == ""

    def test_device_auto_requires_ct2_dir(self, tmp_path, monkeypatch):
        # hf-only staging must not resolve under device=auto: the probe never
        # calls rocm_available() in __init__, so it can't know GPU is present.
        w = _worker(
            tmp_path, monkeypatch, staged=("distil-large-v3-hf",), device="auto",
        )
        assert w.whisper_model_final == ""

    def test_device_gpu_accepts_hf_only_staging(self, tmp_path, monkeypatch):
        w = _worker(
            tmp_path, monkeypatch, staged=("distil-large-v3-hf",), device="gpu",
        )
        assert w.whisper_model_final == "distil-large-v3"

    def test_device_gpu_accepts_ct2_dir_too(self, tmp_path, monkeypatch):
        w = _worker(
            tmp_path, monkeypatch, staged=("distil-large-v3",), device="gpu",
        )
        assert w.whisper_model_final == "distil-large-v3"


class TestExplicitNamesUnchanged:
    def test_empty_string_stays_off(self, tmp_path, monkeypatch):
        w = _worker(
            tmp_path, monkeypatch, staged=("distil-large-v3",), configured="",
        )
        assert w.whisper_model_final == ""
        assert w._final_q is None

    def test_explicit_name_passes_through_even_when_missing(self, tmp_path, monkeypatch):
        # Explicit names keep today's behavior: the loud missing-dir error at
        # load time, not silent auto-fallback at construction.
        w = _worker(tmp_path, monkeypatch, staged=(), configured="distil-large-v3")
        assert w.whisper_model_final == "distil-large-v3"
        assert w._final_q is not None

    def test_configured_value_stored_alongside_resolved(self, tmp_path, monkeypatch):
        w = _worker(tmp_path, monkeypatch, staged=("distil-large-v3",))
        assert w.whisper_model_final_configured == "auto"
        assert w.whisper_model_final == "distil-large-v3"
