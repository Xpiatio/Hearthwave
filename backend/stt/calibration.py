"""STT calibration wizard: capture a known-good reading and sweep the real
accuracy-affecting settings (gain mode, noise-profile denoise, Whisper model)
against it, scoring each combination with the same WER machinery as the
offline eval CLI (backend.tools.eval_stt).

The capture buffer taps the same raw-audio fanout the live STT worker already
emits (backend.server._audio_chunk_fanout) — no changes to the worker or its
debug-capture recorder are needed.
"""
from __future__ import annotations

from typing import Callable, Sequence

import numpy as np

from backend.constants import GAIN_MODES
from backend.tools.eval_stt import EvalPipelineConfig, run_pipeline
from backend.stt.wer import score

PREAMBLE_TEXT = (
    "When in the Course of human events, it becomes necessary for one people "
    "to dissolve the political bands which have connected them with another, "
    "and to assume among the powers of the earth, the separate and equal "
    "station to which the Laws of Nature and of Nature's God entitle them, a "
    "decent respect to the opinions of mankind requires that they should "
    "declare the causes which impel them to the separation."
)


class CalibrationCapture:
    """Accumulates raw RX audio for one calibration session.

    Bounded by ``max_duration_s`` so a forgotten "stop" can't grow the buffer
    unbounded; feeding past the cap auto-deactivates the capture.
    """

    def __init__(self, sample_rate: int, max_duration_s: float = 180.0) -> None:
        self.sample_rate = sample_rate
        self._max_samples = int(max_duration_s * sample_rate)
        self._chunks: list[np.ndarray] = []
        self._samples = 0
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    def start(self) -> None:
        self._chunks = []
        self._samples = 0
        self._active = True

    def feed_raw(self, chunk: np.ndarray) -> None:
        if not self._active:
            return
        self._chunks.append(np.asarray(chunk, dtype=np.float32))
        self._samples += len(chunk)
        if self._samples >= self._max_samples:
            self._active = False

    def stop(self) -> np.ndarray:
        self._active = False
        if not self._chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(self._chunks)


def run_sweep(
    audio: np.ndarray,
    *,
    models: Sequence[str],
    transcriber_loader: Callable[[str], object],
    vad_iterator_factory: Callable[[], object],
    gain_modes: Sequence[str] = GAIN_MODES,
    noise_profiles: Sequence[bool] = (False, True),
    reference_text: str = PREAMBLE_TEXT,
    progress_cb: "Callable[[dict], None] | None" = None,
) -> list[dict]:
    """Run ``audio`` through every (model, gain_mode, noise_profile) combo,
    scoring each against ``reference_text``. Models are the outer loop so
    ``transcriber_loader`` is called once per model, not once per combo —
    reloading a Whisper model is the expensive part of a sweep.

    Returns combos ranked best (lowest WER) first.
    """
    total = len(models) * len(gain_modes) * len(noise_profiles)
    results: list[dict] = []
    index = 0
    for model in models:
        transcriber = transcriber_loader(model)
        for gain_mode in gain_modes:
            for noise_profile in noise_profiles:
                index += 1
                cfg = EvalPipelineConfig(gain_mode=gain_mode, noise_profile=noise_profile)
                vad_iter = vad_iterator_factory()
                pipeline_results = run_pipeline(audio, cfg, transcriber, vad_iter)
                hypothesis = " ".join(r["text"] for r in pipeline_results).strip()
                wer_result = score([reference_text], [hypothesis])
                entry = {
                    "model": model,
                    "gain_mode": gain_mode,
                    "noise_profile": noise_profile,
                    "wer": wer_result["wer"],
                    "hypothesis": hypothesis,
                }
                results.append(entry)
                if progress_cb is not None:
                    progress_cb({"index": index, "total": total, **entry})
    results.sort(key=lambda e: e["wer"])
    return results
