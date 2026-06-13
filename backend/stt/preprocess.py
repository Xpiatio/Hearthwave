"""Per-segment DSP chain applied between segmentation and transcription.

Extracted from STTWorker._transcription_loop so the offline eval CLI can run
the exact production chain with individual stages toggled for A/B comparison.
"""
import numpy as np

from backend.audio.dsp import bandpass, denoise, dynamic_agc


def preprocess_segment(
    audio: np.ndarray,
    sample_rate: int,
    bandpass_sos,
    *,
    denoise_enabled: bool = True,
    prop_decrease: float = 0.7,
    agc_enabled: bool = True,
) -> np.ndarray:
    """Bandpass → spectral-gating denoise → dynamic AGC, each stage optional.

    The bandpass always runs: Whisper sees narrowband-FM voice (300–3000 Hz)
    and everything outside that band is noise by definition.
    """
    out = bandpass(audio, bandpass_sos)
    if denoise_enabled:
        out = denoise(out, sample_rate, prop_decrease=prop_decrease)
    if agc_enabled:
        out = dynamic_agc(out, sample_rate)
    return out
