from __future__ import annotations

import os
import sys

import pytest


def _real_numpy() -> bool:
    try:
        import numpy as np
        return type(np.zeros(1)).__name__ == "ndarray"
    except Exception:
        return False


if not _real_numpy():
    pytest.skip("real numpy not available", allow_module_level=True)

import numpy as np

from backend.speaker.embedder import (
    EMBED_DIM,
    MIN_EMBED_DURATION_S,
    SpeakerEmbedder,
    _l2_normalize,
)


class TestL2Normalize:
    def test_unit_vector_unchanged(self):
        v = np.zeros(EMBED_DIM, dtype="float32")
        v[0] = 1.0
        result = _l2_normalize(v)
        assert abs(np.linalg.norm(result) - 1.0) < 1e-6

    def test_non_unit_vector_normalized(self):
        v = np.ones(EMBED_DIM, dtype="float32") * 3.0
        result = _l2_normalize(v)
        assert abs(np.linalg.norm(result) - 1.0) < 1e-6

    def test_zero_vector_returns_zero(self):
        v = np.zeros(EMBED_DIM, dtype="float32")
        result = _l2_normalize(v)
        assert np.all(result == 0.0)

    def test_output_is_float32(self):
        v = np.ones(EMBED_DIM, dtype="float64") * 2.0
        result = _l2_normalize(v)
        assert result.dtype == np.float32

    def test_preserves_direction(self):
        rng = np.random.default_rng(42)
        v = rng.standard_normal(EMBED_DIM).astype("float32")
        result = _l2_normalize(v)
        cosine = float(np.dot(v / np.linalg.norm(v), result))
        assert abs(cosine - 1.0) < 1e-5


class TestSpeakerEmbedderAvailable:
    def test_unavailable_when_dir_missing(self, tmp_path):
        embedder = SpeakerEmbedder(model_dir=str(tmp_path / "nonexistent"))
        assert embedder.available is False

    def test_unavailable_when_ckpt_missing(self, tmp_path):
        model_dir = tmp_path / "model"
        model_dir.mkdir()
        embedder = SpeakerEmbedder(model_dir=str(model_dir))
        assert embedder.available is False

    def test_available_when_dir_and_ckpt_exist(self, tmp_path):
        model_dir = tmp_path / "model"
        model_dir.mkdir()
        (model_dir / "embedding_model.ckpt").write_text("fake")
        embedder = SpeakerEmbedder(model_dir=str(model_dir))
        assert embedder.available is True


class TestSpeakerEmbedderEmbed:
    def test_embed_returns_none_when_not_available(self, tmp_path):
        embedder = SpeakerEmbedder(model_dir=str(tmp_path / "nonexistent"))
        audio = np.zeros(16000, dtype="int16")
        result = embedder.embed(audio, sample_rate=16000)
        assert result is None

    def test_embed_returns_none_for_short_audio(self, tmp_path):
        model_dir = tmp_path / "model"
        model_dir.mkdir()
        (model_dir / "embedding_model.ckpt").write_text("fake")
        embedder = SpeakerEmbedder(model_dir=str(model_dir))
        short_audio = np.zeros(10, dtype="int16")
        result = embedder.embed(short_audio, sample_rate=16000)
        assert result is None

    def test_error_property_is_none_initially(self, tmp_path):
        embedder = SpeakerEmbedder(model_dir=str(tmp_path / "nonexistent"))
        assert embedder.error is None
