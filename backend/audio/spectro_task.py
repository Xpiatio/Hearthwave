"""Asyncio spectrogram streaming task.

Receives raw audio chunks from the STT worker (thread-safe push_chunk),
computes FFT frames via ChunkRing, extracts the configured frequency band,
normalizes to uint8, and broadcasts spectrogram_row WS messages at up to 20 Hz.

Each broadcast includes live VAD and squelch state flags so the frontend can
draw colour overlays on the waterfall without a separate channel.
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

import numpy as np

from backend.audio.spectrogram import (
    DEFAULT_FRAME_SIZE,
    DEFAULT_HOP_SIZE,
    DEFAULT_SAMPLE_RATE,
    MIN_DB,
    ChunkRing,
    bin_range_for_band,
    compute_frame,
    hann_window,
    magnitude_to_db,
)

# Output width: always 256 values, regardless of freq_range.
_BINS = 256
# Poll interval — limits WS output to ≤ 20 rows/second.
_POLL_INTERVAL = 0.05

# Named frequency bands (Hz).
FREQ_BANDS: dict[str, tuple[float, float]] = {
    "voice": (300.0, 3400.0),
    "full": (0.0, 8000.0),
}


class SpectroTask:
    """Consumes audio chunks and streams spectrogram rows to WS clients.

    push_chunk() is thread-safe — called from the STT worker thread.
    run() is an asyncio coroutine that must be wrapped in an asyncio.Task.

    The ``vad_fn`` and ``squelch_fn`` callables are invoked once per poll
    cycle and their current boolean values are included in every broadcasted
    row during that cycle.
    """

    def __init__(
        self,
        broadcast_fn: Callable[[dict], Awaitable[None]],
        freq_range: str = "full",
        vad_fn: Callable[[], bool] | None = None,
        squelch_fn: Callable[[], bool] | None = None,
    ) -> None:
        self._ring = ChunkRing(frame_size=DEFAULT_FRAME_SIZE, hop_size=DEFAULT_HOP_SIZE)
        self._window = hann_window(DEFAULT_FRAME_SIZE)
        self._broadcast_fn = broadcast_fn
        self._vad_fn = vad_fn
        self._squelch_fn = squelch_fn
        lo_hz, hi_hz = FREQ_BANDS.get(freq_range, FREQ_BANDS["full"])
        self._lo_bin, self._hi_bin = bin_range_for_band(
            DEFAULT_FRAME_SIZE, DEFAULT_SAMPLE_RATE, lo_hz, hi_hz
        )

    def set_freq_range(self, freq_range: str) -> None:
        """Update the displayed frequency band (safe to call from asyncio context)."""
        lo_hz, hi_hz = FREQ_BANDS.get(freq_range, FREQ_BANDS["full"])
        self._lo_bin, self._hi_bin = bin_range_for_band(
            DEFAULT_FRAME_SIZE, DEFAULT_SAMPLE_RATE, lo_hz, hi_hz
        )

    def push_chunk(self, chunk: np.ndarray) -> None:
        """Push a raw audio chunk. Thread-safe; called from STT worker thread."""
        self._ring.push(chunk)

    async def run(self) -> None:
        """Poll the ring at 20 Hz, compute FFT frames, broadcast rows."""
        try:
            while True:
                await asyncio.sleep(_POLL_INTERVAL)
                rows: list[list[int]] = []
                lo, hi = self._lo_bin, self._hi_bin
                while True:
                    frame = self._ring.pop_frame()
                    if frame is None:
                        break
                    spectrum = compute_frame(frame, self._window)
                    db_row = magnitude_to_db(spectrum)
                    band = db_row[lo:hi]
                    resampled = _resample(band, _BINS)
                    rows.append(_db_to_uint8(resampled).tolist())

                if not rows:
                    continue

                vad = self._vad_fn() if self._vad_fn else False
                squelch = self._squelch_fn() if self._squelch_fn else False
                for row in rows:
                    await self._broadcast_fn({
                        "type": "spectrogram_row",
                        "row": row,
                        "vad": vad,
                        "squelch": squelch,
                    })
        except asyncio.CancelledError:
            pass


def _resample(band: np.ndarray, target: int) -> np.ndarray:
    """Linearly resample *band* to exactly *target* values."""
    n = len(band)
    if n == target:
        return band
    if n == 0:
        return np.zeros(target, dtype=np.float32)
    indices = np.linspace(0, n - 1, target)
    return np.interp(indices, np.arange(n), band).astype(np.float32)


def _db_to_uint8(db_row: np.ndarray) -> np.ndarray:
    """Map MIN_DB → 0, 0 dBFS → 255 and clamp to uint8."""
    normalized = (db_row - MIN_DB) / (-MIN_DB)
    return (np.clip(normalized, 0.0, 1.0) * 255).astype(np.uint8)
