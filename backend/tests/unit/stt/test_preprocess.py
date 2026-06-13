"""Tests for backend.stt.preprocess — the per-segment DSP chain."""
import numpy as np
import pytest

from backend.audio.dsp import make_bandpass_sos
from backend.stt.preprocess import preprocess_segment

SAMPLE_RATE = 16000


@pytest.fixture(scope="module")
def sos():
    return make_bandpass_sos(SAMPLE_RATE)


def _tone_with_noise(seconds=1.0, freq=1000.0, noise=0.05, seed=42):
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    sig = 0.3 * np.sin(2 * np.pi * freq * t) + noise * rng.standard_normal(t.size)
    return sig.astype(np.float32)


def test_full_chain_returns_float32_same_length(sos):
    audio = _tone_with_noise()
    out = preprocess_segment(audio, SAMPLE_RATE, sos)
    assert out.dtype == np.float32
    assert out.shape == audio.shape


def test_denoise_disabled_skips_denoise(sos, monkeypatch):
    calls = []
    import backend.stt.preprocess as mod
    monkeypatch.setattr(mod, "denoise", lambda *a, **k: calls.append(k) or a[0])
    audio = _tone_with_noise()
    preprocess_segment(audio, SAMPLE_RATE, sos, denoise_enabled=False)
    assert calls == []


def test_agc_disabled_skips_agc(sos, monkeypatch):
    calls = []
    import backend.stt.preprocess as mod
    monkeypatch.setattr(mod, "dynamic_agc", lambda *a, **k: calls.append(a) or a[0])
    audio = _tone_with_noise()
    preprocess_segment(audio, SAMPLE_RATE, sos, agc_enabled=False)
    assert calls == []


def test_prop_decrease_forwarded_to_denoise(sos, monkeypatch):
    seen = {}
    import backend.stt.preprocess as mod
    monkeypatch.setattr(
        mod, "denoise",
        lambda audio, sr, prop_decrease: seen.update(prop_decrease=prop_decrease) or audio,
    )
    audio = _tone_with_noise()
    preprocess_segment(audio, SAMPLE_RATE, sos, prop_decrease=0.4)
    assert seen["prop_decrease"] == 0.4


def test_bandpass_attenuates_out_of_band_tone(sos):
    # A 100 Hz tone is far below the 300 Hz band edge: even with denoise and
    # AGC active the in-band energy must collapse relative to a 1 kHz tone.
    low = _tone_with_noise(freq=100.0, noise=0.0)
    mid = _tone_with_noise(freq=1000.0, noise=0.0)
    out_low = preprocess_segment(low, SAMPLE_RATE, sos, denoise_enabled=False, agc_enabled=False)
    out_mid = preprocess_segment(mid, SAMPLE_RATE, sos, denoise_enabled=False, agc_enabled=False)
    assert np.sqrt(np.mean(out_low**2)) < 0.05 * np.sqrt(np.mean(out_mid**2))


def test_all_stages_disabled_still_bandpasses(sos):
    audio = _tone_with_noise()
    out = preprocess_segment(audio, SAMPLE_RATE, sos, denoise_enabled=False, agc_enabled=False)
    assert out.dtype == np.float32
    assert not np.array_equal(out, audio)
