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


class TestAdaptiveThreshold:
    def test_non_adaptive_effective_threshold_is_fixed(self):
        sq = SquelchDetector(open_threshold=0.05)
        for _ in range(50):
            sq.update(0.001)
        assert sq.effective_open_threshold == 0.05

    def test_effective_threshold_starts_at_configured_threshold(self):
        sq = SquelchDetector(open_threshold=0.05, adaptive=True)
        assert sq.effective_open_threshold == 0.05

    def test_quiet_floor_lowers_threshold_so_weak_carrier_opens(self):
        sq = SquelchDetector(
            open_threshold=0.05, open_hold_chunks=2,
            adaptive=True, floor_alpha=0.5, open_factor=3.0,
            min_open_threshold=0.01,
        )
        for _ in range(20):
            sq.update(0.001)  # very quiet channel
        assert sq.effective_open_threshold < 0.05
        # A 0.03-peak carrier is below the fixed 0.05 default but must now open
        sq.update(0.03)
        assert sq.update(0.03) == "opened"

    def test_floor_does_not_learn_while_open(self):
        sq = SquelchDetector(
            open_threshold=0.05, open_hold_chunks=1, close_hold_chunks=100,
            adaptive=True, floor_alpha=0.5,
        )
        sq.update(0.8)  # opens
        assert sq.is_open
        before = sq.effective_open_threshold
        for _ in range(50):
            sq.update(0.8)
        assert sq.effective_open_threshold == before

    def test_floor_does_not_learn_from_above_threshold_chunks(self):
        # Carrier-rise chunks while still closed must not drag the floor up.
        sq = SquelchDetector(
            open_threshold=0.05, open_hold_chunks=10,
            adaptive=True, floor_alpha=0.5,
        )
        before = sq.effective_open_threshold
        for _ in range(5):
            sq.update(0.9)  # above effective threshold, but not open yet
        assert sq.effective_open_threshold == before

    def test_threshold_clipped_to_max(self):
        sq = SquelchDetector(
            open_threshold=0.05, adaptive=True, floor_alpha=1.0,
            open_factor=3.0, max_open_threshold=0.25,
        )
        # noisy-but-closed channel just below effective threshold each time
        for _ in range(100):
            sq.update(sq.effective_open_threshold * 0.99)
        assert sq.effective_open_threshold <= 0.25

    def test_threshold_clipped_to_min(self):
        sq = SquelchDetector(
            open_threshold=0.05, adaptive=True, floor_alpha=1.0,
            min_open_threshold=0.01,
        )
        for _ in range(20):
            sq.update(0.0)
        assert sq.effective_open_threshold >= 0.01

    def test_reset_restores_initial_floor(self):
        sq = SquelchDetector(open_threshold=0.05, adaptive=True, floor_alpha=0.5)
        for _ in range(20):
            sq.update(0.001)
        assert sq.effective_open_threshold != 0.05
        sq.reset()
        assert sq.effective_open_threshold == 0.05

    def test_weak_carrier_below_fixed_threshold_never_opens_non_adaptive(self):
        sq = SquelchDetector(open_threshold=0.05, open_hold_chunks=1)
        for _ in range(100):
            sq.update(0.03)
        assert not sq.is_open


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
