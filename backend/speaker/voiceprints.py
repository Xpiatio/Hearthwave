from __future__ import annotations

import logging
import re
import threading
from pathlib import Path

import numpy as np

from backend.speaker.embedder import (
    EMBED_DIM,
    MATCH_THRESHOLD,
    MAX_SAMPLES_PER_CONTACT,
    _l2_normalize,
)

_log = logging.getLogger(__name__)

_SAFE_RE = re.compile(r"[^A-Za-z0-9_-]")


class VoiceprintStore:
    def __init__(self, directory: Path) -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        # key → list of 192-dim float32 arrays (most recent last, capped at MAX)
        self._embeddings: dict[str, list[np.ndarray]] = {}
        # key → centroid (L2-normalized mean)
        self._centroids: dict[str, np.ndarray] = {}
        self._load_all()

    @staticmethod
    def _key(callsign: str, name: str = "") -> str:
        cs = callsign.strip().upper()
        safe_name = _SAFE_RE.sub("_", name.strip()) if name.strip() else ""
        return f"{cs}_{safe_name}" if safe_name else cs

    def _npz_path(self, key: str) -> Path:
        return self._dir / f"{key}.npz"

    def _load_all(self) -> None:
        for path in self._dir.glob("*.npz"):
            key = path.stem
            try:
                data = np.load(str(path))
                samples = [data[k] for k in sorted(data.files)]
                if samples:
                    self._embeddings[key] = samples
                    self._centroids[key] = self._compute_centroid(samples)
            except Exception as exc:
                _log.warning("Failed to load voiceprint %s: %s", path, exc)

    @staticmethod
    def _compute_centroid(samples: list[np.ndarray]) -> np.ndarray:
        stacked = np.stack(samples, axis=0).astype("float32")
        mean = stacked.mean(axis=0)
        return _l2_normalize(mean)

    def _save(self, key: str) -> None:
        samples = self._embeddings.get(key, [])
        path = self._npz_path(key)
        try:
            arrays = {str(i): s for i, s in enumerate(samples)}
            np.savez(str(path), **arrays)
        except Exception as exc:
            _log.warning("Failed to save voiceprint %s: %s", key, exc)

    def enroll(self, callsign: str, name: str, embedding: np.ndarray) -> None:
        key = self._key(callsign, name)
        with self._lock:
            samples = self._embeddings.get(key, [])
            samples.append(_l2_normalize(embedding))
            if len(samples) > MAX_SAMPLES_PER_CONTACT:
                samples = samples[-MAX_SAMPLES_PER_CONTACT:]
            self._embeddings[key] = samples
            self._centroids[key] = self._compute_centroid(samples)
            self._save(key)

    def best_match(
        self, embedding: np.ndarray, threshold: float = MATCH_THRESHOLD
    ) -> tuple[str | None, str | None, float]:
        v = _l2_normalize(embedding)
        best_key: str | None = None
        best_score: float = -1.0
        with self._lock:
            for key, centroid in self._centroids.items():
                score = float(np.dot(v, centroid))
                if score > best_score:
                    best_score = score
                    best_key = key
        if best_key is None or best_score < threshold:
            return None, None, best_score
        # Reconstruct callsign and name from key
        parts = best_key.split("_", 1)
        callsign = parts[0]
        name = parts[1].replace("_", " ") if len(parts) > 1 else ""
        return callsign, name, best_score

    def reset_contact(self, callsign: str, name: str = "") -> None:
        key = self._key(callsign, name)
        with self._lock:
            self._embeddings.pop(key, None)
            self._centroids.pop(key, None)
            path = self._npz_path(key)
            try:
                if path.exists():
                    path.unlink()
            except Exception as exc:
                _log.warning("Failed to delete voiceprint file %s: %s", path, exc)

    def sample_count(self, callsign: str, name: str = "") -> int:
        key = self._key(callsign, name)
        with self._lock:
            return len(self._embeddings.get(key, []))

    def known_speakers(self) -> list[dict]:
        with self._lock:
            result = []
            for key, samples in self._embeddings.items():
                parts = key.split("_", 1)
                callsign = parts[0]
                name = parts[1].replace("_", " ") if len(parts) > 1 else ""
                result.append({
                    "callsign": callsign,
                    "name": name,
                    "sample_count": len(samples),
                })
            return result
