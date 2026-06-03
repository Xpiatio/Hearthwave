"""Unit tests for backend.plugins.base.BasePlugin.

All hook methods are no-ops by default; this suite verifies that contract so
subclasses can rely on calling super() safely.
"""
from __future__ import annotations

import pytest

from backend.plugins.base import BasePlugin


class TestBasePluginDefaults:
    """BasePlugin default implementations are all no-ops / pass-throughs."""

    async def test_on_client_message_received_returns_none(self):
        plugin = BasePlugin()
        result = await plugin.on_client_message_received({"type": "ping"})
        assert result is None

    async def test_on_client_message_received_accepts_reply_kwarg(self):
        """reply= kwarg must be accepted without error."""
        plugin = BasePlugin()
        calls = []
        async def mock_reply(msg):
            calls.append(msg)

        result = await plugin.on_client_message_received({"type": "ping"}, reply=mock_reply)
        assert result is None
        assert calls == [], "base impl must not call reply"

    async def test_on_audio_rx_start_returns_none(self):
        plugin = BasePlugin()
        result = await plugin.on_audio_rx_start()
        assert result is None

    def test_on_audio_rx_chunk_returns_none(self):
        plugin = BasePlugin()
        result = plugin.on_audio_rx_chunk(b"\x00\x01\x02\x03")
        assert result is None

    def test_on_audio_rx_chunk_is_synchronous(self):
        """Verify the method is not a coroutine — it runs on the STT worker thread."""
        import inspect
        plugin = BasePlugin()
        assert not inspect.iscoroutinefunction(plugin.on_audio_rx_chunk)

    async def test_on_rx_final_returns_none(self):
        plugin = BasePlugin()
        result = await plugin.on_rx_final("hello world")
        assert result is None

    async def test_on_audio_tx_pre_queue_returns_payload_unchanged(self):
        """Default implementation must pass the payload through unmodified."""
        plugin = BasePlugin()
        payload = {"text": "test transmission", "_voice_name": "default"}
        result = await plugin.on_audio_tx_pre_queue(payload)
        assert result is payload

    async def test_on_audio_tx_pre_queue_does_not_block_tx(self):
        """Returning the payload (not None) means TX is allowed."""
        plugin = BasePlugin()
        payload = {"text": "go ahead"}
        result = await plugin.on_audio_tx_pre_queue(payload)
        assert result is not None

    async def test_on_audio_tx_pre_queue_empty_payload(self):
        plugin = BasePlugin()
        result = await plugin.on_audio_tx_pre_queue({})
        assert result == {}

    def test_base_plugin_is_instantiable(self):
        plugin = BasePlugin()
        assert isinstance(plugin, BasePlugin)

    async def test_multiple_hook_calls_are_independent(self):
        """Repeated calls produce the same result — no state accumulates."""
        plugin = BasePlugin()
        for _ in range(3):
            assert await plugin.on_client_message_received({}) is None
            assert await plugin.on_audio_rx_start() is None
            assert await plugin.on_rx_final("text") is None
            payload = {"text": "x"}
            assert await plugin.on_audio_tx_pre_queue(payload) is payload
