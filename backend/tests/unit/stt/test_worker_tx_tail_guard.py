"""Tests for STTWorker's post-resume TX-tail guard.

After STT resumes following a transmit, the tail of our own TTS bleeds back
through the same sound card (acoustic/electrical coupling). Measured on the
rig, that bleed is LOW amplitude (~0.02 peak) — below the squelch/carrier
threshold (0.05) — yet spectrally clean enough that Silero VAD transcribes it.
It also arrives after a brief quiet gap, so "release on first quiet chunk" lets
it through.

The guard therefore discards all *sub-squelch* audio for a bounded window after
a TX, and releases early only when a genuine carrier opens squelch (a real
station replying) so RX is never delayed. The window cap guarantees release.
"""
import asyncio

from backend.stt.worker import STTWorker


def _make_worker():
    # squelch_open_threshold defaults to SQUELCH_OPEN_THRESHOLD (0.05)
    return STTWorker(out_queue=asyncio.Queue())


class TestTxTailGuardRelease:
    def test_real_carrier_releases_immediately(self):
        """A chunk at/above the squelch threshold is a real station — let it
        through at once so we never clip an incoming reply."""
        w = _make_worker()
        carrier = w.squelch_open_threshold + 0.1
        assert w._tx_tail_guard_release(carrier, count=0) is True

    def test_chunk_at_threshold_releases(self):
        """Squelch opens at >= threshold, so a chunk AT the threshold counts as
        a real carrier."""
        w = _make_worker()
        assert w._tx_tail_guard_release(w.squelch_open_threshold, count=0) is True

    def test_subsquelch_bleed_is_held(self):
        """Low-amplitude bleed (below squelch) must be discarded, not released —
        this is the measured failure (~0.02 peak slipping through)."""
        w = _make_worker()
        bleed = w.squelch_open_threshold - 0.025  # ~0.025, the observed bleed level
        assert w._tx_tail_guard_release(bleed, count=0) is False

    def test_quiet_floor_is_held_inside_window(self):
        """Even a near-silent chunk is held while inside the window, so the bleed
        can't slip through a quiet gap before it arrives."""
        w = _make_worker()
        floor = 0.003
        assert w._tx_tail_guard_release(floor, count=5) is False

    def test_window_cap_forces_release(self):
        """The bounded window guarantees release so a steady sub-squelch floor
        can't keep RX muted forever."""
        w = _make_worker()
        floor = 0.003
        assert w._tx_tail_guard_release(floor, count=w.TX_TAIL_GUARD_MAX_CHUNKS) is True

    def test_subsquelch_below_cap_still_held(self):
        w = _make_worker()
        bleed = w.squelch_open_threshold - 0.025
        assert w._tx_tail_guard_release(bleed, count=w.TX_TAIL_GUARD_MAX_CHUNKS - 1) is False
