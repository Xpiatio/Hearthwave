"""Unit tests for WhisperTranscriber prompt building and update logic."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np

from backend.stt.transcriber import WhisperTranscriber


def _make(phrases=()):
    return WhisperTranscriber(model=MagicMock(), saved_phrases=phrases)


def _seg(text, no_speech_prob=0.0, avg_logprob=0.0):
    return SimpleNamespace(text=text, no_speech_prob=no_speech_prob, avg_logprob=avg_logprob)


class _FakeModel:
    """Records the kwargs transcribe() forwards and returns canned segments."""

    def __init__(self, segments):
        self._segments = segments
        self.call_kwargs = None

    def transcribe(self, audio, **kwargs):
        self.call_kwargs = kwargs
        return iter(self._segments), SimpleNamespace()


def _transcriber(segments):
    return WhisperTranscriber(model=_FakeModel(segments))


# ---------------------------------------------------------------------------
# transcribe() — segment filtering and final-pass robustness flags
# ---------------------------------------------------------------------------

class TestTranscribeFiltering:
    def test_drops_low_logprob_segment_by_default(self):
        t = _transcriber([_seg("clear"), _seg("garbled", avg_logprob=-2.0)])
        assert t.transcribe(np.zeros(16000, dtype=np.float32)) == "clear"

    def test_keeps_low_logprob_when_drop_disabled(self):
        # The whole-utterance final pass must not truncate a long message by
        # discarding lower-confidence tail segments.
        t = _transcriber([_seg("clear"), _seg("quiet tail", avg_logprob=-2.0)])
        result = t.transcribe(np.zeros(16000, dtype=np.float32), drop_low_confidence=False)
        assert result == "clear quiet tail"

    def test_always_drops_silence_segments(self):
        # no_speech_prob filtering stays on even with confidence drop disabled.
        t = _transcriber([_seg("speech"), _seg("hiss", no_speech_prob=0.9)])
        assert (
            t.transcribe(np.zeros(16000, dtype=np.float32), drop_low_confidence=False)
            == "speech"
        )

    def test_vad_filter_flag_forwarded(self):
        model = _FakeModel([_seg("hi")])
        t = WhisperTranscriber(model=model)
        t.transcribe(np.zeros(16000, dtype=np.float32), vad_filter=False)
        assert model.call_kwargs["vad_filter"] is False

    def test_vad_filter_defaults_on(self):
        model = _FakeModel([_seg("hi")])
        t = WhisperTranscriber(model=model)
        t.transcribe(np.zeros(16000, dtype=np.float32))
        assert model.call_kwargs["vad_filter"] is True


# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    def test_empty_list_returns_base(self):
        assert WhisperTranscriber._build_prompt([]) == "GMRS radio."

    def test_empty_tuple_returns_base(self):
        assert WhisperTranscriber._build_prompt(()) == "GMRS radio."

    def test_single_phrase(self):
        assert WhisperTranscriber._build_prompt(["break break"]) == (
            "GMRS radio. Phrases: break break."
        )

    def test_multiple_phrases_joined(self):
        assert WhisperTranscriber._build_prompt(["over", "10-4", "QSL"]) == (
            "GMRS radio. Phrases: over, 10-4, QSL."
        )

    def test_phrases_containing_commas_pass_through(self):
        result = WhisperTranscriber._build_prompt(["break, break"])
        assert result == "GMRS radio. Phrases: break, break."


# ---------------------------------------------------------------------------
# __init__ sets initial_prompt
# ---------------------------------------------------------------------------

class TestInit:
    def test_no_phrases_gives_base_prompt(self):
        assert _make().initial_prompt == "GMRS radio."

    def test_phrases_included_in_prompt(self):
        assert _make(["roger that"]).initial_prompt == "GMRS radio. Phrases: roger that."

    def test_multiple_phrases_at_init(self):
        t = _make(["over", "QSL"])
        assert t.initial_prompt == "GMRS radio. Phrases: over, QSL."


# ---------------------------------------------------------------------------
# update_prompt
# ---------------------------------------------------------------------------

class TestUpdatePrompt:
    def test_replaces_existing_phrases(self):
        t = _make(["old"])
        t.update_prompt(["new"])
        assert t.initial_prompt == "GMRS radio. Phrases: new."

    def test_empty_list_resets_to_base(self):
        t = _make(["break break"])
        t.update_prompt([])
        assert t.initial_prompt == "GMRS radio."

    def test_default_arg_resets_to_base(self):
        t = _make(["break break"])
        t.update_prompt()
        assert t.initial_prompt == "GMRS radio."

    def test_multiple_updates_are_independent(self):
        t = _make()
        t.update_prompt(["first"])
        t.update_prompt(["second"])
        assert t.initial_prompt == "GMRS radio. Phrases: second."


# ---------------------------------------------------------------------------
# load() cpu_threads plumbing (faster_whisper is stubbed by conftest)
# ---------------------------------------------------------------------------

class TestLoadCpuThreads:
    def _last_call_kwargs(self):
        import faster_whisper
        return faster_whisper.WhisperModel.call_args.kwargs

    def test_default_leaves_one_core_free(self):
        import os
        WhisperTranscriber.load("/tmp/model")
        expected = max(1, (os.cpu_count() or 2) - 1)
        assert self._last_call_kwargs()["cpu_threads"] == expected

    def test_explicit_cpu_threads_forwarded(self):
        WhisperTranscriber.load("/tmp/model", cpu_threads=2)
        assert self._last_call_kwargs()["cpu_threads"] == 2
