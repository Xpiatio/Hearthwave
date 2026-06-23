"""Unit tests for backend.plugins.mesh_forwarder.

MeshForwarderPlugin is the shared base for outbound-only mesh bridges (MeshCore
today, Meshtastic later). It builds a name-prefixed packet, clamps it to the
mesh max length, and forwards it without ever blocking or modifying the radio TX
path. Concrete subclasses supply only the wire protocol + config mapping.
"""
from __future__ import annotations

import asyncio

import pytest

from backend.plugins.mesh_forwarder import (
    _OUTBOUND_QUEUE_MAX,
    MeshForwardConfig,
    MeshForwarderPlugin,
    MeshTransport,
)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class FakeTransport(MeshTransport):
    def __init__(self, *, fail_send: bool = False) -> None:
        self._connected = False
        self._fail_send = fail_send
        self.sent: list[tuple[str, int]] = []
        self.connect_calls = 0
        self.disconnect_calls = 0

    async def connect(self) -> None:
        self._connected = True
        self.connect_calls += 1

    async def disconnect(self) -> None:
        self._connected = False
        self.disconnect_calls += 1

    async def send_text(self, text: str, channel: int) -> None:
        if self._fail_send:
            raise RuntimeError("serial write failed")
        self.sent.append((text, channel))

    @property
    def is_connected(self) -> bool:
        return self._connected


class _Ctx:
    """Minimal PluginContext stand-in exposing just get_config()."""

    def __init__(self, config: dict) -> None:
        self._config = config

    def get_config(self) -> dict:
        return self._config


class FakeForwarder(MeshForwarderPlugin):
    """Concrete forwarder reading a plain dict.

    If a fixed transport is injected it is always returned; otherwise each
    _make_transport() builds a fresh FakeTransport (so rebuilds are observable).
    _transport_key keys off config["port"] so a port change triggers a rebuild.
    """

    def __init__(self, config: dict, transport: MeshTransport | None = None) -> None:
        super().__init__()
        self.ctx = _Ctx(config)
        self._fixed = transport
        self.created: list[MeshTransport] = []

    def _read_config(self, config) -> MeshForwardConfig:
        return MeshForwardConfig(
            enabled=config["enabled"],
            max_packet_length=config["max"],
            prefix_separator=config["sep"],
            channel_idx=config["chan"],
        )

    def _make_transport(self, config) -> MeshTransport:
        t = self._fixed if self._fixed is not None else FakeTransport()
        self.created.append(t)
        return t

    def _transport_key(self, config):
        return config["port"]


def make_config(*, enabled=True, max_len=140, sep=": ", chan=0, port="/dev/ttyUSB0") -> dict:
    return {"enabled": enabled, "max": max_len, "sep": sep, "chan": chan, "port": port}


# ---------------------------------------------------------------------------
# build_message — prefix + clamp
# ---------------------------------------------------------------------------

class TestBuildMessage:
    def setup_method(self):
        self.fwd = FakeForwarder(make_config(), FakeTransport())

    def test_prefixes_display_name(self):
        cfg = self.fwd._read_config(make_config())
        out = self.fwd.build_message({"_display_name": "Ben", "text": "hello"}, cfg)
        assert out == "Ben: hello"

    def test_falls_back_to_operator_then_callsign(self):
        cfg = self.fwd._read_config(make_config())
        assert self.fwd.build_message({"operator": "Op", "text": "hi"}, cfg) == "Op: hi"
        assert self.fwd.build_message({"callsign": "WX1", "text": "hi"}, cfg) == "WX1: hi"

    def test_no_name_means_no_prefix(self):
        cfg = self.fwd._read_config(make_config())
        assert self.fwd.build_message({"text": "anon"}, cfg) == "anon"

    def test_clamps_to_max_packet_length(self):
        cfg = self.fwd._read_config(make_config(max_len=10))
        out = self.fwd.build_message({"_display_name": "Ben", "text": "0123456789"}, cfg)
        assert out == "Ben: 01234"  # "Ben: " (5) + first 5 chars = 10
        assert len(out) == 10

    def test_custom_separator(self):
        cfg = self.fwd._read_config(make_config(sep=" > "))
        assert self.fwd.build_message({"_display_name": "Ben", "text": "go"}, cfg) == "Ben > go"


# ---------------------------------------------------------------------------
# on_audio_tx_pre_queue — never blocks, only enqueues when live
# ---------------------------------------------------------------------------

class TestTxPreQueue:
    async def test_always_returns_payload_unchanged(self):
        fwd = FakeForwarder(make_config(enabled=False), FakeTransport())
        payload = {"text": "x", "_display_name": "Ben"}
        result = await fwd.on_audio_tx_pre_queue(payload)
        assert result is payload  # never blocks or copies

    async def test_does_not_enqueue_when_disabled(self):
        fwd = FakeForwarder(make_config(enabled=False), FakeTransport())
        await fwd.on_audio_tx_pre_queue({"text": "x", "_display_name": "Ben"})
        assert fwd._queue.qsize() == 0

    async def test_does_not_enqueue_when_not_connected(self):
        # enabled, but on_config_changed never ran → transport not connected
        fwd = FakeForwarder(make_config(enabled=True), FakeTransport())
        await fwd.on_audio_tx_pre_queue({"text": "x", "_display_name": "Ben"})
        assert fwd._queue.qsize() == 0

    async def test_enqueue_failure_does_not_block_tx(self):
        """A broken enqueue must still return the payload (TX proceeds)."""
        fwd = FakeForwarder(make_config(enabled=True), FakeTransport())
        await fwd.on_config_changed(fwd.ctx.get_config())

        class BoomQueue:
            def put_nowait(self, item):
                raise RuntimeError("queue full")

        fwd._queue = BoomQueue()  # only put_nowait is exercised by the TX path
        payload = {"text": "x", "_display_name": "Ben"}
        assert await fwd.on_audio_tx_pre_queue(payload) is payload
        fwd._sender_task.cancel()  # was awaiting the real queue; stop it cleanly


# ---------------------------------------------------------------------------
# lifecycle + end-to-end delivery
# ---------------------------------------------------------------------------

class TestLifecycleAndDelivery:
    async def test_enabled_connects_and_starts_sender(self):
        transport = FakeTransport()
        fwd = FakeForwarder(make_config(enabled=True), transport)
        await fwd.on_config_changed(fwd.ctx.get_config())
        assert transport.connect_calls == 1
        assert transport.is_connected
        assert fwd._sender_task is not None
        await fwd._teardown()

    async def test_disabled_tears_down_connection(self):
        transport = FakeTransport()
        cfg = make_config(enabled=True)
        fwd = FakeForwarder(cfg, transport)
        await fwd.on_config_changed(cfg)
        cfg["enabled"] = False
        await fwd.on_config_changed(cfg)
        assert transport.disconnect_calls == 1
        assert not transport.is_connected

    async def test_forwards_prefixed_message_to_transport(self):
        transport = FakeTransport()
        fwd = FakeForwarder(make_config(enabled=True, chan=2), transport)
        await fwd.on_config_changed(fwd.ctx.get_config())
        await fwd.on_audio_tx_pre_queue({"_display_name": "Ben", "text": "hello mesh"})
        await asyncio.wait_for(fwd._queue.join(), timeout=1.0)
        assert transport.sent == [("Ben: hello mesh", 2)]
        await fwd._teardown()

    async def test_send_failure_is_swallowed(self):
        transport = FakeTransport(fail_send=True)
        fwd = FakeForwarder(make_config(enabled=True), transport)
        await fwd.on_config_changed(fwd.ctx.get_config())
        await fwd.on_audio_tx_pre_queue({"_display_name": "Ben", "text": "boom"})
        # join() returns once the item is marked done even though send raised
        await asyncio.wait_for(fwd._queue.join(), timeout=1.0)
        assert transport.sent == []
        await fwd._teardown()


# ---------------------------------------------------------------------------
# bounded outbound queue
# ---------------------------------------------------------------------------

class TestBoundedQueue:
    async def test_queue_is_bounded(self):
        fwd = FakeForwarder(make_config(enabled=True), FakeTransport())
        assert fwd._queue.maxsize == _OUTBOUND_QUEUE_MAX

    async def test_drops_when_full_without_blocking_tx(self):
        """A wedged link must not grow memory: enqueue drops, TX still proceeds."""
        transport = FakeTransport()
        fwd = FakeForwarder(make_config(enabled=True), transport)
        # Mark connected but do NOT start the sender loop, so the queue can't drain.
        fwd._transport = transport
        transport._connected = True
        for _ in range(_OUTBOUND_QUEUE_MAX):
            fwd._queue.put_nowait(("filler", 0))
        assert fwd._queue.full()

        payload = {"_display_name": "Ben", "text": "overflow"}
        result = await fwd.on_audio_tx_pre_queue(payload)
        assert result is payload  # TX unaffected
        assert fwd._queue.qsize() == _OUTBOUND_QUEUE_MAX  # dropped, no growth


# ---------------------------------------------------------------------------
# transport rebuild on connection-param change
# ---------------------------------------------------------------------------

class TestTransportRebuild:
    async def test_teardown_clears_transport(self):
        fwd = FakeForwarder(make_config(enabled=True))
        await fwd.on_config_changed(fwd.ctx.get_config())
        assert fwd._transport is not None
        await fwd._teardown()
        assert fwd._transport is None

    async def test_disable_then_enable_rebuilds_transport(self):
        cfg = make_config(enabled=True)
        fwd = FakeForwarder(cfg)
        await fwd.on_config_changed(cfg)
        cfg["enabled"] = False
        await fwd.on_config_changed(cfg)
        cfg["enabled"] = True
        await fwd.on_config_changed(cfg)
        assert len(fwd.created) == 2  # rebuilt on re-enable
        await fwd._teardown()

    async def test_port_change_while_enabled_rebuilds_and_reconnects(self):
        cfg = make_config(enabled=True, port="/dev/ttyUSB0")
        fwd = FakeForwarder(cfg)
        await fwd.on_config_changed(cfg)
        first = fwd.created[0]
        cfg["port"] = "/dev/ttyACM1"
        await fwd.on_config_changed(cfg)
        assert len(fwd.created) == 2
        assert first is not fwd.created[1]
        assert first.disconnect_calls == 1  # old link closed
        assert fwd.created[1].is_connected  # new link opened
        await fwd._teardown()

    async def test_no_rebuild_when_params_unchanged(self):
        cfg = make_config(enabled=True)
        fwd = FakeForwarder(cfg)
        await fwd.on_config_changed(cfg)
        await fwd.on_config_changed(cfg)  # same params
        assert len(fwd.created) == 1
        await fwd._teardown()
