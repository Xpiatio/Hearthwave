"""Pure FFT + ring-buffer helpers for the rolling RX spectrometer.

Kept dependency-free (only numpy) so the STT worker tap and unit tests can
use it without any audio framework.

Pipeline:
    capture chunk (512 samples @ 16 kHz)
        └─► ChunkRing  ─►  compute_frame(...)  ─►  rfft + Hann + dB  ─►  row

The ring accumulates chunks until enough samples are available for one FFT
frame (frame_size samples), then slides forward by hop_size samples per frame.
Defaults: 1024-sample frame with 50% overlap at 16 kHz — hop every ~32 ms.
"""
from __future__ import annotations

import threading

import numpy as np


DEFAULT_FRAME_SIZE = 1024
DEFAULT_HOP_SIZE = 512
DEFAULT_SAMPLE_RATE = 16000
# Silent inputs would produce -inf; clamp to MIN_DB instead.
MIN_DB = -120.0


def hann_window(n: int) -> np.ndarray:
    """Symmetric Hann window of length n."""
    if n <= 0:
        raise ValueError("hann_window length must be positive")
    if n == 1:
        return np.ones(1, dtype=np.float32)
    return (0.5 - 0.5 * np.cos(2.0 * np.pi * np.arange(n) / (n - 1))).astype(np.float32)


def magnitude_to_db(magnitudes: np.ndarray, ref: float = 1.0) -> np.ndarray:
    """Convert linear magnitude spectra to dB with a floor at MIN_DB."""
    if magnitudes.size == 0:
        return magnitudes.astype(np.float32)
    safe = np.maximum(magnitudes, 1e-12)
    db = 20.0 * np.log10(safe / max(ref, 1e-12))
    return np.maximum(db, MIN_DB).astype(np.float32)


def compute_frame(samples: np.ndarray, window: np.ndarray) -> np.ndarray:
    """Hann-window + rfft a single frame; returns linear magnitude spectrum."""
    if samples.shape[0] != window.shape[0]:
        raise ValueError(
            f"frame length {samples.shape[0]} != window length {window.shape[0]}"
        )
    windowed = samples.astype(np.float32) * window
    spectrum = np.fft.rfft(windowed)
    return np.abs(spectrum).astype(np.float32)


class ChunkRing:
    """Thread-safe sample accumulator that emits fixed-size FFT frames.

    push() accepts variable chunk sizes; pop_frame() returns one frame_size
    window at a time, advancing by hop_size. When the ring fills past
    capacity, oldest samples are dropped — the spectrometer never
    back-pressures the capture loop.
    """

    def __init__(
        self,
        frame_size: int = DEFAULT_FRAME_SIZE,
        hop_size: int = DEFAULT_HOP_SIZE,
        capacity_frames: int = 16,
    ) -> None:
        if frame_size <= 0:
            raise ValueError("frame_size must be positive")
        if hop_size <= 0 or hop_size > frame_size:
            raise ValueError("hop_size must be in (0, frame_size]")
        if capacity_frames < 1:
            raise ValueError("capacity_frames must be >= 1")
        self.frame_size = int(frame_size)
        self.hop_size = int(hop_size)
        self.capacity_samples = self.frame_size + self.hop_size * int(capacity_frames)
        self._buf = np.zeros(self.capacity_samples, dtype=np.float32)
        self._start = 0
        self._fill = 0
        self._lock = threading.Lock()
        self.dropped_samples = 0

    def push(self, chunk: np.ndarray) -> None:
        """Append chunk; older samples are evicted when capacity is reached."""
        if chunk is None or chunk.size == 0:
            return
        data = np.asarray(chunk, dtype=np.float32).reshape(-1)
        with self._lock:
            n = data.size
            cap = self.capacity_samples
            total = self._fill + n
            if total > cap:
                drop = total - cap
                drop = ((drop + self.hop_size - 1) // self.hop_size) * self.hop_size
                if drop <= self._fill:
                    self._start = (self._start + drop) % cap
                    self._fill -= drop
                    self.dropped_samples += drop
                else:
                    from_input = min(drop - self._fill, n)
                    self.dropped_samples += self._fill + from_input
                    self._start = 0
                    self._fill = 0
                    data = data[from_input:]
                    n = data.size
            write_pos = (self._start + self._fill) % cap
            space_to_end = cap - write_pos
            if n <= space_to_end:
                self._buf[write_pos:write_pos + n] = data
            else:
                self._buf[write_pos:] = data[:space_to_end]
                self._buf[:n - space_to_end] = data[space_to_end:]
            self._fill += n

    def pop_frame(self) -> np.ndarray | None:
        """Return one frame_size window and advance by hop_size, or None."""
        with self._lock:
            if self._fill < self.frame_size:
                return None
            cap = self.capacity_samples
            end = self._start + self.frame_size
            if end <= cap:
                frame = self._buf[self._start:end].copy()
            else:
                frame = np.empty(self.frame_size, dtype=np.float32)
                first = cap - self._start
                frame[:first] = self._buf[self._start:]
                frame[first:] = self._buf[:self.frame_size - first]
            self._start = (self._start + self.hop_size) % cap
            self._fill -= self.hop_size
            return frame

    def clear(self) -> None:
        with self._lock:
            self._start = 0
            self._fill = 0


def frequency_bins(frame_size: int, sample_rate: int) -> np.ndarray:
    """Return center frequency (Hz) of every rfft bin."""
    return np.fft.rfftfreq(frame_size, d=1.0 / sample_rate).astype(np.float32)


def bin_range_for_band(
    frame_size: int, sample_rate: int, low_hz: float, high_hz: float
) -> tuple[int, int]:
    """Return (lo_bin, hi_bin_exclusive) for a frequency band."""
    nyquist = sample_rate / 2.0
    low = max(0.0, min(low_hz, nyquist))
    high = max(low, min(high_hz, nyquist))
    bins = frequency_bins(frame_size, sample_rate)
    lo = int(np.searchsorted(bins, low, side="left"))
    hi = int(np.searchsorted(bins, high, side="right"))
    if hi <= lo:
        hi = min(lo + 1, bins.size)
    return lo, hi
