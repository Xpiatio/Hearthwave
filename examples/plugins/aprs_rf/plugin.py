"""APRS over RF — example Hearthwave plugin (position receive only).

Reads a KISS TNC (direwolf over TCP, or a serial TNC), decodes the AX.25 UI
frames it hears, and plots any station that beacons a position. Third example
plugin alongside meshcore and meshtastic, and the only inbound-only one — a
useful template for "listen to a radio, report what you hear".

RECEIVE ONLY, DELIBERATELY. This plugin has no transmit path and must not grow
one. Two independent reasons:

  * APRS on 144.390 MHz is the amateur service; transmitting there needs an
    amateur licence and amateur-certified equipment, and a GMRS station may not
    key it (47 CFR 95.1761 — GMRS transmitters must be certified for Part 95
    Subpart E).
  * GMRS *does* permit short digital data bursts carrying GPS location, and has
    since the 2017 Report and Order — but only from a hand-held portable unit
    (95.1731(d)) whose antenna is "a non-removable integral part" of it
    (95.1787(a)(4)), at most one one-second transmission per thirty seconds
    (95.1787(a)(2)-(3)), addressed to a specific GMRS or FRS unit rather than
    broadcast (95.1731(d)), and only on 462 MHz channels (95.1773(c),
    95.1787(a)(5)). Identification still has to be by voice or Morse
    (95.1751(b)), which a data burst cannot do. A PC-driven TNC bolted to a
    mobile or base radio satisfies none of that. See docs/legality.html.

Listening is unrestricted, so receive is all this does.

The link is driven by the SDK's PositionPoller. Its poll interval is the
*reconnect* delay here rather than a scan period: one "poll" opens the link and
stays inside the read loop until the TNC drops, at which point the poller waits
and re-opens. That is what the poller docs mean by a push-based source.
"""
from __future__ import annotations

import logging

from backend.plugins.sdk import (
    MIN_POLL_SECONDS,
    BasePlugin,
    ConfigField,
    PluginManifest,
    PositionPoller,
)

from . import parser
from .ax25 import FrameError, decode_ui_frame
from .kiss import KissDeframer
from .transport import KissSerialLink, KissTcpLink

_log = logging.getLogger(__name__)

PLUGIN_ID = "aprs_rf"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_TCP_PORT = 8001  # direwolf's default KISSPORT
DEFAULT_SERIAL_PORT = "/dev/ttyUSB1"
DEFAULT_BAUD = 9600
DEFAULT_RECONNECT_SECONDS = 15


class AprsRfPlugin(BasePlugin):
    """Plot stations heard on an APRS RF channel (see module docstring)."""

    manifest = PluginManifest(
        id=PLUGIN_ID,
        name="APRS (RF receive)",
        description="Listen to a KISS TNC and plot the position of every APRS station "
        "heard on the air. Receive only — never transmits.",
        config_schema=(
            ConfigField("transport", "TNC connection", "select", "tcp",
                        options=(("tcp", "KISS over TCP (direwolf)"),
                                 ("serial", "KISS over serial TNC")),
                        help="How to reach the TNC. Direwolf listens on TCP by default."),
            ConfigField("host", "TNC host", "text", DEFAULT_HOST,
                        help="KISS TCP host. 127.0.0.1 when direwolf runs beside Hearthwave."),
            ConfigField("port", "TNC port", "number", DEFAULT_TCP_PORT, minimum=1, maximum=65535,
                        help="KISS TCP port — direwolf's KISSPORT, 8001 unless changed."),
            ConfigField("serial_port", "TNC serial device", "text", DEFAULT_SERIAL_PORT,
                        help="Used only when the connection is set to serial."),
            ConfigField("baud", "Serial baud rate", "number", DEFAULT_BAUD, minimum=1),
            ConfigField("reconnect_seconds", "Reconnect delay", "number",
                        DEFAULT_RECONNECT_SECONDS, minimum=MIN_POLL_SECONDS,
                        help="Seconds to wait before re-opening a dropped TNC link."),
            ConfigField("callsign_filter", "Callsign filter", "text", "",
                        help="Comma-separated callsigns. Empty plots every station heard. "
                             "W8ABC matches every SSID; W8ABC-9 matches just that one."),
            ConfigField("filter_mode", "Filter mode", "select", "allow",
                        options=(("allow", "Plot only these callsigns"),
                                 ("deny", "Plot everything except these")),
                        help="Applied only when a callsign filter is set."),
        ),
    )

    def __init__(self) -> None:
        super().__init__()
        self._deframer = KissDeframer()
        self._link = None
        self._filter: frozenset[str] = frozenset()
        self._filter_mode = "allow"
        self._link_factory = self._make_tcp_link
        self._host = DEFAULT_HOST
        self._port = DEFAULT_TCP_PORT
        self._serial_port = DEFAULT_SERIAL_PORT
        self._baud = DEFAULT_BAUD
        self._poller = PositionPoller(
            PLUGIN_ID,
            self._pump,
            ctx_getter=lambda: self.ctx,
        )

    # -- lifecycle -------------------------------------------------------
    async def on_config_changed(self, config) -> None:
        c = config.plugin_config(PLUGIN_ID)
        self._filter = _parse_filter(c.get("callsign_filter", ""))
        self._filter_mode = "deny" if c.get("filter_mode") == "deny" else "allow"
        self._link_factory = (
            self._make_serial_link if c.get("transport") == "serial" else self._make_tcp_link
        )
        self._host = str(c.get("host", DEFAULT_HOST) or DEFAULT_HOST)
        self._port = int(c.get("port", DEFAULT_TCP_PORT) or DEFAULT_TCP_PORT)
        self._serial_port = str(c.get("serial_port", DEFAULT_SERIAL_PORT) or DEFAULT_SERIAL_PORT)
        self._baud = int(c.get("baud", DEFAULT_BAUD) or DEFAULT_BAUD)
        await self._poller.configure(
            enabled=bool(c.get("enabled", False)),
            poll_seconds=float(c.get("reconnect_seconds", DEFAULT_RECONNECT_SECONDS)),
        )

    async def on_unload(self) -> None:
        await self._poller.stop()

    def _make_tcp_link(self) -> KissTcpLink:
        return KissTcpLink(self._host, self._port)

    def _make_serial_link(self) -> KissSerialLink:
        return KissSerialLink(self._serial_port, self._baud)

    # -- read loop -------------------------------------------------------
    async def _pump(self) -> None:
        """Hold the TNC link open and decode until it drops.

        Returning (or raising) hands control back to the poller, which waits the
        reconnect delay and calls this again.
        """
        parser.load_aprslib()  # fail before opening the link, not per packet
        link = self._link_factory()
        self._deframer.reset()
        await link.open()
        self._link = link
        try:
            while True:
                chunk = await link.read()
                for frame in self._deframer.feed(chunk):
                    await self._handle_frame(frame)
        finally:
            self._link = None
            link.close()

    async def _handle_frame(self, frame: bytes) -> None:
        try:
            tnc2 = decode_ui_frame(frame)
        except FrameError as exc:
            _log.debug("APRS RF: skipped frame (%s)", exc)
            return
        fix = parser.parse_position(tnc2)
        if fix is None or not self._passes_filter(fix["node_id"]):
            return
        await self._poller.report(
            fix["node_id"],
            fix["lat"],
            fix["lon"],
            label=fix["node_id"],
            alt_m=fix["alt_m"],
            **fix["extra"],
        )

    def _passes_filter(self, callsign: str) -> bool:
        if not self._filter:
            return True
        listed = _matches(callsign, self._filter)
        return listed if self._filter_mode == "allow" else not listed


def _parse_filter(raw) -> frozenset[str]:
    return frozenset(
        entry.strip().upper() for entry in str(raw or "").split(",") if entry.strip()
    )


def _matches(callsign: str, entries: frozenset[str]) -> bool:
    """A bare callsign in the list matches every SSID of that station."""
    callsign = callsign.upper()
    return callsign in entries or callsign.split("-")[0] in entries
