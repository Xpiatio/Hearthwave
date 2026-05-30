from backend.audio.silence_watchdog import SilenceWatchdog


class TestNoteSilence:
    def test_does_not_fire_before_threshold(self):
        wd = SilenceWatchdog(reset_after_chunks=3)
        assert not wd.note_silence()
        assert not wd.note_silence()

    def test_fires_exactly_at_threshold(self):
        wd = SilenceWatchdog(reset_after_chunks=3)
        wd.note_silence()
        wd.note_silence()
        assert wd.note_silence()

    def test_fires_again_after_threshold_if_not_reset(self):
        wd = SilenceWatchdog(reset_after_chunks=2)
        wd.note_silence()
        wd.note_silence()
        assert wd.note_silence()
        assert wd.note_silence()

    def test_threshold_of_one(self):
        wd = SilenceWatchdog(reset_after_chunks=1)
        assert wd.note_silence()


class TestNoteSpeech:
    def test_speech_resets_silent_counter(self):
        wd = SilenceWatchdog(reset_after_chunks=3)
        wd.note_silence()
        wd.note_silence()
        wd.note_speech()    # resets
        assert not wd.note_silence()   # counter back to 1
        assert not wd.note_silence()   # counter = 2

    def test_speech_after_threshold_still_resets(self):
        wd = SilenceWatchdog(reset_after_chunks=2)
        wd.note_silence()
        wd.note_silence()   # fires
        wd.note_speech()    # reset
        assert not wd.note_silence()   # back to 1


class TestReset:
    def test_reset_clears_counter(self):
        wd = SilenceWatchdog(reset_after_chunks=3)
        wd.note_silence()
        wd.note_silence()
        wd.reset()
        assert not wd.note_silence()   # counter restarted at 1

    def test_reset_then_fires_at_threshold(self):
        wd = SilenceWatchdog(reset_after_chunks=2)
        wd.note_silence()
        wd.note_silence()
        wd.reset()
        wd.note_silence()
        assert wd.note_silence()
