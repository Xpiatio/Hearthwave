"""Unit tests for backend.plugins.meshcore.

MeshCorePlugin is a thin concrete MeshForwarderPlugin: it maps the meshcore_*
ServerConfig keys and builds a MeshCoreClient transport. The forwarding/queue
behaviour itself is covered by test_mesh_forwarder; here we verify the config
mapping, the transport factory, and the client's connect/disconnect contract
(the wire protocol is exercised against a fake serial link, not real hardware).
"""
from __future__ import annotations

import pytest

from backend.config import ServerConfig
from backend.plugins.mesh_forwarder import MeshForwardConfig, MeshForwarderPlugin, MeshTransport
from backend.plugins.meshcore import MeshCoreClient, MeshCorePlugin


def make_config(**kwargs) -> ServerConfig:
    cfg = ServerConfig()
    cfg.update(kwargs)
    return cfg


# ---------------------------------------------------------------------------
# MeshCorePlugin — config mapping + transport factory
# ---------------------------------------------------------------------------

class TestMeshCorePlugin:
    def test_is_a_mesh_forwarder(self):
        plugin = MeshCorePlugin(config_getter=make_config)
        assert isinstance(plugin, MeshForwarderPlugin)

    def test_read_config_maps_meshcore_keys(self):
        cfg = make_config(
            meshcore_enabled=True,
            meshcore_max_packet_length=200,
            meshcore_prefix_separator=" > ",
            meshcore_channel_idx=2,
        )
        plugin = MeshCorePlugin(config_getter=lambda: cfg)
        fc = plugin._read_config(cfg)
        assert fc == MeshForwardConfig(
            enabled=True, max_packet_length=200, prefix_separator=" > ", channel_idx=2
        )

    def test_read_config_defaults_when_disabled(self):
        cfg = make_config()
        plugin = MeshCorePlugin(config_getter=lambda: cfg)
        fc = plugin._read_config(cfg)
        assert fc.enabled is False
        assert fc.max_packet_length == 140
        assert fc.prefix_separator == ": "
        assert fc.channel_idx == 0

    def test_make_transport_returns_meshcore_client(self):
        cfg = make_config(meshcore_serial_port="/dev/ttyACM1", meshcore_baud=9600)
        plugin = MeshCorePlugin(config_getter=lambda: cfg)
        transport = plugin._make_transport(cfg)
        assert isinstance(transport, MeshCoreClient)
        assert isinstance(transport, MeshTransport)
        assert transport.port == "/dev/ttyACM1"
        assert transport.baud == 9600

    def test_transport_key_tracks_port_and_baud(self):
        plugin = MeshCorePlugin(config_getter=make_config)
        assert plugin._transport_key(make_config(meshcore_serial_port="/dev/ttyUSB0", meshcore_baud=115200)) == ("/dev/ttyUSB0", 115200)
        # A port or baud change yields a different key (→ rebuild).
        assert plugin._transport_key(make_config(meshcore_serial_port="/dev/ttyACM1")) != ("/dev/ttyUSB0", 115200)


# ---------------------------------------------------------------------------
# MeshCoreClient — connect/disconnect contract
# ---------------------------------------------------------------------------

class TestMeshCoreClient:
    def test_starts_disconnected(self):
        client = MeshCoreClient(port="/dev/ttyUSB0", baud=115200)
        assert client.is_connected is False

    async def test_disconnect_when_never_connected_is_safe(self):
        client = MeshCoreClient(port="/dev/ttyUSB0", baud=115200)
        await client.disconnect()  # must not raise
        assert client.is_connected is False

    async def test_send_text_before_connect_raises(self):
        client = MeshCoreClient(port="/dev/ttyUSB0", baud=115200)
        with pytest.raises(RuntimeError):
            await client.send_text("hi", 0)
