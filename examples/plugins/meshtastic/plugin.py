"""Meshtastic — example Hearthwave plugin (outbound LoRa mesh bridge).

Reference plugin, sibling to the MeshCore example. Mirrors every accepted radio
transmission onto a Meshtastic mesh, prefixed with the sender's name. Serial-only.
Mutually exclusive with MeshCore (one serial mesh radio at a time) — declared via
the manifest's `conflicts_with`, enforced by the host.

The `meshtastic` Python API is synchronous/blocking (pubsub + a blocking serial
reader), so interface construction and every send run in a thread executor to keep
the event loop responsive. Imported lazily. Verify the two library calls
(SerialInterface ctor + sendText channel arg) and the true max text length against
your installed meshtastic version / firmware.
"""
from __future__ import annotations

import asyncio
import logging

from backend.plugins.sdk import (
    ConfigField,
    MeshForwardConfig,
    MeshForwarderPlugin,
    MeshTransport,
    PluginManifest,
)

_log = logging.getLogger(__name__)

PLUGIN_ID = "meshtastic"


class MeshtasticClient(MeshTransport):
    """Serial link to a Meshtastic radio (blocking lib wrapped in an executor)."""

    def __init__(self, port: str) -> None:
        self.port = port
        self._iface = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        try:
            from meshtastic.serial_interface import SerialInterface  # optional dependency
        except ImportError as exc:  # pragma: no cover - env-dependent
            raise RuntimeError(
                "meshtastic package not installed — `pip install meshtastic` to "
                "enable the Meshtastic plugin"
            ) from exc
        loop = asyncio.get_event_loop()
        # NOTE: verify against the installed meshtastic API / firmware.
        self._iface = await loop.run_in_executor(
            None, lambda: SerialInterface(devPath=self.port)
        )
        self._connected = True
        _log.info("Meshtastic connected on %s", self.port)

    async def disconnect(self) -> None:
        if self._iface is not None:
            loop = asyncio.get_event_loop()
            try:
                await loop.run_in_executor(None, self._iface.close)
            except Exception:  # pragma: no cover - best-effort teardown
                _log.exception("Meshtastic disconnect failed")
            self._iface = None
        self._connected = False

    async def send_text(self, text: str, channel: int) -> None:
        if not self._connected or self._iface is None:
            raise RuntimeError("Meshtastic not connected")
        loop = asyncio.get_event_loop()
        # NOTE: verify against the installed meshtastic API / firmware.
        await loop.run_in_executor(
            None, lambda: self._iface.sendText(text, channelIndex=channel)
        )


class MeshtasticPlugin(MeshForwarderPlugin):
    """Forward accepted TX onto a Meshtastic mesh (see module docstring)."""

    manifest = PluginManifest(
        id=PLUGIN_ID,
        name="Meshtastic",
        description="Mirror every accepted transmission onto a Meshtastic LoRa mesh, "
        "prefixed with the sender's name. Serial-connected radio.",
        conflicts_with=("meshcore",),
        config_schema=(
            ConfigField("serial_port", "Meshtastic device", "text", "/dev/ttyUSB0",
                        help="Meshtastic serial device, e.g. /dev/ttyUSB0"),
            ConfigField("max_packet_length", "Max packet length", "number", 200, minimum=1,
                        help="UTF-8 bytes per mesh packet, including the sender prefix."),
            ConfigField("channel_idx", "Channel index", "number", 0, minimum=0,
                        help="0 is the primary channel."),
            ConfigField("prefix_separator", "Name separator", "text", ": ",
                        help='Joins the sender name and message, e.g. ": " → "Ben: hello"'),
        ),
        tx_composition={
            "max_len_key": "max_packet_length",
            "separator_key": "prefix_separator",
            "hint": "Meshtastic",
        },
    )

    def _read_config(self, config) -> MeshForwardConfig:
        c = config.plugin_config(PLUGIN_ID)
        return MeshForwardConfig(
            enabled=bool(c.get("enabled", False)),
            max_packet_length=int(c.get("max_packet_length", 200)),
            prefix_separator=c.get("prefix_separator", ": "),
            channel_idx=int(c.get("channel_idx", 0)),
        )

    def _make_transport(self, config) -> MeshTransport:
        c = config.plugin_config(PLUGIN_ID)
        return MeshtasticClient(port=c.get("serial_port", "/dev/ttyUSB0"))

    def _transport_key(self, config):
        c = config.plugin_config(PLUGIN_ID)
        return (c.get("serial_port", "/dev/ttyUSB0"),)
