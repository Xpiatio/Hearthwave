"""CW (morse code) audio decoder.

Decodes a mono float32 audio buffer captured at 16 kHz into text.
Uses FFT-based tone detection, bandpass filtering, envelope extraction,
and adaptive WPM estimation from on-segment timing.
"""
from __future__ import annotations

import numpy as np
from scipy import signal as sp_signal

# Morse code lookup table: symbol string → character
_MORSE_TABLE: dict[str, str] = {
    ".-": "A", "-...": "B", "-.-.": "C", "-..": "D", ".": "E",
    "..-.": "F", "--.": "G", "....": "H", "..": "I", ".---": "J",
    "-.-": "K", ".-..": "L", "--": "M", "-.": "N", "---": "O",
    ".--.": "P", "--.-": "Q", ".-.": "R", "...": "S", "-": "T",
    "..-": "U", "...-": "V", ".--": "W", "-..-": "X", "-.--": "Y",
    "--..": "Z",
    "-----": "0", ".----": "1", "..---": "2", "...--": "3",
    "....-": "4", ".....": "5", "-....": "6", "--...": "7",
    "---..": "8", "----.": "9",
    ".-.-.-": ".", "--..--": ",", "..--..": "?", ".----.": "'",
    "-.-.--": "!", "-..-.": "/", "-.--.": "(", "-.--.-": ")",
    ".-...": "&", "---...": ":", "-.-.-.": ";", "-...-": "=",
    ".-.-.": "+", "-....-": "-", "..--.-": "_", ".-..-.": '"',
    "...-..-": "$", ".--.-.": "@", "...---...": "SOS",
}


class CWDecoder:
    """Decode CW (morse code) from a float32 audio buffer.

    All audio must be mono, 16 kHz (SAMPLE_RATE). The decoder is
    stateless — call decode() once per captured transmission.
    """

    SAMPLE_RATE = 16000
    TONE_MIN_HZ = 400
    TONE_MAX_HZ = 1200
    BANDPASS_WIDTH_HZ = 100   # ± around detected tone
    ENVELOPE_LP_HZ = 40       # low-pass cutoff for envelope smoothing
    THRESHOLD_RATIO = 0.30    # fraction of peak envelope → key-down

    def decode(self, audio: np.ndarray) -> str | None:
        """Decode morse from *audio*. Returns decoded text or None on failure."""
        if audio.size < self.SAMPLE_RATE * 0.1:
            return None

        audio = audio.astype(np.float32)

        tone_hz = self._detect_tone(audio)
        if tone_hz is None:
            return None

        filtered = self._narrow_bandpass(audio, tone_hz)
        envelope = self._envelope(filtered)

        peak = float(np.max(envelope))
        if peak < 1e-6:
            return None

        keyed = (envelope > peak * self.THRESHOLD_RATIO).astype(np.int8)
        return self._timing_decode(keyed)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _detect_tone(self, audio: np.ndarray) -> float | None:
        """Return the dominant frequency in the CW tone window, or None."""
        spectrum = np.abs(np.fft.rfft(audio))
        freqs = np.fft.rfftfreq(len(audio), d=1.0 / self.SAMPLE_RATE)
        mask = (freqs >= self.TONE_MIN_HZ) & (freqs <= self.TONE_MAX_HZ)
        if not np.any(mask):
            return None
        peak_idx = int(np.argmax(spectrum[mask]))
        return float(freqs[mask][peak_idx])

    def _narrow_bandpass(self, audio: np.ndarray, center_hz: float) -> np.ndarray:
        """4th-order Butterworth bandpass ±BANDPASS_WIDTH_HZ around center."""
        low = max(center_hz - self.BANDPASS_WIDTH_HZ, 50.0)
        high = min(center_hz + self.BANDPASS_WIDTH_HZ, self.SAMPLE_RATE / 2 - 50.0)
        sos = sp_signal.butter(
            4, [low, high], btype="band", fs=self.SAMPLE_RATE, output="sos"
        )
        return sp_signal.sosfilt(sos, audio)

    def _envelope(self, audio: np.ndarray) -> np.ndarray:
        """Rectified signal smoothed by a 2nd-order Butterworth low-pass."""
        rectified = np.abs(audio)
        b, a = sp_signal.butter(2, self.ENVELOPE_LP_HZ, btype="low", fs=self.SAMPLE_RATE)
        return sp_signal.lfilter(b, a, rectified)

    def _timing_decode(self, keyed: np.ndarray) -> str | None:
        """Convert a binary key-up/key-down signal to text.

        Uses run-length encoding of the signal, estimates dit duration from
        the lower-third of on-segment lengths, then classifies each segment
        and gap as dit/dah/element/char/word boundary.
        """
        # Run-length encode: [(value, length), ...]
        runs: list[tuple[int, int]] = []
        if len(keyed) == 0:
            return None
        current = int(keyed[0])
        count = 1
        for v in keyed[1:]:
            iv = int(v)
            if iv == current:
                count += 1
            else:
                runs.append((current, count))
                current = iv
                count = 1
        runs.append((current, count))

        on_durations = [length for value, length in runs if value == 1]
        if len(on_durations) < 2:
            return None

        # Estimate dit duration from the shorter on-segments
        dit_samples = float(np.percentile(on_durations, 33))
        if dit_samples < 10:
            return None

        # Decode runs to morse symbols and word/char boundaries
        result_chars: list[str] = []
        current_symbol = ""

        i = 0
        while i < len(runs):
            value, length = runs[i]

            if value == 1:
                # Key-down: classify dit vs dah
                current_symbol += "." if length < 2 * dit_samples else "-"
            else:
                # Key-up gap: classify boundary type
                if length < 2 * dit_samples:
                    # Inter-element gap — do nothing, next element follows
                    pass
                elif length < 5 * dit_samples:
                    # Inter-character gap — commit current symbol
                    if current_symbol:
                        result_chars.append(
                            _MORSE_TABLE.get(current_symbol, "?")
                        )
                        current_symbol = ""
                else:
                    # Inter-word gap — commit symbol then add space
                    if current_symbol:
                        result_chars.append(
                            _MORSE_TABLE.get(current_symbol, "?")
                        )
                        current_symbol = ""
                    result_chars.append(" ")

            i += 1

        # Commit any trailing symbol
        if current_symbol:
            result_chars.append(_MORSE_TABLE.get(current_symbol, "?"))

        text = "".join(result_chars).strip()
        return text if text else None
