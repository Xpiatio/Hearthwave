import sys
import types
import importlib
import pytest


def _reload_hw_detect():
    if "backend.hw_detect" in sys.modules:
        del sys.modules["backend.hw_detect"]
    from backend import hw_detect
    return hw_detect


def _make_torch(cuda_available: bool, hip_version):
    """Return a minimal fake torch module."""
    torch = types.ModuleType("torch")
    torch.cuda = types.SimpleNamespace(is_available=lambda: cuda_available)
    torch.version = types.SimpleNamespace(hip=hip_version)
    return torch


class TestCUDABackend:
    def test_returns_cuda_when_cuda_available(self, monkeypatch):
        fake_torch = _make_torch(cuda_available=True, hip_version=None)
        monkeypatch.setitem(sys.modules, "torch", fake_torch)

        hw = _reload_hw_detect()
        backend = hw.detect()

        assert backend.provider == "CUDAExecutionProvider"
        assert backend.device_label == "NVIDIA GPU (CUDA)"
        assert "CUDAExecutionProvider" in backend.ort_providers


class TestROCmBackend:
    def test_returns_rocm_when_cuda_unavailable_and_hip_present(self, monkeypatch):
        fake_torch = _make_torch(cuda_available=False, hip_version="5.7.0")
        monkeypatch.setitem(sys.modules, "torch", fake_torch)
        # Ensure openvino and onnxruntime are absent so ROCm is the first hit
        monkeypatch.setitem(sys.modules, "openvino", None)
        monkeypatch.setitem(sys.modules, "onnxruntime", None)

        hw = _reload_hw_detect()
        backend = hw.detect()

        assert backend.provider == "ROCMExecutionProvider"
        assert backend.device_label == "AMD GPU (ROCm)"
        assert "ROCMExecutionProvider" in backend.ort_providers


class TestCPUFallback:
    def test_falls_back_to_cpu_when_all_gpu_probes_raise(self, monkeypatch):
        # Remove all accelerator libs so every probe hits ImportError
        for mod in ("torch", "openvino", "onnxruntime"):
            monkeypatch.setitem(sys.modules, mod, None)

        hw = _reload_hw_detect()
        backend = hw.detect()

        assert backend.provider == "CPUExecutionProvider"
        assert backend.device_label == "CPU (quantized)"
        assert backend.ort_providers == ["CPUExecutionProvider"]
