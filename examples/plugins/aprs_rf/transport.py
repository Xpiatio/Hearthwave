"""KISS links — where the TNC byte stream comes from.

Two ways in, both receive-only as far as this plugin is concerned: a KISS TCP
port (direwolf, `KISSPORT 8001` by default) or a serial TNC. Both present the
same three calls so the plugin doesn't care which is configured.

``close()`` is deliberately synchronous. It runs from the ``finally`` of a read
loop that is usually being cancelled, and awaiting anything there risks a second
CancelledError before the socket is released.
"""
from __future__ import annotations

import asyncio
import logging

_log = logging.getLogger(__name__)

CONNECT_TIMEOUT_S = 10.0
READ_BYTES = 4096

#: Serial read timeout. Short enough that a cancelled poll loop's worker thread
#: retires promptly, long enough not to spin on an idle TNC.
SERIAL_READ_TIMEOUT_S = 0.5


class KissLink:
    """Byte source for the deframer."""

    description = "kiss"

    async def open(self) -> None:
        raise NotImplementedError

    async def read(self) -> bytes:
        """Return the next bytes read, possibly empty. Raises on a dead link."""
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class KissTcpLink(KissLink):
    """KISS over TCP — direwolf, soundmodem, or any KISS-over-network TNC."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.description = f"tcp {host}:{port}"
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    async def open(self) -> None:
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), timeout=CONNECT_TIMEOUT_S
        )
        _log.info("APRS RF: KISS TCP connected to %s:%d", self.host, self.port)

    async def read(self) -> bytes:
        if self._reader is None:
            raise ConnectionError("KISS TCP link is not open")
        chunk = await self._reader.read(READ_BYTES)
        if not chunk:
            raise ConnectionError(f"KISS TCP {self.host}:{self.port} closed the connection")
        return chunk

    def close(self) -> None:
        writer, self._writer, self._reader = self._writer, None, None
        if writer is not None:
            try:
                writer.close()
            except Exception:  # pragma: no cover - best-effort teardown
                _log.exception("APRS RF: KISS TCP close failed")


class KissSerialLink(KissLink):
    """KISS over a serial TNC. Blocking reads run in a worker thread."""

    def __init__(self, port: str, baud: int) -> None:
        self.port = port
        self.baud = baud
        self.description = f"serial {port} @ {baud}"
        self._ser = None

    async def open(self) -> None:
        try:
            import serial  # optional dependency (pyserial)
        except ImportError as exc:  # pragma: no cover - env-dependent
            raise RuntimeError(
                "pyserial not installed — `pip install pyserial` to use a serial TNC"
            ) from exc
        self._ser = await asyncio.to_thread(
            serial.Serial, self.port, self.baud, timeout=SERIAL_READ_TIMEOUT_S
        )
        _log.info("APRS RF: KISS serial opened on %s @ %d", self.port, self.baud)

    async def read(self) -> bytes:
        if self._ser is None:
            raise ConnectionError("KISS serial link is not open")
        return await asyncio.to_thread(self._read_blocking)

    def _read_blocking(self) -> bytes:
        ser = self._ser
        if ser is None:
            raise ConnectionError("KISS serial link closed mid-read")
        # One blocking byte (bounded by the port timeout), then drain whatever
        # else arrived with it, so a burst costs one thread hop rather than N.
        data = ser.read(1)
        waiting = getattr(ser, "in_waiting", 0)
        if waiting:
            data += ser.read(waiting)
        return data

    def close(self) -> None:
        ser, self._ser = self._ser, None
        if ser is not None:
            try:
                ser.close()
            except Exception:  # pragma: no cover - best-effort teardown
                _log.exception("APRS RF: KISS serial close failed")
