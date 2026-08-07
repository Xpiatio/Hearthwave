"""MeshCore — example Hearthwave plugin (LoRa mesh bridge + position source).

This is a reference plugin: it shows how to write a real, installable Hearthwave
plugin against the public SDK. Drop this directory into /data/plugins/ and it loads.

What it does: mirrors every accepted radio transmission onto a MeshCore mesh,
prefixed with the sender's name, clamped to the mesh packet limit, forwarded
without ever delaying the radio TX path. Received mesh *messages* are never
forwarded into the app; the only inbound path is optional position RX, below.

Everything mechanical (prefix build, length clamp, non-blocking queue, sender
task, connect/disconnect lifecycle) comes from the SDK's MeshForwarderPlugin; this
file supplies only the serial transport + the config mapping + the manifest.

The MeshCore Companion serial protocol is spoken via the optional `meshcore`
Python package, imported lazily so the plugin loads even when it's absent (the
error surfaces only when you enable it). Verify the library calls (create, send,
get_contacts) against your installed meshcore version / firmware.

Position RX refreshes the contact list and reads each contact's advertised
coordinates. The record shape below was read from meshcore 2.3.8: the reader
decodes a CONTACT frame into `adv_lat` / `adv_lon` floats (raw int32 / 1e6)
alongside `public_key`, `adv_name` and `last_advert`, and MeshCore.contacts is
the accumulated mapping keyed by public key. A contact that has never advertised
a location decodes to exactly 0.0 / 0.0, which is indistinguishable from a node
genuinely sitting at null island — both are dropped.
"""
from __future__ import annotations

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

    async def read_contacts(self) -> list[dict]:
        """Refresh the radio's contact list and snapshot what it advertises.

        get_contacts() drives the refresh; MeshCore.contacts is the mapping the
        library accumulates from the resulting frames. The rows are copied
        rather than handed out by reference — the reader task keeps mutating
        the live dicts as adverts arrive.
        """
        if not self._connected or self._mc is None:
            return []
        # NOTE: verify against the installed meshcore-py API / firmware.
        await self._mc.commands.get_contacts()
        contacts = getattr(self._mc, "contacts", None) or {}
        return [
            {
                "public_key": contact.get("public_key") or key,
                "adv_name": contact.get("adv_name", ""),
                "adv_lat": contact.get("adv_lat"),
                "adv_lon": contact.get("adv_lon"),
                "last_advert": contact.get("last_advert"),
            }
            for key, contact in list(contacts.items())
            if isinstance(contact, dict)
        ]


class MeshCorePlugin(MeshForwarderPlugin):
    """Forward accepted TX onto a MeshCore mesh (see module docstring)."""

    manifest = PluginManifest(
        id=PLUGIN_ID,
        name="MeshCore",
        description="Mirror every accepted transmission onto a MeshCore LoRa mesh, "
        "prefixed with the sender's name. Serial-connected Companion radio. Can also "
        "read contacts' advertised positions for the map.",
        conflicts_with=("meshtastic",),
        config_schema=(
            ConfigField("serial_port", "MeshCore device", "text", "/dev/ttyUSB0",
                        help="MeshCore Companion serial device, e.g. /dev/ttyUSB0"),
            ConfigField("baud", "Baud rate", "number", 115200, minimum=1),
            ConfigField("max_packet_length", "Max packet length", "number", 140, minimum=1,
                        help="UTF-8 bytes per mesh packet, including the sender prefix."),
            ConfigField("channel_idx", "Channel index", "number", 0, minimum=0),
            ConfigField("prefix_separator", "Name separator", "text", ": ",
                        help='Joins the sender name and message, e.g. ": " → "Ben: hello"'),
            ConfigField("position_rx_enabled", "Show contact positions on the map", "bool", False,
                        help="Read the radio's contact list and plot contacts that "
                             "advertise a location."),
            ConfigField("position_poll_seconds", "Position poll interval", "number", 60,
                        minimum=MIN_POLL_SECONDS,
                        help="Seconds between contact-list reads."),
        ),
        tx_composition={
            "max_len_key": "max_packet_length",
            "separator_key": "prefix_separator",
            "hint": "MeshCore",
        },
    )

    def __init__(self) -> None:
        super().__init__()
        self._poller = PositionPoller(
            PLUGIN_ID,
            self._poll_contacts,
            ctx_getter=lambda: getattr(self, "ctx", None),
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

    async def _poll_contacts(self) -> None:
        transport = self._transport
        if not isinstance(transport, MeshCoreClient) or not transport.is_connected:
            return
        for contact in await transport.read_contacts():
            await self._report_contact(contact)

    async def _report_contact(self, contact: dict) -> None:
        lat, lon = _contact_coords(contact)
        if lat is None or lon is None:
            return
        await self._poller.report(
            contact.get("public_key") or "",
            lat,
            lon,
            label=contact.get("adv_name") or "",
            # The advert's own time, not the contact-list read: the list is a
            # roster the radio keeps, and re-reading it is not a new hearing.
            heard_at=contact.get("last_advert"),
        )


def _contact_coords(contact: dict) -> tuple[float | None, float | None]:
    """Pull advertised coordinates out of a MeshCore contact record.

    A contact that has never advertised a location carries a raw int32 zero in
    both fields, so 0.0/0.0 means "no location", not "on the equator off the
    coast of Africa".
    """
    try:
        lat = float(contact.get("adv_lat"))
        lon = float(contact.get("adv_lon"))
    except (TypeError, ValueError):
        return None, None
    if lat == 0.0 and lon == 0.0:
        return None, None
    return lat, lon
