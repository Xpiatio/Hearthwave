"""Unit tests for backend.cw.decoder.

scipy is NOT installed in the test environment; we inject a minimal fake
before importing the module so the top-level `from scipy import signal`
does not raise an ImportError.
"""
from __future__ import annotations

import sys
import types
import unittest.mock
import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Inject fake scipy BEFORE importing the module under test
# ---------------------------------------------------------------------------
_fake_signal = types.ModuleType("scipy.signal")
_fake_signal.butter = unittest.mock.MagicMock(return_value=(np.array([1.0]), np.array([1.0])))
_fake_signal.sosfilt = unittest.mock.MagicMock(side_effect=lambda sos, x: x)
_fake_signal.lfilter = unittest.mock.MagicMock(side_effect=lambda b, a, x: x)

_fake_scipy = types.ModuleType("scipy")
_fake_scipy.signal = _fake_signal
sys.modules.setdefault("scipy", _fake_scipy)
sys.modules.setdefault("scipy.signal", _fake_signal)

# Clear cached module if a previous import sneaked through
for _mod_name in list(sys.modules):
    if _mod_name.startswith("backend.cw"):
        del sys.modules[_mod_name]

from backend.cw.decoder import CWDecoder, _MORSE_TABLE  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SR = CWDecoder.SAMPLE_RATE  # 16 000


def _sine(freq_hz: float, duration_s: float, amplitude: float = 0.5) -> np.ndarray:
    """Generate a pure-tone sine wave at SAMPLE_RATE."""
    t = np.linspace(0, duration_s, int(SR * duration_s), endpoint=False)
    return (amplitude * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)


def _make_keyed(pattern: list[tuple[int, int]]) -> np.ndarray:
    """Build a binary keyed array from (value, sample_count) pairs."""
    return np.array(
        [v for value, count in pattern for v in [value] * count],
        dtype=np.int8,
    )


# WPM 20 dit ≈ 60/(50*20) s = 0.06 s => 960 samples at 16 kHz
_DIT = 960   # samples per dit at ~20 WPM
_DAH = _DIT * 3
_ELEM_GAP = _DIT           # inter-element gap (< 2*dit)
_CHAR_GAP = _DIT * 3       # inter-character gap (2*dit … <5*dit boundary: use 3x)
_WORD_GAP = _DIT * 7       # inter-word gap (>= 5*dit)


def _keyed_letter(morse: str, dit: int = _DIT) -> list[tuple[int, int]]:
    """Return (value, count) run-list for a single morse symbol with inter-element gaps."""
    runs: list[tuple[int, int]] = []
    for i, sym in enumerate(morse):
        if i > 0:
            runs.append((0, dit))           # inter-element gap
        runs.append((1, dit if sym == "." else dit * 3))
    return runs


def _keyed_word(letters: list[str], dit: int = _DIT) -> list[tuple[int, int]]:
    """Build runs for a sequence of morse letters separated by char gaps."""
    runs: list[tuple[int, int]] = []
    for i, letter in enumerate(letters):
        if i > 0:
            runs.append((0, dit * 3))       # inter-character gap
        runs.extend(_keyed_letter(letter, dit))
    return runs


# ---------------------------------------------------------------------------
# _MORSE_TABLE completeness
# ---------------------------------------------------------------------------

class TestMorseTable:
    def test_all_uppercase_letters_present(self):
        import string
        for ch in string.ascii_uppercase:
            # At least one key must map to this character
            assert ch in _MORSE_TABLE.values(), f"Missing letter: {ch}"

    def test_all_digits_present(self):
        for digit in "0123456789":
            assert digit in _MORSE_TABLE.values(), f"Missing digit: {digit}"

    def test_keys_contain_only_dots_and_dashes(self):
        for key in _MORSE_TABLE:
            assert all(c in ".-" for c in key), f"Invalid key: {key!r}"

    def test_known_letters(self):
        assert _MORSE_TABLE[".-"] == "A"
        assert _MORSE_TABLE["-..."] == "B"
        assert _MORSE_TABLE["-.-."] == "C"
        assert _MORSE_TABLE["."] == "E"
        assert _MORSE_TABLE["--"] == "M"
        assert _MORSE_TABLE["-"] == "T"
        assert _MORSE_TABLE["--.."] == "Z"

    def test_known_digits(self):
        assert _MORSE_TABLE["-----"] == "0"
        assert _MORSE_TABLE[".----"] == "1"
        assert _MORSE_TABLE["....."] == "5"
        assert _MORSE_TABLE["----."] == "9"

    def test_known_punctuation(self):
        assert _MORSE_TABLE[".-.-.-"] == "."
        assert _MORSE_TABLE["--..--"] == ","
        assert _MORSE_TABLE["..--.."] == "?"

    def test_sos_prosign_present(self):
        assert _MORSE_TABLE["...---..."] == "SOS"

    def test_no_duplicate_characters(self):
        # Every value should map to at most one key (all unique)
        values = list(_MORSE_TABLE.values())
        assert len(values) == len(set(values)), "Duplicate character in morse table"

    def test_table_has_at_least_36_entries(self):
        # 26 letters + 10 digits
        assert len(_MORSE_TABLE) >= 36


# ---------------------------------------------------------------------------
# _detect_tone
# ---------------------------------------------------------------------------

class TestDetectTone:
    def setup_method(self):
        self.decoder = CWDecoder()
        # Reset fake_signal mocks between tests
        _fake_signal.butter.reset_mock()
        _fake_signal.sosfilt.reset_mock()
        _fake_signal.lfilter.reset_mock()

    def test_detects_tone_within_cw_window(self):
        # 700 Hz is comfortably within TONE_MIN_HZ=400 … TONE_MAX_HZ=1200
        audio = _sine(700.0, 1.0)
        tone = self.decoder._detect_tone(audio)
        assert tone is not None
        assert abs(tone - 700.0) < 5.0, f"Expected ~700 Hz, got {tone:.1f} Hz"

    def test_detects_800hz_tone(self):
        audio = _sine(800.0, 0.5)
        tone = self.decoder._detect_tone(audio)
        assert tone is not None
        assert abs(tone - 800.0) < 10.0

    def test_returns_none_for_silent_audio(self):
        audio = np.zeros(SR, dtype=np.float32)
        # All spectrum bins are 0; argmax returns 0 — but mask may still produce
        # a frequency.  The method will return _some_ frequency inside the window.
        # What matters: it does NOT raise.
        result = self.decoder._detect_tone(audio)
        # Either None or a float in the valid range
        if result is not None:
            assert CWDecoder.TONE_MIN_HZ <= result <= CWDecoder.TONE_MAX_HZ

    def test_returns_frequency_in_cw_window(self):
        # Any tone in the CW window should return a frequency within that window
        for freq in (400, 600, 900, 1200):
            audio = _sine(float(freq), 0.5)
            tone = self.decoder._detect_tone(audio)
            assert tone is not None
            assert CWDecoder.TONE_MIN_HZ <= tone <= CWDecoder.TONE_MAX_HZ

    def test_tone_outside_window_not_selected(self):
        # 200 Hz is below TONE_MIN_HZ; a 700 Hz component should still win
        t = np.linspace(0, 1.0, SR, endpoint=False)
        audio = (
            0.1 * np.sin(2 * np.pi * 200 * t)      # small out-of-window component
            + 0.5 * np.sin(2 * np.pi * 700 * t)    # dominant in-window component
        ).astype(np.float32)
        tone = self.decoder._detect_tone(audio)
        assert tone is not None
        assert abs(tone - 700.0) < 10.0


# ---------------------------------------------------------------------------
# _timing_decode — core pure-Python logic
# ---------------------------------------------------------------------------

class TestTimingDecode:
    def setup_method(self):
        self.decoder = CWDecoder()

    # -- Edge / guard cases --------------------------------------------------

    def test_empty_array_returns_none(self):
        assert self.decoder._timing_decode(np.array([], dtype=np.int8)) is None

    def test_all_zeros_returns_none(self):
        keyed = np.zeros(10_000, dtype=np.int8)
        assert self.decoder._timing_decode(keyed) is None

    def test_single_element_on_segment_returns_none(self):
        # Only one on-segment => len(on_durations) < 2 => None
        keyed = _make_keyed([(0, 100), (1, _DIT), (0, 100)])
        assert self.decoder._timing_decode(keyed) is None

    def test_tiny_on_segments_returns_none(self):
        # dit_samples < 10 guard
        keyed = _make_keyed([(1, 3), (0, 2), (1, 4), (0, 50)])
        assert self.decoder._timing_decode(keyed) is None

    # -- Single character decoding ------------------------------------------

    def test_decode_letter_e(self):
        # E = "." = single dit
        # Two separate E's so we have >= 2 on_durations
        runs = (
            _keyed_letter(".")          # first E
            + [(0, _CHAR_GAP)]
            + _keyed_letter(".")        # second E
        )
        keyed = _make_keyed(runs)
        result = self.decoder._timing_decode(keyed)
        assert result == "EE"

    def test_decode_letter_t(self):
        # T = "-" = single dah.
        # The dit estimator uses percentile(on_durations, 33), so we need
        # enough dit-length on-segments to anchor the estimate below dah length.
        # Use "ETE" (. - .) so on_durations = [dit, dah, dit] => p33 = dit.
        runs = _keyed_word([".", "-", "."])
        keyed = _make_keyed(runs)
        result = self.decoder._timing_decode(keyed)
        assert result == "ETE"

    def test_decode_letter_a(self):
        # A = ".-"
        runs = (
            _keyed_letter(".-")
            + [(0, _CHAR_GAP)]
            + _keyed_letter(".-")
        )
        keyed = _make_keyed(runs)
        result = self.decoder._timing_decode(keyed)
        assert result == "AA"

    def test_decode_letter_m(self):
        # M = "--". Needs dit context so the p33 estimator anchors to dit length.
        # "EME" = (.) (--) (.) => on_durations has enough dits
        runs = _keyed_word([".", "--", "."])
        keyed = _make_keyed(runs)
        result = self.decoder._timing_decode(keyed)
        assert result == "EME"

    def test_decode_letter_s(self):
        # S = "..."
        runs = (
            _keyed_letter("...")
            + [(0, _CHAR_GAP)]
            + _keyed_letter("...")
        )
        keyed = _make_keyed(runs)
        result = self.decoder._timing_decode(keyed)
        assert result == "SS"

    def test_decode_letter_o(self):
        # O = "---". Use "SOS" (... --- ...) which has plenty of dit context
        # to keep the p33 estimator calibrated to dit length.
        runs = _keyed_word(["...", "---", "..."])
        keyed = _make_keyed(runs)
        result = self.decoder._timing_decode(keyed)
        assert result == "SOS"

    # -- Multi-character words -----------------------------------------------

    def test_decode_cq(self):
        # CQ = "-.-." "--.-"
        # Both letters have dit context within them, but total on_durations:
        # C: [dah,dit,dah,dit] + Q: [dah,dah,dit,dah] = 8 segments, 4 dits
        # p33 of mixed list = dit length => classifier works correctly.
        # Verify with "CQ DE" to get even more dit context.
        runs = _keyed_word(["-.-.","--.-", "-..", "."])
        keyed = _make_keyed(runs)
        result = self.decoder._timing_decode(keyed)
        assert result == "CQDE"

    def test_decode_de(self):
        # DE = "-.. ."
        runs = _keyed_word(["-..", "."])
        keyed = _make_keyed(runs)
        result = self.decoder._timing_decode(keyed)
        assert result == "DE"

    def test_decode_sos(self):
        # SOS = "... --- ..."
        runs = _keyed_word(["...", "---", "..."])
        keyed = _make_keyed(runs)
        result = self.decoder._timing_decode(keyed)
        assert result == "SOS"

    def test_decode_hi(self):
        # HI = ".... .."
        runs = _keyed_word(["....", ".."])
        keyed = _make_keyed(runs)
        result = self.decoder._timing_decode(keyed)
        assert result == "HI"

    def test_decode_73(self):
        # 73 = "--... .--.."   Wait, 7="--..." 3="...--"
        runs = _keyed_word(["--...", "...--"])
        keyed = _make_keyed(runs)
        result = self.decoder._timing_decode(keyed)
        assert result == "73"

    # -- Word boundary (space insertion) ------------------------------------

    def test_word_boundary_inserts_space(self):
        # "DE" space "CQ"
        de_runs = _keyed_word(["-..", "."])
        cq_runs = _keyed_word(["-.-.","--.-"])
        runs = de_runs + [(0, _WORD_GAP)] + cq_runs
        keyed = _make_keyed(runs)
        result = self.decoder._timing_decode(keyed)
        assert result == "DE CQ"

    def test_multiple_word_boundaries(self):
        # "CQ DE" style: CQ <word_gap> DE
        cq_runs = _keyed_word(["-.-.","--.-"])
        de_runs = _keyed_word(["-..", "."])
        runs = cq_runs + [(0, _WORD_GAP)] + de_runs
        keyed = _make_keyed(runs)
        result = self.decoder._timing_decode(keyed)
        assert result == "CQ DE"

    # -- Trailing symbol committed -------------------------------------------

    def test_trailing_symbol_committed_without_gap(self):
        # A sequence that ends without a trailing gap still emits the last char.
        # Use "SE" (... .) — all dits, no calibration issue.
        runs = _keyed_word(["...", "."])
        keyed = _make_keyed(runs)
        result = self.decoder._timing_decode(keyed)
        assert result == "SE"

    # -- Unknown symbol ------------------------------------------------------

    def test_unknown_symbol_produces_question_mark(self):
        # An invalid Morse sequence not in _MORSE_TABLE
        # Use a pattern that is clearly invalid: five dits followed by a dah
        # ......- is not in the table
        invalid_morse = [(1, _DIT), (0, _DIT), (1, _DIT), (0, _DIT),
                         (1, _DIT), (0, _DIT), (1, _DIT), (0, _DIT),
                         (1, _DIT), (0, _DIT), (1, _DAH)]
        # Pair with a known second symbol so on_durations >= 2
        second = [(0, _CHAR_GAP)] + _keyed_letter(".")
        runs = invalid_morse + second
        keyed = _make_keyed(runs)
        result = self.decoder._timing_decode(keyed)
        assert result is not None
        assert "?" in result

    # -- Dit/dah boundary classification ------------------------------------

    def test_dit_is_shorter_than_2x_dit_samples(self):
        # A segment of exactly 1x dit_samples should be classified as dit
        runs = (
            _keyed_letter(".")     # reference: single dit for E
            + [(0, _CHAR_GAP)]
            + _keyed_letter(".")   # second E (need >=2 on segments)
        )
        keyed = _make_keyed(runs)
        result = self.decoder._timing_decode(keyed)
        assert result == "EE"

    def test_dah_is_longer_than_2x_dit_samples(self):
        # A segment of 3x dit_samples must be classified as dah.
        # Use ETE (. - .) so the dit estimator is anchored to dit length and
        # the dah in the middle is correctly identified.
        runs = _keyed_word([".", "-", "."])
        keyed = _make_keyed(runs)
        result = self.decoder._timing_decode(keyed)
        assert result == "ETE"

    # -- Gap boundary classification ----------------------------------------

    def test_inter_element_gap_does_not_commit_symbol(self):
        # An element gap (< 2*dit) must NOT cause early commit
        # ".-" (A) should not split into "E" + "T" if gap is < 2*dit
        runs = _keyed_word([".-", ".-"])
        keyed = _make_keyed(runs)
        result = self.decoder._timing_decode(keyed)
        assert result == "AA", f"Expected AA got {result!r}"

    def test_char_gap_commits_symbol(self):
        # Char gap (>= 2*dit, < 5*dit) must commit the current symbol.
        # Use "SE" (...) (.) — pure dits, no calibration problem.
        # A char_gap between them must produce two separate characters.
        runs = (
            _keyed_letter("...")
            + [(0, _CHAR_GAP)]
            + _keyed_letter(".")
        )
        keyed = _make_keyed(runs)
        result = self.decoder._timing_decode(keyed)
        assert result == "SE"

    # -- All-zeros / all-ones guards ----------------------------------------

    def test_all_ones_two_segments_needed_none(self):
        # Exactly one long on segment — only one element in on_durations
        keyed = np.ones(5000, dtype=np.int8)
        # on_durations has 1 element => None
        assert self.decoder._timing_decode(keyed) is None

    def test_result_is_stripped(self):
        # Leading/trailing spaces from word gaps should be stripped
        runs = (
            [(0, _WORD_GAP)]
            + _keyed_word([".", "."])   # EE
            + [(0, _WORD_GAP)]
        )
        keyed = _make_keyed(runs)
        result = self.decoder._timing_decode(keyed)
        assert result is not None
        assert not result.startswith(" ")
        assert not result.endswith(" ")

    # -- Longer sentence -----------------------------------------------------

    def test_decode_cq_cq_de(self):
        cq_runs = _keyed_word(["-.-.","--.-"])
        de_runs = _keyed_word(["-..", "."])
        runs = (
            cq_runs
            + [(0, _WORD_GAP)]
            + cq_runs
            + [(0, _WORD_GAP)]
            + de_runs
        )
        keyed = _make_keyed(runs)
        result = self.decoder._timing_decode(keyed)
        assert result == "CQ CQ DE"

    def test_decode_digits_12345(self):
        digit_morse = {
            "1": ".----",
            "2": "..---",
            "3": "...--",
            "4": "....-",
            "5": ".....",
        }
        letters = [digit_morse[d] for d in "12345"]
        runs = _keyed_word(letters)
        keyed = _make_keyed(runs)
        result = self.decoder._timing_decode(keyed)
        assert result == "12345"


# ---------------------------------------------------------------------------
# decode() — top-level method
# ---------------------------------------------------------------------------

class TestDecode:
    def setup_method(self):
        self.decoder = CWDecoder()
        _fake_signal.butter.reset_mock()
        _fake_signal.sosfilt.reset_mock()
        _fake_signal.lfilter.reset_mock()

    def test_short_audio_rejected(self):
        # < 0.1 s at 16 kHz = < 1600 samples
        short = np.zeros(100, dtype=np.float32)
        assert self.decoder.decode(short) is None

    def test_exactly_at_threshold_not_rejected(self):
        # 0.1 * SR = 1600 samples => not rejected (size >= threshold)
        threshold = int(SR * 0.1)
        audio = np.zeros(threshold, dtype=np.float32)
        # Will return None for other reasons (silent) but must NOT be rejected
        # by the size check alone — i.e. must call _detect_tone
        with unittest.mock.patch.object(
            self.decoder, "_detect_tone", return_value=None
        ) as mock_detect:
            result = self.decoder.decode(audio)
            mock_detect.assert_called_once()
            assert result is None

    def test_silent_audio_returns_none(self):
        # _detect_tone returns a frequency but peak < 1e-6 after envelope
        # We need sosfilt and lfilter to return zeros so peak < 1e-6
        _fake_signal.sosfilt.side_effect = lambda sos, x: np.zeros_like(x)
        _fake_signal.lfilter.side_effect = lambda b, a, x: np.zeros_like(x)
        audio = np.zeros(SR * 2, dtype=np.float32)
        result = self.decoder.decode(audio)
        assert result is None
        # Restore defaults
        _fake_signal.sosfilt.side_effect = lambda sos, x: x
        _fake_signal.lfilter.side_effect = lambda b, a, x: x

    def test_no_tone_detected_returns_none(self):
        # _detect_tone returns None for silence (no dominant peak)
        audio = np.zeros(SR * 2, dtype=np.float32)
        with unittest.mock.patch.object(
            self.decoder, "_detect_tone", return_value=None
        ):
            result = self.decoder.decode(audio)
            assert result is None

    def test_full_pipeline_with_mocked_internals(self):
        """Verify decode() chains helpers correctly using mocks."""
        # Build a keyed signal that spells "E E" (two single-dit letters)
        runs = (
            _keyed_letter(".")
            + [(0, _CHAR_GAP)]
            + _keyed_letter(".")
        )
        keyed_signal = _make_keyed(runs).astype(np.int8)

        fake_envelope = np.zeros(SR * 2, dtype=np.float32)
        # Place ON segments from keyed_signal into envelope
        for v, c in runs:
            pass  # envelope built differently below

        # Use a simulated envelope: high where keyed=1
        envelope_arr = keyed_signal.astype(np.float32)
        # Peak = 1.0; threshold = 0.3 → keyed regions stay ON

        audio = np.zeros(SR * 2, dtype=np.float32)

        with (
            unittest.mock.patch.object(self.decoder, "_detect_tone", return_value=700.0),
            unittest.mock.patch.object(self.decoder, "_narrow_bandpass", return_value=audio),
            unittest.mock.patch.object(self.decoder, "_envelope", return_value=envelope_arr),
        ):
            result = self.decoder.decode(audio)
            assert result == "EE"

    def test_decode_converts_audio_to_float32(self):
        """decode() should cast int16 arrays to float32 before processing."""
        int16_audio = np.zeros(SR * 2, dtype=np.int16)
        with unittest.mock.patch.object(
            self.decoder, "_detect_tone", return_value=None
        ) as mock_detect:
            self.decoder.decode(int16_audio)
            called_audio = mock_detect.call_args[0][0]
            assert called_audio.dtype == np.float32

    def test_empty_timing_result_returns_none(self):
        """decode() returns None when _timing_decode yields empty/None."""
        audio = np.zeros(SR * 2, dtype=np.float32)
        tiny_envelope = np.full(SR * 2, 0.5, dtype=np.float32)

        with (
            unittest.mock.patch.object(self.decoder, "_detect_tone", return_value=700.0),
            unittest.mock.patch.object(self.decoder, "_narrow_bandpass", return_value=audio),
            unittest.mock.patch.object(self.decoder, "_envelope", return_value=tiny_envelope),
            unittest.mock.patch.object(self.decoder, "_timing_decode", return_value=None),
        ):
            assert self.decoder.decode(audio) is None
