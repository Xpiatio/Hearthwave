"""Shared base for outbound-only mesh-bridge plugins.

MeshCore and Meshtastic both mirror every accepted radio transmission onto a LoRa
mesh, prefixed with the sender's name, clamped to the mesh packet limit, and
forwarded without ever delaying or altering the radio TX path. The only thing
that differs between them is the serial wire protocol.

`MeshForwarderPlugin` owns everything shared — prefix build, length clamp, a
non-blocking outbound queue, the background sender task, and the enable/disable
lifecycle. A concrete subclass supplies just two things:

    _read_config(config) -> MeshForwardConfig   # map ServerConfig keys
    _make_transport(config) -> MeshTransport     # the protocol-specific link

Outbound only: RX radio traffic is never forwarded (we hook the TX path, not RX).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from backend.plugins.base import BasePlugin

_log = logging.getLogger(__name__)

# Cap the outbound queue so a wedged link (connected but send_text hangs) can't
# grow memory without bound. Forwarding is best-effort, so dropping the oldest-
# pending copies is acceptable.
_OUTBOUND_QUEUE_MAX = 128


class MeshTransport:
    """Protocol-specific link to a mesh network. Subclass once per radio type."""

    async def connect(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    async def disconnect(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    async def send_text(self, text: str, channel: int) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    @property
    def is_connected(self) -> bool:  # pragma: no cover - interface
        raise NotImplementedError


@dataclass
class MeshForwardConfig:
    """The subset of config a forwarder needs, mapped from ServerConfig by a subclass."""

    enabled: bool
    max_packet_length: int
    prefix_separator: str
    channel_idx: int


class MeshForwarderPlugin(BasePlugin):
    """Forwards every accepted TX onto a mesh, prefixed with the sender's name."""

    def __init__(self) -> None:
        # No-arg construction: the loader binds self.ctx before setup(). Config is
        # read live via self.ctx.get_config() (the TX hook has no config argument).
        self._transport: MeshTransport | None = None
        self._transport_key_active = None
        self._queue: asyncio.Queue | None = asyncio.Queue(maxsize=_OUTBOUND_QUEUE_MAX)
        self._sender_task: asyncio.Task | None = None

    # -- subclass extension points -------------------------------------
    def _read_config(self, config) -> MeshForwardConfig:
        raise NotImplementedError

    def _make_transport(self, config) -> MeshTransport:
        raise NotImplementedError

    def _transport_key(self, config):
        """Hashable identity of the connection params. When it changes, the live
        transport is rebuilt. Override in subclasses that have reconnectable
        params (e.g. MeshCore returns (port, baud)); the default never rebuilds."""
        return None

    # -- message assembly ----------------------------------------------
    @staticmethod
    def _sender_name(payload: dict) -> str:
        return (
            payload.get("_display_name")
            or payload.get("operator")
            or payload.get("callsign")
            or ""
        )

    def build_message(self, payload: dict, cfg: MeshForwardConfig) -> str:
        """Build the name-prefixed packet body, clamped to the mesh max length.

        The limit is in UTF-8 bytes (what the mesh radios actually measure on the
        wire), not characters: a name or message with multibyte glyphs encodes to
        more bytes than its character count, and the radio libs reject an oversized
        payload rather than truncate it. We clamp on encoded length and never split
        a multibyte sequence, so the result is always valid UTF-8 within the cap.
        """
        name = self._sender_name(payload)
        prefix = f"{name}{cfg.prefix_separator}" if name else ""
        body = prefix + (payload.get("text") or "")
        return self._clamp_utf8_bytes(body, cfg.max_packet_length)

    @staticmethod
    def _clamp_utf8_bytes(text: str, max_bytes: int) -> str:
        """Truncate to at most max_bytes of UTF-8 without splitting a code point."""
        encoded = text.encode("utf-8")
        if len(encoded) <= max_bytes:
            return text
        # "ignore" drops the partial multibyte sequence left at the truncation
        # boundary, guaranteeing valid UTF-8 no longer than max_bytes.
        return encoded[:max_bytes].decode("utf-8", "ignore")

    # -- lifecycle (on_config_changed) ---------------------------------
    async def on_config_changed(self, config) -> None:
        cfg = self._read_config(config)
        if cfg.enabled:
            await self._ensure_connected(config)
        else:
            await self._teardown()

    async def on_unload(self) -> None:
        """Drop the serial link + sender task when unloaded (hot-reload/uninstall)."""
        await self._teardown()

    async def _ensure_connected(self, config) -> None:
        key = self._transport_key(config)
        # Connection params changed (e.g. serial port) — drop the stale link so
        # the new params take effect without a server restart.
        if self._transport is not None and key != self._transport_key_active:
            await self._teardown()
        if self._transport is None:
            self._transport = self._make_transport(config)
            self._transport_key_active = key
        if not self._transport.is_connected:
            await self._transport.connect()
        if self._queue is None:
            self._queue = asyncio.Queue(maxsize=_OUTBOUND_QUEUE_MAX)
        if self._sender_task is None or self._sender_task.done():
            self._sender_task = asyncio.create_task(self._sender_loop(), name="mesh-sender")

    async def _teardown(self) -> None:
        if self._sender_task is not None:
            self._sender_task.cancel()
            self._sender_task = None
        if self._transport is not None and self._transport.is_connected:
            await self._transport.disconnect()
        # Clear the handle so the next enable rebuilds from current config.
        self._transport = None
        self._transport_key_active = None

    # -- TX forwarding (never blocks the radio path) -------------------
    async def on_audio_tx_pre_queue(self, payload: dict) -> dict | None:
        try:
            cfg = self._read_config(self.ctx.get_config())
            if (
                cfg.enabled
                and self._transport is not None
                and self._transport.is_connected
            ):
                try:
                    self._queue.put_nowait((self.build_message(payload, cfg), cfg.channel_idx))
                except asyncio.QueueFull:
                    _log.warning("mesh outbound queue full; dropping forwarded message")
        except Exception:
            # Forwarding is best-effort; a mesh hiccup must never delay or drop TX.
            _log.exception("mesh forward enqueue failed")
        return payload

    async def _sender_loop(self) -> None:
        assert self._queue is not None
        while True:
            text, channel = await self._queue.get()
            try:
                if self._transport is not None:
                    await self._transport.send_text(text, channel)
            except Exception:
                _log.exception("mesh send_text failed")
            finally:
                self._queue.task_done()
