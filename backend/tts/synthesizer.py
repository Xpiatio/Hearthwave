"""TTS synthesizer — asyncio port of the GMRS-TTY QThread TTSSynthesisThread.

Piper synthesis (blocking, espeak-ng global state) runs in a thread-pool
executor to avoid stalling the event loop. PTT keying, playback via
sounddevice, and lead/tail silence are all handled inside the async
synthesize() method.

Status events are pushed to out_queue as dicts:
    {"event": "started"}
    {"event": "finished"}
    {"event": "error", "detail": str}
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import numpy as np
import sounddevice as sd
from piper.config import SynthesisConfig

if TYPE_CHECKING:
    from backend.hw_detect import ComputeBackend
    from backend.ptt.base import PTT


class TTSSynthesizer:
    """Renders Piper TTS and plays it with PTT keying.

    Only one synthesis should run at a time — espeak-ng's global state is
    not safe under concurrent synthesis. Callers are responsible for
    serializing calls (e.g. via a single-consumer asyncio queue).
    """

    def __init__(
        self,
        out_queue: asyncio.Queue,
        compute_backend: "ComputeBackend | None" = None,
        output_device=None,
    ):
        self.out_queue = out_queue
        self.compute_backend = compute_backend
        self.output_device = output_device if output_device not in (None, -1) else None

    # ------------------------------------------------------------------
    # Public async interface
    # ------------------------------------------------------------------

    async def synthesize(self, voice, text: str, ptt: "PTT", length_scale: float = 1.0) -> None:
        """Synthesize ``text`` with ``voice``, key ``ptt``, and play the result.

        Synthesis (blocking espeak-ng + Piper) runs in the thread executor.
        PTT keying, playback, and queue events happen on the asyncio side so
        the caller can cancel or coordinate with other coroutines cleanly.

        Args:
            voice:        A loaded Piper Voice object.
            text:         Text to synthesize.
            ptt:          PTT implementation to key around the audio.
            length_scale: Piper speech rate scale (1.0 = normal, >1 = slower).
        """
        await self.out_queue.put({"event": "started"})
        try:
            audio, sample_rate = await asyncio.get_running_loop().run_in_executor(
                None, self._synthesize_blocking, voice, text, ptt, length_scale
            )
        except Exception as e:
            await self.out_queue.put({"event": "error", "detail": str(e)})
            await self.out_queue.put({"event": "finished"})
            return

        if audio is None:
            # Nothing synthesized (empty text or voice produced no chunks).
            await self.out_queue.put({"event": "finished"})
            return

        try:
            ptt.key()
            await asyncio.get_running_loop().run_in_executor(
                None, self._play_blocking, audio, sample_rate
            )
        finally:
            ptt.unkey()
            await self.out_queue.put({"event": "finished"})

    # ------------------------------------------------------------------
    # Blocking helpers — run in thread-pool executor
    # ------------------------------------------------------------------

    def _synthesize_blocking(
        self,
        voice,
        text: str,
        ptt: "PTT",
        length_scale: float,
    ) -> tuple[np.ndarray | None, int]:
        """Run Piper synthesis and build the padded PCM buffer.

        Returns (audio_int16, sample_rate) or (None, sample_rate) when no
        audio chunks were produced.
        """
        syn_config = SynthesisConfig(
            speaker_id=0 if voice.config.num_speakers > 1 else None,
            length_scale=length_scale,
        )
        sample_rate: int = voice.config.sample_rate

        chunks = []
        for chunk in voice.synthesize(text, syn_config=syn_config):
            arr = chunk.audio_int16_array
            if len(arr) > 0:
                chunks.append(arr)

        if not chunks:
            return None, sample_rate

        lead_samples = int(ptt.lead_in_seconds * sample_rate)
        tail_samples = int(ptt.tail_seconds * sample_rate)
        total = lead_samples + sum(len(c) for c in chunks) + tail_samples
        # np.zeros so lead and tail regions are already silence; no
        # extra concatenations needed to splice them in.
        audio = np.zeros(total, dtype=np.int16)
        pos = lead_samples
        for c in chunks:
            n = len(c)
            audio[pos:pos + n] = c
            pos += n

        return audio, sample_rate

    def _play_blocking(self, audio: np.ndarray, sample_rate: int) -> None:
        """Block until sounddevice finishes playing the audio buffer."""
        sd.play(
            audio,
            samplerate=sample_rate,
            device=self.output_device,
        )
        sd.wait()
