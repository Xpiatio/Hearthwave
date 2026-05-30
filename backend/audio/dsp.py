import numpy as np


def make_bandpass_sos(sample_rate, low_hz=300, high_hz=3000, order=4):
    """Design a Butterworth bandpass for narrowband-FM voice (300–3000 Hz).

    Returned in second-order-sections form so it survives `sosfiltfilt`
    forward/backward filtering without numerical blowup at higher orders.
    """
    from scipy.signal import butter

    nyquist = sample_rate / 2
    return butter(
        order,
        [low_hz / nyquist, high_hz / nyquist],
        btype="band",
        output="sos",
    )


def bandpass(audio, sos):
    """Apply a precomputed SOS bandpass to a float32 audio buffer."""
    from scipy.signal import sosfiltfilt

    return sosfiltfilt(sos, audio).astype(np.float32)


def denoise(audio, sample_rate, prop_decrease=0.7):
    """Spectral-gating noise reduction via `noisereduce`. Run AFTER the bandpass."""
    import noisereduce as nr

    return nr.reduce_noise(
        y=audio, sr=sample_rate, prop_decrease=prop_decrease
    ).astype(np.float32)


def normalize_rms(audio: np.ndarray, target_dbfs: float = -20.0) -> np.ndarray:
    """Normalize audio to a target RMS level in dBFS, in-place.

    Skips near-silent buffers to avoid amplifying pure noise. Clips to
    [-1, 1] as a guard against transient peaks after gain application.
    Returns the same array (modified in place).
    """
    rms = float(np.sqrt(np.mean(audio ** 2)))
    if rms < 1e-6:
        return audio
    gain = (10.0 ** (target_dbfs / 20.0)) / rms
    audio *= gain
    np.clip(audio, -1.0, 1.0, out=audio)
    return audio
