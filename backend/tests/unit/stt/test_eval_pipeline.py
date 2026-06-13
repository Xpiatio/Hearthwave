"""Tests for backend.tools.eval_stt — offline pipeline replay + WER scoring.

Uses the MockVAD pattern from test_segmenter.py and a stub transcriber so no
ML models load. The pipeline under test drives the real SpeechSegmenter,
SquelchDetector, and preprocess_segment.
"""
import numpy as np
import pytest

from backend.tools.eval_stt import (
    EvalPipelineConfig,
    find_reference,
    normalize_text,
    run_pipeline,
    score,
)

SR = 16000
CHUNK = 512


class MockVAD:
    def __init__(self, events=()):
        self._events = list(events)
        self._idx = 0

    def __call__(self, audio_chunk, return_seconds=False):
        if self._idx < len(self._events):
            ev = self._events[self._idx]
            self._idx += 1
            if ev == "start":
                return {"start": 0}
            if ev == "end":
                return {"end": CHUNK}
        return None

    def reset_states(self):
        pass


class StubTranscriber:
    """Returns a canned text per call and records the audio it was given."""

    def __init__(self, texts=("hello",)):
        self.texts = list(texts)
        self.calls = []

    def transcribe(self, audio):
        self.calls.append(audio)
        return self.texts[(len(self.calls) - 1) % len(self.texts)]


def _audio(n_chunks, value=0.5):
    return np.full(n_chunks * CHUNK, value, dtype=np.float32)


def _cfg(**kw):
    kw.setdefault("min_speech_s", 0.0)
    kw.setdefault("flush_silence_s", 0.0)
    return EvalPipelineConfig(**kw)


def test_simple_utterance_produces_one_final(tmp_path):
    # speech starts on chunk 1, ends on chunk 5
    vad = MockVAD([None, "start", None, None, None, "end"])
    stub = StubTranscriber(["radio check"])
    results = run_pipeline(_audio(8), _cfg(), stub, vad)
    assert len(results) == 1
    assert results[0]["text"] == "radio check"
    assert len(stub.calls) == 1


def test_audio_not_multiple_of_chunk_size_is_handled():
    vad = MockVAD([None, "start", None, "end"])
    stub = StubTranscriber(["ok"])
    audio = np.zeros(6 * CHUNK + 100, dtype=np.float32) + 0.5
    results = run_pipeline(audio, _cfg(), stub, vad)
    assert len(results) == 1


def test_partials_concatenated_with_final():
    # Force partial slices with a tiny rolling window: rolling 4 chunks +
    # cut window 2 → slice trigger at 6 in-speech chunks.
    rolling_s = 4 * CHUNK / SR
    cut_s = 2 * CHUNK / SR
    events = [None, "start"] + [None] * 12 + ["end"]
    vad = MockVAD(events)
    stub = StubTranscriber(["one", "two", "three"])
    cfg = _cfg(rolling_segment_s=rolling_s, cut_window_s=cut_s)
    results = run_pipeline(_audio(20), cfg, stub, vad)
    assert len(results) == 1
    # N partial slices then the tail; text mirrors the server's concat rule
    assert len(stub.calls) >= 2
    expected = " ".join(stub.texts[: len(stub.calls)])
    assert results[0]["text"] == expected


def test_stage_toggles_forwarded(monkeypatch):
    seen = {}
    import backend.tools.eval_stt as mod

    def fake_preprocess(audio, sr, sos, **kw):
        seen.update(kw)
        return audio

    monkeypatch.setattr(mod, "preprocess_segment", fake_preprocess)
    vad = MockVAD([None, "start", None, "end"])
    cfg = _cfg(denoise_enabled=False, agc_enabled=False, prop_decrease=0.3)
    run_pipeline(_audio(6), cfg, StubTranscriber(), vad)
    assert seen == {"denoise_enabled": False, "agc_enabled": False, "prop_decrease": 0.3}


def test_normalize_text_strips_case_and_punctuation():
    assert normalize_text("Hello, World!  Over.") == "hello world over"


def test_score_zero_wer_for_equivalent_text():
    result = score(["Radio check, over!"], ["radio check over"])
    assert result["wer"] == 0.0


def test_score_counts_errors():
    result = score(["alpha bravo charlie delta"], ["alpha bravo charlie echo"])
    assert result["wer"] == pytest.approx(0.25)


def test_find_reference_sibling_txt(tmp_path):
    wav = tmp_path / "sample.wav"
    wav.touch()
    (tmp_path / "sample.txt").write_text("hello there\n")
    assert find_reference(wav) == "hello there"


def test_find_reference_capture_dir(tmp_path):
    utt = tmp_path / "utt_123_0001"
    utt.mkdir()
    wav = utt / "raw.wav"
    wav.touch()
    (utt / "reference.txt").write_text("copy that\n")
    assert find_reference(wav) == "copy that"


def test_find_reference_missing_returns_none(tmp_path):
    wav = tmp_path / "nolabel.wav"
    wav.touch()
    assert find_reference(wav) is None
