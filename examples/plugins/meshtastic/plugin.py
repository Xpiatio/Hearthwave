"""Meshtastic — example Hearthwave plugin (LoRa mesh bridge + position source).

Reference plugin, sibling to the MeshCore example. Mirrors every accepted radio
transmission onto a Meshtastic mesh, prefixed with the sender's name, and
optionally reads the radio's node database for other nodes' GPS positions.
Serial-only. Mutually exclusive with MeshCore (one serial mesh radio at a time)
— declared via the manifest's `conflicts_with`, enforced by the host.

The `meshtastic` Python API is synchronous/blocking (pubsub + a blocking serial
reader), so interface construction, every send, and the node-database read run
in a thread executor to keep the event loop responsive. Imported lazily. Verify
the two library calls (SerialInterface ctor + sendText channel arg) and the true
max text length against your installed meshtastic version / firmware.

Position RX polls `iface.nodes` rather than subscribing to
`meshtastic.receive.position`: the node database already accumulates every
position the radio has heard, and polling keeps the callback off the library's
serial reader thread. The record shape below was read from meshtastic 2.7.11 —
`nodes` is keyed by node ID string and each value is a `MessageToDict` of the
NodeInfo protobuf, hence the camelCase keys and the float `latitude`/`longitude`
that `_fixupPosition` derives from the integer `latitudeI`/`longitudeI`.
Because MessageToDict omits zero-valued fields, a node sitting at exactly 0°
has no coordinate key at all — which is indistinguishable from no fix, and is
handled the same way.
"""
from __future__ import annotations

import asyncio
import logging

from backend.plugins.sdk import (
    MIN_POLL_SECONDS,
    ConfigField,
    MeshForwardConfig,
    MeshForwarderPlugin,
    MeshTransport,
    PluginManifest,
    PositionPoller,
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

    async def read_nodes(self) -> list[dict]:
        """Snapshot the radio's node database.

        Copied in the executor rather than handed out by reference: the
        library's serial reader thread mutates these dicts as packets arrive,
        so iterating the live mapping from the event loop would race.
        """
        if not self._connected or self._iface is None:
            return []
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._snapshot_nodes)

    def _snapshot_nodes(self) -> list[dict]:
        nodes = getattr(self._iface, "nodes", None) or {}
        snapshot = []
        for node_id, node in list(nodes.items()):
            if not isinstance(node, dict):
                continue
            position = node.get("position")
            user = node.get("user")
            snapshot.append({
                "id": node_id,
                "long_name": (user or {}).get("longName", ""),
                "short_name": (user or {}).get("shortName", ""),
                "position": dict(position) if isinstance(position, dict) else None,
                "last_heard": node.get("lastHeard"),
                "snr": node.get("snr"),
            })
        return snapshot


class MeshtasticPlugin(MeshForwarderPlugin):
    """Forward accepted TX onto a Meshtastic mesh (see module docstring)."""

    manifest = PluginManifest(
        id=PLUGIN_ID,
        name="Meshtastic",
        description="Mirror every accepted transmission onto a Meshtastic LoRa mesh, "
        "prefixed with the sender's name. Serial-connected radio. Can also read "
        "other nodes' GPS positions for the map.",
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
            ConfigField("position_rx_enabled", "Show node positions on the map", "bool", False,
                        help="Read the radio's node database and plot nodes that have a GPS fix."),
            ConfigField("position_poll_seconds", "Position poll interval", "number", 60,
                        minimum=MIN_POLL_SECONDS,
                        help="Seconds between node-database reads."),
        ),
        tx_composition={
            "max_len_key": "max_packet_length",
            "separator_key": "prefix_separator",
            "hint": "Meshtastic",
        },
    )

    def __init__(self) -> None:
        super().__init__()
        self._poller = PositionPoller(
            PLUGIN_ID,
            self._poll_nodes,
            ctx_getter=lambda: getattr(self, "ctx", None),
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

    # -- position RX ----------------------------------------------------
    async def on_config_changed(self, config) -> None:
        # The forwarder half owns the serial link, so it runs first — the
        # poller has nothing to read until the transport is up.
        await super().on_config_changed(config)
        c = config.plugin_config(PLUGIN_ID)
        await self._poller.configure(
            enabled=bool(c.get("enabled", False)) and bool(c.get("position_rx_enabled", False)),
            poll_seconds=float(c.get("position_poll_seconds", 60)),
        )

    async def on_unload(self) -> None:
        await self._poller.stop()
        await super().on_unload()

    async def _poll_nodes(self) -> None:
        transport = self._transport
        if not isinstance(transport, MeshtasticClient) or not transport.is_connected:
            return
        for node in await transport.read_nodes():
            await self._report_node(node)

    async def _report_node(self, node: dict) -> None:
        lat, lon = _node_coords(node.get("position"))
        if lat is None or lon is None:
            return
        position = node.get("position") or {}
        extra = {}
        if node.get("snr") is not None:
            extra["snr"] = f"{float(node['snr']):.1f} dB"
        if node.get("short_name"):
            extra["short_name"] = node["short_name"]
        await self._poller.report(
            node.get("id") or "",
            lat,
            lon,
            label=node.get("long_name") or node.get("short_name") or "",
            alt_m=position.get("altitude"),
            # When our radio heard it, not when we read the database — the node
            # DB keeps nodes for days, so polling it is not a hearing.
            heard_at=node.get("last_heard"),
            **extra,
        )


def _node_coords(position) -> tuple[float | None, float | None]:
    """Pull float coordinates out of a Meshtastic position dict.

    Prefers the float keys the library derives, falling back to the raw
    1e-7-degree integers in case a future version stops deriving them.
    """
    if not isinstance(position, dict):
        return None, None
    lat, lon = position.get("latitude"), position.get("longitude")
    if lat is None and position.get("latitudeI") is not None:
        lat = position["latitudeI"] * 1e-7
    if lon is None and position.get("longitudeI") is not None:
        lon = position["longitudeI"] * 1e-7
    try:
        return (None if lat is None else float(lat), None if lon is None else float(lon))
    except (TypeError, ValueError):
        return None, None
