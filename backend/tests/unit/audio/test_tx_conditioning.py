"""Tests for backend.audio.tx_conditioning — the pre-PTT speech chain."""
import numpy as np
import pytest

from backend.audio.tx_conditioning import compress, condition_tx_audio, preemphasis

SR = 22050  # Piper's common native rate


def _tone(freq=1000.0, seconds=1.0, amp=0.5, sr=SR):
    t = np.arange(int(seconds * sr)) / sr
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _speechlike(sr=SR):
    """Loud and quiet passages with a silent gap, int16 — crest-rich."""
    loud = _tone(800, 0.4, amp=0.8, sr=sr)
    quiet = _tone(600, 0.4, amp=0.05, sr=sr)
    gap = np.zeros(int(0.2 * sr), dtype=np.float32)
    f = np.concatenate([loud, gap, quiet])
    return (f * 32767).astype(np.int16)


def _rms_dbfs(x):
    f = x.astype(np.float32) / 32767.0 if x.dtype == np.int16 else x
    rms = float(np.sqrt(np.mean(f**2)))
    return 20 * np.log10(max(rms, 1e-12))


class TestConditionTxAudio:
    def test_returns_int16_same_length(self):
        audio = _speechlike()
        out = condition_tx_audio(audio, SR)
        assert out.dtype == np.int16
        assert out.shape == audio.shape

    def test_silence_in_silence_out(self):
        out = condition_tx_audio(np.zeros(SR, dtype=np.int16), SR)
        assert np.all(out == 0)

    def test_voiced_rms_lands_near_target(self):
        out = condition_tx_audio(_speechlike(), SR, target_rms_dbfs=-18.0)
        f = out.astype(np.float32) / 32767.0
        frame = int(0.02 * SR)
        voiced = [
            f[i:i + frame] for i in range(0, len(f) - frame, frame)
            if _rms_dbfs(f[i:i + frame]) > -50.0
        ]
        overall = _rms_dbfs(np.concatenate(voiced))
        assert overall == pytest.approx(-18.0, abs=2.0)

    def test_peak_ceiling_respected(self):
        out = condition_tx_audio(_speechlike(), SR, peak_ceiling_dbfs=-1.0)
        peak = np.max(np.abs(out.astype(np.float32) / 32767.0))
        assert peak <= 10 ** (-1.0 / 20.0) + 1e-3

    def test_dynamic_range_between_loud_and_quiet_passages_reduced(self):
        # The point of the compressor: quiet words must not sink under the
        # receive-side noise floor while loud ones splatter. Compare the
        # loud/quiet passage RMS ratio before and after.
        audio = _speechlike()
        n_loud = int(0.4 * SR)
        n_gap = int(0.2 * SR)

        def passage_ratio(x):
            f = x.astype(np.float32) / 32767.0
            loud = np.sqrt(np.mean(f[:n_loud] ** 2))
            quiet = np.sqrt(np.mean(f[n_loud + n_gap:] ** 2))
            return loud / quiet

        out = condition_tx_audio(audio, SR)
        assert passage_ratio(out) < 0.6 * passage_ratio(audio)

    def test_out_of_band_tone_attenuated(self):
        # 100 Hz is far below the 300 Hz floor → ≥30 dB down vs an in-band tone
        low = (_tone(100, amp=0.5) * 32767).astype(np.int16)
        mid = (_tone(1000, amp=0.5) * 32767).astype(np.int16)
        # disable level normalization so the filter's effect is observable
        out_low = condition_tx_audio(low, SR, target_rms_dbfs=None)
        out_mid = condition_tx_audio(mid, SR, target_rms_dbfs=None)
        assert _rms_dbfs(out_low) < _rms_dbfs(out_mid) - 30.0


class TestPreemphasis:
    def test_zero_coef_is_identity(self):
        x = _tone()
        assert np.array_equal(preemphasis(x, 0.0), x)

    def test_boosts_highs_relative_to_lows(self):
        hi, lo = _tone(3000), _tone(300)
        gain_hi = _rms_dbfs(preemphasis(hi, 0.9)) - _rms_dbfs(hi)
        gain_lo = _rms_dbfs(preemphasis(lo, 0.9)) - _rms_dbfs(lo)
        assert gain_hi > gain_lo


class TestCompress:
    def test_reduces_level_difference_between_loud_and_quiet(self):
        loud, quiet = _tone(amp=0.8), _tone(amp=0.05)
        diff_before = _rms_dbfs(loud) - _rms_dbfs(quiet)
        out_loud = compress(loud, SR)
        out_quiet = compress(quiet, SR)
        diff_after = _rms_dbfs(out_loud) - _rms_dbfs(out_quiet)
        assert diff_after < diff_before

    def test_below_threshold_audio_roughly_unchanged(self):
        quiet = _tone(amp=0.01)  # ~-40 dBFS, well under the -18 threshold
        out = compress(quiet, SR)
        assert _rms_dbfs(out) == pytest.approx(_rms_dbfs(quiet), abs=1.0)
