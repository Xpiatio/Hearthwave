"""Selection + fallback logic for the final-pass transcriber backend."""
import asyncio
from unittest.mock import MagicMock

import backend.stt.worker as worker_mod
from backend.stt.worker import STTWorker


def _worker(tmp_path, device, monkeypatch):
    # Make both the CT2 and HF model dirs exist so path checks pass.
    models = tmp_path / "Models" / "STT"
    (models / "distil-large-v3").mkdir(parents=True)
    (models / "distil-large-v3-hf").mkdir(parents=True)
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
