"""Tests for backend.stt.debug_capture — per-utterance capture for offline eval."""
import json
import wave

import numpy as np
import pytest

from backend.stt.debug_capture import UtteranceDebugRecorder

SR = 16000
CHUNK = 512


def _chunk(value=0.1):
    return np.full(CHUNK, value, dtype=np.float32)


def _read_wav(path):
    with wave.open(str(path), "rb") as w:
        assert w.getframerate() == SR
        assert w.getnchannels() == 1
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return data.astype(np.float32) / 32767.0


def _make(tmp_path, **kw):
    kw.setdefault("sample_rate", SR)
    kw.setdefault("pre_roll_chunks", 3)
    kw.setdefault("meta", {"model": "small.en"})
    return UtteranceDebugRecorder(tmp_path, **kw)


def _run_utterance(rec, uid=1, n_active=5, text="hello world"):
    """Drive a complete utterance through the recorder."""
    for i in range(6):
        rec.feed_raw(_chunk(0.01 * (i + 1)))  # idle chunks fill the pre-roll ring
    rec.on_capture_event("vad_start")
    for _ in range(n_active):
        rec.feed_raw(_chunk(0.5))
    rec.on_segment(uid, np.concatenate([_chunk(0.5)] * n_active), is_final=False)
    rec.feed_raw(_chunk(0.5))
    rec.on_capture_event("vad_end")
    rec.on_segment(uid, _chunk(0.5), is_final=True)
    rec.on_processed(uid, _chunk(0.4))
    rec.on_transcript(uid, text, partial=True)
    rec.on_transcript(uid, text + " final", partial=False)
    return rec.finalize(uid)


def test_finalize_writes_utterance_dir_with_all_files(tmp_path):
    rec = _make(tmp_path)
    out = _run_utterance(rec)
    assert out is not None and out.is_dir()
    for name in ("raw.wav", "segmented.wav", "processed.wav", "transcript.json"):
        assert (out / name).exists(), name


def test_raw_wav_includes_pre_roll_and_active_audio(tmp_path):
    rec = _make(tmp_path, pre_roll_chunks=3)
    out = _run_utterance(rec, n_active=5)
    raw = _read_wav(out / "raw.wav")
    # 3 pre-roll chunks + 5 active + 1 trailing chunk before vad_end
    assert raw.size == (3 + 5 + 1) * CHUNK
    # the first pre-roll chunk is the 4th idle chunk (value 0.04)
    assert raw[:CHUNK] == pytest.approx(np.full(CHUNK, 0.04), abs=1e-3)


def test_transcript_json_contents(tmp_path):
    rec = _make(tmp_path, meta={"model": "small.en", "vad_threshold": 0.5})
    out = _run_utterance(rec, uid=7, text="radio check")
    data = json.loads((out / "transcript.json").read_text())
    assert data["utterance_id"] == 7
    assert data["sample_rate"] == SR
    assert data["meta"]["model"] == "small.en"
    assert data["truncated"] is False
    texts = [(t["text"], t["partial"]) for t in data["transcripts"]]
    assert texts == [("radio check", True), ("radio check final", False)]


def test_two_utterances_are_isolated(tmp_path):
    rec = _make(tmp_path)
    out1 = _run_utterance(rec, uid=1, text="first")
    out2 = _run_utterance(rec, uid=2, text="second")
    assert out1 != out2
    d1 = json.loads((out1 / "transcript.json").read_text())
    d2 = json.loads((out2 / "transcript.json").read_text())
    assert d1["utterance_id"] == 1
    assert d2["utterance_id"] == 2
    assert d2["transcripts"][0]["text"] == "second"


def test_raw_accumulation_capped_and_flagged_truncated(tmp_path):
    # max_seconds chosen so the cap is 4 chunks
    max_s = 4 * CHUNK / SR
    rec = _make(tmp_path, pre_roll_chunks=0, max_seconds=max_s)
    rec.on_capture_event("vad_start")
    for _ in range(10):
        rec.feed_raw(_chunk(0.5))
    rec.on_capture_event("vad_end")
    rec.on_segment(1, _chunk(0.5), is_final=True)
    out = rec.finalize(1)
    raw = _read_wav(out / "raw.wav")
    assert raw.size == 4 * CHUNK
    data = json.loads((out / "transcript.json").read_text())
    assert data["truncated"] is True


def test_finalize_unknown_uid_returns_none(tmp_path):
    rec = _make(tmp_path)
    assert rec.finalize(99) is None
    assert list(tmp_path.iterdir()) == []


def test_vad_start_without_segments_discarded_on_next_utterance(tmp_path):
    rec = _make(tmp_path, pre_roll_chunks=0)
    # kerchunk: vad_start then vad_end with no segments ever bound
    rec.on_capture_event("vad_start")
    rec.feed_raw(_chunk(0.9))
    rec.on_capture_event("vad_end")
    # real utterance afterwards must not contain the kerchunk audio
    rec.on_capture_event("vad_start")
    rec.feed_raw(_chunk(0.5))
    rec.on_capture_event("vad_end")
    rec.on_segment(2, _chunk(0.5), is_final=True)
    out = rec.finalize(2)
    raw = _read_wav(out / "raw.wav")
    assert raw.size == CHUNK
    assert raw == pytest.approx(np.full(CHUNK, 0.5), abs=1e-3)


def test_segmented_wav_concatenates_segments(tmp_path):
    rec = _make(tmp_path)
    out = _run_utterance(rec, n_active=5)
    seg = _read_wav(out / "segmented.wav")
    assert seg.size == 6 * CHUNK  # 5-chunk partial + 1-chunk final
