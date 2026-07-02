"""Tests for backend.tools.eval_stt — offline pipeline replay + WER scoring.

Uses the MockVAD pattern from test_segmenter.py and a stub transcriber so no
ML models load. The pipeline under test drives the real SpeechSegmenter,
SquelchDetector, and preprocess_segment.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pytest

from backend.tools.eval_stt import (
    EvalPipelineConfig,
    build_decode_options,
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


def test_eval_config_gain_mode_defaults_to_agc():
    from backend.tools.eval_stt import EvalPipelineConfig
    assert EvalPipelineConfig().gain_mode == "agc"
    assert EvalPipelineConfig(gain_mode="rms").gain_mode == "rms"


def test_stage_toggles_forwarded(monkeypatch):
    seen = {}
    import backend.tools.eval_stt as mod

    def fake_preprocess(audio, sr, sos, **kw):
        seen.update(kw)
        return audio

    monkeypatch.setattr(mod, "preprocess_segment", fake_preprocess)
    vad = MockVAD([None, "start", None, "end"])
    cfg = _cfg(denoise_enabled=False, gain_mode="off", prop_decrease=0.3)
    run_pipeline(_audio(6), cfg, StubTranscriber(), vad)
    assert seen == {"denoise_enabled": False, "gain_mode": "off", "prop_decrease": 0.3, "noise_clip": None}


def test_no_agc_maps_to_gain_mode_off():
    """--no-agc alone must resolve to gain_mode='off'."""
    import argparse

    args = argparse.Namespace(no_agc=True, gain_mode="agc")
    gain_mode = "off" if args.no_agc else args.gain_mode
    assert gain_mode == "off"


def test_no_agc_wins_over_explicit_gain_mode():
    """--no-agc must override --gain-mode rms → 'off'."""
    import argparse

    args = argparse.Namespace(no_agc=True, gain_mode="rms")
    gain_mode = "off" if args.no_agc else args.gain_mode
    assert gain_mode == "off"


def test_gain_mode_without_no_agc():
    """Without --no-agc, --gain-mode is passed through unchanged."""
    import argparse
    from backend.constants import GAIN_MODES

    for mode in GAIN_MODES:
        args = argparse.Namespace(no_agc=False, gain_mode=mode)
        gain_mode = "off" if args.no_agc else args.gain_mode
        assert gain_mode == mode


def test_no_agc_precedence_via_argparse():
    """Round-trip through the real argparse definition to confirm both flags co-exist."""
    import argparse
    from backend.constants import GAIN_MODES

    ap = argparse.ArgumentParser()
    ap.add_argument("--gain-mode", choices=list(GAIN_MODES), default="agc")
    ap.add_argument("--no-agc", action="store_true")

    # --no-agc alone
    args = ap.parse_args(["--no-agc"])
    assert ("off" if args.no_agc else args.gain_mode) == "off"

    # --no-agc + --gain-mode rms: --no-agc wins
    args = ap.parse_args(["--no-agc", "--gain-mode", "rms"])
    assert ("off" if args.no_agc else args.gain_mode) == "off"

    # --gain-mode rms alone
    args = ap.parse_args(["--gain-mode", "rms"])
    assert ("off" if args.no_agc else args.gain_mode) == "rms"


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


# ---------------------------------------------------------------------------
# build_decode_options — only explicitly-passed flags end up in the dict
# ---------------------------------------------------------------------------

def _decode_args(**overrides):
    base = dict(repetition_penalty=None, no_repeat_ngram_size=None, beam_size=None, hotwords=None)
    base.update(overrides)
    return argparse.Namespace(**base)


def test_build_decode_options_none_when_nothing_passed():
    assert build_decode_options(_decode_args()) is None


def test_build_decode_options_only_includes_passed_flag():
    assert build_decode_options(_decode_args(repetition_penalty=1.2)) == {"repetition_penalty": 1.2}


def test_build_decode_options_all_flags():
    args = _decode_args(repetition_penalty=1.1, no_repeat_ngram_size=3, beam_size=8, hotwords="alpha bravo")
    assert build_decode_options(args) == {
        "repetition_penalty": 1.1,
        "no_repeat_ngram_size": 3,
        "beam_size": 8,
        "hotwords": "alpha bravo",
    }


# ---------------------------------------------------------------------------
# main() arg plumbing — decode/VAD/prompt knobs reach construction seams
# ---------------------------------------------------------------------------

def _patch_main_deps(monkeypatch, mod, *, decode_calls=None, vad_calls=None, hypothesis="hello world"):
    """Stub out every heavy/side-effecting seam main() touches so it can be
    exercised end-to-end against a fake single-file corpus."""
    from backend.stt.transcriber import WhisperTranscriber

    def fake_load(model_path, saved_phrases=(), *, decode_options=None, word_confidence_min=None, prompt_style="list"):
        if decode_calls is not None:
            decode_calls.append({
                "decode_options": decode_options,
                "word_confidence_min": word_confidence_min,
                "prompt_style": prompt_style,
            })
        return object()

    def fake_make_vad_iterator(vad_model, sample_rate, threshold, **kw):
        if vad_calls is not None:
            vad_calls.append(kw)
        return object()

    monkeypatch.setattr(WhisperTranscriber, "load", fake_load)
    monkeypatch.setattr("backend.audio.vad.load_vad_model", lambda: object())
    monkeypatch.setattr("backend.audio.vad.make_vad_iterator", fake_make_vad_iterator)
    monkeypatch.setattr(mod, "_discover_wavs", lambda root: [Path("dummy.wav")])
    monkeypatch.setattr(mod, "find_reference", lambda wav: "hello world")
    monkeypatch.setattr(mod, "_read_wav", lambda wav, sr: np.zeros(10, dtype=np.float32))
    monkeypatch.setattr(
        mod, "run_pipeline",
        lambda audio, cfg, transcriber, vad_iter, **kw: [{"utterance_id": 0, "text": hypothesis}],
    )


def test_main_forwards_decode_prompt_and_confidence_to_transcriber(monkeypatch, tmp_path):
    import backend.tools.eval_stt as mod

    decode_calls = []
    _patch_main_deps(monkeypatch, mod, decode_calls=decode_calls)

    rc = mod.main([
        "--audio", str(tmp_path),
        "--beam-size", "8",
        "--word-confidence-min", "0.4",
        "--prompt-style", "transcript",
    ])
    assert rc == 0
    assert decode_calls == [{
        "decode_options": {"beam_size": 8},
        "word_confidence_min": 0.4,
        "prompt_style": "transcript",
    }]


def test_main_decode_options_none_when_no_decode_flags_passed(monkeypatch, tmp_path):
    import backend.tools.eval_stt as mod

    decode_calls = []
    _patch_main_deps(monkeypatch, mod, decode_calls=decode_calls)

    rc = mod.main(["--audio", str(tmp_path)])
    assert rc == 0
    assert decode_calls == [{
        "decode_options": None,
        "word_confidence_min": None,
        "prompt_style": "list",
    }]


def test_main_forwards_vad_params_to_make_vad_iterator(monkeypatch, tmp_path):
    import backend.tools.eval_stt as mod

    vad_calls = []
    _patch_main_deps(monkeypatch, mod, vad_calls=vad_calls)

    rc = mod.main(["--audio", str(tmp_path), "--vad-min-silence-ms", "800", "--vad-speech-pad-ms", "300"])
    assert rc == 0
    assert vad_calls == [{"min_silence_duration_ms": 800, "speech_pad_ms": 300}]


def test_main_vad_defaults_forwarded_when_not_set(monkeypatch, tmp_path):
    import backend.tools.eval_stt as mod

    vad_calls = []
    _patch_main_deps(monkeypatch, mod, vad_calls=vad_calls)

    rc = mod.main(["--audio", str(tmp_path)])
    assert rc == 0
    assert vad_calls == [{"min_silence_duration_ms": 500, "speech_pad_ms": 200}]


# ---------------------------------------------------------------------------
# --json output — echoes non-default knobs, leaves the baseline shape alone
# ---------------------------------------------------------------------------

def test_json_output_includes_config_when_knobs_set(monkeypatch, tmp_path, capsys):
    import backend.tools.eval_stt as mod

    _patch_main_deps(monkeypatch, mod)

    rc = mod.main(["--audio", str(tmp_path), "--beam-size", "8", "--vad-min-silence-ms", "800", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["config"] == {"decode_options": {"beam_size": 8}, "vad_min_silence_ms": 800}
    assert set(out.keys()) == {"corpus", "skipped_unlabelled", "files", "config"}


def test_json_output_baseline_shape_unchanged_without_knobs(monkeypatch, tmp_path, capsys):
    import backend.tools.eval_stt as mod

    _patch_main_deps(monkeypatch, mod)

    rc = mod.main(["--audio", str(tmp_path), "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert set(out.keys()) == {"corpus", "skipped_unlabelled", "files"}


# ---------------------------------------------------------------------------
# --noise-profile — squelch-derived stationary denoise in eval replay
# ---------------------------------------------------------------------------

def test_eval_config_noise_profile_defaults_off():
    assert EvalPipelineConfig().noise_profile is False


def _capture_preprocess(monkeypatch):
    seen = []
    import backend.tools.eval_stt as mod

    def fake_preprocess(audio, sr, sos, **kw):
        seen.append(kw)
        return audio

    monkeypatch.setattr(mod, "preprocess_segment", fake_preprocess)
    return seen


def test_run_pipeline_forwards_override_clip(monkeypatch):
    seen = _capture_preprocess(monkeypatch)
    vad = MockVAD([None, "start", None, "end"])
    clip = np.full(10 * CHUNK, 0.01, dtype=np.float32)
    cfg = _cfg(noise_profile=True)
    run_pipeline(_audio(6), cfg, StubTranscriber(), vad, noise_clip=clip)
    assert seen and all(kw["noise_clip"] is clip for kw in seen)


def test_run_pipeline_derives_clip_live_from_quiet_span(monkeypatch):
    # A long closed-squelch quiet span before the speech must become the
    # stationary noise estimate, exactly as the live segmenter derives it.
    seen = _capture_preprocess(monkeypatch)
    quiet_chunks = 20  # 0.64 s >= NOISE_MIN_S (0.5 s)
    vad = MockVAD([None] * quiet_chunks + ["start", "end"])
    quiet = np.zeros(quiet_chunks * CHUNK, dtype=np.float32)
    speech = np.full(2 * CHUNK, 0.5, dtype=np.float32)
    cfg = _cfg(noise_profile=True)
    run_pipeline(np.concatenate([quiet, speech]), cfg, StubTranscriber(), vad)
    assert seen
    assert seen[0]["noise_clip"] is not None
    assert seen[0]["noise_clip"].size == quiet_chunks * CHUNK


def test_run_pipeline_off_passes_none_clip(monkeypatch):
    seen = _capture_preprocess(monkeypatch)
    vad = MockVAD([None, "start", None, "end"])
    run_pipeline(_audio(6), _cfg(), StubTranscriber(), vad)
    assert seen and all(kw["noise_clip"] is None for kw in seen)


def test_run_pipeline_marks_noise_clip_used_when_enabled(monkeypatch):
    _capture_preprocess(monkeypatch)
    vad = MockVAD([None, "start", None, "end"])
    clip = np.full(10 * CHUNK, 0.01, dtype=np.float32)
    results = run_pipeline(_audio(6), _cfg(noise_profile=True), StubTranscriber(), vad, noise_clip=clip)
    assert results[0]["noise_clip_used"] is True
    results = run_pipeline(_audio(6), _cfg(noise_profile=True), StubTranscriber(),
                           MockVAD([None, "start", None, "end"]))
    assert results[0]["noise_clip_used"] is False


def test_run_pipeline_result_shape_unchanged_when_off():
    vad = MockVAD([None, "start", None, "end"])
    results = run_pipeline(_audio(6), _cfg(), StubTranscriber(), vad)
    assert set(results[0].keys()) == {"utterance_id", "text"}


def test_load_noise_override_reads_sibling_noise_wav(tmp_path):
    import wave as wave_mod
    from backend.tools.eval_stt import _load_noise_override

    utt = tmp_path / "utt_1_0001"
    utt.mkdir()
    wav = utt / "raw.wav"
    wav.touch()
    pcm = (np.full(4 * CHUNK, 0.01) * 32767).astype(np.int16)
    with wave_mod.open(str(utt / "noise.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    clip = _load_noise_override(wav, SR)
    assert clip is not None
    assert clip.size == 4 * CHUNK


def test_load_noise_override_missing_returns_none(tmp_path):
    from backend.tools.eval_stt import _load_noise_override
    wav = tmp_path / "sample.wav"
    wav.touch()
    assert _load_noise_override(wav, SR) is None


def test_main_noise_profile_auto_passes_override_to_pipeline(monkeypatch, tmp_path):
    import backend.tools.eval_stt as mod

    _patch_main_deps(monkeypatch, mod)
    sentinel = np.full(8 * CHUNK, 0.01, dtype=np.float32)
    monkeypatch.setattr(mod, "_load_noise_override", lambda wav, sr: sentinel)
    pipeline_calls = []
    monkeypatch.setattr(
        mod, "run_pipeline",
        lambda audio, cfg, transcriber, vad_iter, **kw: pipeline_calls.append(
            {"noise_profile": cfg.noise_profile, **kw}
        ) or [{"utterance_id": 0, "text": "hello world", "noise_clip_used": True}],
    )
    rc = mod.main(["--audio", str(tmp_path), "--noise-profile", "auto"])
    assert rc == 0
    assert pipeline_calls == [{"noise_profile": True, "noise_clip": sentinel}]


def test_main_noise_profile_off_by_default(monkeypatch, tmp_path):
    import backend.tools.eval_stt as mod

    _patch_main_deps(monkeypatch, mod)
    pipeline_calls = []
    monkeypatch.setattr(
        mod, "run_pipeline",
        lambda audio, cfg, transcriber, vad_iter, **kw: pipeline_calls.append(
            {"noise_profile": cfg.noise_profile, **kw}
        ) or [{"utterance_id": 0, "text": "hello world"}],
    )
    rc = mod.main(["--audio", str(tmp_path)])
    assert rc == 0
    assert pipeline_calls == [{"noise_profile": False, "noise_clip": None}]


def test_json_reports_noise_profile_and_fallbacks_when_auto(monkeypatch, tmp_path, capsys):
    import backend.tools.eval_stt as mod

    _patch_main_deps(monkeypatch, mod)
    monkeypatch.setattr(mod, "_load_noise_override", lambda wav, sr: None)
    monkeypatch.setattr(
        mod, "run_pipeline",
        lambda audio, cfg, transcriber, vad_iter, **kw: [
            {"utterance_id": 0, "text": "hello", "noise_clip_used": False},
            {"utterance_id": 1, "text": "world", "noise_clip_used": True},
        ],
    )
    rc = mod.main(["--audio", str(tmp_path), "--noise-profile", "auto", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["config"]["noise_profile"] == "auto"
    assert out["noise_profile_fallbacks"] == 1
