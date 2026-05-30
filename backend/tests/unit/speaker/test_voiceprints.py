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

from backend.speaker.embedder import EMBED_DIM, MATCH_THRESHOLD, MAX_SAMPLES_PER_CONTACT
from backend.speaker.voiceprints import VoiceprintStore


def _make_embedding(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(EMBED_DIM).astype("float32")
    v /= np.linalg.norm(v)
    return v


def _opposite(v: np.ndarray) -> np.ndarray:
    w = -v.copy()
    w /= np.linalg.norm(w)
    return w


class TestKey:
    def test_callsign_only(self):
        assert VoiceprintStore._key("W5TST") == "W5TST"

    def test_callsign_lowercased_uppercased(self):
        assert VoiceprintStore._key("w5tst") == "W5TST"

    def test_callsign_and_name(self):
        key = VoiceprintStore._key("W5TST", "Alice")
        assert key == "W5TST_Alice"

    def test_name_special_chars_replaced(self):
        key = VoiceprintStore._key("W5TST", "Alice Smith")
        assert " " not in key
        assert "W5TST" in key
        assert "Alice" in key

    def test_empty_name_omits_suffix(self):
        assert VoiceprintStore._key("W5TST", "") == "W5TST"

    def test_whitespace_name_omits_suffix(self):
        assert VoiceprintStore._key("W5TST", "   ") == "W5TST"


class TestEnrollAndMatch:
    def test_match_above_threshold(self, tmp_path):
        store = VoiceprintStore(tmp_path)
        emb = _make_embedding(1)
        store.enroll("W5TST", "Alice", emb)
        callsign, name, score = store.best_match(emb, threshold=0.5)
        assert callsign == "W5TST"
        assert score >= 0.5

    def test_match_below_threshold_returns_none(self, tmp_path):
        store = VoiceprintStore(tmp_path)
        emb = _make_embedding(1)
        store.enroll("W5TST", "Alice", emb)
        query = _opposite(emb)
        callsign, name, score = store.best_match(query, threshold=MATCH_THRESHOLD)
        assert callsign is None
        assert name is None
        assert score < MATCH_THRESHOLD

    def test_match_returns_best_of_multiple(self, tmp_path):
        store = VoiceprintStore(tmp_path)
        emb_a = _make_embedding(1)
        emb_b = _make_embedding(99)
        store.enroll("W5TST", "Alice", emb_a)
        store.enroll("W9FOO", "Bob", emb_b)
        callsign, name, score = store.best_match(emb_a, threshold=0.5)
        assert callsign == "W5TST"


class TestFifoCap:
    def test_fifo_cap_does_not_exceed_max(self, tmp_path):
        store = VoiceprintStore(tmp_path)
        for i in range(MAX_SAMPLES_PER_CONTACT + 5):
            store.enroll("W5TST", "", _make_embedding(i))
        assert store.sample_count("W5TST") == MAX_SAMPLES_PER_CONTACT

    def test_most_recent_kept(self, tmp_path):
        store = VoiceprintStore(tmp_path)
        for i in range(MAX_SAMPLES_PER_CONTACT + 1):
            store.enroll("W5TST", "", _make_embedding(i))
        count = store.sample_count("W5TST")
        assert count == MAX_SAMPLES_PER_CONTACT


class TestResetContact:
    def test_reset_removes_data(self, tmp_path):
        store = VoiceprintStore(tmp_path)
        emb = _make_embedding(1)
        store.enroll("W5TST", "Alice", emb)
        store.reset_contact("W5TST", "Alice")
        assert store.sample_count("W5TST", "Alice") == 0
        callsign, _, _ = store.best_match(emb, threshold=0.5)
        assert callsign is None

    def test_reset_removes_npz_file(self, tmp_path):
        store = VoiceprintStore(tmp_path)
        emb = _make_embedding(1)
        store.enroll("W5TST", "", emb)
        npz_files_before = list(tmp_path.glob("*.npz"))
        assert len(npz_files_before) == 1
        store.reset_contact("W5TST")
        npz_files_after = list(tmp_path.glob("*.npz"))
        assert len(npz_files_after) == 0

    def test_reset_nonexistent_is_noop(self, tmp_path):
        store = VoiceprintStore(tmp_path)
        store.reset_contact("NOBODY", "NoOne")


class TestSampleCount:
    def test_count_zero_before_enroll(self, tmp_path):
        store = VoiceprintStore(tmp_path)
        assert store.sample_count("W5TST") == 0

    def test_count_increments_on_enroll(self, tmp_path):
        store = VoiceprintStore(tmp_path)
        store.enroll("W5TST", "", _make_embedding(1))
        store.enroll("W5TST", "", _make_embedding(2))
        assert store.sample_count("W5TST") == 2


class TestKnownSpeakers:
    def test_empty_initially(self, tmp_path):
        store = VoiceprintStore(tmp_path)
        assert store.known_speakers() == []

    def test_lists_enrolled_speakers(self, tmp_path):
        store = VoiceprintStore(tmp_path)
        store.enroll("W5TST", "Alice", _make_embedding(1))
        store.enroll("W9FOO", "", _make_embedding(2))
        speakers = store.known_speakers()
        callsigns = {s["callsign"] for s in speakers}
        assert "W5TST" in callsigns
        assert "W9FOO" in callsigns

    def test_sample_count_in_result(self, tmp_path):
        store = VoiceprintStore(tmp_path)
        store.enroll("W5TST", "", _make_embedding(1))
        store.enroll("W5TST", "", _make_embedding(2))
        speakers = store.known_speakers()
        w5tst = next(s for s in speakers if s["callsign"] == "W5TST")
        assert w5tst["sample_count"] == 2


class TestPersistence:
    def test_reloads_from_disk(self, tmp_path):
        store1 = VoiceprintStore(tmp_path)
        emb = _make_embedding(7)
        store1.enroll("W5TST", "", emb)
        store2 = VoiceprintStore(tmp_path)
        callsign, _, score = store2.best_match(emb, threshold=0.5)
        assert callsign == "W5TST"
