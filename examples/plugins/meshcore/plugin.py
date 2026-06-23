"""MeshCore — example Hearthwave plugin (outbound LoRa mesh bridge).

This is a reference plugin: it shows how to write a real, installable Hearthwave
plugin against the public SDK. Drop this directory into /data/plugins/ and it loads.

What it does: mirrors every accepted radio transmission onto a MeshCore mesh,
prefixed with the sender's name, clamped to the mesh packet limit, forwarded
without ever delaying the radio TX path. Outbound only — received radio traffic
is never forwarded.

Everything mechanical (prefix build, length clamp, non-blocking queue, sender
task, connect/disconnect lifecycle) comes from the SDK's MeshForwarderPlugin; this
file supplies only the serial transport + the config mapping + the manifest.

The MeshCore Companion serial protocol is spoken via the optional `meshcore`
Python package, imported lazily so the plugin loads even when it's absent (the
error surfaces only when you enable it). Verify the two library calls (create +
send) against your installed meshcore version / firmware.
"""
from __future__ import annotations

import logging

from backend.plugins.sdk import (
    ConfigField,
    MeshForwardConfig,
    MeshForwarderPlugin,
    MeshTransport,
    PluginManifest,
)

_log = logging.getLogger(__name__)

PLUGIN_ID = "meshcore"


class MeshCoreClient(MeshTransport):
    """Serial link to a MeshCore Companion radio."""

    def __init__(self, port: str, baud: int) -> None:
        self.port = port
        self.baud = baud
        self._mc = None
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

    manifest = PluginManifest(
        id=PLUGIN_ID,
        name="MeshCore",
        description="Mirror every accepted transmission onto a MeshCore LoRa mesh, "
        "prefixed with the sender's name. Serial-connected Companion radio.",
        conflicts_with=("meshtastic",),
        config_schema=(
            ConfigField("serial_port", "MeshCore device", "text", "/dev/ttyUSB0",
                        help="MeshCore Companion serial device, e.g. /dev/ttyUSB0"),
            ConfigField("baud", "Baud rate", "number", 115200, minimum=1),
            ConfigField("max_packet_length", "Max packet length", "number", 140, minimum=1,
                        help="Characters per mesh packet, including the sender prefix."),
            ConfigField("channel_idx", "Channel index", "number", 0, minimum=0),
            ConfigField("prefix_separator", "Name separator", "text", ": ",
                        help='Joins the sender name and message, e.g. ": " → "Ben: hello"'),
        ),
        tx_composition={
            "max_len_key": "max_packet_length",
            "separator_key": "prefix_separator",
            "hint": "MeshCore",
        },
    )

    def _read_config(self, config) -> MeshForwardConfig:
        c = config.plugin_config(PLUGIN_ID)
        return MeshForwardConfig(
            enabled=bool(c.get("enabled", False)),
            max_packet_length=int(c.get("max_packet_length", 140)),
            prefix_separator=c.get("prefix_separator", ": "),
            channel_idx=int(c.get("channel_idx", 0)),
        )

    def _make_transport(self, config) -> MeshTransport:
        c = config.plugin_config(PLUGIN_ID)
        return MeshCoreClient(
            port=c.get("serial_port", "/dev/ttyUSB0"),
            baud=int(c.get("baud", 115200)),
        )

    def _transport_key(self, config):
        c = config.plugin_config(PLUGIN_ID)
        return (c.get("serial_port", "/dev/ttyUSB0"), int(c.get("baud", 115200)))
