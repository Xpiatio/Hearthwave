"""Tests for the two-tier final-pass transcription in STTWorker.

Drives _transcription_loop and _final_pass_loop directly (no audio device,
no ML models — transcribers are stubs, _emit_result is captured).
"""
import asyncio
import queue

import numpy as np
import pytest

from backend.audio.dsp import make_bandpass_sos
from backend.stt.worker import STTWorker

SR = STTWorker.SAMPLE_RATE
SOS = make_bandpass_sos(SR)


class StubTranscriber:
    def __init__(self, texts=("hello",)):
        self.texts = list(texts)
        self.calls = []

    def transcribe(self, audio):
        self.calls.append(audio)
        return self.texts[(len(self.calls) - 1) % len(self.texts)]

    def update_prompt(self, phrases=()):
        pass


def _audio(seconds=0.5, value=0.1):
    return np.full(int(seconds * SR), value, dtype=np.float32)


def make_worker(final_model="distil-large-v3", **kw):
    w = STTWorker(out_queue=asyncio.Queue(), whisper_model_final=final_model, **kw)
    results = []

    def capture(uid, text, partial, source="voice", replace=False):
        results.append({"uid": uid, "text": text, "partial": partial, "replace": replace})

    w._emit_result = capture
    return w, results


def run_transcription_loop(w, jobs, transcriber):
    q = queue.Queue()
    for j in jobs:
        q.put(j)
    q.put(None)
    w._transcription_loop(q, transcriber, SOS)


def run_final_loop(w, jobs, final_transcriber):
    w._load_final_transcriber = lambda: final_transcriber
    fq = w._final_q
    for j in jobs:
        fq.put(j)
    fq.put(None)
    w._final_pass_loop(fq, SOS)


# ---------------------------------------------------------------------------
# Disabled mode — behavior identical to the single-pass pipeline
# ---------------------------------------------------------------------------

class TestDisabledMode:
    def test_no_final_queue_when_model_empty(self):
        w, _ = make_worker(final_model="")
        assert w._final_q is None

    def test_final_emitted_directly(self):
        w, results = make_worker(final_model="")
        run_transcription_loop(
            w,
            [(1, _audio(), False), (1, _audio(), True)],
            StubTranscriber(["part", "tail"]),
        )
        assert results == [
            {"uid": 1, "text": "part", "partial": True, "replace": False},
            {"uid": 1, "text": "tail", "partial": False, "replace": False},
        ]


# ---------------------------------------------------------------------------
# Enabled mode — fast-path tail demoted to partial, full audio queued
# ---------------------------------------------------------------------------

class TestEnabledFastPath:
    def test_tail_emitted_as_partial_and_full_audio_queued(self):
        w, results = make_worker()
        seg1, seg2 = _audio(0.5), _audio(0.3)
        run_transcription_loop(w, [(1, seg1, False), (1, seg2, True)], StubTranscriber(["a", "b"]))
        # tail "b" must NOT be a final — the final pass will replace it
        assert results[-1] == {"uid": 1, "text": "b", "partial": True, "replace": False}
        uid, full = w._final_q.get_nowait()
        assert uid == 1
        assert full.size == seg1.size + seg2.size

    def test_overlong_utterance_abandons_final_pass(self):
        # cap below the segment total → final pass skipped, tail emitted as a
        # plain final so the partials still get flushed downstream
        w, results = make_worker(final_max_s=0.5)
        run_transcription_loop(
            w,
            [(1, _audio(0.4), False), (1, _audio(0.4), True)],
            StubTranscriber(["a", "b"]),
        )
        assert results[-1]["partial"] is False
        assert results[-1]["replace"] is False
        assert w._final_q.empty()

    def test_empty_tail_still_queues_final_pass(self):
        # Whisper returning None on the tail must not lose the utterance
        w, results = make_worker()

        class NoneTranscriber(StubTranscriber):
            def transcribe(self, audio):
                super().transcribe(audio)
                return None

        run_transcription_loop(w, [(1, _audio(), True)], NoneTranscriber())
        assert not w._final_q.empty()

    def test_queue_full_drops_oldest_with_fallback_final(self):
        w, results = make_worker()
        w._final_q = queue.Queue(maxsize=1)
        w._enqueue_final(1, _audio())
        w._enqueue_final(2, _audio())
        # uid 1 dropped → empty fallback final so the server flushes partials
        assert {"uid": 1, "text": "", "partial": False, "replace": False} in results
        uid, _ = w._final_q.get_nowait()
        assert uid == 2


# ---------------------------------------------------------------------------
# Final-pass loop
# ---------------------------------------------------------------------------

class TestFinalPassLoop:
    def test_emits_replacing_final(self):
        w, results = make_worker()
        run_final_loop(w, [(1, _audio())], StubTranscriber(["the better transcript"]))
        assert results == [
            {"uid": 1, "text": "the better transcript", "partial": False, "replace": True}
        ]

    def test_empty_text_falls_back_to_plain_final(self):
        w, results = make_worker()

        class NoneTranscriber(StubTranscriber):
            def transcribe(self, audio):
                return None

        run_final_loop(w, [(1, _audio())], NoneTranscriber())
        assert results == [{"uid": 1, "text": "", "partial": False, "replace": False}]

    def test_transcription_exception_falls_back(self):
        w, results = make_worker()

        class BoomTranscriber(StubTranscriber):
            def transcribe(self, audio):
                raise RuntimeError("boom")

        run_final_loop(w, [(1, _audio())], BoomTranscriber())
        assert results == [{"uid": 1, "text": "", "partial": False, "replace": False}]

    def test_model_load_failure_falls_back_for_all_jobs(self):
        w, results = make_worker()
        run_final_loop(w, [(1, _audio()), (2, _audio())], None)
        assert results == [
            {"uid": 1, "text": "", "partial": False, "replace": False},
            {"uid": 2, "text": "", "partial": False, "replace": False},
        ]

    def test_multiple_jobs_processed_in_order(self):
        w, results = make_worker()
        run_final_loop(w, [(1, _audio()), (2, _audio())], StubTranscriber(["one", "two"]))
        assert [r["uid"] for r in results] == [1, 2]
        assert all(r["replace"] for r in results)


# ---------------------------------------------------------------------------
# _emit_result wire format
# ---------------------------------------------------------------------------

class TestEmitResultReplace:
    def test_replace_field_in_payload(self):
        w = STTWorker(out_queue=asyncio.Queue())
        captured = {}

        class FakeLoop:
            def call_soon_threadsafe(self, fn, payload):
                captured.update(payload)

        w._loop = FakeLoop()
        w._emit_result(3, "text", False, replace=True)
        assert captured["replace"] is True
        assert captured["partial"] is False

    def test_replace_defaults_false(self):
        w = STTWorker(out_queue=asyncio.Queue())
        captured = {}

        class FakeLoop:
            def call_soon_threadsafe(self, fn, payload):
                captured.update(payload)

        w._loop = FakeLoop()
        w._emit_result(3, "text", True)
        assert captured["replace"] is False
