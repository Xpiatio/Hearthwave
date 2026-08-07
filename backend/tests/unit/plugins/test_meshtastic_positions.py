"""Unit tests for the Meshtastic example's position-RX half.

The forwarder half of that plugin is covered by test_example_plugins; this
module is only about the node-database read: the snapshot the client takes off
the library's live mapping, the coordinate extraction, the mapping onto
ctx.report_position, and the fact that positions stay off until *both* the
plugin and position RX are enabled.

Node records here are shaped the way meshtastic 2.7.11 shapes them — `nodes`
keyed by node-ID string, values a MessageToDict of NodeInfo, so camelCase keys,
derived float latitude/longitude alongside the raw latitudeI/longitudeI, and
zero-valued fields omitted entirely.

No radio and no meshtastic install is needed: the interface is a plain stub.
"""
from __future__ import annotations

import sys

import pytest

from backend.tests.unit.plugins._helpers import load_example, make_config, make_ctx


def plugin_module(inst):
    """The loaded plugin's own module (loader names it hw_plugin_meshtastic)."""
    return sys.modules[type(inst).__module__]


class FakeInterface:
    """Stands in for meshtastic.serial_interface.SerialInterface."""

    def __init__(self, nodes=None):
        self.nodes = nodes
        self.closed = False

    def close(self):
        self.closed = True


class Reports:
    """Collects ctx.report_position calls the way the server would receive them."""

    def __init__(self, accept=True):
        self.calls: list[tuple] = []
        self._accept = accept

    async def __call__(self, source, node_id, lat, lon, label="", **meta):
        self.calls.append((source, node_id, lat, lon, label, meta))
        return self._accept

    @property
    def by_id(self) -> dict:
        return {call[1]: call for call in self.calls}


async def make_plugin(reports=None, **values):
    """Load the example with a ctx whose report_position we can inspect."""
    cfg = make_config("meshtastic", **values)
    ctx = make_ctx(cfg, report_position=reports)
    return await load_example("meshtastic", cfg, ctx=ctx), cfg


class TestNodeCoords:
    """The float keys the library derives, with the raw integers as a fallback."""

    async def test_prefers_the_derived_float_keys(self):
        inst, _ = await make_plugin()
        coords = plugin_module(inst)._node_coords
        assert coords({"latitude": 42.9, "longitude": -85.8}) == (42.9, -85.8)

    async def test_falls_back_to_the_1e7_degree_integers(self):
        inst, _ = await make_plugin()
        coords = plugin_module(inst)._node_coords
        lat, lon = coords({"latitudeI": 429000000, "longitudeI": -858000000})
        assert lat == pytest.approx(42.9)
        assert lon == pytest.approx(-85.8)

    async def test_mixes_a_derived_key_with_an_integer_one(self):
        inst, _ = await make_plugin()
        coords = plugin_module(inst)._node_coords
        lat, lon = coords({"latitude": 42.9, "longitudeI": -858000000})
        assert (lat, lon) == (42.9, pytest.approx(-85.8))

    @pytest.mark.parametrize(
        "position",
        [
            None,
            "not a dict",
            {},                                   # no fix at all
            {"time": 1700000000},                 # position packet with no coordinates
            {"latitude": "north", "longitude": 1.0},
        ],
    )
    async def test_no_usable_fix_yields_no_coordinates(self, position):
        inst, _ = await make_plugin()
        assert plugin_module(inst)._node_coords(position) == (None, None)

    @pytest.mark.parametrize(
        "position", [{"latitude": 42.9}, {"longitude": -85.8}]
    )
    async def test_a_half_fix_is_left_incomplete_for_the_caller_to_drop(self, position):
        """MessageToDict omits a zero-valued coordinate, so exactly 0° looks like this."""
        inst, _ = await make_plugin()
        assert None in plugin_module(inst)._node_coords(position)


class TestSnapshotNodes:
    async def make_client(self, nodes, connected=True):
        inst, cfg = await make_plugin()
        client = inst._make_transport(cfg)
        client._iface = FakeInterface(nodes)
        client._connected = connected
        return client

    async def test_maps_the_library_record_onto_a_flat_row(self):
        client = await self.make_client({
            "!a1b2c3d4": {
                "num": 2712847316,
                "user": {"id": "!a1b2c3d4", "longName": "Base Station", "shortName": "BASE"},
                "position": {"latitudeI": 429000000, "longitudeI": -858000000,
                             "latitude": 42.9, "longitude": -85.8, "altitude": 218},
                "lastHeard": 1700000000,
                "snr": 6.25,
            },
        })
        assert await client.read_nodes() == [{
            "id": "!a1b2c3d4",
            "long_name": "Base Station",
            "short_name": "BASE",
            "position": {"latitudeI": 429000000, "longitudeI": -858000000,
                         "latitude": 42.9, "longitude": -85.8, "altitude": 218},
            "last_heard": 1700000000,
            "snr": 6.25,
        }]

    async def test_tolerates_a_node_with_no_user_or_position(self):
        """A node heard once but never identified still has a record in the DB."""
        client = await self.make_client({"!deadbeef": {"num": 1}})
        assert await client.read_nodes() == [{
            "id": "!deadbeef",
            "long_name": "",
            "short_name": "",
            "position": None,
            "last_heard": None,
            "snr": None,
        }]

    async def test_skips_entries_that_are_not_records(self):
        client = await self.make_client({"!a": {"num": 1}, "!b": "junk", "!c": None})
        assert [row["id"] for row in await client.read_nodes()] == ["!a"]

    async def test_copies_the_position_instead_of_aliasing_it(self):
        """The serial reader thread mutates these dicts as packets arrive."""
        live = {"latitude": 42.9, "longitude": -85.8}
        client = await self.make_client({"!a": {"position": live}})
        rows = await client.read_nodes()
        live["latitude"] = 0.0
        assert rows[0]["position"]["latitude"] == 42.9

    async def test_reads_nothing_while_disconnected(self):
        client = await self.make_client({"!a": {"position": {"latitude": 1.0,
                                                             "longitude": 2.0}}},
                                        connected=False)
        assert await client.read_nodes() == []

    async def test_a_radio_with_no_node_database_yields_no_rows(self):
        client = await self.make_client(None)
        assert await client.read_nodes() == []


class TestReportNode:
    async def test_reports_coordinates_label_and_altitude(self):
        reports = Reports()
        inst, _ = await make_plugin(reports)
        await inst._report_node({
            "id": "!a1b2c3d4",
            "long_name": "Base Station",
            "short_name": "BASE",
            "position": {"latitude": 42.9, "longitude": -85.8, "altitude": 218},
            "last_heard": 1_700_000_000,
            "snr": 6.25,
        })
        source, node_id, lat, lon, label, meta = reports.calls[0]
        assert (source, node_id, lat, lon, label) == (
            "meshtastic", "!a1b2c3d4", 42.9, -85.8, "Base Station"
        )
        assert meta == {
            "alt_m": 218, "snr": "6.2 dB", "short_name": "BASE",
            "heard_at": 1_700_000_000,
        }

    async def test_the_fix_carries_when_the_radio_heard_it_not_when_we_read_it(self):
        # The node DB remembers nodes for days; without this every poll would
        # re-stamp a long-gone node as live.
        reports = Reports()
        inst, _ = await make_plugin(reports)
        await inst._report_node({
            "id": "!a",
            "position": {"latitude": 42.9, "longitude": -85.8},
            "last_heard": 1_699_999_000,
        })
        assert reports.calls[0][5]["heard_at"] == 1_699_999_000

    async def test_falls_back_to_the_short_name_for_the_label(self):
        reports = Reports()
        inst, _ = await make_plugin(reports)
        await inst._report_node({
            "id": "!a", "short_name": "BASE",
            "position": {"latitude": 42.9, "longitude": -85.8},
        })
        assert reports.calls[0][4] == "BASE"

    async def test_an_unnamed_node_reports_with_an_empty_label(self):
        reports = Reports()
        inst, _ = await make_plugin(reports)
        await inst._report_node({"id": "!a", "position": {"latitude": 42.9, "longitude": -85.8}})
        source, node_id, lat, lon, label, meta = reports.calls[0]
        assert (node_id, label) == ("!a", "")
        assert meta == {"alt_m": None, "heard_at": None}

    async def test_a_node_without_a_fix_is_not_reported(self):
        reports = Reports()
        inst, _ = await make_plugin(reports)
        await inst._report_node({"id": "!a", "long_name": "No GPS", "position": None})
        assert reports.calls == []

    async def test_a_node_sitting_at_exactly_zero_degrees_is_not_reported(self):
        """MessageToDict drops the zero coordinate, leaving half a fix — unplottable."""
        reports = Reports()
        inst, _ = await make_plugin(reports)
        await inst._report_node({"id": "!a", "position": {"latitude": 42.9}})
        assert reports.calls == []

    async def test_a_node_with_no_id_is_not_reported(self):
        """The poller drops it rather than keying the store on an empty string."""
        reports = Reports()
        inst, _ = await make_plugin(reports)
        await inst._report_node({"id": "", "position": {"latitude": 42.9, "longitude": -85.8}})
        assert reports.calls == []


class TestPollNodes:
    async def test_reports_every_node_that_has_a_fix(self):
        reports = Reports()
        inst, cfg = await make_plugin(reports)
        client = inst._make_transport(cfg)
        client._iface = FakeInterface({
            "!a": {"user": {"longName": "Alpha"},
                   "position": {"latitude": 42.9, "longitude": -85.8}},
            "!b": {"user": {"longName": "Bravo"}},  # heard, no GPS
            "!c": {"user": {"longName": "Charlie"},
                   "position": {"latitudeI": 428000000, "longitudeI": -857000000}},
        })
        client._connected = True
        inst._transport = client

        await inst._poll_nodes()

        assert set(reports.by_id) == {"!a", "!c"}
        assert reports.by_id["!c"][2] == pytest.approx(42.8)

    async def test_polling_without_a_transport_is_a_no_op(self):
        reports = Reports()
        inst, _ = await make_plugin(reports)
        await inst._poll_nodes()  # must not raise
        assert reports.calls == []

    async def test_polling_a_disconnected_radio_is_a_no_op(self):
        reports = Reports()
        inst, cfg = await make_plugin(reports)
        client = inst._make_transport(cfg)
        client._iface = FakeInterface({"!a": {"position": {"latitude": 1.0, "longitude": 2.0}}})
        inst._transport = client  # built but never connected
        await inst._poll_nodes()
        assert reports.calls == []

    async def test_an_unchanged_fix_is_reported_once(self):
        """Dedupe lives in the poller; this confirms the plugin routes through it."""
        reports = Reports()
        inst, cfg = await make_plugin(reports)
        client = inst._make_transport(cfg)
        client._iface = FakeInterface(
            {"!a": {"position": {"latitude": 42.9, "longitude": -85.8}}}
        )
        client._connected = True
        inst._transport = client

        await inst._poll_nodes()
        await inst._poll_nodes()
        assert len(reports.calls) == 1

        client._iface.nodes["!a"]["position"]["latitude"] = 43.0
        await inst._poll_nodes()
        assert len(reports.calls) == 2


class TestPositionRxLifecycle:
    """Position RX must stay off until the plugin *and* the toggle are on."""

    async def make_enabled_plugin(self, **values):
        inst, cfg = await make_plugin(Reports(), **values)

        class _Stub:
            is_connected = True

            async def connect(self): ...
            async def disconnect(self): ...
            async def send_text(self, text, channel): ...

        # Keeps on_config_changed off the (absent) meshtastic library and the serial port.
        inst._make_transport = lambda config: _Stub()
        return inst, cfg

    async def test_manifest_defaults_position_rx_off(self):
        inst, _ = await make_plugin()
        fields = {f.key: f for f in inst.manifest.config_schema}
        assert fields["position_rx_enabled"].default is False
        assert fields["position_poll_seconds"].default == 60

    async def test_enabling_the_plugin_alone_does_not_start_the_poller(self):
        inst, cfg = await self.make_enabled_plugin(enabled=True)
        await inst.on_config_changed(cfg)
        assert inst._poller.is_running is False
        await inst.on_unload()

    async def test_the_toggle_alone_does_not_start_the_poller(self):
        inst, cfg = await self.make_enabled_plugin(position_rx_enabled=True)
        await inst.on_config_changed(cfg)
        assert inst._poller.is_running is False
        await inst.on_unload()

    async def test_both_enabled_starts_the_poller(self):
        inst, cfg = await self.make_enabled_plugin(enabled=True, position_rx_enabled=True)
        await inst.on_config_changed(cfg)
        assert inst._poller.is_running is True
        await inst.on_unload()
        assert inst._poller.is_running is False

    async def test_turning_the_toggle_back_off_stops_the_poller(self):
        inst, cfg = await self.make_enabled_plugin(enabled=True, position_rx_enabled=True)
        await inst.on_config_changed(cfg)
        assert inst._poller.is_running is True

        cfg.set_plugin_config("meshtastic", {"enabled": True, "position_rx_enabled": False})
        await inst.on_config_changed(cfg)
        assert inst._poller.is_running is False

    async def test_the_poll_interval_honours_the_floor(self):
        inst, cfg = await self.make_enabled_plugin(
            enabled=True, position_rx_enabled=True, position_poll_seconds=1
        )
        await inst.on_config_changed(cfg)
        assert inst._poller._poll_seconds == 5.0
        await inst.on_unload()
