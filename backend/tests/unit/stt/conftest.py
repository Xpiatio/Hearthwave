"""Stub audio/ML deps before any stt unit-test module is imported.

backend.stt.__init__ eagerly imports STTWorker, which transitively pulls in
sounddevice, faster_whisper, silero_vad, and piper.  These are not available
in the bare CI environment, so we stub them out the same way the integration
conftest does.
"""
import sys
from unittest.mock import MagicMock

for _name in ("sounddevice", "faster_whisper", "silero_vad", "piper"):
    sys.modules.setdefault(_name, MagicMock())

_piper_config = MagicMock()
_piper_config.SynthesisConfig = MagicMock
sys.modules.setdefault("piper.config", _piper_config)
