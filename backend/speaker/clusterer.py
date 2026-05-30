from __future__ import annotations

import numpy as np

from backend.speaker.embedder import CLUSTER_THRESHOLD, _l2_normalize

_LABELS = [
    "Voice A", "Voice B", "Voice C", "Voice D", "Voice E",
    "Voice F", "Voice G", "Voice H", "Voice I", "Voice J",
]


class UnknownClusterer:
    def __init__(self, threshold: float = CLUSTER_THRESHOLD) -> None:
        self._threshold = threshold
        self.reset()

    def reset(self) -> None:
        self._centroids: list[np.ndarray] = []
        self._samples: list[list[np.ndarray]] = []
        self._label_indices: list[int] = []
        self._next_label_idx: int = 0

    def assign(self, embedding: np.ndarray) -> str:
        v = _l2_normalize(embedding)
        best_idx: int | None = None
        best_score: float = -1.0
        for i, centroid in enumerate(self._centroids):
            score = float(np.dot(v, centroid))
            if score > best_score:
                best_score = score
                best_idx = i

        if best_idx is not None and best_score >= self._threshold:
            self._samples[best_idx].append(v)
            stacked = np.stack(self._samples[best_idx], axis=0).astype("float32")
            self._centroids[best_idx] = _l2_normalize(stacked.mean(axis=0))
            label_idx = self._label_indices[best_idx]
        else:
            label_idx = self._next_label_idx
            self._next_label_idx += 1
            self._centroids.append(v.copy())
            self._samples.append([v])
            self._label_indices.append(label_idx)

        if label_idx < len(_LABELS):
            return _LABELS[label_idx]
        return f"Voice {label_idx + 1}"

    def pop_cluster(self, label: str) -> list[np.ndarray]:
        idx = self._label_for(label)
        if idx is None:
            return []
        samples = self._samples[idx]
        del self._centroids[idx]
        del self._samples[idx]
        del self._label_indices[idx]
        return samples

    def samples_for(self, label: str) -> list[np.ndarray]:
        idx = self._label_for(label)
        if idx is None:
            return []
        return list(self._samples[idx])

    def labels(self) -> list[str]:
        result = []
        for li in self._label_indices:
            if li < len(_LABELS):
                result.append(_LABELS[li])
            else:
                result.append(f"Voice {li + 1}")
        return result

    def _label_for(self, label: str) -> int | None:
        for pos, li in enumerate(self._label_indices):
            candidate = _LABELS[li] if li < len(_LABELS) else f"Voice {li + 1}"
            if candidate == label:
                return pos
        return None
