"""Tests for STTWorker.channel_busy threading.Event."""
import asyncio
import threading

from backend.stt.worker import STTWorker


def _make_worker():
    return STTWorker(out_queue=asyncio.Queue())


class TestChannelBusyAttribute:
    def test_channel_busy_exists(self):
        w = _make_worker()
        assert hasattr(w, "channel_busy")

    def test_channel_busy_is_threading_event(self):
        w = _make_worker()
        assert isinstance(w.channel_busy, threading.Event)

    def test_channel_busy_starts_clear(self):
        w = _make_worker()
        assert not w.channel_busy.is_set()


class TestChannelBusySetClear:
    """_apply_squelch_event is the internal helper that sets/clears the flag.
    We call it directly to test the state machine without starting the full
    capture loop (which requires a real audio device)."""

    def test_squelch_opened_sets_busy(self):
        w = _make_worker()
        w._apply_squelch_event("squelch_opened")
        assert w.channel_busy.is_set()

    def test_squelch_closed_clears_busy(self):
        w = _make_worker()
        w._apply_squelch_event("squelch_opened")
        w._apply_squelch_event("squelch_closed")
        assert not w.channel_busy.is_set()

    def test_vad_start_does_not_change_busy(self):
        w = _make_worker()
        w._apply_squelch_event("vad_start")
        assert not w.channel_busy.is_set()

    def test_vad_end_does_not_change_busy(self):
        w = _make_worker()
        w._apply_squelch_event("squelch_opened")
        w._apply_squelch_event("vad_end")
        assert w.channel_busy.is_set()  # unchanged by vad_end
