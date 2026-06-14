"""VOX primer tone generator + splicing into the TX buffer."""
import asyncio
from unittest.mock import MagicMock

import numpy as np

from backend.tts.synthesizer import TTSSynthesizer, make_vox_primer

SR = 22050


def _fake_voice(amp=0.8, seconds=0.5):
    t = np.arange(int(seconds * SR)) / SR
    pcm = (amp * np.sin(2 * np.pi * 800 * t) * 32767).astype(np.int16)
    chunk = MagicMock()
    chunk.audio_int16_array = pcm
    voice = MagicMock()
    voice.config.sample_rate = SR
    voice.config.num_speakers = 1
    voice.synthesize.return_value = [chunk]
    return voice, pcm


class TestMakeVoxPrimer:
    def test_length_is_tone_plus_gap(self):
        primer = make_vox_primer(SR, ms=300, gap_ms=80)
        assert len(primer) == int(0.300 * SR) + int(0.080 * SR)

    def test_dtype_is_int16(self):
        assert make_vox_primer(SR, ms=300).dtype == np.int16

    def test_tone_region_is_non_silent(self):
        primer = make_vox_primer(SR, ms=300, gap_ms=80)
        tone_n = int(0.300 * SR)
        assert np.max(np.abs(primer[:tone_n])) > 0

    def test_gap_region_is_silent(self):
        primer = make_vox_primer(SR, ms=300, gap_ms=80)
        tone_n = int(0.300 * SR)
        assert np.all(primer[tone_n:] == 0)

    def test_amplitude_within_int16_and_level(self):
        primer = make_vox_primer(SR, ms=300, level=0.3)
        peak = np.max(np.abs(primer))
        assert peak <= 32767
        assert peak >= int(0.25 * 32767)  # ~level, allowing for sine peak/rounding
