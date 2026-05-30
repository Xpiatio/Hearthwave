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
    """

    def __init__(self, open_threshold=0.05, open_hold_chunks=2, close_hold_chunks=16):
        self.open_threshold = float(open_threshold)
        self.open_hold_chunks = int(open_hold_chunks)
        self.close_hold_chunks = int(close_hold_chunks)
        self._open = False
        self._above = 0
        self._below = 0

    @property
    def is_open(self):
        return self._open

    def update(self, peak):
        """Feed one chunk's peak amplitude (0.0–1.0). Returns:
          'opened' on the rising edge,
          'closed' on the falling edge,
          None otherwise.
        """
        if peak > self.open_threshold:
            self._above += 1
            self._below = 0
            if not self._open and self._above >= self.open_hold_chunks:
                self._open = True
                return 'opened'
        else:
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
