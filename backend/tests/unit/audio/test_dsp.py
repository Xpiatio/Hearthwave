"""Tests for backend.audio.dsp — DSP helper functions."""
import numpy as np
import scipy.signal  # noqa: F401 — must be imported before cw/test_decoder.py injects its fake

from backend.audio.dsp import make_lowpass_sos, lowpass, dynamic_agc


SAMPLE_RATE = 16000


class TestMakeLowpassSos:
    def test_returns_sos_array(self):
        sos = make_lowpass_sos(SAMPLE_RATE)
        assert isinstance(sos, np.ndarray)
        assert sos.ndim == 2
        assert sos.shape[1] == 6  # standard SOS shape: (sections, 6)

    def test_custom_cutoff_and_order(self):
        sos = make_lowpass_sos(SAMPLE_RATE, cutoff_hz=1000, order=2)
        assert sos.shape[0] == 1  # order=2 → 1 section


class TestMakeLowpassSosFallback:
    def test_raises_on_impossible_cutoff(self):
        """make_lowpass_sos raises when cutoff exceeds Nyquist.

        This confirms the exception path in STTWorker._run() is reachable —
        the try/except that sets lowpass_sos=None depends on this raising.
        """
        import pytest
        with pytest.raises(Exception):
            make_lowpass_sos(16000, cutoff_hz=99999)  # Wn = cutoff/nyquist > 1.0


class TestLowpass:
    def test_attenuates_high_frequency(self):
        """Sine well above 2700 Hz cutoff must be attenuated by > 20 dB."""
        duration = 0.5
        t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
        # 7 kHz is well above the 2700 Hz default cutoff
        signal = np.sin(2 * np.pi * 7000 * t).astype(np.float32)
        sos = make_lowpass_sos(SAMPLE_RATE, cutoff_hz=2700)
        filtered = lowpass(signal, sos)
        rms_in = float(np.sqrt(np.mean(signal ** 2)))
        rms_out = float(np.sqrt(np.mean(filtered ** 2)))
        db_atten = 20 * np.log10(rms_out / rms_in)
        assert db_atten < -20.0, f"Expected > 20 dB attenuation, got {db_atten:.1f} dB"

    def test_passes_low_frequency(self):
        """1 kHz sine (below 2700 Hz cutoff) must pass with < 3 dB loss."""
        duration = 0.5
        t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
        signal = np.sin(2 * np.pi * 1000 * t).astype(np.float32)
        sos = make_lowpass_sos(SAMPLE_RATE, cutoff_hz=2700)
        filtered = lowpass(signal, sos)
        rms_in = float(np.sqrt(np.mean(signal ** 2)))
        rms_out = float(np.sqrt(np.mean(filtered[100:] ** 2)))  # skip transient
        db_loss = 20 * np.log10(rms_out / rms_in)
        assert db_loss > -3.0, f"Expected < 3 dB loss, got {db_loss:.1f} dB"

    def test_output_is_float32(self):
        signal = np.zeros(256, dtype=np.float32)
        sos = make_lowpass_sos(SAMPLE_RATE)
        out = lowpass(signal, sos)
        assert out.dtype == np.float32

    def test_output_length_matches_input(self):
        signal = np.random.randn(1024).astype(np.float32)
        sos = make_lowpass_sos(SAMPLE_RATE)
        out = lowpass(signal, sos)
        assert len(out) == len(signal)


class TestDynamicAgc:
    def test_normalizes_quiet_signal(self):
        """A quiet signal should be brought up closer to target dBFS."""
        # -40 dBFS signal → should approach -20 dBFS target
        amplitude = 10 ** (-40 / 20)
        signal = (np.sin(2 * np.pi * 440 * np.arange(SAMPLE_RATE) / SAMPLE_RATE) * amplitude).astype(np.float32)
        out = dynamic_agc(signal, SAMPLE_RATE, target_dbfs=-20.0)
        rms_out = float(np.sqrt(np.mean(out ** 2)))
        dbfs_out = 20 * np.log10(rms_out)
        # Should be within 10 dB of target (AGC converges gradually)
        assert dbfs_out > -25.0, f"Expected AGC to boost quiet signal, got {dbfs_out:.1f} dBFS"

    def test_skips_near_silence(self):
        """Near-zero input must not be amplified to noise."""
        signal = np.zeros(SAMPLE_RATE, dtype=np.float32)
        out = dynamic_agc(signal, SAMPLE_RATE)
        assert float(np.max(np.abs(out))) < 1e-5

    def test_clips_to_unit_range(self):
        """Output must be clipped to [-1, 1]."""
        signal = np.ones(SAMPLE_RATE, dtype=np.float32) * 0.8
        out = dynamic_agc(signal, SAMPLE_RATE, target_dbfs=-3.0)
        assert float(np.max(np.abs(out))) <= 1.0

    def test_output_length_matches_input(self):
        signal = np.random.randn(SAMPLE_RATE).astype(np.float32)
        out = dynamic_agc(signal, SAMPLE_RATE)
        assert len(out) == len(signal)

    def test_pure_function_no_mutation(self):
        """dynamic_agc must not mutate the input array."""
        signal = np.random.randn(SAMPLE_RATE).astype(np.float32)
        original = signal.copy()
        dynamic_agc(signal, SAMPLE_RATE)
        np.testing.assert_array_equal(signal, original)
