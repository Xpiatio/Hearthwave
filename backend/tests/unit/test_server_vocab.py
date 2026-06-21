import sys
from unittest.mock import MagicMock

# backend.server transitively imports sounddevice (and other audio/ML deps) at
# module load time.  Stub them out so tests run in environments without audio hardware.
for _stub in ("sounddevice", "faster_whisper", "silero_vad", "piper"):
    sys.modules.setdefault(_stub, MagicMock())
_piper_config_stub = MagicMock()
_piper_config_stub.SynthesisConfig = MagicMock
sys.modules.setdefault("piper.config", _piper_config_stub)

import backend.server as server


class _FakeStore:
    def __init__(self, contacts): self._c = contacts
    def get_all(self): return self._c


class _FakeWorker:
    def __init__(self): self.last = None
    def update_phrases(self, phrases): self.last = phrases


class _FakeConfig:
    saved_phrases = ["my custom phrase"]
    stt_vocab_max_callsigns = 100


def test_assemble_stt_phrases_orders_callsigns_last(monkeypatch):
    monkeypatch.setattr(server, "_contacts_store", _FakeStore([{"callsign": "KE8AAA"}]))
    monkeypatch.setattr(server, "_config", _FakeConfig())
    out = server._assemble_stt_phrases()
    assert out[-1] == "KE8AAA"
    assert "my custom phrase" in out
    assert out.index("my custom phrase") < out.index("KE8AAA")


def test_rebuild_pushes_to_worker_and_counts(monkeypatch):
    worker = _FakeWorker()
    monkeypatch.setattr(server, "_contacts_store", _FakeStore([{"callsign": "KE8AAA"}]))
    monkeypatch.setattr(server, "_config", _FakeConfig())
    monkeypatch.setattr(server, "_stt_worker", worker)
    count = server._rebuild_stt_vocabulary()
    assert worker.last[-1] == "KE8AAA"
    assert count == len(worker.last)


def test_rebuild_no_worker_is_noop(monkeypatch):
    monkeypatch.setattr(server, "_stt_worker", None)
    assert server._rebuild_stt_vocabulary() == 0
