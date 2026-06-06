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


def make_lowpass_sos(sample_rate: int, cutoff_hz: float = 2700, order: int = 4):
    """Butterworth low-pass filter coefficients for per-chunk stream filtering.

    Uses causal sosfilt (not sosfiltfilt) to avoid look-ahead latency.
    """
    from scipy.signal import butter

    nyquist = sample_rate / 2
    return butter(order, cutoff_hz / nyquist, btype="low", output="sos")


def lowpass(audio: np.ndarray, sos) -> np.ndarray:
    """Apply causal low-pass filter to a chunk. No look-ahead latency."""
    from scipy.signal import sosfilt

    return sosfilt(sos, audio).astype(np.float32)


def dynamic_agc(
    audio: np.ndarray,
    sample_rate: int,
    target_dbfs: float = -20.0,
    attack_ms: float = 10.0,
    release_ms: float = 100.0,
    chunk_ms: float = 20.0,
) -> np.ndarray:
    """Per-chunk attack/release AGC applied to a full segment buffer.

    Walks the segment in chunk_ms frames, tracks a smoothed gain envelope
    (fast attack, slow release), applies it sample-by-sample, clips to [-1, 1].
    Skips near-silent frames to avoid amplifying pure noise.
    """
    chunk_n = int(chunk_ms / 1000.0 * sample_rate)
    attack_coef = np.exp(-chunk_n / (attack_ms / 1000.0 * sample_rate))
    release_coef = np.exp(-chunk_n / (release_ms / 1000.0 * sample_rate))
    target_amp = 10.0 ** (target_dbfs / 20.0)

    out = audio.copy()
    gain = 1.0
    for start in range(0, len(out), chunk_n):
        frame = out[start:start + chunk_n]  # view — *= modifies out in-place
        rms = float(np.sqrt(np.mean(frame ** 2)))
        if rms > 1e-6:
            desired = target_amp / rms
            coef = attack_coef if desired < gain else release_coef
            gain = gain * coef + desired * (1.0 - coef)
        frame *= gain
    np.clip(out, -1.0, 1.0, out=out)
    return out.astype(np.float32)
