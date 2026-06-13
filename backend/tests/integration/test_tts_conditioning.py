"""TX conditioning hook in TTSSynthesizer._synthesize_blocking.

Verifies the conditioning chain runs only on the radio (PTT) path, never on
the browser read-aloud path, and that lead/tail padding stays exact zeros.
"""
import asyncio
from unittest.mock import MagicMock

import numpy as np

from backend.tts.synthesizer import TTSSynthesizer

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


def _synth(tx_conditioning):
    return TTSSynthesizer(
        out_queue=asyncio.Queue(),
        tx_conditioning=tx_conditioning,
    )


class TestConditioningHook:
    def test_disabled_returns_raw_synthesis(self):
        voice, pcm = _fake_voice()
        synth = _synth(tx_conditioning=False)
        audio, sr = synth._synthesize_blocking(voice, "hi", 0.0, 0.0, 1.0, condition=False)
        assert np.array_equal(audio, pcm)

    def test_enabled_changes_speech_audio(self):
        voice, pcm = _fake_voice()
        synth = _synth(tx_conditioning=True)
        audio, sr = synth._synthesize_blocking(voice, "hi", 0.0, 0.0, 1.0, condition=True)
        assert audio.dtype == np.int16
        assert audio.shape == pcm.shape
        assert not np.array_equal(audio, pcm)

    def test_lead_and_tail_padding_stay_exact_zeros(self):
        voice, pcm = _fake_voice()
        synth = _synth(tx_conditioning=True)
        audio, sr = synth._synthesize_blocking(voice, "hi", 0.1, 0.05, 1.0, condition=True)
        lead_n, tail_n = int(0.1 * SR), int(0.05 * SR)
        assert np.all(audio[:lead_n] == 0)
        assert np.all(audio[-tail_n:] == 0)
        assert audio.size == lead_n + pcm.size + tail_n

    def test_synthesize_to_buffer_never_conditions(self):
        # Browser read-aloud goes to the user's speakers, not the radio —
        # band-limiting and compression would just degrade it.
        voice, pcm = _fake_voice()
        synth = _synth(tx_conditioning=True)
        audio, sr = asyncio.run(synth.synthesize_to_buffer(voice, "hi"))
        assert np.array_equal(audio, pcm)

    def test_synthesize_honors_tx_conditioning_attr(self):
        voice, pcm = _fake_voice()
        synth = _synth(tx_conditioning=True)
        played = {}

        def fake_play(audio, sample_rate):
            played["audio"] = audio

        synth._play_blocking = fake_play
        ptt = MagicMock()
        ptt.lead_in_seconds = 0.0
        ptt.tail_seconds = 0.0
        asyncio.run(synth.synthesize(voice, "hi", ptt))
        assert not np.array_equal(played["audio"], pcm)
