"""Asyncio spectrogram streaming task.

Receives raw audio chunks from the STT worker (thread-safe push_chunk),
computes FFT frames via ChunkRing, normalizes to uint8, and broadcasts
spectrogram_row WS messages at up to 20 Hz.
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

import numpy as np

from backend.audio.spectrogram import (
    DEFAULT_FRAME_SIZE,
    DEFAULT_HOP_SIZE,
    MIN_DB,
    ChunkRing,
    compute_frame,
    hann_window,
    magnitude_to_db,
)

# Number of FFT bins to transmit (0–4 kHz with 1024-pt FFT @ 16 kHz).
_BINS = 256
# Poll interval — limits WS output to ≤ 20 rows/second.
_POLL_INTERVAL = 0.05


class SpectroTask:
    """Consumes audio chunks and streams spectrogram rows to WS clients.

    push_chunk() is thread-safe — called from the STT worker thread.
    run() is an asyncio coroutine that must be wrapped in an asyncio.Task.
    """

    def __init__(self, broadcast_fn: Callable[[dict], Awaitable[None]]) -> None:
        self._ring = ChunkRing(frame_size=DEFAULT_FRAME_SIZE, hop_size=DEFAULT_HOP_SIZE)
        self._window = hann_window(DEFAULT_FRAME_SIZE)
        self._broadcast_fn = broadcast_fn

    def push_chunk(self, chunk: np.ndarray) -> None:
        """Push a raw audio chunk. Thread-safe; called from STT worker thread."""
        self._ring.push(chunk)

    async def run(self) -> None:
        """Poll the ring at 20 Hz, compute FFT frames, broadcast rows."""
        try:
            while True:
                await asyncio.sleep(_POLL_INTERVAL)
                rows: list[list[int]] = []
                while True:
                    frame = self._ring.pop_frame()
                    if frame is None:
                        break
                    spectrum = compute_frame(frame, self._window)
                    db_row = magnitude_to_db(spectrum)
                    rows.append(_db_to_uint8(db_row[:_BINS]).tolist())
                for row in rows:
                    await self._broadcast_fn({"type": "spectrogram_row", "row": row})
        except asyncio.CancelledError:
            pass


def _db_to_uint8(db_row: np.ndarray) -> np.ndarray:
    """Map MIN_DB → 0, 0 dBFS → 255 and clamp to uint8."""
    normalized = (db_row - MIN_DB) / (-MIN_DB)
    return (np.clip(normalized, 0.0, 1.0) * 255).astype(np.uint8)
