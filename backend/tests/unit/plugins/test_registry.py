"""Unit tests for backend.plugins.registry.PluginRegistry.

Covers: register, dispatch_client_message, dispatch_audio_rx_start,
dispatch_audio_rx_chunk, dispatch_rx_final, dispatch_tx_pre_queue
(including chain-stopping on None return and exception swallowing).
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.plugins.base import BasePlugin
from backend.plugins.registry import PluginRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_registry(*plugins) -> PluginRegistry:
    r = PluginRegistry()
    for p in plugins:
        r.register(p)
    return r


def spy_plugin(
    *,
    on_client_message_received=None,
    on_audio_rx_start=None,
    on_audio_rx_chunk=None,
    on_rx_final=None,
    on_audio_tx_pre_queue=None,
) -> BasePlugin:
    """Return a BasePlugin subclass with overrideable async/sync hooks."""
    plugin = BasePlugin()
    if on_client_message_received is not None:
        plugin.on_client_message_received = on_client_message_received
    if on_audio_rx_start is not None:
        plugin.on_audio_rx_start = on_audio_rx_start
    if on_audio_rx_chunk is not None:
        plugin.on_audio_rx_chunk = on_audio_rx_chunk
    if on_rx_final is not None:
        plugin.on_rx_final = on_rx_final
    if on_audio_tx_pre_queue is not None:
        plugin.on_audio_tx_pre_queue = on_audio_tx_pre_queue
    return plugin


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------

class TestRegister:
    def test_register_adds_plugin(self):
        registry = PluginRegistry()
        p = BasePlugin()
        registry.register(p)
        assert p in registry._plugins

    def test_register_multiple_plugins_preserves_order(self):
        registry = PluginRegistry()
        p1, p2, p3 = BasePlugin(), BasePlugin(), BasePlugin()
        registry.register(p1)
        registry.register(p2)
        registry.register(p3)
        assert registry._plugins == [p1, p2, p3]

    def test_register_empty_by_default(self):
        registry = PluginRegistry()
        assert registry._plugins == []

    def test_register_logs_plugin_name(self, caplog):
        import logging
        registry = PluginRegistry()

        class MySpecialPlugin(BasePlugin):
            pass

        with caplog.at_level(logging.INFO, logger="backend.plugins.registry"):
            registry.register(MySpecialPlugin())
        assert "MySpecialPlugin" in caplog.text


# ---------------------------------------------------------------------------
# dispatch_client_message
# ---------------------------------------------------------------------------

class TestDispatchClientMessage:
    async def test_calls_all_plugins(self):
        called = []

        async def hook(payload, reply=None):
            called.append(payload)

        p1 = spy_plugin(on_client_message_received=hook)
        p2 = spy_plugin(on_client_message_received=hook)
        registry = make_registry(p1, p2)
        await registry.dispatch_client_message({"type": "ping"})
        assert len(called) == 2

    async def test_passes_payload_and_reply(self):
        received = {}

        async def hook(payload, reply=None):
            received["payload"] = payload
            received["reply"] = reply

        registry = make_registry(spy_plugin(on_client_message_received=hook))
        reply_fn = AsyncMock()
        await registry.dispatch_client_message({"type": "x"}, reply=reply_fn)
        assert received["payload"] == {"type": "x"}
        assert received["reply"] is reply_fn

    async def test_swallows_exception_and_continues(self):
        """An exception in plugin 1 must not prevent plugin 2 from being called."""
        called = []

        async def bad_hook(payload, reply=None):
            raise RuntimeError("boom")

        async def good_hook(payload, reply=None):
            called.append(True)

        registry = make_registry(
            spy_plugin(on_client_message_received=bad_hook),
            spy_plugin(on_client_message_received=good_hook),
        )
        await registry.dispatch_client_message({"type": "test"})
        assert called == [True]

    async def test_no_plugins_does_not_raise(self):
        registry = PluginRegistry()
        await registry.dispatch_client_message({"type": "empty"})

    async def test_exception_is_logged(self, caplog):
        import logging

        async def bad_hook(payload, reply=None):
            raise ValueError("test error")

        registry = make_registry(spy_plugin(on_client_message_received=bad_hook))
        with caplog.at_level(logging.ERROR, logger="backend.plugins.registry"):
            await registry.dispatch_client_message({})
        assert "on_client_message_received" in caplog.text


# ---------------------------------------------------------------------------
# dispatch_audio_rx_start
# ---------------------------------------------------------------------------

class TestDispatchAudioRxStart:
    async def test_calls_all_plugins(self):
        calls = []

        async def hook():
            calls.append(True)

        p1 = spy_plugin(on_audio_rx_start=hook)
        p2 = spy_plugin(on_audio_rx_start=hook)
        registry = make_registry(p1, p2)
        await registry.dispatch_audio_rx_start()
        assert len(calls) == 2

    async def test_swallows_exception_and_continues(self):
        calls = []

        async def bad_hook():
            raise RuntimeError("rx start boom")

        async def good_hook():
            calls.append(True)

        registry = make_registry(
            spy_plugin(on_audio_rx_start=bad_hook),
            spy_plugin(on_audio_rx_start=good_hook),
        )
        await registry.dispatch_audio_rx_start()
        assert calls == [True]

    async def test_no_plugins_does_not_raise(self):
        await PluginRegistry().dispatch_audio_rx_start()

    async def test_exception_logged(self, caplog):
        import logging

        async def bad_hook():
            raise OSError("device gone")

        registry = make_registry(spy_plugin(on_audio_rx_start=bad_hook))
        with caplog.at_level(logging.ERROR, logger="backend.plugins.registry"):
            await registry.dispatch_audio_rx_start()
        assert "on_audio_rx_start" in caplog.text


# ---------------------------------------------------------------------------
# dispatch_audio_rx_chunk
# ---------------------------------------------------------------------------

class TestDispatchAudioRxChunk:
    def test_calls_all_plugins(self):
        chunks = []

        def hook(chunk):
            chunks.append(chunk)

        p1 = spy_plugin(on_audio_rx_chunk=hook)
        p2 = spy_plugin(on_audio_rx_chunk=hook)
        registry = make_registry(p1, p2)
        data = b"\x00\x01\x02\x03"
        registry.dispatch_audio_rx_chunk(data)
        assert chunks == [data, data]

    def test_is_synchronous(self):
        """dispatch_audio_rx_chunk must be a regular function, not a coroutine."""
        import inspect
        registry = PluginRegistry()
        assert not inspect.iscoroutinefunction(registry.dispatch_audio_rx_chunk)

    def test_swallows_exception_and_continues(self):
        calls = []

        def bad_hook(chunk):
            raise RuntimeError("chunk boom")

        def good_hook(chunk):
            calls.append(chunk)

        registry = make_registry(
            spy_plugin(on_audio_rx_chunk=bad_hook),
            spy_plugin(on_audio_rx_chunk=good_hook),
        )
        registry.dispatch_audio_rx_chunk(b"\xff")
        assert calls == [b"\xff"]

    def test_no_plugins_does_not_raise(self):
        PluginRegistry().dispatch_audio_rx_chunk(b"")

    def test_exception_logged(self, caplog):
        import logging

        def bad_hook(chunk):
            raise ValueError("bad chunk")

        registry = make_registry(spy_plugin(on_audio_rx_chunk=bad_hook))
        with caplog.at_level(logging.ERROR, logger="backend.plugins.registry"):
            registry.dispatch_audio_rx_chunk(b"\x00")
        assert "on_audio_rx_chunk" in caplog.text


# ---------------------------------------------------------------------------
# dispatch_rx_final
# ---------------------------------------------------------------------------

class TestDispatchRxFinal:
    async def test_calls_all_plugins_with_text(self):
        received = []

        async def hook(text):
            received.append(text)

        p1 = spy_plugin(on_rx_final=hook)
        p2 = spy_plugin(on_rx_final=hook)
        registry = make_registry(p1, p2)
        await registry.dispatch_rx_final("hello there")
        assert received == ["hello there", "hello there"]

    async def test_swallows_exception_and_continues(self):
        calls = []

        async def bad_hook(text):
            raise RuntimeError("rx final boom")

        async def good_hook(text):
            calls.append(text)

        registry = make_registry(
            spy_plugin(on_rx_final=bad_hook),
            spy_plugin(on_rx_final=good_hook),
        )
        await registry.dispatch_rx_final("test")
        assert calls == ["test"]

    async def test_no_plugins_does_not_raise(self):
        await PluginRegistry().dispatch_rx_final("any text")

    async def test_exception_logged(self, caplog):
        import logging

        async def bad_hook(text):
            raise TypeError("bad type")

        registry = make_registry(spy_plugin(on_rx_final=bad_hook))
        with caplog.at_level(logging.ERROR, logger="backend.plugins.registry"):
            await registry.dispatch_rx_final("hi")
        assert "on_rx_final" in caplog.text


# ---------------------------------------------------------------------------
# dispatch_tx_pre_queue
# ---------------------------------------------------------------------------

class TestDispatchTxPreQueue:
    async def test_returns_payload_when_no_plugins(self):
        payload = {"text": "go"}
        result = await PluginRegistry().dispatch_tx_pre_queue(payload)
        assert result is payload

    async def test_single_plugin_passes_payload_through(self):
        payload = {"text": "hello"}
        registry = make_registry(BasePlugin())
        result = await registry.dispatch_tx_pre_queue(payload)
        assert result == payload

    async def test_plugin_can_modify_payload(self):
        async def hook(payload):
            return {**payload, "text": payload["text"].upper()}

        registry = make_registry(spy_plugin(on_audio_tx_pre_queue=hook))
        result = await registry.dispatch_tx_pre_queue({"text": "quiet please"})
        assert result == {"text": "QUIET PLEASE"}

    async def test_first_none_blocks_chain_and_returns_none(self):
        """First plugin returning None must stop the chain immediately."""
        second_called = []

        async def blocking_hook(payload):
            return None

        async def second_hook(payload):
            second_called.append(True)
            return payload

        registry = make_registry(
            spy_plugin(on_audio_tx_pre_queue=blocking_hook),
            spy_plugin(on_audio_tx_pre_queue=second_hook),
        )
        result = await registry.dispatch_tx_pre_queue({"text": "blocked"})
        assert result is None
        assert second_called == [], "chain must stop when first plugin returns None"

    async def test_second_plugin_can_block(self):
        """The second plugin in a chain can also block TX."""
        async def pass_hook(payload):
            return payload

        async def block_hook(payload):
            return None

        registry = make_registry(
            spy_plugin(on_audio_tx_pre_queue=pass_hook),
            spy_plugin(on_audio_tx_pre_queue=block_hook),
        )
        result = await registry.dispatch_tx_pre_queue({"text": "hello"})
        assert result is None

    async def test_modified_payload_passed_to_next_plugin(self):
        """Each plugin in the chain receives the payload as returned by the previous one."""
        seen = []

        async def modifier(payload):
            return {**payload, "step": payload.get("step", 0) + 1}

        async def recorder(payload):
            seen.append(payload["step"])
            return payload

        registry = make_registry(
            spy_plugin(on_audio_tx_pre_queue=modifier),
            spy_plugin(on_audio_tx_pre_queue=recorder),
        )
        await registry.dispatch_tx_pre_queue({"text": "chained"})
        assert seen == [1]

    async def test_exception_is_swallowed_and_chain_continues(self):
        """A plugin that raises must not block the rest of the chain."""
        calls = []

        async def bad_hook(payload):
            raise RuntimeError("tx boom")

        async def good_hook(payload):
            calls.append(payload)
            return payload

        registry = make_registry(
            spy_plugin(on_audio_tx_pre_queue=bad_hook),
            spy_plugin(on_audio_tx_pre_queue=good_hook),
        )
        result = await registry.dispatch_tx_pre_queue({"text": "survive"})
        assert result == {"text": "survive"}
        assert len(calls) == 1

    async def test_exception_is_logged(self, caplog):
        import logging

        async def bad_hook(payload):
            raise ValueError("exploded")

        registry = make_registry(spy_plugin(on_audio_tx_pre_queue=bad_hook))
        with caplog.at_level(logging.ERROR, logger="backend.plugins.registry"):
            await registry.dispatch_tx_pre_queue({"text": "log me"})
        assert "on_audio_tx_pre_queue" in caplog.text

    async def test_three_plugins_all_pass(self):
        registry = make_registry(BasePlugin(), BasePlugin(), BasePlugin())
        payload = {"text": "all pass"}
        result = await registry.dispatch_tx_pre_queue(payload)
        assert result == payload

    async def test_none_return_is_logged(self, caplog):
        import logging

        async def blocking_hook(payload):
            return None

        registry = make_registry(spy_plugin(on_audio_tx_pre_queue=blocking_hook))
        with caplog.at_level(logging.DEBUG, logger="backend.plugins.registry"):
            result = await registry.dispatch_tx_pre_queue({"text": "block"})
        assert result is None


# ---------------------------------------------------------------------------
# module-level singleton
# ---------------------------------------------------------------------------

class TestModuleLevelSingleton:
    def test_plugin_registry_singleton_is_exported(self):
        from backend.plugins.registry import plugin_registry
        assert isinstance(plugin_registry, PluginRegistry)
