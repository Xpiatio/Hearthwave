"""Unit tests for the APRS RF example plugin (examples/plugins/aprs_rf).

No TNC and no aprslib needed. The KISS deframer and the AX.25 decoder are
exercised against frames this module encodes byte by byte — the plugin only
ever decodes, so the encoders live here in the tests. aprslib is faked, with
canned returns copied from a real aprslib 0.7.2 parse of these exact TNC2
strings, so the mapping is checked without pinning an optional dependency into
the test environment.
"""
from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import pytest

from backend.plugins.base import BasePlugin
from backend.tests.unit.plugins._helpers import EXAMPLES, load_example, make_config, make_ctx

APRS_DIR = EXAMPLES / "aprs_rf"


def _load_standalone(name: str):
    """Import one of the plugin's dependency-free helper modules directly."""
    spec = importlib.util.spec_from_file_location(f"aprs_rf_test_{name}", APRS_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


kiss = _load_standalone("kiss")
ax25 = _load_standalone("ax25")
parser = _load_standalone("parser")


# ---------------------------------------------------------------------------
# Frame encoders — test-side only
# ---------------------------------------------------------------------------

def encode_address(call: str, *, last: bool = False, repeated: bool = False) -> bytes:
    base, _, ssid = call.partition("-")
    out = bytearray((ord(char) << 1) & 0xFE for char in base.ljust(6))
    ssid_byte = 0x60 | (int(ssid or 0) << 1)
    if last:
        ssid_byte |= 0x01
    if repeated:
        ssid_byte |= 0x80
    out.append(ssid_byte)
    return bytes(out)


def ui_frame(src: str, dest: str, digis=(), info: str = "", control=0x03, pid=0xF0) -> bytes:
    """Build an AX.25 UI frame. A digi suffixed with '*' has been repeated."""
    addresses = [encode_address(dest), encode_address(src)]
    for digi in digis:
        addresses.append(encode_address(digi.rstrip("*"), repeated=digi.endswith("*")))
    frame = bytearray(b"".join(addresses))
    frame[-1] |= 0x01  # end-of-address on the last one
    frame += bytes([control, pid]) + info.encode("latin-1")
    return bytes(frame)


def kiss_wrap(frame: bytes, command: int = 0x00) -> bytes:
    body = bytearray([command])
    for byte in frame:
        if byte == kiss.FEND:
            body += bytes([kiss.FESC, kiss.TFEND])
        elif byte == kiss.FESC:
            body += bytes([kiss.FESC, kiss.TFESC])
        else:
            body.append(byte)
    return bytes([kiss.FEND]) + bytes(body) + bytes([kiss.FEND])


BEACON_INFO = "!4254.00N/08548.00W>Mobile unit"
BEACON_FRAME = ui_frame("W8ABC-9", "APRS", ["WIDE1-1*", "WIDE2-1"], BEACON_INFO)
BEACON_TNC2 = "W8ABC-9>APRS,WIDE1-1*,WIDE2-1:" + BEACON_INFO


# ---------------------------------------------------------------------------
# KISS deframer
# ---------------------------------------------------------------------------

class TestKissDeframer:
    def test_extracts_one_frame(self):
        assert kiss.KissDeframer().feed(kiss_wrap(BEACON_FRAME)) == [BEACON_FRAME]

    def test_extracts_several_frames_from_one_read(self):
        stream = kiss_wrap(BEACON_FRAME) + kiss_wrap(b"\x01\x02\x03")
        assert kiss.KissDeframer().feed(stream) == [BEACON_FRAME, b"\x01\x02\x03"]

    def test_reassembles_a_frame_split_across_reads(self):
        stream = kiss_wrap(BEACON_FRAME)
        deframer = kiss.KissDeframer()
        got = []
        for start in range(0, len(stream), 7):
            got += deframer.feed(stream[start:start + 7])
        assert got == [BEACON_FRAME]

    def test_unescapes_fend_and_fesc_in_the_payload(self):
        payload = bytes([0x11, kiss.FEND, 0x22, kiss.FESC, 0x33])
        assert kiss.KissDeframer().feed(kiss_wrap(payload)) == [payload]

    def test_drops_non_data_command_frames(self):
        """TXDELAY and friends share the stream and are not AX.25."""
        assert kiss.KissDeframer().feed(kiss_wrap(b"\x20", command=0x01)) == []

    def test_honours_the_port_nibble(self):
        """Command byte 0x10 is port 1, data — still a frame."""
        assert kiss.KissDeframer().feed(kiss_wrap(BEACON_FRAME, command=0x10)) == [BEACON_FRAME]

    def test_ignores_noise_before_the_first_fend(self):
        assert kiss.KissDeframer().feed(b"junk" + kiss_wrap(BEACON_FRAME)) == [BEACON_FRAME]

    def test_ignores_idle_padding_between_frames(self):
        stream = bytes([kiss.FEND] * 4) + kiss_wrap(BEACON_FRAME) + bytes([kiss.FEND] * 3)
        assert kiss.KissDeframer().feed(stream) == [BEACON_FRAME]

    def test_drops_an_invalid_escape_sequence(self):
        corrupt = bytes([kiss.FEND, 0x00, 0x11, kiss.FESC, 0x99, 0x22, kiss.FEND])
        assert kiss.KissDeframer().feed(corrupt) == []

    def test_oversized_frames_are_dropped_not_buffered(self):
        deframer = kiss.KissDeframer(max_frame_bytes=16)
        assert deframer.feed(kiss_wrap(b"x" * 64)) == []
        assert len(deframer._buf) <= 16
        # Recovers on the next frame that fits.
        assert deframer.feed(kiss_wrap(b"short")) == [b"short"]

    def test_reset_drops_a_partial_frame(self):
        deframer = kiss.KissDeframer()
        deframer.feed(kiss_wrap(BEACON_FRAME)[:20])
        deframer.reset()
        assert deframer.feed(kiss_wrap(BEACON_FRAME)) == [BEACON_FRAME]


# ---------------------------------------------------------------------------
# AX.25
# ---------------------------------------------------------------------------

class TestAx25Decoder:
    def test_renders_tnc2_text(self):
        assert ax25.decode_ui_frame(BEACON_FRAME) == BEACON_TNC2

    def test_renders_a_pathless_frame(self):
        frame = ui_frame("W8XYZ", "APDR16", [], "=4254.00N/08548.00W$Home")
        assert ax25.decode_ui_frame(frame) == "W8XYZ>APDR16:=4254.00N/08548.00W$Home"

    def test_ssid_zero_is_not_suffixed(self):
        call, last, repeated = ax25.decode_address(encode_address("W8XYZ", last=True))
        assert (call, last, repeated) == ("W8XYZ", True, False)

    def test_repeated_digis_are_starred(self):
        frame = ui_frame("W8ABC", "APRS", ["W8REP-1*", "WIDE2-1"], "!0000.00N/00000.00W-")
        assert ax25.decode_ui_frame(frame).startswith("W8ABC>APRS,W8REP-1*,WIDE2-1:")

    def test_accepts_the_poll_variant_of_the_ui_control_byte(self):
        assert ax25.decode_ui_frame(ui_frame("W8ABC", "APRS", [], "!x", control=0x13))

    @pytest.mark.parametrize("kwargs", [{"control": 0x00}, {"pid": 0xCF}])
    def test_rejects_non_ui_traffic(self, kwargs):
        """Connected-mode AX.25 shares the channel and carries no APRS."""
        with pytest.raises(ax25.FrameError):
            ax25.decode_ui_frame(ui_frame("W8ABC", "APRS", [], "data", **kwargs))

    def test_rejects_an_empty_info_field(self):
        with pytest.raises(ax25.FrameError):
            ax25.decode_ui_frame(ui_frame("W8ABC", "APRS", [], ""))

    @pytest.mark.parametrize("frame", [b"", b"\x00" * 6, BEACON_FRAME[:10], BEACON_FRAME[:15]])
    def test_rejects_truncated_frames(self, frame):
        with pytest.raises(ax25.FrameError):
            ax25.decode_ui_frame(frame)

    def test_rejects_an_address_block_with_no_end_bit(self):
        with pytest.raises(ax25.FrameError):
            ax25.decode_ui_frame(encode_address("W8ABC") * 12)

    def test_rejects_a_non_alphanumeric_callsign(self):
        with pytest.raises(ax25.FrameError):
            ax25.decode_address(bytes([0x40, 0x40, 0x40, 0x40, 0x40, 0x40, 0x61]))

    def test_info_field_survives_high_bytes(self):
        """Mic-E and comment text are not always valid UTF-8."""
        frame = ui_frame("W8ABC", "APRS", [], "") + b"\xff\xfe"
        assert ax25.decode_ui_frame(frame).endswith("\xff\xfe")


# ---------------------------------------------------------------------------
# aprslib mapping
# ---------------------------------------------------------------------------

class _GenericError(Exception):
    pass


def fake_aprslib(**packets) -> types.ModuleType:
    """An aprslib stand-in returning canned parses, keyed by TNC2 text."""
    module = types.ModuleType("aprslib")
    exceptions = types.ModuleType("aprslib.exceptions")
    exceptions.GenericError = _GenericError
    module.exceptions = exceptions

    def parse(text):
        if text not in packets:
            raise _GenericError(f"unknown format: {text}")
        result = packets[text]
        if isinstance(result, Exception):
            raise result
        return result

    module.parse = parse
    return module


# Verified against aprslib 0.7.2 by parsing these exact strings.
BEACON_PACKET = {
    "from": "W8ABC-9", "latitude": 42.9, "longitude": -85.8, "altitude": None,
    "comment": "Mobile unit", "format": "uncompressed", "symbol": ">", "symbol_table": "/",
    "path": ["WIDE1-1*", "WIDE2-1"],
}
MICE_TNC2 = 'W8ABC-9>T2SY1U,WIDE1-1:`(_fn"Oj/`"4)}147.030MHz'
MICE_PACKET = {
    "from": "W8ABC-9", "latitude": 42.6525, "longitude": -12.129, "altitude": 18,
    "speed": 37.04, "course": 251, "comment": "`147.030MHz", "format": "mic-e",
    "symbol": "j", "symbol_table": "/",
}


@pytest.fixture
def aprs_parser(monkeypatch):
    monkeypatch.setattr(
        parser, "_aprslib",
        fake_aprslib(**{BEACON_TNC2: BEACON_PACKET, MICE_TNC2: MICE_PACKET}),
    )
    return parser


class TestParser:
    def test_maps_a_position_beacon(self, aprs_parser):
        fix = aprs_parser.parse_position(BEACON_TNC2)
        assert (fix["node_id"], fix["lat"], fix["lon"]) == ("W8ABC-9", 42.9, -85.8)
        assert fix["alt_m"] is None
        assert fix["extra"]["comment"] == "Mobile unit"
        assert fix["extra"]["symbol"] == "/>"
        assert fix["extra"]["path"] == "WIDE1-1*,WIDE2-1"
        assert "speed" not in fix["extra"]

    def test_maps_mic_e_altitude_speed_and_course(self, aprs_parser):
        fix = aprs_parser.parse_position(MICE_TNC2)
        assert fix["alt_m"] == 18.0
        assert fix["extra"]["speed"] == "37 km/h"
        assert fix["extra"]["course"] == "251°"

    def test_unparseable_packets_are_skipped(self, aprs_parser):
        assert aprs_parser.parse_position("nonsense") is None

    def test_a_library_crash_is_skipped_not_raised(self, monkeypatch):
        """RF hands aprslib bytes no sender intended; the read loop must survive."""
        monkeypatch.setattr(
            parser, "_aprslib", fake_aprslib(**{BEACON_TNC2: IndexError("string index")})
        )
        assert parser.parse_position(BEACON_TNC2) is None

    @pytest.mark.parametrize("packet", [
        {"from": "W8ABC", "latitude": None, "longitude": None},   # status / message
        {"from": "", "latitude": 42.9, "longitude": -85.8},       # no source callsign
        {"from": "W8ABC", "latitude": "north", "longitude": 1.0},  # non-numeric
    ])
    def test_packets_without_a_usable_fix_are_skipped(self, monkeypatch, packet):
        monkeypatch.setattr(parser, "_aprslib", fake_aprslib(**{"p": packet}))
        assert parser.parse_position("p") is None


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------

class FakeLink:
    """Yields canned reads, then drops the link the way a real TNC would."""

    def __init__(self, chunks) -> None:
        self.description = "fake"
        self.chunks = list(chunks)
        self.opened = False
        self.closed = False

    async def open(self) -> None:
        self.opened = True

    async def read(self) -> bytes:
        if not self.chunks:
            raise ConnectionError("TNC went away")
        return self.chunks.pop(0)

    def close(self) -> None:
        self.closed = True


async def load_aprs(config=None, *, reports=None):
    """Load the plugin from disk with a context that records reported positions."""
    async def _report(source, node_id, lat, lon, label="", **meta):
        if reports is not None:
            reports.append((source, node_id, lat, lon, label, meta))
        return True

    ctx = make_ctx(config, report_position=_report)
    inst = await load_example("aprs_rf", config, ctx=ctx)
    # The plugin's own copy of parser.py, loaded under its package name.
    plugin_parser = sys.modules[f"{type(inst).__module__}.parser"]
    plugin_parser._aprslib = fake_aprslib(**{BEACON_TNC2: BEACON_PACKET})
    return inst


class TestManifest:
    async def test_starts_disabled(self):
        inst = await load_aprs()
        assert inst.manifest.default_enabled is False
        assert inst.is_enabled(make_config("aprs_rf")) is False

    async def test_defaults_target_direwolfs_kiss_port(self):
        inst = await load_aprs()
        fields = {f.key: f.default for f in inst.manifest.config_schema}
        assert (fields["transport"], fields["host"], fields["port"]) == ("tcp", "127.0.0.1", 8001)

    async def test_has_no_transmit_path(self):
        """Receive-only is a legal constraint, not a preference — see the module
        docstring and docs/legality.html. Guard it with a test."""
        inst = await load_aprs()
        assert type(inst).on_audio_tx_pre_queue is BasePlugin.on_audio_tx_pre_queue
        assert inst.manifest.tx_composition is None
        link = inst._make_tcp_link()
        assert not hasattr(link, "write") and not hasattr(link, "send")


class TestConfigMapping:
    async def test_reads_the_namespaced_section(self):
        cfg = make_config("aprs_rf", host="10.0.0.5", port="8010", callsign_filter="w8abc")
        inst = await load_aprs(cfg)
        await inst.on_config_changed(cfg)
        assert (inst._host, inst._port) == ("10.0.0.5", 8010)
        assert inst._filter == frozenset({"W8ABC"})
        assert inst._poller.is_running is False  # still disabled

    async def test_serial_transport_builds_a_serial_link(self):
        cfg = make_config("aprs_rf", transport="serial", serial_port="/dev/ttyS3", baud="19200")
        inst = await load_aprs(cfg)
        await inst.on_config_changed(cfg)
        link = inst._link_factory()
        assert (link.port, link.baud) == ("/dev/ttyS3", 19200)

    @pytest.mark.parametrize("mode,filt,callsign,expected", [
        ("allow", "", "W8ABC-9", True),
        ("allow", "W8ABC", "W8ABC-9", True),      # bare callsign covers every SSID
        ("allow", "W8ABC-7", "W8ABC-9", False),   # a specific SSID does not
        ("allow", "W8XYZ", "W8ABC-9", False),
        ("deny", "W8ABC", "W8ABC-9", False),
        ("deny", "W8XYZ", "W8ABC-9", True),
        ("deny", "", "W8ABC-9", True),
    ])
    async def test_callsign_filter(self, mode, filt, callsign, expected):
        cfg = make_config("aprs_rf", filter_mode=mode, callsign_filter=filt)
        inst = await load_aprs(cfg)
        await inst.on_config_changed(cfg)
        assert inst._passes_filter(callsign) is expected


class TestReadLoop:
    async def test_reports_a_heard_station(self):
        reports = []
        inst = await load_aprs(reports=reports)
        link = FakeLink([kiss_wrap(BEACON_FRAME)])
        inst._link_factory = lambda: link

        with pytest.raises(ConnectionError):
            await inst._pump()

        assert link.opened and link.closed
        source, node_id, lat, lon, label, meta = reports[0]
        assert (source, node_id, lat, lon, label) == ("aprs_rf", "W8ABC-9", 42.9, -85.8, "W8ABC-9")
        assert meta["comment"] == "Mobile unit"

    async def test_a_frame_split_across_reads_still_reports(self):
        reports = []
        inst = await load_aprs(reports=reports)
        stream = kiss_wrap(BEACON_FRAME)
        inst._link_factory = lambda: FakeLink([stream[:11], stream[11:]])

        with pytest.raises(ConnectionError):
            await inst._pump()
        assert len(reports) == 1

    async def test_undecodable_frames_do_not_stop_the_loop(self):
        reports = []
        inst = await load_aprs(reports=reports)
        junk = kiss_wrap(ui_frame("W8ABC", "APRS", [], "data", control=0x00))
        inst._link_factory = lambda: FakeLink([junk, kiss_wrap(BEACON_FRAME)])

        with pytest.raises(ConnectionError):
            await inst._pump()
        assert len(reports) == 1

    async def test_a_filtered_station_is_not_reported(self):
        reports = []
        cfg = make_config("aprs_rf", callsign_filter="W8XYZ")
        inst = await load_aprs(cfg, reports=reports)
        await inst.on_config_changed(cfg)
        inst._link_factory = lambda: FakeLink([kiss_wrap(BEACON_FRAME)])

        with pytest.raises(ConnectionError):
            await inst._pump()
        assert reports == []

    async def test_a_stale_partial_frame_is_dropped_on_reconnect(self):
        reports = []
        inst = await load_aprs(reports=reports)
        stream = kiss_wrap(BEACON_FRAME)
        inst._link_factory = lambda: FakeLink([stream[:11]])
        with pytest.raises(ConnectionError):
            await inst._pump()

        # The second session must not splice the truncated frame onto its first read.
        inst._link_factory = lambda: FakeLink([stream])
        with pytest.raises(ConnectionError):
            await inst._pump()
        assert len(reports) == 1

    async def test_missing_aprslib_fails_before_the_link_is_opened(self, monkeypatch):
        inst = await load_aprs()
        plugin_parser = sys.modules[f"{type(inst).__module__}.parser"]
        monkeypatch.setattr(plugin_parser, "_aprslib", None)
        monkeypatch.setitem(sys.modules, "aprslib", None)  # forces ImportError
        link = FakeLink([])
        inst._link_factory = lambda: link

        with pytest.raises(RuntimeError, match="aprslib not installed"):
            await inst._pump()
        assert link.opened is False


class TestLifecycle:
    """on_config_changed rebuilds the link factory from config, so tests that
    want a fake link install it immediately after — the poll task it starts has
    not reached its first await yet."""

    async def test_enabling_starts_the_reader_and_unload_stops_it(self):
        cfg = make_config("aprs_rf", enabled=True)
        inst = await load_aprs(cfg)

        await inst.on_config_changed(cfg)
        inst._link_factory = lambda: FakeLink([])
        assert inst._poller.is_running is True
        await inst.on_unload()
        assert inst._poller.is_running is False

    async def test_disabling_stops_the_reader(self):
        cfg = make_config("aprs_rf", enabled=True)
        inst = await load_aprs(cfg)
        await inst.on_config_changed(cfg)
        inst._link_factory = lambda: FakeLink([])

        off = make_config("aprs_rf", enabled=False)
        await inst.on_config_changed(off)
        assert inst._poller.is_running is False

    async def test_the_link_is_closed_when_the_reader_is_cancelled(self):
        cfg = make_config("aprs_rf", enabled=True)
        inst = await load_aprs(cfg)
        link = FakeLink([])

        async def _blocking_read():
            await asyncio.Event().wait()

        link.read = _blocking_read

        await inst.on_config_changed(cfg)
        inst._link_factory = lambda: link
        for _ in range(5):
            await asyncio.sleep(0)
        assert link.opened is True

        await inst.on_unload()
        assert link.closed is True
