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


class TestPrimerSplicing:
    def test_primer_prepended_before_speech(self):
        voice, pcm = _fake_voice()
        synth = TTSSynthesizer(out_queue=asyncio.Queue())
        audio, sr = synth._synthesize_blocking(
            voice, "hi", 0.1, 0.05, 1.0, condition=False, vox_primer_ms=300,
        )
        lead_n = int(0.1 * SR)
        tail_n = int(0.05 * SR)
        primer_n = len(make_vox_primer(SR, ms=300))
        assert audio.size == lead_n + primer_n + pcm.size + tail_n
        assert np.all(audio[:lead_n] == 0)
        assert np.max(np.abs(audio[lead_n:lead_n + primer_n])) > 0
        speech_start = lead_n + primer_n
        assert np.array_equal(audio[speech_start:speech_start + pcm.size], pcm)

    def test_disabled_is_unchanged(self):
        voice, pcm = _fake_voice()
        synth = TTSSynthesizer(out_queue=asyncio.Queue())
        audio, sr = synth._synthesize_blocking(
            voice, "hi", 0.1, 0.05, 1.0, condition=False, vox_primer_ms=0,
        )
        lead_n, tail_n = int(0.1 * SR), int(0.05 * SR)
        assert audio.size == lead_n + pcm.size + tail_n

    def test_buffer_path_defaults_to_no_primer(self):
        voice, pcm = _fake_voice()
        synth = TTSSynthesizer(out_queue=asyncio.Queue())
        audio, sr = asyncio.run(synth.synthesize_to_buffer(voice, "hi"))
        assert np.array_equal(audio, pcm)

    def test_buffer_path_forwards_primer(self):
        voice, pcm = _fake_voice()
        synth = TTSSynthesizer(out_queue=asyncio.Queue())
        audio, sr = asyncio.run(
            synth.synthesize_to_buffer(voice, "hi", vox_primer_ms=300)
        )
        primer_n = len(make_vox_primer(SR, ms=300))
        assert audio.size == primer_n + pcm.size
