"""Per-utterance debug capture for offline STT evaluation.

Records three views of every utterance — the raw pre-DSP audio (including
pre-roll context), the segmenter's output, and the post-preprocess audio
Whisper actually saw — plus every partial/final transcript, so captures can
be hand-labelled and replayed through ``backend.tools.eval_stt``.

Threading contract: ``feed_raw``/``on_capture_event``/``on_segment`` are
called from the capture loop and must stay O(1); ``on_processed``/
``on_transcript``/``finalize`` are called from the transcription thread.
All file I/O happens in ``finalize``. A single lock guards the shared
record dict; every critical section is a few list appends.
"""
from __future__ import annotations

import collections
import json
import logging
import threading
import time
import wave
from pathlib import Path

import numpy as np

_log = logging.getLogger(__name__)


class UtteranceDebugRecorder:
    def __init__(
        self,
        out_dir,
        *,
        sample_rate: int,
        pre_roll_chunks: int,
        max_seconds: float = 90.0,
        meta: dict | None = None,
    ) -> None:
        self._out_dir = Path(out_dir)
        self._sample_rate = sample_rate
        self._max_samples = int(max_seconds * sample_rate)
        self._meta = dict(meta or {})
        self._lock = threading.Lock()
        self._ring: collections.deque = collections.deque(maxlen=max(0, pre_roll_chunks) or None)
        self._ring_enabled = pre_roll_chunks > 0
        # Accumulation for the most recent vad_start, bound to a uid by the
        # first on_segment() call. "active" = still between vad_start/vad_end
        # so feed_raw keeps appending; after vad_end it stays pending (the
        # final segment arrives after the event) until bound or overwritten.
        self._pending: dict | None = None
        self._pending_active = False
        # uid → record awaiting processed/transcripts/finalize
        self._records: dict[int, dict] = {}

    @staticmethod
    def _new_record() -> dict:
        return {
            "raw": [],
            "raw_samples": 0,
            "truncated": False,
            "segments": [],
            "processed": [],
            "transcripts": [],
            "started_at": time.time(),
        }

    def feed_raw(self, chunk: np.ndarray) -> None:
        with self._lock:
            if self._pending is not None and self._pending_active:
                if self._pending["raw_samples"] + chunk.size <= self._max_samples:
                    self._pending["raw"].append(chunk)
                    self._pending["raw_samples"] += chunk.size
                else:
                    self._pending["truncated"] = True
            elif self._ring_enabled:
                self._ring.append(chunk)

    def on_capture_event(self, event: str) -> None:
        with self._lock:
            if event == "vad_start":
                # A previous accumulation that never got a segment (kerchunk)
                # is discarded by overwriting it here.
                rec = self._new_record()
                rec["raw"] = list(self._ring)
                rec["raw_samples"] = sum(c.size for c in rec["raw"])
                self._ring.clear()
                self._pending = rec
                self._pending_active = True
                # Records that never finalized (e.g. TX pause mid-utterance)
                # would otherwise accumulate forever. Log on eviction so a
                # missing capture isn't a silent mystery later.
                while len(self._records) > 16:
                    stale_uid = next(iter(self._records))
                    self._records.pop(stale_uid)
                    _log.warning(
                        "debug_capture: evicting stale unfinalized record uid=%s "
                        "(never finalized — capture discarded)", stale_uid
                    )
            elif event == "vad_end":
                # Keep _pending: the final segment arrives after this event
                # (same feed() call, events are processed first) and still
                # needs to bind. Only stop raw accumulation.
                self._pending_active = False

    def on_segment(self, uid: int, audio: np.ndarray, is_final: bool) -> None:
        with self._lock:
            rec = self._records.get(uid)
            if rec is None:
                # First segment binds the pending accumulation; _pending keeps
                # pointing at the same dict so raw audio accrues until vad_end.
                rec = self._pending if self._pending is not None else self._new_record()
                self._records[uid] = rec
            rec["segments"].append(audio)

    def on_processed(self, uid: int, audio: np.ndarray) -> None:
        with self._lock:
            rec = self._records.get(uid)
            if rec is not None:
                rec["processed"].append(audio)

    def on_transcript(self, uid: int, text: str, partial: bool) -> None:
        with self._lock:
            rec = self._records.get(uid)
            if rec is not None:
                rec["transcripts"].append(
                    {"text": text, "partial": bool(partial), "t": time.time()}
                )

    def finalize(self, uid: int) -> Path | None:
        """Write the utterance directory and drop the record. Returns the
        directory path, or None if the uid was never seen or writing failed.
        """
        with self._lock:
            rec = self._records.pop(uid, None)
        if rec is None:
            return None
        try:
            utt_dir = self._out_dir / f"utt_{int(rec['started_at'] * 1000)}_{uid:04d}"
            utt_dir.mkdir(parents=True, exist_ok=True)
            self._write_wav(utt_dir / "raw.wav", rec["raw"])
            self._write_wav(utt_dir / "segmented.wav", rec["segments"])
            self._write_wav(utt_dir / "processed.wav", rec["processed"])
            payload = {
                "utterance_id": uid,
                "sample_rate": self._sample_rate,
                "started_at": rec["started_at"],
                "truncated": rec["truncated"],
                "meta": self._meta,
                "transcripts": rec["transcripts"],
            }
            (utt_dir / "transcript.json").write_text(json.dumps(payload, indent=2))
            return utt_dir
        except Exception as exc:
            _log.warning("Debug capture write failed for uid %s: %s", uid, exc)
            return None

    def _write_wav(self, path: Path, chunks: list[np.ndarray]) -> None:
        audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
        pcm = (np.clip(audio, -1.0, 1.0) * 32767.0).astype(np.int16)
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self._sample_rate)
            w.writeframes(pcm.tobytes())
