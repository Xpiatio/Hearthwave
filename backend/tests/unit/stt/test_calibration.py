"""Tests for backend.stt.calibration — the STT calibration wizard's raw-audio
capture buffer and gain/noise/model sweep runner.

Sweep tests reuse the MockVAD/StubTranscriber doubles from
test_eval_pipeline.py so no ML models load; run_sweep drives the real
eval_stt.run_pipeline, so this only tests the sweep's own orchestration
(grouping by model, progress reporting, ranking).
"""
import numpy as np

from backend.stt.calibration import CalibrationCapture, PREAMBLE_TEXT, run_sweep

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
    def __init__(self, text):
        self.text = text
        self.calls = 0

    def transcribe(self, audio):
        self.calls += 1
        return self.text


def _audio(n_chunks, value=0.5):
    return np.full(n_chunks * CHUNK, value, dtype=np.float32)


# ---------------------------------------------------------------------------
# CalibrationCapture
# ---------------------------------------------------------------------------

def test_feed_raw_ignored_before_start():
    cap = CalibrationCapture(sample_rate=SR)
    cap.feed_raw(np.ones(CHUNK, dtype=np.float32))
    assert cap.stop().size == 0


def test_start_then_feed_accumulates_and_stop_returns_concatenated_audio():
    cap = CalibrationCapture(sample_rate=SR)
    cap.start()
    cap.feed_raw(np.full(CHUNK, 1.0, dtype=np.float32))
    cap.feed_raw(np.full(CHUNK, 2.0, dtype=np.float32))
    audio = cap.stop()
    assert audio.shape == (2 * CHUNK,)
    assert audio[0] == 1.0 and audio[-1] == 2.0


def test_stop_deactivates_capture():
    cap = CalibrationCapture(sample_rate=SR)
    cap.start()
    assert cap.is_active is True
    cap.stop()
    assert cap.is_active is False


def test_start_resets_previous_buffer():
    cap = CalibrationCapture(sample_rate=SR)
    cap.start()
    cap.feed_raw(np.ones(CHUNK, dtype=np.float32))
    cap.stop()
    cap.start()
    audio = cap.stop()
    assert audio.size == 0


def test_capture_auto_stops_at_max_duration():
    cap = CalibrationCapture(sample_rate=SR, max_duration_s=CHUNK / SR)  # exactly 1 chunk
    cap.start()
    cap.feed_raw(np.ones(CHUNK, dtype=np.float32))
    assert cap.is_active is False
    cap.feed_raw(np.ones(CHUNK, dtype=np.float32))  # dropped — already inactive
    assert cap.stop().size == CHUNK


# ---------------------------------------------------------------------------
# run_sweep
# ---------------------------------------------------------------------------

def _make_pipeline_deps(texts_by_model):
    """transcriber_loader/vad_iterator_factory doubles. Each model maps to a
    canned hypothesis text; a fresh MockVAD/StubTranscriber is handed out per
    call so state never bleeds between combos."""
    load_calls = []

    def transcriber_loader(model):
        load_calls.append(model)
        return StubTranscriber(texts_by_model[model])

    def vad_iterator_factory():
        # 15 in-speech chunks (~0.48s) clears STTWorker.MIN_SPEECH_DURATION_S
        # (0.4s), the real default run_sweep's EvalPipelineConfig uses.
        return MockVAD([None, "start"] + [None] * 14 + ["end"])

    return transcriber_loader, vad_iterator_factory, load_calls


def test_sweep_covers_every_model_gain_noise_combo():
    transcriber_loader, vad_factory, _ = _make_pipeline_deps(
        {"small.en": PREAMBLE_TEXT, "tiny.en": PREAMBLE_TEXT}
    )
    results = run_sweep(
        _audio(20), models=["small.en", "tiny.en"],
        transcriber_loader=transcriber_loader, vad_iterator_factory=vad_factory,
        gain_modes=("agc", "off"), noise_profiles=(False, True),
    )
    assert len(results) == 2 * 2 * 2
    combos = {(r["model"], r["gain_mode"], r["noise_profile"]) for r in results}
    assert combos == {
        (m, g, n) for m in ("small.en", "tiny.en") for g in ("agc", "off") for n in (False, True)
    }


def test_sweep_loads_transcriber_once_per_model_not_per_combo():
    transcriber_loader, vad_factory, load_calls = _make_pipeline_deps(
        {"small.en": "hello", "tiny.en": "hello"}
    )
    run_sweep(
        _audio(20), models=["small.en", "tiny.en"],
        transcriber_loader=transcriber_loader, vad_iterator_factory=vad_factory,
        gain_modes=("agc", "rms", "off"), noise_profiles=(False, True),
    )
    assert load_calls == ["small.en", "tiny.en"]


def test_sweep_scores_against_preamble_and_ranks_best_first():
    transcriber_loader, vad_factory, _ = _make_pipeline_deps(
        {"good_model": PREAMBLE_TEXT, "bad_model": "completely wrong text"}
    )
    results = run_sweep(
        _audio(20), models=["bad_model", "good_model"],
        transcriber_loader=transcriber_loader, vad_iterator_factory=vad_factory,
        gain_modes=("agc",), noise_profiles=(False,),
    )
    assert results[0]["model"] == "good_model"
    assert results[0]["wer"] == 0.0
    assert results[-1]["model"] == "bad_model"
    assert results[0]["wer"] < results[-1]["wer"]


def test_sweep_reports_progress_with_index_and_total():
    transcriber_loader, vad_factory, _ = _make_pipeline_deps({"small.en": "hello"})
    progress = []
    run_sweep(
        _audio(20), models=["small.en"],
        transcriber_loader=transcriber_loader, vad_iterator_factory=vad_factory,
        gain_modes=("agc", "off"), noise_profiles=(False,),
        progress_cb=progress.append,
    )
    assert [p["index"] for p in progress] == [1, 2]
    assert all(p["total"] == 2 for p in progress)
    assert progress[0]["model"] == "small.en"
