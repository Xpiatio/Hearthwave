"""Speech segmentation state machine — VAD + squelch, no Qt / no Whisper.

Extracted from STTWorker so it can be unit-tested without an audio
device or ML model, and so STTWorker owns only I/O + asyncio bridging.
"""
from __future__ import annotations

import collections
import logging

import numpy as np

_log = logging.getLogger(__name__)

from backend.audio.segmentation import pick_cut_index
from backend.audio.silence_watchdog import SilenceWatchdog
from backend.audio.vad import reset_vad_state


class SpeechSegmenter:
    """Stateful VAD + squelch gating that emits speech segments.

    The end of an utterance is whichever comes first: Silero VAD's end
    event, or the squelch closing (the remote operator unkeyed — there is
    no more speech coming, only the static crash and silence).

    The caller feeds one chunk at a time via :meth:`feed`. Each call returns
    zero or more complete ``(uid, audio, is_final)`` segments ready to hand
    to a transcription queue, plus a list of capture-event strings for
    downstream consumers (e.g. a spectrometer overlay).

    Call :meth:`reset` whenever the audio pipeline pauses or resumes so the
    VAD RNN state and all rolling buffers start clean.

    This class is Qt-free and has no import-time ML dependencies so the full
    test suite can exercise it without loading Whisper or a VAD model.
    """

    # Chunks trimmed off the tail beyond the squelch close-hold window when a
    # carrier drop force-finalizes an utterance — covers the static crash
    # that precedes the sub-threshold tail.
    CRASH_TRIM_CHUNKS = 2

    def __init__(
        self,
        vad_iter,
        squelch,
        *,
        sample_rate: int,
        rolling_target_chunks: int,
        cut_window_chunks: int,
        pre_buffer_chunks: int,
        squelch_buffer_max_chunks: int,
        min_speech_duration_s: float,
        silence_reset_chunks: int,
    ) -> None:
        self._vad_iter = vad_iter
        self._squelch = squelch
        self._sample_rate = sample_rate
        self._rolling_target_chunks = rolling_target_chunks
        self._cut_window_chunks = cut_window_chunks
        self._slice_trigger_chunks = rolling_target_chunks + cut_window_chunks
        self._min_speech_duration_s = min_speech_duration_s
        self._rolling: collections.deque = collections.deque(maxlen=pre_buffer_chunks)
        self._squelch_buffer: collections.deque = collections.deque(maxlen=squelch_buffer_max_chunks)
        self._collected: collections.deque = collections.deque(maxlen=self._slice_trigger_chunks)
        self._collected_peaks: collections.deque = collections.deque(maxlen=self._slice_trigger_chunks)
        self._silence_watchdog = SilenceWatchdog(silence_reset_chunks)
        self._in_speech = False
        self._utterance_id = 0
        self._current_uid = -1
        self._partials_emitted = 0
        # Samples of actual speech (trigger chunk onward). The min-duration
        # gate uses this rather than the emitted audio length so pre-roll /
        # squelch-buffer seeding can grow without letting kerchunks through.
        self._speech_samples = 0

    def reset(self) -> None:
        """Clear all buffered audio and reset collaborator state."""
        self._collected.clear()
        self._collected_peaks.clear()
        self._in_speech = False
        self._speech_samples = 0
        self._rolling.clear()
        self._squelch_buffer.clear()
        self._squelch.reset()
        reset_vad_state(self._vad_iter)
        self._silence_watchdog.reset()

    def feed(
        self, chunk: np.ndarray, peak: float
    ) -> tuple[list[tuple[int, np.ndarray, bool]], list[str]]:
        """Process one audio chunk.

        Args:
            chunk: Float32 audio samples (one capture period).
            peak:  Peak absolute amplitude of the chunk (0..1).

        Returns:
            ``(segments, events)`` where each segment is
            ``(uid, audio_array, is_final)`` and each event is one of
            ``'vad_start'``, ``'vad_end'``, ``'squelch_opened'``,
            ``'squelch_closed'``.
        """
        segments: list[tuple[int, np.ndarray, bool]] = []
        events: list[str] = []

        squelch_event = self._squelch.update(peak)
        if squelch_event == "opened":
            self._squelch_buffer.clear()
            events.append("squelch_opened")
        elif squelch_event == "closed":
            events.append("squelch_closed")
            if self._in_speech:
                # Carrier dropped mid-speech: the transmission is over. Trim
                # the sub-threshold tail (close-hold chunks) plus the crash
                # burst, finalize now, and reset the VAD so its own stale
                # "end" can't fire later. The closing chunk itself is never
                # collected — it is ~500 ms past the last voice.
                trim = self._squelch.close_hold_chunks + self.CRASH_TRIM_CHUNKS
                self._finalize_utterance(segments, events, trim_chunks=trim)
                self._silence_watchdog.note_speech()
                reset_vad_state(self._vad_iter)
            else:
                self._squelch_buffer.clear()

        try:
            speech_dict = self._vad_iter(chunk, return_seconds=False)
        except Exception as exc:
            _log.warning("VAD error on chunk: %s", exc)
            speech_dict = None

        if speech_dict and "start" in speech_dict:
            self._in_speech = True
            self._utterance_id += 1
            self._current_uid = self._utterance_id
            self._partials_emitted = 0
            self._collected.clear()
            self._collected_peaks.clear()
            if self._squelch.is_open and self._squelch_buffer:
                seed = self._squelch_buffer
            else:
                seed = self._rolling
            for c in seed:
                self._collected.append(c)
                self._collected_peaks.append(float(np.max(np.abs(c))) if c.size else 0.0)
            self._collected.append(chunk)
            self._collected_peaks.append(peak)
            self._speech_samples = chunk.size
            self._squelch_buffer.clear()
            self._silence_watchdog.note_speech()
            events.append("vad_start")

        elif speech_dict and "end" in speech_dict and self._in_speech:
            self._collected.append(chunk)
            self._collected_peaks.append(peak)
            self._speech_samples += chunk.size
            self._finalize_utterance(segments, events)
            self._silence_watchdog.note_speech()

        elif self._in_speech:
            self._collected.append(chunk)
            self._collected_peaks.append(peak)
            self._speech_samples += chunk.size
            self._silence_watchdog.note_speech()
            if len(self._collected) >= self._slice_trigger_chunks:
                cut_idx = pick_cut_index(
                    list(self._collected_peaks),
                    self._rolling_target_chunks,
                    self._rolling_target_chunks + self._cut_window_chunks,
                )
                if cut_idx is None:
                    cut_idx = self._slice_trigger_chunks - 1
                slice_chunks = [self._collected.popleft() for _ in range(cut_idx + 1)]
                for _ in range(cut_idx + 1):
                    self._collected_peaks.popleft()
                audio = np.concatenate(slice_chunks)
                segments.append((self._current_uid, audio, False))
                self._partials_emitted += 1

        elif self._silence_watchdog.note_silence():
            reset_vad_state(self._vad_iter)
            self._silence_watchdog.reset()

        self._rolling.append(chunk)
        if self._squelch.is_open and not self._in_speech:
            self._squelch_buffer.append(chunk)

        return segments, events

    def _finalize_utterance(self, segments, events, *, trim_chunks: int = 0) -> None:
        """End the current utterance: optionally trim the tail, apply the
        min-speech gate, and emit the final segment + 'vad_end' event."""
        if trim_chunks > 0:
            trim = min(len(self._collected) - 1, trim_chunks)
            for _ in range(max(0, trim)):
                self._collected.pop()
                self._collected_peaks.pop()
        audio = np.concatenate(self._collected) if self._collected else None
        self._in_speech = False
        self._collected.clear()
        self._collected_peaks.clear()
        events.append("vad_end")
        if audio is not None and (
            self._partials_emitted > 0
            or self._speech_samples / self._sample_rate >= self._min_speech_duration_s
        ):
            segments.append((self._current_uid, audio, True))
        self._speech_samples = 0
