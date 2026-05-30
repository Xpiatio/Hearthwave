from __future__ import annotations

import logging
import os

import numpy as np

_log = logging.getLogger(__name__)

EMBED_DIM = 192
MIN_EMBED_DURATION_S = 0.5
MAX_SAMPLES_PER_CONTACT = 20
MATCH_THRESHOLD = 0.75
CLUSTER_THRESHOLD = 0.70
MODELS_SPEAKER_DIR = os.path.join("Models", "Speaker", "ecapa-tdnn")


def _l2_normalize(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v.astype("float32")))
    return v.astype("float32") / n if n > 1e-6 else v.astype("float32")


class SpeakerEmbedder:
    def __init__(self, model_dir: str = MODELS_SPEAKER_DIR) -> None:
        self.model_dir = model_dir
        self._classifier = None
        self._torch = None
        self._load_error: str | None = None

    @property
    def available(self) -> bool:
        return (
            os.path.isdir(self.model_dir)
            and os.path.exists(os.path.join(self.model_dir, "embedding_model.ckpt"))
        )

    def load(self) -> None:
        if self._classifier is not None or self._load_error is not None:
            return
        try:
            import torch
            from speechbrain.inference.speaker import EncoderClassifier

            self._torch = torch
            self._classifier = EncoderClassifier.from_hparams(
                source=self.model_dir,
                savedir=self.model_dir,
                run_opts={"device": "cpu"},
            )
        except Exception as exc:
            self._load_error = str(exc)
            _log.warning("Speaker embedder failed to load: %s", exc)

    def embed(self, audio: np.ndarray, sample_rate: int = 16000) -> np.ndarray | None:
        if not self.available:
            return None
        self.load()
        if self._classifier is None:
            return None
        if audio.size < MIN_EMBED_DURATION_S * sample_rate:
            return None
        try:
            wav = audio.astype("float32") / 32768.0
            tensor = self._torch.from_numpy(wav).unsqueeze(0)
            embedding = self._classifier.encode_batch(tensor)
            v = embedding.squeeze().cpu().numpy()
            return _l2_normalize(v)
        except Exception as exc:
            _log.warning("Speaker embed failed: %s", exc)
            return None

    @property
    def error(self) -> str | None:
        return self._load_error
