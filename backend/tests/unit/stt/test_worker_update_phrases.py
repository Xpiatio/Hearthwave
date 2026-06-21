"""Tests for STTWorker.update_phrases refreshing both fast and final engines.

Task 10: update_phrases must call update_prompt on _model_cache.whisper AND
_model_cache.whisper_final (when present), so live contact/phrase changes reach
the final-pass engine without a worker restart.
"""
import asyncio
from unittest.mock import MagicMock

from backend.stt.worker import ModelCache, STTWorker


def _make_worker():
    return STTWorker(out_queue=asyncio.Queue())


class TestUpdatePhrasesRefreshesBothEngines:
    def test_fast_engine_updated_when_cache_set(self):
        w = _make_worker()
        fast = MagicMock()
        w._model_cache = ModelCache(
            whisper=fast,
            vad_model=MagicMock(),
            model_name="small.en",
        )
        w.update_phrases(["KE8AAA"])
        fast.update_prompt.assert_called_once_with(["KE8AAA"])

    def test_final_engine_updated_when_present(self):
        """The key regression: final engine must also receive the new phrases."""
        w = _make_worker()
        fast = MagicMock()
        final = MagicMock()
        w._model_cache = ModelCache(
            whisper=fast,
            vad_model=MagicMock(),
            model_name="small.en",
            whisper_final=final,
            final_model_name="distil-large-v3",
        )
        w.update_phrases(["KE8AAA", "KD9ZZZ"])
        fast.update_prompt.assert_called_once_with(["KE8AAA", "KD9ZZZ"])
        final.update_prompt.assert_called_once_with(["KE8AAA", "KD9ZZZ"])

    def test_final_engine_none_does_not_raise(self):
        """Workers without a final model must be unaffected."""
        w = _make_worker()
        fast = MagicMock()
        w._model_cache = ModelCache(
            whisper=fast,
            vad_model=MagicMock(),
            model_name="small.en",
            whisper_final=None,
        )
        # Must not raise
        w.update_phrases(["KE8AAA"])
        fast.update_prompt.assert_called_once_with(["KE8AAA"])

    def test_no_cache_does_not_raise(self):
        """update_phrases before model load must still store phrases silently."""
        w = _make_worker()
        assert w._model_cache is None
        w.update_phrases(["KE8AAA"])
        assert w.saved_phrases == ["KE8AAA"]

    def test_saved_phrases_updated_regardless_of_cache(self):
        w = _make_worker()
        w.update_phrases(["W1AW", "KE8AAA"])
        assert w.saved_phrases == ["W1AW", "KE8AAA"]
