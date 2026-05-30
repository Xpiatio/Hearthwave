"""Stub heavy ML/audio deps in sys.modules before server.py is imported.

This file runs during pytest collection — before any test file in this
directory is imported — so the stubs are in place when backend.server pulls
in its transitive dependencies (numpy, sounddevice, piper, etc.).
"""
import sys
from unittest.mock import MagicMock

for _name in ("numpy", "sounddevice", "piper"):
    sys.modules.setdefault(_name, MagicMock())

# tts/synthesizer.py does `from piper.config import SynthesisConfig` at
# module level, so the sub-module and the attribute both need to exist.
_piper_config = MagicMock()
_piper_config.SynthesisConfig = MagicMock
sys.modules["piper.config"] = _piper_config
