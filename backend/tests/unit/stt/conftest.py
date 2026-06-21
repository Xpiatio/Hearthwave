"""Stub audio/ML deps before any stt unit-test module is imported.

backend.stt.__init__ eagerly imports STTWorker, which transitively pulls in
sounddevice, faster_whisper, silero_vad, and piper.  These are not available
in the bare CI environment, so we stub them out the same way the integration
conftest does.

We only stub a dependency that is NOT actually installed. Force-stubbing an
installed package with a MagicMock breaks real submodule imports — e.g.
`import torch.nn` (used by noisereduce.torchgate) requires sys.modules['torch']
to be a real package, which a MagicMock is not.
"""
import importlib.util
import sys
from unittest.mock import MagicMock


def _installed(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:
        return False


# These are always stubbed for fast, hermetic unit tests (several tests assert
# against the mocks, e.g. faster_whisper.WhisperModel.call_args).
for _name in ("sounddevice", "faster_whisper", "silero_vad", "piper", "transformers"):
    sys.modules.setdefault(_name, MagicMock())

# torch is special: noisereduce.torchgate does `import torch.nn`, which needs
# sys.modules['torch'] to be a real package (a MagicMock is not). So stub torch
# only when real torch is genuinely absent (the bare CI environment); otherwise
# let the real package load so the preprocessing chain works.
if not _installed("torch"):
    sys.modules.setdefault("torch", MagicMock())

_piper_config = MagicMock()
_piper_config.SynthesisConfig = MagicMock
sys.modules.setdefault("piper.config", _piper_config)

# scipy's array-API compat layer calls issubclass(cls, torch.Tensor), which
# fails when torch.Tensor is a MagicMock (not a real class).  Patch Tensor to a
# real class so issubclass works — but only when torch is the stub; real torch
# already has a real Tensor.
_torch_stub = sys.modules.get("torch")
if isinstance(_torch_stub, MagicMock) and not isinstance(getattr(_torch_stub, "Tensor", None), type):
    class _TensorStub:
        pass
    _torch_stub.Tensor = _TensorStub
