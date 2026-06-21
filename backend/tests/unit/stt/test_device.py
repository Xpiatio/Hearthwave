"""Unit tests for the ROCm device probe."""
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

from backend.stt import _device


def _fake_torch(hip, cuda_ok):
    t = MagicMock()
    t.version = SimpleNamespace(hip=hip)
    t.cuda.is_available.return_value = cuda_ok
    return t


def test_true_when_hip_and_cuda(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", _fake_torch("6.4", True))
    assert _device.rocm_available() is True


def test_false_when_no_hip(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", _fake_torch(None, True))
    assert _device.rocm_available() is False


def test_false_when_cuda_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", _fake_torch("6.4", False))
    assert _device.rocm_available() is False


def test_false_when_torch_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", None)  # import torch -> ImportError
    assert _device.rocm_available() is False
