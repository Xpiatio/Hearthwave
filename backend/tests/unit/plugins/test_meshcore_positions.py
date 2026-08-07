"""Unit tests for the MeshCore example's position-RX half.

The forwarder half is covered by test_example_plugins; this module is only about
the contact-list read: the snapshot taken off the library's live mapping, the
0.0/0.0 "never advertised" case, the mapping onto ctx.report_position, and the
fact that positions stay off until both the plugin and position RX are enabled.

Contact records here are shaped the way meshcore 2.3.8 shapes them — the reader
decodes a CONTACT frame into public_key / adv_name / adv_lat / adv_lon /
last_advert, with the coordinates already divided down from raw int32 by 1e6,
and MeshCore.contacts keyed by public key.

No radio and no meshcore install is needed: the interface is a plain stub.
"""
from __future__ import annotations

import sys

import pytest

from backend.tests.unit.plugins._helpers import load_example, make_config, make_ctx


def plugin_module(inst):
    """The loaded plugin's own module (loader names it hw_plugin_meshcore)."""
    return sys.modules[type(inst).__module__]


class FakeCommands:
    def __init__(self, owner):
        self._owner = owner

    async def get_contacts(self):
        self._owner.refreshes += 1


class FakeMeshCore:
    """Stands in for meshcore.MeshCore."""

    def __init__(self, contacts=None):
        self.contacts = contacts
        self.commands = FakeCommands(self)
        self.refreshes = 0


class Reports:
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
    cfg = make_config("meshcore", **values)
    ctx = make_ctx(cfg, report_position=reports)
    return await load_example("meshcore", cfg, ctx=ctx), cfg


def contact(key="ab" * 32, name="Repeater", lat=42.9, lon=-85.8, last_advert=1700000000):
    return {
        "public_key": key,
        "type": 2,
        "flags": 0,
        "out_path": "",
        "adv_name": name,
        "last_advert": last_advert,
        "adv_lat": lat,
        "adv_lon": lon,
        "lastmod": last_advert,
    }


class TestContactCoords:
    async def test_reads_the_advertised_floats(self):
        inst, _ = await make_plugin()
        assert plugin_module(inst)._contact_coords(contact()) == (42.9, -85.8)

    async def test_a_contact_that_never_advertised_a_location_has_no_fix(self):
        """The firmware sends a raw int32 zero in both fields for "unset"."""
        inst, _ = await make_plugin()
        assert plugin_module(inst)._contact_coords(contact(lat=0.0, lon=0.0)) == (None, None)

    @pytest.mark.parametrize("row", [{}, {"adv_lat": None, "adv_lon": None},
                                     {"adv_lat": "north", "adv_lon": 1.0}])
    async def test_a_missing_or_unparsable_coordinate_has_no_fix(self, row):
        inst, _ = await make_plugin()
        assert plugin_module(inst)._contact_coords(row) == (None, None)

    async def test_a_zero_on_one_axis_only_is_still_a_fix(self):
        """0° longitude with a real latitude is Greenwich, not an unset field."""
        inst, _ = await make_plugin()
        assert plugin_module(inst)._contact_coords(contact(lat=51.5, lon=0.0)) == (51.5, 0.0)


class TestReadContacts:
    async def make_client(self, contacts, connected=True):
        inst, cfg = await make_plugin()
        client = inst._make_transport(cfg)
        client._mc = FakeMeshCore(contacts)
        client._connected = connected
        return client

    async def test_flattens_the_contact_mapping(self):
        key = "ab" * 32
        client = await self.make_client({key: contact(key)})
        assert await client.read_contacts() == [{
            "public_key": key,
            "adv_name": "Repeater",
            "adv_lat": 42.9,
            "adv_lon": -85.8,
            "last_advert": 1700000000,
        }]

    async def test_refreshes_the_list_before_reading_it(self):
        client = await self.make_client({})
        await client.read_contacts()
        assert client._mc.refreshes == 1

    async def test_falls_back_to_the_mapping_key(self):
        """The library keys on public_key, so the row is authoritative but optional."""
        row = contact()
        del row["public_key"]
        client = await self.make_client({"cd" * 32: row})
        assert (await client.read_contacts())[0]["public_key"] == "cd" * 32

    async def test_skips_entries_that_are_not_records(self):
        client = await self.make_client({"a": contact("a"), "b": "junk", "c": None})
        assert [row["public_key"] for row in await client.read_contacts()] == ["a"]

    async def test_copies_the_row_instead_of_aliasing_it(self):
        live = contact()
        client = await self.make_client({live["public_key"]: live})
        rows = await client.read_contacts()
        live["adv_lat"] = 0.0
        assert rows[0]["adv_lat"] == 42.9

    async def test_reads_nothing_while_disconnected(self):
        client = await self.make_client({"a": contact("a")}, connected=False)
        assert await client.read_contacts() == []

    async def test_a_radio_with_no_contact_list_yields_no_rows(self):
        client = await self.make_client(None)
        assert await client.read_contacts() == []


class TestReportContact:
    async def test_reports_the_key_coordinates_and_name(self):
        reports = Reports()
        inst, _ = await make_plugin(reports)
        await inst._report_contact(contact("ab" * 32, "Hilltop"))
        source, node_id, lat, lon, label, meta = reports.calls[0]
        assert (source, node_id, lat, lon, label) == (
            "meshcore", "ab" * 32, 42.9, -85.8, "Hilltop"
        )
        assert meta == {"heard_at": 1700000000}

    async def test_the_fix_ages_from_the_advert_not_the_contact_list_read(self):
        # The contact list is a roster the radio keeps; re-reading it is not a
        # new hearing, and treating it as one would never let a node age off.
        reports = Reports()
        inst, _ = await make_plugin(reports)
        await inst._report_contact(contact(last_advert=1_699_999_000))
        assert reports.calls[0][5]["heard_at"] == 1_699_999_000

    async def test_an_unnamed_contact_reports_with_an_empty_label(self):
        reports = Reports()
        inst, _ = await make_plugin(reports)
        await inst._report_contact(contact(name=""))
        assert reports.calls[0][4] == ""

    async def test_a_contact_without_a_location_is_not_reported(self):
        reports = Reports()
        inst, _ = await make_plugin(reports)
        await inst._report_contact(contact(lat=0.0, lon=0.0))
        assert reports.calls == []

    async def test_a_contact_with_no_key_is_not_reported(self):
        reports = Reports()
        inst, _ = await make_plugin(reports)
        await inst._report_contact(contact(key=""))
        assert reports.calls == []


class TestPollContacts:
    async def test_reports_every_contact_that_advertises_a_location(self):
        reports = Reports()
        inst, cfg = await make_plugin(reports)
        client = inst._make_transport(cfg)
        client._mc = FakeMeshCore({
            "a": contact("a", "Alpha", 42.9, -85.8),
            "b": contact("b", "Bravo", 0.0, 0.0),  # advertising, no location
            "c": contact("c", "Charlie", 42.8, -85.7),
        })
        client._connected = True
        inst._transport = client

        await inst._poll_contacts()
        assert set(reports.by_id) == {"a", "c"}

    async def test_polling_without_a_transport_is_a_no_op(self):
        reports = Reports()
        inst, _ = await make_plugin(reports)
        await inst._poll_contacts()  # must not raise
        assert reports.calls == []

    async def test_polling_a_disconnected_radio_is_a_no_op(self):
        reports = Reports()
        inst, cfg = await make_plugin(reports)
        client = inst._make_transport(cfg)
        client._mc = FakeMeshCore({"a": contact("a")})
        inst._transport = client  # built but never connected
        await inst._poll_contacts()
        assert reports.calls == []

    async def test_an_unchanged_advert_is_reported_once(self):
        """Dedupe lives in the poller; this confirms the plugin routes through it."""
        reports = Reports()
        inst, cfg = await make_plugin(reports)
        client = inst._make_transport(cfg)
        client._mc = FakeMeshCore({"a": contact("a")})
        client._connected = True
        inst._transport = client

        await inst._poll_contacts()
        await inst._poll_contacts()
        assert len(reports.calls) == 1

        client._mc.contacts["a"]["adv_lat"] = 43.0
        await inst._poll_contacts()
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

        # Keeps on_config_changed off the (absent) meshcore library and the serial port.
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

        cfg.set_plugin_config("meshcore", {"enabled": True, "position_rx_enabled": False})
        await inst.on_config_changed(cfg)
        assert inst._poller.is_running is False

    async def test_the_poll_interval_honours_the_floor(self):
        inst, cfg = await self.make_enabled_plugin(
            enabled=True, position_rx_enabled=True, position_poll_seconds=1
        )
        await inst.on_config_changed(cfg)
        assert inst._poller._poll_seconds == 5.0
        await inst.on_unload()
