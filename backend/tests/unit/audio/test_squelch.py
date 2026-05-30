from backend.audio.squelch import SquelchDetector


class TestRisingEdge:
    def test_single_chunk_above_threshold_does_not_open(self):
        sq = SquelchDetector(open_hold_chunks=2)
        assert sq.update(0.5) is None
        assert not sq.is_open

    def test_opens_after_hold_chunks(self):
        sq = SquelchDetector(open_threshold=0.1, open_hold_chunks=2)
        sq.update(0.5)
        event = sq.update(0.5)
        assert event == "opened"
        assert sq.is_open

    def test_spike_then_silence_resets_open_counter(self):
        sq = SquelchDetector(open_threshold=0.1, open_hold_chunks=3)
        sq.update(0.5)   # above
        sq.update(0.0)   # resets _above counter
        sq.update(0.5)   # above — count restarts at 1
        sq.update(0.5)   # above — count = 2, still < 3
        assert not sq.is_open

    def test_below_threshold_chunk_never_opens(self):
        sq = SquelchDetector(open_threshold=0.5, open_hold_chunks=1)
        for _ in range(10):
            sq.update(0.4)
        assert not sq.is_open


class TestFallingEdge:
    def _open(self, sq, n_chunks=2):
        for _ in range(n_chunks):
            sq.update(1.0)

    def test_single_silent_chunk_does_not_close(self):
        sq = SquelchDetector(open_hold_chunks=1, close_hold_chunks=3)
        self._open(sq)
        assert sq.update(0.0) is None
        assert sq.is_open

    def test_closes_after_hold_chunks(self):
        sq = SquelchDetector(open_hold_chunks=1, close_hold_chunks=2)
        self._open(sq)
        sq.update(0.0)
        event = sq.update(0.0)
        assert event == "closed"
        assert not sq.is_open

    def test_brief_silence_then_audio_resets_close_counter(self):
        sq = SquelchDetector(open_hold_chunks=1, close_hold_chunks=3)
        self._open(sq)
        sq.update(0.0)   # below — count = 1
        sq.update(0.0)   # below — count = 2
        sq.update(1.0)   # above — resets _below counter
        sq.update(0.0)   # below — count = 1 again
        assert sq.is_open


class TestReset:
    def test_reset_clears_open_state(self):
        sq = SquelchDetector(open_hold_chunks=1)
        sq.update(1.0)
        assert sq.is_open
        sq.reset()
        assert not sq.is_open

    def test_reset_clears_pending_open_count(self):
        sq = SquelchDetector(open_threshold=0.1, open_hold_chunks=3)
        sq.update(0.5)
        sq.update(0.5)
        # has 2 of 3 required; reset should clear this
        sq.reset()
        sq.update(0.5)   # count restarts at 1 — still shouldn't open
        sq.update(0.5)   # count = 2 — still < 3
        assert not sq.is_open

    def test_after_reset_can_open_again(self):
        sq = SquelchDetector(open_hold_chunks=1)
        sq.update(1.0)
        sq.reset()
        event = sq.update(1.0)
        assert event == "opened"


class TestReturnValues:
    def test_returns_none_while_stable_open(self):
        sq = SquelchDetector(open_hold_chunks=1, close_hold_chunks=5)
        sq.update(1.0)
        # Already open; three more loud chunks → None each time
        for _ in range(3):
            assert sq.update(1.0) is None

    def test_returns_none_while_stable_closed(self):
        sq = SquelchDetector()
        for _ in range(5):
            assert sq.update(0.0) is None
