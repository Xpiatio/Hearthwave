class SquelchDetector:
    """Rising-/falling-edge detector on raw audio peak amplitude.

    Models the listener's view of a remote operator's PTT cycle: a receiver
    sitting on a quiet channel jumps from near-silence to noise-floor
    audio the moment the remote keys up, well before any voice arrives.
    Treating that step-rise as a "pre-trigger" lets the worker start a
    capture buffer at carrier-open, so the leading syllables — which can
    be clipped by VAD onset latency — survive into transcription.

    Hysteresis on both edges prevents single-sample spikes from
    registering as a key-up and prevents inter-syllable gaps from
    registering as a key-down.

    Adaptive mode tracks the channel's noise floor with an EMA (updated
    only while closed and below the current threshold, so carriers never
    teach the detector that loud is normal) and opens at ``open_factor``
    times the floor. On a quiet channel this lets carriers well below the
    fixed threshold pre-trigger the capture buffer; clipping to
    ``[min_open_threshold, max_open_threshold]`` bounds it against dead
    silence and constantly-noisy channels.
    """

    def __init__(
        self,
        open_threshold=0.05,
        open_hold_chunks=2,
        close_hold_chunks=16,
        *,
        adaptive=False,
        floor_alpha=0.02,
        open_factor=3.0,
        min_open_threshold=0.01,
        max_open_threshold=0.25,
    ):
        self.open_threshold = float(open_threshold)
        self.open_hold_chunks = int(open_hold_chunks)
        self.close_hold_chunks = int(close_hold_chunks)
        self.adaptive = bool(adaptive)
        self.floor_alpha = float(floor_alpha)
        self.open_factor = float(open_factor)
        self.min_open_threshold = float(min_open_threshold)
        self.max_open_threshold = float(max_open_threshold)
        self._initial_floor = self.open_threshold / self.open_factor
        self._floor = self._initial_floor
        self._open = False
        self._above = 0
        self._below = 0

    @property
    def is_open(self):
        return self._open

    @property
    def effective_open_threshold(self):
        """The threshold currently in force: fixed, or noise-floor-derived."""
        if not self.adaptive:
            return self.open_threshold
        scaled = self._floor * self.open_factor
        return min(self.max_open_threshold, max(self.min_open_threshold, scaled))

    def update(self, peak):
        """Feed one chunk's peak amplitude (0.0–1.0). Returns:
          'opened' on the rising edge,
          'closed' on the falling edge,
          None otherwise.
        """
        threshold = self.effective_open_threshold
        if peak > threshold:
            self._above += 1
            self._below = 0
            if not self._open and self._above >= self.open_hold_chunks:
                self._open = True
                return 'opened'
        else:
            if self.adaptive and not self._open:
                self._floor += self.floor_alpha * (peak - self._floor)
            self._below += 1
            self._above = 0
            if self._open and self._below >= self.close_hold_chunks:
                self._open = False
                return 'closed'
        return None

    def reset(self):
        self._open = False
        self._above = 0
        self._below = 0
        self._floor = self._initial_floor
