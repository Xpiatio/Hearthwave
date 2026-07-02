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


def test_gain_mode_off_skips_gain(sos, monkeypatch):
    agc_calls, rms_calls = [], []
    import backend.stt.preprocess as mod
    monkeypatch.setattr(mod, "dynamic_agc", lambda *a, **k: agc_calls.append(a) or a[0])
    monkeypatch.setattr(mod, "normalize_rms", lambda *a, **k: rms_calls.append(a) or a[0])
    preprocess_segment(_tone_with_noise(), SAMPLE_RATE, sos, gain_mode="off")
    assert agc_calls == [] and rms_calls == []


def test_gain_mode_agc_uses_dynamic_agc(sos, monkeypatch):
    agc_calls, rms_calls = [], []
    import backend.stt.preprocess as mod
    monkeypatch.setattr(mod, "dynamic_agc", lambda *a, **k: agc_calls.append(a) or a[0])
    monkeypatch.setattr(mod, "normalize_rms", lambda *a, **k: rms_calls.append(a) or a[0])
    preprocess_segment(_tone_with_noise(), SAMPLE_RATE, sos, gain_mode="agc")
    assert len(agc_calls) == 1 and rms_calls == []


def test_gain_mode_rms_uses_normalize_rms(sos, monkeypatch):
    agc_calls, rms_calls = [], []
    import backend.stt.preprocess as mod
    monkeypatch.setattr(mod, "dynamic_agc", lambda *a, **k: agc_calls.append(a) or a[0])
    monkeypatch.setattr(mod, "normalize_rms", lambda *a, **k: rms_calls.append(a) or a[0])
    preprocess_segment(_tone_with_noise(), SAMPLE_RATE, sos, gain_mode="rms")
    assert len(rms_calls) == 1 and agc_calls == []


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
    out_low = preprocess_segment(low, SAMPLE_RATE, sos, denoise_enabled=False, gain_mode="off")
    out_mid = preprocess_segment(mid, SAMPLE_RATE, sos, denoise_enabled=False, gain_mode="off")
    assert np.sqrt(np.mean(out_low**2)) < 0.05 * np.sqrt(np.mean(out_mid**2))


def test_all_stages_disabled_still_bandpasses(sos):
    audio = _tone_with_noise()
    out = preprocess_segment(audio, SAMPLE_RATE, sos, denoise_enabled=False, gain_mode="off")
    assert out.dtype == np.float32
    assert not np.array_equal(out, audio)


def test_noise_clip_bandpassed_and_forwarded_to_denoise(sos, monkeypatch):
    # The clip must arrive at denoise as y_noise AFTER passing through the
    # same bandpass as the segment, so both share the spectral domain.
    from backend.audio.dsp import bandpass
    seen = {}
    import backend.stt.preprocess as mod
    monkeypatch.setattr(
        mod, "denoise",
        lambda audio, sr, **kw: seen.update(kw) or audio,
    )
    clip = _tone_with_noise(seconds=0.6, seed=7)
    preprocess_segment(_tone_with_noise(), SAMPLE_RATE, sos, noise_clip=clip)
    assert "y_noise" in seen
    np.testing.assert_allclose(seen["y_noise"], bandpass(clip, sos), atol=1e-6)


def test_no_noise_clip_omits_y_noise_kwarg(sos, monkeypatch):
    seen = {}
    import backend.stt.preprocess as mod
    monkeypatch.setattr(
        mod, "denoise",
        lambda audio, sr, **kw: seen.update(kw) or audio,
    )
    preprocess_segment(_tone_with_noise(), SAMPLE_RATE, sos)
    assert "y_noise" not in seen


def test_empty_noise_clip_omits_y_noise_kwarg(sos, monkeypatch):
    seen = {}
    import backend.stt.preprocess as mod
    monkeypatch.setattr(
        mod, "denoise",
        lambda audio, sr, **kw: seen.update(kw) or audio,
    )
    preprocess_segment(
        _tone_with_noise(), SAMPLE_RATE, sos, noise_clip=np.zeros(0, dtype=np.float32)
    )
    assert "y_noise" not in seen
