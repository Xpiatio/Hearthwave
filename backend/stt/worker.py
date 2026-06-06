"""STT worker — asyncio port of the GMRS-TTY QThread STTWorker.

Runs the blocking capture/VAD/segmentation loop in a thread pool executor
so it never stalls the asyncio event loop. Transcription results are pushed
to an asyncio.Queue as dicts:

    {"utterance_id": str, "text": str, "partial": bool}

Callbacks for non-result events (level meter, raw chunk fan-out, capture
events, status, error) are optional callables injected at construction time
so callers stay decoupled from the queue protocol.

Thread-safety contract
----------------------
start()  — must be called from the asyncio event loop thread.
pause()  — thread-safe; safe to call from any thread or coroutine.
resume() — thread-safe; safe to call from any thread or coroutine.
stop()   — thread-safe; safe to call from any thread or coroutine.
           The returned coroutine must be awaited to join the worker task.
"""
from __future__ import annotations

import asyncio
import logging
import os
import queue
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

_log = logging.getLogger(__name__)

from backend.audio.capture import open_input_source
from backend.audio.dsp import bandpass, denoise, dynamic_agc, lowpass, make_bandpass_sos, make_lowpass_sos
from backend.audio.squelch import SquelchDetector
from backend.audio.vad import load_vad_model, make_vad_iterator
from backend.stt.segmenter import SpeechSegmenter
from backend.stt.transcriber import WhisperTranscriber


@dataclass
class ModelCache:
    """Loaded Whisper and VAD objects hoisted out of a stopped STTWorker.

    Passed back into the next STTWorker so the multi-second model load is
    skipped on every Listen toggle.  None means the models have not been
    loaded yet or the model name changed.
    """
    whisper: object
    vad_model: object
    model_name: str


class STTWorker:
    """Captures mic audio, gates on Silero VAD, transcribes speech with faster-whisper.

    Orchestrates four single-purpose collaborators (capture / VAD / DSP /
    transcriber). Owns the run-loop state machine and the asyncio queue that
    feeds downstream consumers. The collaborators are lazy-imported (the heavy
    ML deps don't load until listening starts).

    Long utterances are streamed: every ~2 s of continuous speech, the
    capture loop slices off the buffer at a quiet point (so cuts land
    between words, not mid-syllable) and hands the segment to a background
    transcription thread. Partial transcripts are pushed in order under a
    shared ``utterance_id`` so the UI can grow a single chat line as the
    transmission progresses, instead of waiting for the operator to unkey.
    """

    SAMPLE_RATE = 16000
    CHUNK_SAMPLES = 512   # required by Silero VAD at 16kHz
    PRE_BUFFER_CHUNKS = 10  # ~320ms of pre-speech context (fallback when no squelch open)
    MIN_SPEECH_DURATION_S = 0.4  # drops kerchunks / blips on the *first* segment of an utterance
    BANDPASS_LOW_HZ = 300   # narrowband-FM voice floor
    BANDPASS_HIGH_HZ = 3000  # narrowband-FM voice ceiling
    SILENCE_RESET_S = 30.0  # re-baseline VAD after this much continuous silence
    # Squelch-open pre-trigger: captures audio from carrier-open until VAD
    # fires, so leading syllables clipped by VAD onset latency survive into
    # transcription. Buffer is discarded if the carrier drops without voice.
    SQUELCH_OPEN_THRESHOLD = 0.05  # peak amplitude (0..1) on raw int16-normalized chunks
    SQUELCH_OPEN_HOLD_CHUNKS = 2   # ~64ms above threshold = carrier open
    SQUELCH_CLOSE_HOLD_CHUNKS = 16  # ~500ms below threshold = carrier dropped
    SQUELCH_BUFFER_MAX_CHUNKS = 64  # ~2s cap on pre-VAD capture
    # Streaming-transcription cut points: slice when the in-speech buffer
    # passes ROLLING_SEGMENT_S, choosing the lowest-peak chunk in the next
    # CUT_WINDOW_S so cuts land in a natural pause between words.
    ROLLING_SEGMENT_S = 2.0
    CUT_WINDOW_S = 0.3

    _MODELS_DIR = Path(__file__).resolve().parent.parent / "Models" / "STT"

    def __init__(
        self,
        out_queue: asyncio.Queue,
        input_device=None,
        whisper_model: str = "small.en",
        vad_threshold: float = 0.5,
        model_cache: "ModelCache | None" = None,
        system_monitor_sink: str = "",
        rx_mode: str = "voice",
        # Optional event callbacks — all called from the worker thread;
        # implementations must be thread-safe (e.g. loop.call_soon_threadsafe).
        on_audio_level: "Callable[[int], None] | None" = None,
        on_audio_chunk: "Callable[[np.ndarray], None] | None" = None,
        on_capture_event: "Callable[[str], None] | None" = None,
        on_status: "Callable[[str], None] | None" = None,
        on_error: "Callable[[str], None] | None" = None,
    ):
        self.out_queue = out_queue
        self.input_device = input_device if input_device not in (None, -1) else None
        self.system_monitor_sink = system_monitor_sink or ""
        self.whisper_model_name = whisper_model
        self.whisper_model_path = str(self._MODELS_DIR / whisper_model)
        self.vad_threshold = float(vad_threshold)
        self.rx_mode = rx_mode
        self._model_cache: ModelCache | None = model_cache

        self._on_audio_level = on_audio_level
        self._on_audio_chunk = on_audio_chunk
        self._on_capture_event = on_capture_event
        self._on_status = on_status
        self._on_error = on_error

        self.channel_busy = threading.Event()  # set=channel occupied, clear=idle
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()  # set = paused
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # Public control interface
    # ------------------------------------------------------------------

    @property
    def model_cache(self) -> "ModelCache | None":
        return self._model_cache

    def start(self) -> None:
        """Schedule the worker coroutine on the running event loop.

        Must be called from the asyncio thread. The actual blocking work runs
        in the default thread-pool executor via asyncio.to_thread.
        """
        self._loop = asyncio.get_running_loop()
        self._stop_event.clear()
        self._pause_event.clear()
        self._task = self._loop.create_task(
            asyncio.to_thread(self._run), name="stt-worker"
        )

    def pause(self) -> None:
        """Suspend VAD/STT without tearing down the audio stream or models.

        Thread-safe — call from any thread or coroutine.
        """
        self._pause_event.set()

    def resume(self) -> None:
        """Resume after a pause. Thread-safe."""
        self._pause_event.clear()

    def stop(self) -> None:
        """Signal the worker loop to exit. Thread-safe.

        After calling stop(), await the Task returned by start() (or stored as
        self._task) to ensure the thread has fully joined before teardown.
        """
        self._stop_event.set()
        self._pause_event.clear()  # unblock if paused so the loop can see stop

    async def join(self) -> None:
        """Await the worker task. Call after stop() to ensure clean shutdown."""
        if self._task is not None:
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # ------------------------------------------------------------------
    # Private helpers — emit helpers bridge thread → asyncio queue/callbacks
    # ------------------------------------------------------------------

    def _emit_result(self, utterance_id: int, text: str, partial: bool, source: str = "voice") -> None:
        """Push a transcription result onto the asyncio queue from the worker thread."""
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(
            self.out_queue.put_nowait,
            {
                "utterance_id": str(utterance_id),
                "text": text,
                "partial": partial,
                "source": source,
            },
        )

    def _emit_status(self, msg: str) -> None:
        if self._on_status:
            self._on_status(msg)

    def _emit_error(self, msg: str) -> None:
        if self._on_error:
            self._on_error(msg)

    def _emit_audio_level(self, level: int) -> None:
        if self._on_audio_level:
            self._on_audio_level(level)

    def _emit_audio_chunk(self, chunk: np.ndarray) -> None:
        if self._on_audio_chunk:
            self._on_audio_chunk(chunk)

    def _emit_capture_event(self, event: str) -> None:
        if self._on_capture_event:
            self._on_capture_event(event)

    def _apply_squelch_event(self, event: str) -> None:
        """Update channel_busy based on squelch state transitions."""
        if event == "squelch_opened":
            self.channel_busy.set()
        elif event == "squelch_closed":
            self.channel_busy.clear()

    # ------------------------------------------------------------------
    # Worker body — runs in a thread-pool thread
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Blocking capture/VAD/segmentation loop. Called via asyncio.to_thread."""
        if self._stop_event.is_set():
            return

        if self.rx_mode == "cw":
            self._run_cw()
            return

        if not os.path.isdir(self.whisper_model_path):
            self._emit_error(
                f"Whisper model not found at '{self.whisper_model_path}'. "
                f"Run 'python bootstrap_models.py --model {self.whisper_model_name}' on an "
                f"internet-connected machine, then copy Models/ here. "
                f"Radio-TTY does not download models at runtime."
            )
            return

        try:
            if self._model_cache is None or self._model_cache.model_name != self.whisper_model_name:
                self._emit_status(f"Loading Whisper model from {self.whisper_model_path}...")
                whisper = WhisperTranscriber.load(self.whisper_model_path)
                vad_model = load_vad_model()
                self._model_cache = ModelCache(
                    whisper=whisper,
                    vad_model=vad_model,
                    model_name=self.whisper_model_name,
                )
            transcriber = self._model_cache.whisper
            vad_iter = make_vad_iterator(
                self._model_cache.vad_model,
                sample_rate=self.SAMPLE_RATE,
                threshold=self.vad_threshold,
            )
            bandpass_sos = make_bandpass_sos(
                self.SAMPLE_RATE,
                self.BANDPASS_LOW_HZ,
                self.BANDPASS_HIGH_HZ,
            )
        except Exception as e:
            self._emit_error(f"Failed to initialize STT models: {e}")
            return

        # Construct once; failure is non-fatal (fall back to unfiltered path).
        try:
            lowpass_sos = make_lowpass_sos(self.SAMPLE_RATE, cutoff_hz=2700)
        except Exception as e:
            _log.error("Failed to construct lowpass filter: %s — proceeding without LPF", e)
            lowpass_sos = None

        if self._stop_event.is_set():
            return

        try:
            source = open_input_source(
                sample_rate=self.SAMPLE_RATE,
                chunk_samples=self.CHUNK_SAMPLES,
                input_device=self.input_device,
                system_monitor_sink=self.system_monitor_sink,
            )
        except Exception as e:
            self._emit_error(f"Failed to open input device: {e}")
            return

        transcribe_queue: queue.Queue = queue.Queue()
        transcribe_thread = threading.Thread(
            target=self._transcription_loop,
            args=(transcribe_queue, transcriber, bandpass_sos),
            daemon=True,
        )
        transcribe_thread.start()

        self._emit_status("Listening...")
        squelch = SquelchDetector(
            open_threshold=self.SQUELCH_OPEN_THRESHOLD,
            open_hold_chunks=self.SQUELCH_OPEN_HOLD_CHUNKS,
            close_hold_chunks=self.SQUELCH_CLOSE_HOLD_CHUNKS,
        )
        segmenter = SpeechSegmenter(
            vad_iter, squelch,
            sample_rate=self.SAMPLE_RATE,
            rolling_target_chunks=int(self.ROLLING_SEGMENT_S * self.SAMPLE_RATE / self.CHUNK_SAMPLES),
            cut_window_chunks=int(self.CUT_WINDOW_S * self.SAMPLE_RATE / self.CHUNK_SAMPLES),
            pre_buffer_chunks=self.PRE_BUFFER_CHUNKS,
            squelch_buffer_max_chunks=self.SQUELCH_BUFFER_MAX_CHUNKS,
            min_speech_duration_s=self.MIN_SPEECH_DURATION_S,
            silence_reset_chunks=int(self.SILENCE_RESET_S * self.SAMPLE_RATE / self.CHUNK_SAMPLES),
        )
        was_paused = False

        try:
            while not self._stop_event.is_set():
                try:
                    chunk = source.read()
                except Exception as e:
                    self._emit_error(f"Audio read error: {e}")
                    break

                # Apply lowpass filter to the chunk for squelch/VAD processing.
                # Raw chunk is kept for the level meter and waterfall so the
                # operator sees the true unfiltered signal.
                chunk_for_vad = lowpass(np.asarray(chunk, dtype=np.float32), lowpass_sos) if lowpass_sos is not None else chunk
                peak = float(np.max(np.abs(chunk_for_vad))) if chunk_for_vad.size else 0.0
                # Emit input level before any pause/VAD gating so a stuck or
                # disconnected mic shows up as a flat-zero meter regardless
                # of transmit state. Peak (not RMS) matches what users expect
                # from a VU-style indicator and reacts fast to short syllables.
                self._emit_audio_level(min(100, int(peak * 100)))
                # Fan the raw chunk out to any spectrometer consumer. Done
                # before the pause / VAD branches so the waterfall keeps
                # scrolling during TX (the operator wants to see their own
                # carrier and any breakthrough RX while transmitting).
                # Receivers are responsible for dropping frames if they
                # can't keep up — this emit must stay non-blocking.
                self._emit_audio_chunk(chunk)  # raw — waterfall sees unfiltered signal

                if self._pause_event.is_set():
                    if not was_paused:
                        segmenter.reset()
                        self._emit_status("Paused (transmitting)")
                        was_paused = True
                    continue

                if was_paused:
                    segmenter.reset()
                    self._emit_status("Listening...")
                    was_paused = False

                segments, events = segmenter.feed(chunk_for_vad, peak)
                for event in events:
                    self._apply_squelch_event(event)
                    self._emit_capture_event(event)
                for uid, audio, is_final in segments:
                    transcribe_queue.put((uid, audio, is_final))
        finally:
            try:
                source.close()
            except Exception:
                pass
            transcribe_queue.put(None)
            transcribe_thread.join(timeout=15)
            self._emit_status("Stopped listening")

    def _run_cw(self) -> None:
        """CW-mode receive loop. Buffers audio while the squelch is open, then
        decodes the full transmission as morse code on squelch close.

        Bypasses Whisper and Silero VAD entirely — squelch acts as the sole
        transmission boundary detector, which is appropriate for CW because
        the tone is not speech and VAD would never fire.
        """
        from backend.cw.decoder import CWDecoder

        try:
            source = open_input_source(
                sample_rate=self.SAMPLE_RATE,
                chunk_samples=self.CHUNK_SAMPLES,
                input_device=self.input_device,
                system_monitor_sink=self.system_monitor_sink,
            )
        except Exception as e:
            self._emit_error(f"Failed to open input device: {e}")
            return

        decoder = CWDecoder()
        squelch = SquelchDetector(
            open_threshold=self.SQUELCH_OPEN_THRESHOLD,
            open_hold_chunks=self.SQUELCH_OPEN_HOLD_CHUNKS,
            close_hold_chunks=self.SQUELCH_CLOSE_HOLD_CHUNKS,
        )
        # Chunks of audio accumulated during the current transmission
        buffer: list[np.ndarray] = []
        close_hold_count = 0
        # How many below-threshold chunks to collect after squelch closes
        # before treating the transmission as complete (~500 ms of tail)
        CLOSE_HOLD = 16
        uid_counter = 0
        was_paused = False

        self._emit_status("Listening (CW)...")
        try:
            while not self._stop_event.is_set():
                try:
                    chunk = source.read()
                except Exception as e:
                    self._emit_error(f"Audio read error: {e}")
                    break

                peak = float(np.max(np.abs(chunk))) if chunk.size else 0.0
                self._emit_audio_level(min(100, int(peak * 100)))
                self._emit_audio_chunk(chunk)

                if self._pause_event.is_set():
                    if not was_paused:
                        buffer.clear()
                        close_hold_count = 0
                        squelch.reset()
                        self._emit_status("Paused (transmitting)")
                        was_paused = True
                    continue

                if was_paused:
                    squelch.reset()
                    self._emit_status("Listening (CW)...")
                    was_paused = False

                squelch.update(peak)

                if squelch.is_open:
                    buffer.append(chunk)
                    close_hold_count = 0
                elif buffer:
                    # Squelch is closed but we have a buffered transmission — collect
                    # a short tail then decode.
                    close_hold_count += 1
                    buffer.append(chunk)
                    if close_hold_count >= CLOSE_HOLD:
                        audio = np.concatenate(buffer)
                        buffer = []
                        close_hold_count = 0
                        uid_counter += 1
                        try:
                            text = decoder.decode(audio)
                        except Exception as e:
                            self._emit_error(f"CW decode error: {e}")
                            text = None
                        if text:
                            self._emit_result(uid_counter, text, partial=False, source="cw")
        finally:
            try:
                source.close()
            except Exception:
                pass
            self._emit_status("Stopped listening")

    def _transcription_loop(
        self,
        transcribe_queue: queue.Queue,
        transcriber: WhisperTranscriber,
        bandpass_sos,
    ) -> None:
        """Drain the segmentation queue on a background thread so the capture
        loop never blocks on Whisper. Items are (utterance_id, audio, is_final);
        a None sentinel signals shutdown. Single-threaded by design so
        partials emit in capture order.
        """
        while True:
            job = transcribe_queue.get()
            if job is None:
                break
            uid, audio, is_final = job
            try:
                filtered = bandpass(audio, bandpass_sos)
                denoised = denoise(filtered, self.SAMPLE_RATE, prop_decrease=0.7)
                agc_audio = dynamic_agc(denoised, self.SAMPLE_RATE)
                text = transcriber.transcribe(agc_audio)
                if text:
                    self._emit_result(uid, text, not is_final)
            except Exception as e:
                self._emit_error(f"Transcription error: {e}")
