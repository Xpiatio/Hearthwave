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
    noise_clip: "np.ndarray | None" = None,
) -> np.ndarray:
    """Bandpass → spectral-gating denoise → gain stage, each stage optional.

    The bandpass always runs: Whisper sees narrowband-FM voice (300–3000 Hz)
    and everything outside that band is noise by definition. The gain stage is
    selected by ``gain_mode``: "agc" (dynamic attack/release), "rms" (one-shot
    RMS normalize), or "off" (no gain).

    ``noise_clip`` is squelch-closed noise-floor audio used as the denoise
    stage's stationary noise estimate. It is bandpassed here (not at capture)
    so the clip shares the segment's spectral domain while queue payloads and
    debug captures stay raw.
    """
    out = bandpass(audio, bandpass_sos)
    if denoise_enabled:
        if noise_clip is not None and len(noise_clip) > 0:
            out = denoise(
                out, sample_rate, prop_decrease=prop_decrease,
                y_noise=bandpass(noise_clip, bandpass_sos),
            )
        else:
            out = denoise(out, sample_rate, prop_decrease=prop_decrease)
    if gain_mode == "agc":
        out = dynamic_agc(out, sample_rate)
    elif gain_mode == "rms":
        out = normalize_rms(out)
    return out
