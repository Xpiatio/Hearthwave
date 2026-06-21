"""MeshCore plugin — mirrors accepted radio TX onto a MeshCore LoRa mesh.

Outbound only: every transmission that passes the TX gate chain is forwarded to
the mesh, prefixed with the sender's name. RX radio traffic is never forwarded.
All of the forwarding mechanics (prefix build, length clamp, non-blocking queue,
sender task, enable/disable lifecycle) come from MeshForwarderPlugin — this
module only maps the meshcore_* config keys and supplies the serial transport.

The MeshCore Companion serial protocol is spoken via the optional `meshcore`
Python package, imported lazily so the rest of the app runs without it. The two
calls into that library (create + send) are the only protocol-specific surface;
their exact signatures should be verified against the installed meshcore version
and the firmware in use.
"""
from __future__ import annotations

import logging

from backend.plugins.mesh_forwarder import (
    MeshForwardConfig,
    MeshForwarderPlugin,
    MeshTransport,
)

_log = logging.getLogger(__name__)


class MeshCoreClient(MeshTransport):
    """Serial link to a MeshCore Companion radio."""

    def __init__(self, port: str, baud: int) -> None:
        self.port = port
        self.baud = baud
        self._mc = None  # underlying meshcore companion handle
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        try:
            from meshcore import MeshCore  # optional dependency
        except ImportError as exc:  # pragma: no cover - env-dependent
            raise RuntimeError(
                "meshcore package not installed — `pip install meshcore` to enable "
                "the MeshCore plugin"
            ) from exc
        # NOTE: verify against the installed meshcore-py API / firmware.
        self._mc = await MeshCore.create_serial(self.port, self.baud)
        self._connected = True
        _log.info("MeshCore connected on %s @ %d", self.port, self.baud)

    async def disconnect(self) -> None:
        if self._mc is not None:
            try:
                await self._mc.disconnect()
            except Exception:  # pragma: no cover - best-effort teardown
                _log.exception("MeshCore disconnect failed")
            self._mc = None
        self._connected = False

    async def send_text(self, text: str, channel: int) -> None:
        if not self._connected or self._mc is None:
            raise RuntimeError("MeshCore not connected")
        # NOTE: verify against the installed meshcore-py API / firmware.
        await self._mc.commands.send_chan_msg(channel, text)


class MeshCorePlugin(MeshForwarderPlugin):
    """Forward accepted TX onto a MeshCore mesh (see module docstring)."""

    def _read_config(self, config) -> MeshForwardConfig:
        return MeshForwardConfig(
            enabled=config.meshcore_enabled,
            max_packet_length=config.meshcore_max_packet_length,
            prefix_separator=config.meshcore_prefix_separator,
            channel_idx=config.meshcore_channel_idx,
        )

    def _make_transport(self, config) -> MeshTransport:
        return MeshCoreClient(port=config.meshcore_serial_port, baud=config.meshcore_baud)

    def _transport_key(self, config):
        # Rebuild the serial link when the port or baud changes.
        return (config.meshcore_serial_port, config.meshcore_baud)
