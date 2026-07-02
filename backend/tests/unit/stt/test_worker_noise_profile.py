"""Tests for the squelch-derived noise-profile plumbing in STTWorker.

The clip travels ON the queue items (not a shared attribute) so a final-pass
read seconds later sees the exact snapshot the utterance started with:
transcribe_queue items are (uid, audio, is_final, noise_clip) and _final_q
items are (uid, audio, noise_clip).
"""
import asyncio
import queue

import numpy as np
import pytest

import backend.stt.worker as worker_mod
from backend.audio.dsp import make_bandpass_sos
from backend.stt.worker import STTWorker

SR = STTWorker.SAMPLE_RATE
SOS = make_bandpass_sos(SR)


class StubTranscriber:
    def __init__(self, texts=("hello",)):
        self.texts = list(texts)
        self.calls = []
        self.call_kwargs = []

    def transcribe(self, audio, **kwargs):
        self.calls.append(audio)
        self.call_kwargs.append(kwargs)
        return self.texts[(len(self.calls) - 1) % len(self.texts)]

    def update_prompt(self, phrases=()):
        pass


def _audio(seconds=0.5, value=0.1):
    return np.full(int(seconds * SR), value, dtype=np.float32)


def _clip(seconds=1.0, value=0.01):
    return np.full(int(seconds * SR), value, dtype=np.float32)


def make_worker(final_model="distil-large-v3", **kw):
    w = STTWorker(out_queue=asyncio.Queue(), whisper_model_final=final_model, **kw)
    results = []

    def capture(uid, text, partial, source="voice", replace=False):
        results.append({"uid": uid, "text": text, "partial": partial, "replace": replace})

    w._emit_result = capture
    return w, results


def _capture_preprocess(monkeypatch):
    seen = []

    def fake(audio, sr, sos, **kw):
        seen.append(kw)
        return audio

    monkeypatch.setattr(worker_mod, "preprocess_segment", fake)
    return seen


def test_noise_profile_ctor_defaults_off():
    w = STTWorker(out_queue=asyncio.Queue())
    assert w.noise_profile is False
    w = STTWorker(out_queue=asyncio.Queue(), noise_profile=True)
    assert w.noise_profile is True


def test_transcription_loop_forwards_clip_to_preprocess(monkeypatch):
    seen = _capture_preprocess(monkeypatch)
    w, _ = make_worker(final_model="")
    clip = _clip()
    q = queue.Queue()
    q.put((1, _audio(), True, clip))
    q.put(None)
    w._transcription_loop(q, StubTranscriber(), SOS)
    assert len(seen) == 1
    assert seen[0]["noise_clip"] is clip


def test_transcription_loop_none_clip_forwarded_as_none(monkeypatch):
    seen = _capture_preprocess(monkeypatch)
    w, _ = make_worker(final_model="")
    q = queue.Queue()
    q.put((1, _audio(), True, None))
    q.put(None)
    w._transcription_loop(q, StubTranscriber(), SOS)
    assert seen[0]["noise_clip"] is None


def test_clip_travels_to_final_queue():
    w, _ = make_worker()
    clip = _clip()
    q = queue.Queue()
    q.put((1, _audio(0.5), False, clip))
    q.put((1, _audio(0.3), True, clip))
    q.put(None)
    w._transcription_loop(q, StubTranscriber(["a", "b"]), SOS)
    uid, full, noise_clip = w._final_q.get_nowait()
    assert uid == 1
    assert full.size == _audio(0.5).size + _audio(0.3).size
    assert noise_clip is clip


def test_final_pass_loop_forwards_clip_to_preprocess(monkeypatch):
    seen = _capture_preprocess(monkeypatch)
    w, results = make_worker()
    w._load_final_transcriber = lambda: StubTranscriber(["full transcript"])
    clip = _clip()
    fq = w._final_q
    fq.put((1, _audio(), clip))
    fq.put(None)
    w._final_pass_loop(fq, SOS)
    assert seen[0]["noise_clip"] is clip
    assert results == [
        {"uid": 1, "text": "full transcript", "partial": False, "replace": True}
    ]


def test_final_pass_transcribe_kwargs_unchanged_with_clip():
    # The pinned long-audio decode kwargs must not grow a noise key — the
    # clip enters through preprocess_segment only.
    w, _ = make_worker()
    stub = StubTranscriber(["full transcript"])
    w._load_final_transcriber = lambda: stub
    fq = w._final_q
    fq.put((1, _audio(), _clip()))
    fq.put(None)
    w._final_pass_loop(fq, SOS)
    assert stub.call_kwargs[0] == {"vad_filter": False, "drop_low_confidence": False}


def test_enqueue_final_overflow_drops_oldest_and_keeps_clip():
    w, results = make_worker()
    w._final_q = queue.Queue(maxsize=1)
    clip = _clip()
    w._enqueue_final(1, _audio(), None)
    w._enqueue_final(2, _audio(), clip)
    assert {"uid": 1, "text": "", "partial": False, "replace": False} in results
    uid, _, noise_clip = w._final_q.get_nowait()
    assert uid == 2
    assert noise_clip is clip


def test_abandoned_final_discards_pending_clip():
    # Over-cap utterance abandons the final pass; its stored clip must not
    # leak into _pending_noise for a later utterance.
    w, _ = make_worker(final_max_s=0.5)
    clip = _clip()
    q = queue.Queue()
    q.put((1, _audio(0.4), False, clip))
    q.put((1, _audio(0.4), True, clip))
    q.put(None)
    w._transcription_loop(q, StubTranscriber(["a", "b"]), SOS)
    assert w._final_q.empty()
    assert w._pending_noise == {}
