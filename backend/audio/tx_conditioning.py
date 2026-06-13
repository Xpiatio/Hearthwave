"""Speech conditioning applied to synthesized TTS audio before it drives the
radio's mic input.

Narrowband FM carries roughly 300–3000 Hz and the transmitter clips or
splatters on hot peaks, while quiet passages sink under the receive-side
noise floor. The chain here — band-limit, gentle compression, voiced-level
normalization, peak ceiling — keeps the synthesized voice inside the channel
and at a consistent modulation level, which is most of what "sounding clear
over the radio" means.

Pre-emphasis is available but defaults off: FM transmitters already apply
pre-emphasis in hardware, and doubling it makes speech harsh.
"""
import numpy as np

from backend.audio.dsp import make_bandpass_sos


def preemphasis(audio: np.ndarray, coef: float) -> np.ndarray:
    """First-order high-frequency boost: y[n] = x[n] - coef * x[n-1]."""
    if coef == 0.0:
        return audio
    out = np.empty_like(audio)
    out[0] = audio[0]
    out[1:] = audio[1:] - coef * audio[:-1]
    return out


def compress(
    audio: np.ndarray,
    sample_rate: int,
    threshold_dbfs: float = -18.0,
    ratio: float = 3.0,
    release_ms: float = 80.0,
    frame_ms: float = 10.0,
) -> np.ndarray:
    """Frame-RMS downward compressor: instant attack, smoothed release.

    Frames above the threshold are reduced toward it at `ratio`:1. Gain
    reductions apply within the frame they're detected (a smoothed attack
    would let syllable onsets overshoot, raising the crest factor this
    chain exists to lower); recovery follows a slow release so inter-word
    gaps don't pump.
    """
    frame_n = max(1, int(frame_ms / 1000.0 * sample_rate))
    release_coef = float(np.exp(-frame_n / (release_ms / 1000.0 * sample_rate)))

    out = audio.astype(np.float32).copy()
    gain = 1.0
    for start in range(0, len(out), frame_n):
        frame = out[start:start + frame_n]
        rms = float(np.sqrt(np.mean(frame ** 2)))
        if rms > 1e-9:
            level_db = 20.0 * np.log10(rms)
            if level_db > threshold_dbfs:
                desired = 10.0 ** (-(level_db - threshold_dbfs) * (1.0 - 1.0 / ratio) / 20.0)
            else:
                desired = 1.0
            if desired < gain:
                gain = desired
            else:
                gain = gain * release_coef + desired * (1.0 - release_coef)
        frame *= gain
    return out


def condition_tx_audio(
    audio_int16: np.ndarray,
    sample_rate: int,
    *,
    low_hz: float = 300.0,
    high_hz: float = 3000.0,
    preemph_coef: float = 0.0,
    target_rms_dbfs: "float | None" = -18.0,
    peak_ceiling_dbfs: float = -1.0,
) -> np.ndarray:
    """Band-limit → compress → voiced-RMS normalize → peak ceiling.

    Takes and returns int16 PCM. The RMS target is computed over voiced
    frames only (>-50 dBFS) so pauses and lead/tail padding don't skew the
    gain. target_rms_dbfs=None skips normalization (useful for measurement).
    """
    from scipy.signal import sosfiltfilt

    if audio_int16.size == 0:
        return audio_int16

    audio = audio_int16.astype(np.float32) / 32767.0

    sos = make_bandpass_sos(sample_rate, low_hz, high_hz)
    audio = sosfiltfilt(sos, audio).astype(np.float32)

    if preemph_coef:
        audio = preemphasis(audio, preemph_coef)

    audio = compress(audio, sample_rate)

    if target_rms_dbfs is not None:
        frame_n = max(1, int(0.02 * sample_rate))
        voiced = []
        for start in range(0, len(audio), frame_n):
            frame = audio[start:start + frame_n]
            rms = float(np.sqrt(np.mean(frame ** 2)))
            if rms > 10.0 ** (-50.0 / 20.0):
                voiced.append(frame)
        if voiced:
            voiced_rms = float(np.sqrt(np.mean(np.concatenate(voiced) ** 2)))
            audio = audio * (10.0 ** (target_rms_dbfs / 20.0) / voiced_rms)

    ceiling = 10.0 ** (peak_ceiling_dbfs / 20.0)
    peak = float(np.max(np.abs(audio)))
    if peak > ceiling:
        audio = audio * (ceiling / peak)

    return (np.clip(audio, -1.0, 1.0) * 32767.0).astype(np.int16)
