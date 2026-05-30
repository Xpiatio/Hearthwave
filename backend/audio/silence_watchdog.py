class SilenceWatchdog:
    """Counts consecutive silent chunks and signals when the VAD should be
    re-baselined. Silero's VADIterator carries hidden RNN state that drifts
    after prolonged silence, leaving the next true speech onset unable to
    cross the threshold; periodically resetting that state keeps detection
    responsive on long-quiet channels. The worker's pre-roll buffer covers
    the reset boundary, so resets do not lose audio context."""

    def __init__(self, reset_after_chunks):
        self._reset_after = int(reset_after_chunks)
        self._silent = 0

    def note_speech(self):
        self._silent = 0

    def note_silence(self):
        """Increment the silent-chunk counter and return True when the reset
        threshold has been reached. The caller is responsible for performing
        the actual VAD reset and then calling reset() on this watchdog."""
        self._silent += 1
        return self._silent >= self._reset_after

    def reset(self):
        self._silent = 0
