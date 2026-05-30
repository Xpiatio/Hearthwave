from __future__ import annotations

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

from backend.speaker.clusterer import UnknownClusterer
from backend.speaker.embedder import CLUSTER_THRESHOLD, EMBED_DIM


def _make_embedding(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(EMBED_DIM).astype("float32")
    v /= np.linalg.norm(v)
    return v


def _opposite(v: np.ndarray) -> np.ndarray:
    w = -v.copy()
    w /= np.linalg.norm(w)
    return w


class TestAssign:
    def test_first_embedding_creates_voice_a(self):
        c = UnknownClusterer()
        emb = _make_embedding(1)
        label = c.assign(emb)
        assert label == "Voice A"

    def test_similar_embedding_reuses_label(self):
        c = UnknownClusterer()
        emb = _make_embedding(1)
        label1 = c.assign(emb)
        slightly_perturbed = emb + np.random.default_rng(99).standard_normal(EMBED_DIM).astype("float32") * 0.01
        slightly_perturbed /= np.linalg.norm(slightly_perturbed)
        label2 = c.assign(slightly_perturbed)
        assert label1 == label2 == "Voice A"

    def test_dissimilar_embedding_creates_voice_b(self):
        c = UnknownClusterer()
        emb = _make_embedding(1)
        c.assign(emb)
        dissimilar = _opposite(emb)
        label = c.assign(dissimilar)
        assert label == "Voice B"

    def test_sequential_distinct_voices(self):
        c = UnknownClusterer(threshold=0.99)
        labels = []
        for seed in range(5):
            emb = _make_embedding(seed * 1000)
            labels.append(c.assign(emb))
        assert labels[0] == "Voice A"
        assert labels[1] == "Voice B"


class TestPopCluster:
    def test_pop_returns_samples(self):
        c = UnknownClusterer()
        emb = _make_embedding(1)
        c.assign(emb)
        samples = c.pop_cluster("Voice A")
        assert len(samples) >= 1

    def test_pop_removes_label(self):
        c = UnknownClusterer()
        emb = _make_embedding(1)
        c.assign(emb)
        c.pop_cluster("Voice A")
        assert "Voice A" not in c.labels()

    def test_pop_nonexistent_returns_empty(self):
        c = UnknownClusterer()
        result = c.pop_cluster("Voice Z")
        assert result == []

    def test_pop_does_not_affect_other_clusters(self):
        c = UnknownClusterer(threshold=0.99)
        c.assign(_make_embedding(0))
        c.assign(_make_embedding(1000))
        c.pop_cluster("Voice A")
        assert "Voice B" in c.labels()


class TestLabels:
    def test_labels_empty_initially(self):
        c = UnknownClusterer()
        assert c.labels() == []

    def test_labels_grows_with_clusters(self):
        c = UnknownClusterer(threshold=0.99)
        c.assign(_make_embedding(0))
        c.assign(_make_embedding(1000))
        labels = c.labels()
        assert "Voice A" in labels
        assert "Voice B" in labels

    def test_reset_clears_all(self):
        c = UnknownClusterer()
        c.assign(_make_embedding(1))
        c.reset()
        assert c.labels() == []

    def test_samples_for_returns_copy(self):
        c = UnknownClusterer()
        emb = _make_embedding(1)
        c.assign(emb)
        samples = c.samples_for("Voice A")
        assert len(samples) >= 1
        assert "Voice A" in c.labels()
