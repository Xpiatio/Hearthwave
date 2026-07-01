"""Unit tests for WhisperTranscriber prompt building and update logic."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np

from backend.stt.transcriber import WhisperTranscriber


def _wordcount(s):  # fake tokenizer: 1 token per word
    return len(s.split())


def _make(phrases=()):
    return WhisperTranscriber(model=MagicMock(), saved_phrases=phrases)


def _seg(text, no_speech_prob=0.0, avg_logprob=0.0, words=None):
    return SimpleNamespace(
        text=text, no_speech_prob=no_speech_prob, avg_logprob=avg_logprob, words=words
    )


def _word(word, probability):
    return SimpleNamespace(word=word, probability=probability)


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
# decode_options — extra/override kwargs merged into model.transcribe()
# ---------------------------------------------------------------------------

class TestDecodeOptions:
    def test_none_gives_todays_exact_kwargs(self):
        # Pin the exact kwarg set/values so a later change can't silently grow
        # or shrink the default decode call (mirrors TestFinalPassLoop's pin
        # on the worker side).
        model = _FakeModel([_seg("hi")])
        t = WhisperTranscriber(model=model)
        t.transcribe(np.zeros(16000, dtype=np.float32))
        assert model.call_kwargs == {
            "language": "en",
            "beam_size": 5,
            "vad_filter": True,
            "condition_on_previous_text": False,
            "initial_prompt": "GMRS radio.",
        }

    def test_new_key_is_forwarded(self):
        model = _FakeModel([_seg("hi")])
        t = WhisperTranscriber(model=model, decode_options={"repetition_penalty": 1.2})
        t.transcribe(np.zeros(16000, dtype=np.float32))
        assert model.call_kwargs["repetition_penalty"] == 1.2

    def test_overrides_beam_size(self):
        model = _FakeModel([_seg("hi")])
        t = WhisperTranscriber(model=model, decode_options={"beam_size": 8})
        t.transcribe(np.zeros(16000, dtype=np.float32))
        assert model.call_kwargs["beam_size"] == 8

    def test_cannot_override_vad_filter(self):
        model = _FakeModel([_seg("hi")])
        t = WhisperTranscriber(model=model, decode_options={"vad_filter": False})
        t.transcribe(np.zeros(16000, dtype=np.float32))  # call-site default: vad_filter=True
        assert model.call_kwargs["vad_filter"] is True

    def test_cannot_override_initial_prompt(self):
        model = _FakeModel([_seg("hi")])
        t = WhisperTranscriber(
            model=model, saved_phrases=["over"], decode_options={"initial_prompt": "hijacked"}
        )
        t.transcribe(np.zeros(16000, dtype=np.float32))
        assert model.call_kwargs["initial_prompt"] == "GMRS radio. Phrases: over."


# ---------------------------------------------------------------------------
# word_confidence_min — rebuild segment text from word-level confidences
# ---------------------------------------------------------------------------

class TestWordConfidenceGate:
    def test_none_omits_word_timestamps_kwarg(self):
        model = _FakeModel([_seg("hi")])
        t = WhisperTranscriber(model=model)
        t.transcribe(np.zeros(16000, dtype=np.float32))
        assert "word_timestamps" not in model.call_kwargs

    def test_set_passes_word_timestamps_true(self):
        model = _FakeModel([_seg("hi", words=[_word("hi", 0.9)])])
        t = WhisperTranscriber(model=model, word_confidence_min=0.5)
        t.transcribe(np.zeros(16000, dtype=np.float32))
        assert model.call_kwargs["word_timestamps"] is True

    def test_drops_low_confidence_words(self):
        words = [_word(" clear", 0.95), _word(" mumble", 0.2)]
        model = _FakeModel([_seg(" clear mumble", words=words)])
        t = WhisperTranscriber(model=model, word_confidence_min=0.5)
        assert t.transcribe(np.zeros(16000, dtype=np.float32)) == "clear"

    def test_segment_with_all_words_below_threshold_contributes_nothing(self):
        words = [_word(" clear", 0.95), _word(" mumble", 0.2)]
        low_words = [_word(" garbled", 0.1)]
        model = _FakeModel(
            [_seg(" clear mumble", words=words), _seg(" garbled", words=low_words)]
        )
        t = WhisperTranscriber(model=model, word_confidence_min=0.5)
        assert t.transcribe(np.zeros(16000, dtype=np.float32)) == "clear"

    def test_all_words_filtered_returns_none(self):
        words = [_word(" um", 0.1), _word(" uh", 0.2)]
        model = _FakeModel([_seg(" um uh", words=words)])
        t = WhisperTranscriber(model=model, word_confidence_min=0.5)
        assert t.transcribe(np.zeros(16000, dtype=np.float32)) is None


# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    def test_empty_list_returns_base(self):
        assert WhisperTranscriber._build_prompt([], count_tokens=_wordcount) == "GMRS radio."

    def test_empty_tuple_returns_base(self):
        assert WhisperTranscriber._build_prompt((), count_tokens=_wordcount) == "GMRS radio."

    def test_single_phrase(self):
        assert WhisperTranscriber._build_prompt(["break break"], count_tokens=_wordcount) == (
            "GMRS radio. Phrases: break break."
        )

    def test_multiple_phrases_joined(self):
        assert WhisperTranscriber._build_prompt(["over", "10-4", "QSL"], count_tokens=_wordcount) == (
            "GMRS radio. Phrases: over, 10-4, QSL."
        )

    def test_phrases_containing_commas_pass_through(self):
        result = WhisperTranscriber._build_prompt(["break, break"], count_tokens=_wordcount)
        assert result == "GMRS radio. Phrases: break, break."

    def test_build_prompt_frames_phrases(self):
        from backend.stt.transcriber import WhisperTranscriber
        out = WhisperTranscriber._build_prompt(["over", "KE8AAA"], count_tokens=_wordcount)
        assert out == "GMRS radio. Phrases: over, KE8AAA."

    def test_build_prompt_token_trims_keeping_tail(self):
        from backend.stt.transcriber import WhisperTranscriber
        # Force a tiny budget by using a counter that overcounts, proving the
        # front is dropped and the high-priority tail token survives.
        phrases = [f"term{i}" for i in range(300)] + ["KE8ZZZ"]
        out = WhisperTranscriber._build_prompt(phrases, count_tokens=_wordcount)
        assert _wordcount(out) <= WhisperTranscriber._MAX_PROMPT_TOKENS
        assert out.endswith("KE8ZZZ.")
        assert "term0," not in out


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

    def test_decode_options_and_word_confidence_min_forwarded(self):
        t = WhisperTranscriber.load(
            "/tmp/model",
            decode_options={"beam_size": 8},
            word_confidence_min=0.4,
        )
        assert t.decode_options == {"beam_size": 8}
        assert t.word_confidence_min == 0.4
