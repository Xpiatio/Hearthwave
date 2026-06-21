"""Unit tests for GpuWhisperTranscriber logic (no real GPU/torch)."""
from unittest.mock import MagicMock

import numpy as np

from backend.stt.gpu_transcriber import GpuWhisperTranscriber


class _FakeProcessor:
    """Minimal stand-in for a transformers WhisperProcessor."""
    def __init__(self):
        self.tokenizer = MagicMock()
        self.tokenizer.side_effect = lambda s: MagicMock(input_ids=list(range(len(s.split()))))
        self.gen_calls = []
        self.decoded = "unit seven en route"

    def get_prompt_ids(self, text, return_tensors=None):
        return MagicMock(name="prompt_ids")

    def __call__(self, audio, sampling_rate=16000, **kw):
        feats = MagicMock()
        feats.input_features.to.return_value = "FEATS"
        return feats

    def batch_decode(self, ids, skip_special_tokens=True):
        return [self.decoded]


class _FakeModel:
    def __init__(self):
        self.generate_kwargs = None

    def generate(self, feats, **kwargs):
        self.generate_kwargs = kwargs
        return MagicMock(name="token_ids")


def _make(decoded="unit seven en route", phrases=()):
    proc = _FakeProcessor()
    proc.decoded = decoded
    return GpuWhisperTranscriber(model=_FakeModel(), processor=proc, saved_phrases=phrases), proc


def test_initial_prompt_built():
    t, _ = _make(phrases=["over", "QSL"])
    assert t.initial_prompt == "GMRS radio. Phrases: over, QSL."


def test_transcribe_returns_decoded_text():
    t, _ = _make(decoded="unit seven en route")
    assert t.transcribe(np.zeros(16000, dtype=np.float32)) == "unit seven en route"


def test_transcribe_drops_hallucination():
    t, _ = _make(decoded="You.")
    assert t.transcribe(np.zeros(16000, dtype=np.float32)) is None


def test_transcribe_uses_beam_and_timestamps():
    t, _ = _make()
    t.transcribe(np.zeros(16000, dtype=np.float32))
    kw = t.model.generate_kwargs
    assert kw["num_beams"] == 5
    assert kw["return_timestamps"] is True
    assert kw["language"] == "en"
    assert kw["task"] == "transcribe"


def test_update_prompt_rebuilds():
    t, _ = _make(phrases=["old"])
    t.update_prompt(["new"])
    assert t.initial_prompt == "GMRS radio. Phrases: new."
