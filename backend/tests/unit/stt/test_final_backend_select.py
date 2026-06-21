"""Selection + fallback logic for the final-pass transcriber backend."""
import asyncio
from unittest.mock import MagicMock

import backend.stt.worker as worker_mod
from backend.stt.worker import STTWorker


def _worker(tmp_path, device, monkeypatch, *, make_ct2=True, make_hf=True):
    # Make model dirs based on flags so tests can simulate missing dirs.
    models = tmp_path / "Models" / "STT"
    models.mkdir(parents=True, exist_ok=True)
    if make_ct2:
        (models / "distil-large-v3").mkdir(parents=True, exist_ok=True)
    if make_hf:
        (models / "distil-large-v3-hf").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(STTWorker, "_MODELS_DIR", models)
    w = STTWorker(
        out_queue=asyncio.Queue(),
        whisper_model_final="distil-large-v3",
        stt_final_device=device,
    )
    w._emit_status = lambda *a, **k: None
    w._emit_error = lambda *a, **k: None
    return w


def test_auto_uses_gpu_when_available(tmp_path, monkeypatch):
    monkeypatch.setattr(worker_mod, "rocm_available", lambda: True)
    gpu = MagicMock(name="gpu_inst")
    monkeypatch.setattr(worker_mod.GpuWhisperTranscriber, "load", lambda *a, **k: gpu)
    w = _worker(tmp_path, "auto", monkeypatch)
    assert w._load_final_transcriber() is gpu


def test_auto_uses_cpu_when_no_gpu(tmp_path, monkeypatch):
    monkeypatch.setattr(worker_mod, "rocm_available", lambda: False)
    cpu = MagicMock(name="cpu_inst")
    monkeypatch.setattr(worker_mod.WhisperTranscriber, "load", lambda *a, **k: cpu)
    w = _worker(tmp_path, "auto", monkeypatch)
    assert w._load_final_transcriber() is cpu


def test_gpu_failure_falls_back_to_cpu(tmp_path, monkeypatch):
    monkeypatch.setattr(worker_mod, "rocm_available", lambda: True)
    def boom(*a, **k):
        raise RuntimeError("hip error")
    monkeypatch.setattr(worker_mod.GpuWhisperTranscriber, "load", boom)
    cpu = MagicMock(name="cpu_inst")
    monkeypatch.setattr(worker_mod.WhisperTranscriber, "load", lambda *a, **k: cpu)
    w = _worker(tmp_path, "auto", monkeypatch)
    assert w._load_final_transcriber() is cpu


def test_forced_cpu_ignores_gpu(tmp_path, monkeypatch):
    monkeypatch.setattr(worker_mod, "rocm_available", lambda: True)
    cpu = MagicMock(name="cpu_inst")
    monkeypatch.setattr(worker_mod.WhisperTranscriber, "load", lambda *a, **k: cpu)
    # GpuWhisperTranscriber.load must NOT be called; make it explode if it is.
    monkeypatch.setattr(worker_mod.GpuWhisperTranscriber, "load",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("gpu used")))
    w = _worker(tmp_path, "cpu", monkeypatch)
    assert w._load_final_transcriber() is cpu


def test_missing_gpu_dir_no_error_when_cpu_succeeds(tmp_path, monkeypatch):
    """GPU -hf dir missing + CPU succeeds: _emit_error must NOT be called."""
    monkeypatch.setattr(worker_mod, "rocm_available", lambda: True)
    cpu = MagicMock(name="cpu_inst")
    monkeypatch.setattr(worker_mod.WhisperTranscriber, "load", lambda *a, **k: cpu)
    # GPU dir absent; CT2 dir present (make_hf=False)
    w = _worker(tmp_path, "auto", monkeypatch, make_ct2=True, make_hf=False)

    error_calls = []
    w._emit_error = lambda *a, **k: error_calls.append(a)
    w._emit_status = lambda *a, **k: None

    result = w._load_final_transcriber()
    assert result is cpu, "Expected CPU transcriber to be returned"
    assert error_calls == [], f"_emit_error should not be called; got: {error_calls}"


def test_both_dirs_missing_emits_error_returns_none(tmp_path, monkeypatch):
    """Both GPU and CPU dirs missing: _emit_error IS called and None returned."""
    monkeypatch.setattr(worker_mod, "rocm_available", lambda: True)
    # Neither dir exists (make_ct2=False, make_hf=False)
    w = _worker(tmp_path, "auto", monkeypatch, make_ct2=False, make_hf=False)

    error_calls = []
    w._emit_error = lambda *a, **k: error_calls.append(a)
    w._emit_status = lambda *a, **k: None

    result = w._load_final_transcriber()
    assert result is None, "Expected None when both dirs missing"
    assert len(error_calls) == 1, f"Expected exactly one _emit_error call; got: {error_calls}"
