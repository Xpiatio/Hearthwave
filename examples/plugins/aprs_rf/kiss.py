"""KISS deframer — turns a TNC byte stream into AX.25 frames.

KISS (Kantronics/Chepponis-Karn) wraps each frame between FEND bytes, escaping
any FEND or FESC that occurs inside it. The first byte of a frame is a command
byte: high nibble = port, low nibble = command, where 0 means "data frame".
Only data frames carry AX.25; everything else (TXDELAY, persistence, ...) is a
host-to-TNC control byte and is dropped.

The deframer is fed arbitrary chunks — a frame may span several reads, and a
read may hold several frames — so it keeps its state between calls.
"""
from __future__ import annotations

FEND = 0xC0
FESC = 0xDB
TFEND = 0xDC
TFESC = 0xDD

CMD_DATA = 0x00

#: A frame longer than this is a stuck stream, not AX.25 (the AX.25 spec caps
#: the info field at 256 bytes; direwolf and friends never exceed ~1 kB). The
#: overrun is dropped rather than buffered, so a noisy link can't eat memory.
MAX_FRAME_BYTES = 1024


class KissDeframer:
    """Incremental KISS deframer. Feed bytes, get complete AX.25 frames back."""

    def __init__(self, max_frame_bytes: int = MAX_FRAME_BYTES) -> None:
        self._max_frame_bytes = max_frame_bytes
        self._buf = bytearray()
        self._in_frame = False
        self._escaped = False
        self._overrun = False

    def reset(self) -> None:
        """Drop any partial frame. Call after a reconnect."""
        self._buf.clear()
        self._in_frame = False
        self._escaped = False
        self._overrun = False

    def feed(self, chunk: bytes) -> list[bytes]:
        """Return every complete data frame contained in *chunk*, unescaped."""
        frames: list[bytes] = []
        for byte in chunk:
            if byte == FEND:
                # FEND both ends the frame in progress and opens the next one;
                # back-to-back FENDs (idle padding) yield an empty frame we skip.
                frame = self._finish()
                if frame is not None:
                    frames.append(frame)
                self.reset()
                self._in_frame = True
                continue
            if not self._in_frame:
                continue  # noise before the first FEND
            if self._escaped:
                self._escaped = False
                if byte == TFEND:
                    byte = FEND
                elif byte == TFESC:
                    byte = FESC
                else:
                    # Invalid escape: the frame is corrupt, so drop it rather
                    # than hand a mangled one to the AX.25 decoder.
                    self._overrun = True
                    continue
            elif byte == FESC:
                self._escaped = True
                continue
            if len(self._buf) >= self._max_frame_bytes:
                self._overrun = True
                continue
            self._buf.append(byte)
        return frames

    def _finish(self) -> bytes | None:
        if not self._in_frame or self._overrun or len(self._buf) < 2:
            return None
        if self._buf[0] & 0x0F != CMD_DATA:
            return None
        return bytes(self._buf[1:])
