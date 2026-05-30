"""Stub heavy ML/audio deps in sys.modules before server.py is imported.

This file runs during pytest collection — before any test file in this
directory is imported — so the stubs are in place when backend.server pulls
in its transitive dependencies (sounddevice, piper, etc.).

numpy is imported for real when available so unit tests that need actual
array operations are not broken by this stub file leaking into sys.modules.
"""
import sys
from unittest.mock import MagicMock

# Import numpy for real if available; only stub when absent.  The unit/stt
# tests need real numpy; the integration tests mock STTWorker anyway so they
# don't exercise numpy code paths directly.
try:
    import numpy  # noqa: F401 — ensure real module in sys.modules
except ImportError:
    sys.modules.setdefault("numpy", MagicMock())

for _name in ("sounddevice", "piper"):
    sys.modules.setdefault(_name, MagicMock())

# tts/synthesizer.py does `from piper.config import SynthesisConfig` at
# module level, so the sub-module and the attribute both need to exist.
_piper_config = MagicMock()
_piper_config.SynthesisConfig = MagicMock
sys.modules["piper.config"] = _piper_config
