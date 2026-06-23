"""Per-segment DSP chain applied between segmentation and transcription.

Extracted from STTWorker._transcription_loop so the offline eval CLI can run
the exact production chain with individual stages toggled for A/B comparison.
"""
import numpy as np

from backend.audio.dsp import bandpass, denoise, dynamic_agc, normalize_rms


def preprocess_segment(
    audio: np.ndarray,
    sample_rate: int,
    bandpass_sos,
    *,
    denoise_enabled: bool = True,
    prop_decrease: float = 0.7,
    gain_mode: str = "agc",
) -> np.ndarray:
    """Bandpass → spectral-gating denoise → gain stage, each stage optional.

    The bandpass always runs: Whisper sees narrowband-FM voice (300–3000 Hz)
    and everything outside that band is noise by definition. The gain stage is
    selected by ``gain_mode``: "agc" (dynamic attack/release), "rms" (one-shot
    RMS normalize), or "off" (no gain).
    """
    out = bandpass(audio, bandpass_sos)
    if denoise_enabled:
        out = denoise(out, sample_rate, prop_decrease=prop_decrease)
    if gain_mode == "agc":
        out = dynamic_agc(out, sample_rate)
    elif gain_mode == "rms":
        out = normalize_rms(out)
    return out
