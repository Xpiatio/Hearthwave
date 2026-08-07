"""Unit tests for the shipped example plugins (examples/plugins/meshcore, meshtastic).

The APRS RF example has its own module (test_aprs_rf) — it is a position source
rather than a mesh forwarder, so it shares none of the parametrisation here.

These are the reference third-party plugins, so they are exercised the way a real
install runs them: loaded from disk through the public loader, then poked at their
own surface — manifest defaults, the namespaced config mapping, the transport
factory, and each serial client's connect/send/disconnect contract. The forwarding
mechanics themselves (prefix, clamp, queue) live in the SDK and are covered by
test_mesh_forwarder; here we only check what each example file supplies.

No radio and no optional mesh library is needed: the library is faked in sys.modules
for the connect path, and its absence is asserted separately.
"""
from __future__ import annotations

import sys
import types

import pytest

from backend.plugins.sdk import MeshForwardConfig, MeshForwarderPlugin, MeshTransport
from backend.tests.unit.plugins._helpers import load_example, make_config


# Per-example expectations: id, default packet length, transport class name, and the
# transport key the plugin derives from config (meshtastic has no baud).
EXAMPLES_META = [
    ("meshcore", 140, "MeshCoreClient"),
    ("meshtastic", 200, "MeshtasticClient"),
]


class TestExampleManifests:
    @pytest.mark.parametrize("plugin_id,default_len,_client", EXAMPLES_META)
    async def test_is_a_mesh_forwarder(self, plugin_id, default_len, _client):
        inst = await load_example(plugin_id)
        assert isinstance(inst, MeshForwarderPlugin)

    @pytest.mark.parametrize("plugin_id,default_len,_client", EXAMPLES_META)
    async def test_config_schema_declares_its_own_defaults(self, plugin_id, default_len, _client):
        inst = await load_example(plugin_id)
        fields = {f.key: f for f in inst.manifest.config_schema}
        assert fields["serial_port"].default == "/dev/ttyUSB0"
        assert fields["max_packet_length"].default == default_len
        assert fields["prefix_separator"].default == ": "
        assert fields["channel_idx"].default == 0
        # The declared cap is in bytes — the unit the forwarder clamps on.
        assert "bytes" in (fields["max_packet_length"].help or "")

    @pytest.mark.parametrize("plugin_id,default_len,_client", EXAMPLES_META)
    async def test_starts_disabled(self, plugin_id, default_len, _client):
        """A freshly seeded plugin must never key a mesh radio until enabled."""
        inst = await load_example(plugin_id)
        assert inst.manifest.default_enabled is False
        assert inst.is_enabled(make_config(plugin_id)) is False
        assert inst.is_enabled(make_config(plugin_id, enabled=True)) is True


class TestExampleConfigMapping:
    @pytest.mark.parametrize("plugin_id,default_len,_client", EXAMPLES_META)
    async def test_read_config_maps_the_namespaced_section(self, plugin_id, default_len, _client):
        cfg = make_config(
            plugin_id,
            enabled=True,
            max_packet_length=64,
            prefix_separator=" > ",
            channel_idx=2,
        )
        inst = await load_example(plugin_id, cfg)
        assert inst._read_config(cfg) == MeshForwardConfig(
            enabled=True, max_packet_length=64, prefix_separator=" > ", channel_idx=2
        )

    @pytest.mark.parametrize("plugin_id,default_len,_client", EXAMPLES_META)
    async def test_read_config_falls_back_to_defaults(self, plugin_id, default_len, _client):
        cfg = make_config(plugin_id)
        inst = await load_example(plugin_id, cfg)
        fc = inst._read_config(cfg)
        assert fc == MeshForwardConfig(
            enabled=False, max_packet_length=default_len, prefix_separator=": ", channel_idx=0
        )

    @pytest.mark.parametrize("plugin_id,default_len,_client", EXAMPLES_META)
    async def test_read_config_coerces_string_numbers(self, plugin_id, default_len, _client):
        """Config arrives from JSON/WS, so numbers may come through as strings."""
        cfg = make_config(plugin_id, max_packet_length="80", channel_idx="3")
        inst = await load_example(plugin_id, cfg)
        fc = inst._read_config(cfg)
        assert fc.max_packet_length == 80
        assert fc.channel_idx == 3

    @pytest.mark.parametrize("plugin_id,default_len,client_name", EXAMPLES_META)
    async def test_make_transport_builds_its_own_client(self, plugin_id, default_len, client_name):
        cfg = make_config(plugin_id, serial_port="/dev/ttyACM1")
        inst = await load_example(plugin_id, cfg)
        transport = inst._make_transport(cfg)
        assert isinstance(transport, MeshTransport)
        assert type(transport).__name__ == client_name
        assert transport.port == "/dev/ttyACM1"
        assert transport.is_connected is False

    @pytest.mark.parametrize("plugin_id,default_len,_client", EXAMPLES_META)
    async def test_transport_key_changes_with_the_port(self, plugin_id, default_len, _client):
        """A changed key is what makes the SDK rebuild the link on a settings save."""
        inst = await load_example(plugin_id)
        key_a = inst._transport_key(make_config(plugin_id, serial_port="/dev/ttyUSB0"))
        key_b = inst._transport_key(make_config(plugin_id, serial_port="/dev/ttyACM1"))
        assert key_a != key_b

    async def test_meshcore_transport_key_tracks_baud_too(self):
        inst = await load_example("meshcore")
        base = inst._transport_key(make_config("meshcore"))
        assert base == ("/dev/ttyUSB0", 115200)
        assert inst._transport_key(make_config("meshcore", baud=9600)) != base

    async def test_meshcore_make_transport_passes_baud(self):
        cfg = make_config("meshcore", baud="9600")
        inst = await load_example("meshcore", cfg)
        assert inst._make_transport(cfg).baud == 9600


class TestForwardingSkipsTextlessPayloads:
    """Voice TX and standalone IDs reach the hook with no text to put on the mesh."""

    @pytest.mark.parametrize("plugin_id,default_len,_client", EXAMPLES_META)
    async def test_textless_payload_is_passed_through_unforwarded(
        self, plugin_id, default_len, _client
    ):
        cfg = make_config(plugin_id, enabled=True)
        inst = await load_example(plugin_id, cfg)

        class _FakeTransport(MeshTransport):
            sent: list[tuple[str, int]] = []

            @property
            def is_connected(self) -> bool:
                return True

            async def connect(self) -> None: ...
            async def disconnect(self) -> None: ...

            async def send_text(self, text: str, channel: int) -> None:
                self.sent.append((text, channel))

        inst._transport = _FakeTransport()

        # Control: a payload with text is forwarded, so the skip below is meaningful.
        spoken = {"text": "hello", "_display_name": "Ben"}
        assert await inst.on_audio_tx_pre_queue(spoken) is spoken
        assert inst._queue.get_nowait() == ("Ben: hello", 0)

        payload = {"_voice_tx": True, "_display_name": "Ben"}
        assert await inst.on_audio_tx_pre_queue(payload) is payload
        # Nothing queued for the sender task — not even a bare "Ben: " prefix.
        assert inst._queue.empty()


# ---------------------------------------------------------------------------
# Serial clients — connect / send / disconnect contract, no hardware
# ---------------------------------------------------------------------------

def fake_module(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    return mod


class TestMeshCoreClient:
    async def make_client(self, port="/dev/ttyUSB0", baud=115200):
        inst = await load_example("meshcore")
        return type(inst)._make_transport(
            inst, make_config("meshcore", serial_port=port, baud=baud)
        )

    async def test_starts_disconnected(self):
        client = await self.make_client()
        assert client.is_connected is False

    async def test_send_text_before_connect_raises(self):
        client = await self.make_client()
        with pytest.raises(RuntimeError):
            await client.send_text("hi", 0)

    async def test_disconnect_when_never_connected_is_safe(self):
        client = await self.make_client()
        await client.disconnect()  # must not raise
        assert client.is_connected is False

    async def test_connect_without_the_library_raises_an_actionable_error(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "meshcore", None)  # forces ImportError
        client = await self.make_client()
        with pytest.raises(RuntimeError, match="pip install meshcore"):
            await client.connect()
        assert client.is_connected is False

    async def test_connect_then_send_uses_the_channel_message_command(self, monkeypatch):
        sent: list[tuple[int, str]] = []

        class _Commands:
            async def send_chan_msg(self, channel, text):
                sent.append((channel, text))

        class _MeshCore:
            def __init__(self):
                self.commands = _Commands()
                self.closed = False

            @classmethod
            async def create_serial(cls, port, baud):
                cls.opened = (port, baud)
                return cls()

            async def disconnect(self):
                self.closed = True

        monkeypatch.setitem(sys.modules, "meshcore", fake_module("meshcore", MeshCore=_MeshCore))
        client = await self.make_client(port="/dev/ttyACM0", baud=9600)
        await client.connect()
        assert client.is_connected is True
        assert _MeshCore.opened == ("/dev/ttyACM0", 9600)

        await client.send_text("Ben: hello", 2)
        assert sent == [(2, "Ben: hello")]

        await client.disconnect()
        assert client.is_connected is False
        # A second disconnect is still safe once the handle is gone.
        await client.disconnect()


class TestMeshtasticClient:
    async def make_client(self, port="/dev/ttyUSB0"):
        inst = await load_example("meshtastic")
        return type(inst)._make_transport(inst, make_config("meshtastic", serial_port=port))

    async def test_starts_disconnected(self):
        client = await self.make_client()
        assert client.is_connected is False

    async def test_send_text_before_connect_raises(self):
        client = await self.make_client()
        with pytest.raises(RuntimeError):
            await client.send_text("hi", 0)

    async def test_disconnect_when_never_connected_is_safe(self):
        client = await self.make_client()
        await client.disconnect()
        assert client.is_connected is False

    async def test_connect_without_the_library_raises_an_actionable_error(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "meshtastic.serial_interface", None)
        client = await self.make_client()
        with pytest.raises(RuntimeError, match="pip install meshtastic"):
            await client.connect()
        assert client.is_connected is False

    async def test_connect_then_send_uses_sendtext_with_the_channel_index(self, monkeypatch):
        sent: list[tuple[str, int]] = []

        class _SerialInterface:
            def __init__(self, devPath):  # noqa: N803 - the library's own kwarg name
                self.devPath = devPath
                _SerialInterface.opened = devPath
                self.closed = False

            def sendText(self, text, channelIndex):  # noqa: N803 - library kwarg
                sent.append((text, channelIndex))

            def close(self):
                self.closed = True

        monkeypatch.setitem(
            sys.modules,
            "meshtastic.serial_interface",
            fake_module("meshtastic.serial_interface", SerialInterface=_SerialInterface),
        )
        client = await self.make_client(port="/dev/ttyACM0")
        await client.connect()
        assert client.is_connected is True
        assert _SerialInterface.opened == "/dev/ttyACM0"

        await client.send_text("Ben: hello", 1)
        assert sent == [("Ben: hello", 1)]

        await client.disconnect()
        assert client.is_connected is False
        await client.disconnect()  # still safe
