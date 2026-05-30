"""Unit tests for SpeechSegmenter.

No ML models or audio hardware required — VAD is replaced by a controllable
mock callable, and SquelchDetector runs its actual logic (pure Python, no deps).
"""
import numpy as np
import pytest

from backend.audio.squelch import SquelchDetector
from backend.stt.segmenter import SpeechSegmenter

SAMPLE_RATE = 16000
CHUNK = 512  # samples per chunk (Silero requirement at 16 kHz)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def chunk(peak: float = 0.0) -> np.ndarray:
    """Make a float32 chunk of CHUNK samples with the given peak amplitude."""
    arr = np.zeros(CHUNK, dtype=np.float32)
    if peak > 0.0:
        arr[0] = float(peak)
    return arr


class MockVAD:
    """Scripted VAD iterator.

    `events` is a list where each entry is one of:
    - None       → no speech boundary this chunk
    - "start"    → speech onset
    - "end"      → speech offset

    Calls past the end of the list return None. reset_states() is tracked.
    """

    def __init__(self, events=()):
        self._events = list(events)
        self._idx = 0
        self.reset_count = 0

    def __call__(self, audio_chunk, return_seconds=False):
        if self._idx < len(self._events):
            ev = self._events[self._idx]
            self._idx += 1
            if ev == "start":
                return {"start": 0}
            if ev == "end":
                return {"end": CHUNK}
        return None

    def reset_states(self):
        self.reset_count += 1


def make_seg(
    vad_events=(),
    *,
    pre_buffer=3,
    squelch_buf_max=8,
    min_speech_s=0.0,       # default 0 to keep most tests simple
    silence_reset_chunks=50,
    rolling=20,
    cut_window=5,
    squelch=None,
):
    """Build a SpeechSegmenter with a MockVAD and the given parameters."""
    vad = MockVAD(vad_events)
    if squelch is None:
        squelch = SquelchDetector(
            open_threshold=0.1,
            open_hold_chunks=1,
            close_hold_chunks=2,
        )
    seg = SpeechSegmenter(
        vad,
        squelch,
        sample_rate=SAMPLE_RATE,
        rolling_target_chunks=rolling,
        cut_window_chunks=cut_window,
        pre_buffer_chunks=pre_buffer,
        squelch_buffer_max_chunks=squelch_buf_max,
        min_speech_duration_s=min_speech_s,
        silence_reset_chunks=silence_reset_chunks,
    )
    return seg, vad


# ---------------------------------------------------------------------------
# Speech start / end basics
# ---------------------------------------------------------------------------

class TestVadOnsetAndOffset:
    def test_vad_start_begins_utterance(self):
        seg, _ = make_seg(["start", "end"])
        segs, _ = seg.feed(chunk(0.0), 0.0)
        assert not segs   # start chunk; no segment yet
        segs, _ = seg.feed(chunk(0.0), 0.0)
        assert len(segs) == 1
        uid, audio, is_final = segs[0]
        assert is_final is True
        assert isinstance(audio, np.ndarray)

    def test_final_segment_uid_is_positive(self):
        seg, _ = make_seg(["start", "end"])
        seg.feed(chunk(), 0.0)
        segs, _ = seg.feed(chunk(), 0.0)
        uid, _, _ = segs[0]
        assert int(uid) > 0

    def test_consecutive_utterances_get_different_uids(self):
        seg, _ = make_seg(["start", "end", "start", "end"])
        seg.feed(chunk(), 0.0)          # start 1
        segs1, _ = seg.feed(chunk(), 0.0)  # end 1
        seg.feed(chunk(), 0.0)          # start 2
        segs2, _ = seg.feed(chunk(), 0.0)  # end 2
        assert segs1[0][0] != segs2[0][0]

    def test_no_segments_during_silence(self):
        seg, _ = make_seg()   # VAD always returns None
        for _ in range(10):
            segs, _ = seg.feed(chunk(), 0.0)
            assert segs == []


# ---------------------------------------------------------------------------
# Minimum speech duration gate
# ---------------------------------------------------------------------------

class TestMinSpeechDuration:
    def _short_audio_chunks(self):
        # 5 chunks × 512 = 2560 samples = 0.16 s < 0.4 s
        return 5

    def test_utterance_below_min_without_partials_is_dropped(self):
        n = self._short_audio_chunks()
        events = ["start"] + [None] * (n - 2) + ["end"]
        seg, _ = make_seg(events, min_speech_s=0.4)
        for i, ev in enumerate(events):
            segs, _ = seg.feed(chunk(), 0.0)
        assert segs == []

    def test_utterance_above_min_is_emitted(self):
        # 14 chunks × 512 = 7168 samples = 0.448 s > 0.4 s
        n = 14
        events = ["start"] + [None] * (n - 2) + ["end"]
        seg, _ = make_seg(events, min_speech_s=0.4)
        last_segs = []
        for _ in events:
            last_segs, _ = seg.feed(chunk(), 0.0)
        assert len(last_segs) == 1
        assert last_segs[0][2] is True

    def test_short_utterance_with_prior_partial_is_emitted(self):
        # If a partial was already sent for this utterance, the final must
        # be emitted even if the tail segment is shorter than min_speech_s.
        seg, _ = make_seg(min_speech_s=0.4, rolling=4, cut_window=2)
        # Feed enough chunks to trigger a rolling slice (partial)
        events_in = ["start"] + [None] * 10 + ["end"]
        vad = MockVAD(events_in)
        squelch = SquelchDetector(open_hold_chunks=1, close_hold_chunks=2)
        seg = SpeechSegmenter(
            vad, squelch,
            sample_rate=SAMPLE_RATE,
            rolling_target_chunks=4,
            cut_window_chunks=2,
            pre_buffer_chunks=2,
            squelch_buffer_max_chunks=8,
            min_speech_duration_s=0.4,
            silence_reset_chunks=50,
        )
        all_segs = []
        for _ in events_in:
            segs, _ = seg.feed(chunk(), 0.0)
            all_segs.extend(segs)
        # Should have at least one partial + one final
        partials = [s for s in all_segs if not s[2]]
        finals = [s for s in all_segs if s[2]]
        assert len(partials) >= 1
        assert len(finals) == 1


# ---------------------------------------------------------------------------
# Pre-buffer and squelch-buffer prepending
# ---------------------------------------------------------------------------

class TestPreBuffer:
    def test_pre_roll_prepended_when_no_squelch(self):
        # 3 None events exhaust the pre-roll window, then start+end fire.
        # Segment audio must include all 3 pre-roll chunks.
        seg, _ = make_seg([None, None, None, "start", "end"], pre_buffer=3)
        seg.feed(chunk(0.1), 0.0)   # pre-roll 1 → rolling ring
        seg.feed(chunk(0.2), 0.0)   # pre-roll 2 → rolling ring
        seg.feed(chunk(0.3), 0.0)   # pre-roll 3 → rolling ring (maxlen=3)
        segs_start, _ = seg.feed(chunk(0.0), 0.0)   # VAD=start; rolling prepended
        segs_end, _ = seg.feed(chunk(0.0), 0.0)     # VAD=end
        assert len(segs_end) == 1
        _, audio, _ = segs_end[0]
        # 3 pre-roll chunks + start chunk + end chunk = 5 × CHUNK
        assert len(audio) == 5 * CHUNK

    def test_squelch_buffer_replaces_pre_roll_on_vad_start(self):
        # Squelch opens, 2 above-threshold chunks accumulate in squelch_buf,
        # then VAD fires while squelch is still open → squelch_buf prepended
        # instead of the 3 pre-roll chunks.
        seg, _ = make_seg(
            [None, None, None, None, None, "start", "end"],
            pre_buffer=3,
            squelch_buf_max=8,
        )
        seg.feed(chunk(0.0), 0.0)   # pre-roll 1
        seg.feed(chunk(0.0), 0.0)   # pre-roll 2
        seg.feed(chunk(0.0), 0.0)   # pre-roll 3
        seg.feed(chunk(0.5), 0.5)   # squelch opens → squelch_buf grows
        seg.feed(chunk(0.5), 0.5)   # above threshold → squelch stays open; squelch_buf grows
        # squelch_buf now has 2 chunks; squelch still open (close_hold=2, below count=0)
        segs_start, _ = seg.feed(chunk(0.0), 0.0)   # VAD=start; below=1 < close_hold=2
        # squelch still open when VAD fires → squelch_buf prepended
        segs_end, _ = seg.feed(chunk(0.0), 0.0)     # VAD=end
        assert len(segs_end) == 1
        _, audio, _ = segs_end[0]
        # squelch_buf (2) + start chunk + end chunk = 4 × CHUNK
        assert len(audio) == 4 * CHUNK

    def test_squelch_buffer_cleared_on_carrier_close_without_vad(self):
        # Carrier opens then closes before VAD fires → squelch buffer discarded;
        # subsequent speech uses pre-roll only (pre_buffer=0 → empty).
        seg, _ = make_seg(
            [None, None, None, None, None, None, "start", "end"],
            pre_buffer=0,
            squelch_buf_max=8,
        )
        seg.feed(chunk(0.5), 0.5)   # squelch opens, buf grows
        seg.feed(chunk(0.5), 0.5)   # above threshold, buf grows
        seg.feed(chunk(0.0), 0.0)   # below=1
        seg.feed(chunk(0.0), 0.0)   # below=2 → squelch closes; buf discarded
        seg.feed(chunk(0.0), 0.0)   # silent (5th None event)
        seg.feed(chunk(0.0), 0.0)   # silent (6th None event)
        segs_start, _ = seg.feed(chunk(0.0), 0.0)  # VAD=start; no squelch buf
        segs_end, _ = seg.feed(chunk(0.0), 0.0)    # VAD=end
        assert len(segs_end) == 1
        _, audio, _ = segs_end[0]
        # pre_buffer=0 (empty rolling) + start chunk + end chunk = 2 × CHUNK
        assert len(audio) == 2 * CHUNK


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class TestCaptureEvents:
    def test_squelch_opened_event_emitted(self):
        seg, _ = make_seg()
        _, events = seg.feed(chunk(0.5), 0.5)
        assert "squelch_opened" in events

    def test_squelch_closed_event_emitted(self):
        seg, _ = make_seg()
        seg.feed(chunk(0.5), 0.5)   # open
        seg.feed(chunk(0.0), 0.0)
        _, events = seg.feed(chunk(0.0), 0.0)   # close_hold=2 → closes here
        assert "squelch_closed" in events

    def test_vad_start_event_emitted(self):
        seg, _ = make_seg(["start"])
        _, events = seg.feed(chunk(), 0.0)
        assert "vad_start" in events

    def test_vad_end_event_emitted(self):
        seg, _ = make_seg(["start", "end"])
        seg.feed(chunk(), 0.0)
        _, events = seg.feed(chunk(), 0.0)
        assert "vad_end" in events

    def test_silent_chunk_emits_no_events(self):
        seg, _ = make_seg()
        _, events = seg.feed(chunk(0.0), 0.0)
        assert events == []


# ---------------------------------------------------------------------------
# VAD auto-rebaseline (SilenceWatchdog)
# ---------------------------------------------------------------------------

class TestVadRebaseline:
    def test_vad_reset_after_silence_threshold(self):
        seg, vad = make_seg(silence_reset_chunks=5)
        # Feed 5 silent chunks — watchdog should fire on the 5th
        for _ in range(5):
            seg.feed(chunk(0.0), 0.0)
        assert vad.reset_count >= 1

    def test_vad_not_reset_before_threshold(self):
        seg, vad = make_seg(silence_reset_chunks=10)
        for _ in range(9):
            seg.feed(chunk(0.0), 0.0)
        assert vad.reset_count == 0

    def test_speech_prevents_reset(self):
        seg, vad = make_seg(["start", "end"], silence_reset_chunks=3)
        # Start + end uses 2 speech events; watchdog resets on speech
        seg.feed(chunk(0.0), 0.0)   # start
        seg.feed(chunk(0.0), 0.0)   # end — note_speech() called
        # Now only 2 more silent chunks (below threshold of 3)
        seg.feed(chunk(0.0), 0.0)
        seg.feed(chunk(0.0), 0.0)
        assert vad.reset_count == 0

    def test_watchdog_resets_after_firing(self):
        seg, vad = make_seg(silence_reset_chunks=3)
        for _ in range(3):
            seg.feed(chunk(0.0), 0.0)
        first_count = vad.reset_count
        for _ in range(3):
            seg.feed(chunk(0.0), 0.0)
        # Should fire again after another threshold's worth of silence
        assert vad.reset_count > first_count


# ---------------------------------------------------------------------------
# Rolling streaming slices (long-utterance partials)
# ---------------------------------------------------------------------------

class TestRollingSlices:
    def test_partial_emitted_when_buffer_exceeds_trigger(self):
        # rolling=4, cut_window=2 → trigger at 6 chunks in speech
        seg, _ = make_seg(
            ["start"] + [None] * 20,   # long speech, no end event
            rolling=4,
            cut_window=2,
        )
        all_segs = []
        for _ in range(21):
            segs, _ = seg.feed(chunk(0.0), 0.0)
            all_segs.extend(segs)
        partials = [s for s in all_segs if not s[2]]
        assert len(partials) >= 1

    def test_partial_segment_has_same_uid_as_subsequent_final(self):
        seg, _ = make_seg(
            ["start"] + [None] * 20 + ["end"],
            rolling=4,
            cut_window=2,
        )
        all_segs = []
        for _ in range(22):
            segs, _ = seg.feed(chunk(0.0), 0.0)
            all_segs.extend(segs)
        partials = [s for s in all_segs if not s[2]]
        finals = [s for s in all_segs if s[2]]
        assert len(partials) >= 1
        assert len(finals) == 1
        assert partials[0][0] == finals[0][0]


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

class TestReset:
    def test_reset_mid_utterance_clears_collected_buffer(self):
        seg, _ = make_seg(["start"] + [None] * 10)
        # Start + 5 in-speech chunks
        for _ in range(6):
            seg.feed(chunk(0.0), 0.0)
        seg.reset()
        # After reset, in_speech=False; subsequent end event should not emit
        vad2 = MockVAD(["end"])
        seg._vad_iter = vad2
        segs, _ = seg.feed(chunk(0.0), 0.0)
        assert segs == []

    def test_reset_clears_squelch_state(self):
        seg, _ = make_seg()
        seg.feed(chunk(0.5), 0.5)   # squelch opens
        assert seg._squelch.is_open
        seg.reset()
        assert not seg._squelch.is_open

    def test_reset_clears_silence_watchdog(self):
        seg, vad = make_seg(silence_reset_chunks=3)
        seg.feed(chunk(0.0), 0.0)
        seg.feed(chunk(0.0), 0.0)   # silent count=2 (watchdog not yet fired)
        seg.reset()
        # reset() calls reset_vad_state() once; record the count here
        count_after_reset = vad.reset_count
        # With watchdog cleared, 2 more silent chunks should NOT fire it again
        seg.feed(chunk(0.0), 0.0)
        seg.feed(chunk(0.0), 0.0)
        assert vad.reset_count == count_after_reset
