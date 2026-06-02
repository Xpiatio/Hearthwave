"""Plugin registry — collects BasePlugin instances and dispatches hook calls."""
from __future__ import annotations

import logging

from backend.plugins.base import BasePlugin

_log = logging.getLogger(__name__)


class PluginRegistry:
    """Singleton registry that dispatches lifecycle hooks to all registered plugins."""

    def __init__(self) -> None:
        self._plugins: list[BasePlugin] = []

    def register(self, plugin: BasePlugin) -> None:
        """Add a plugin to the registry. Call before the server accepts connections."""
        self._plugins.append(plugin)
        _log.info("Plugin registered: %s", type(plugin).__name__)

    # ------------------------------------------------------------------
    # Hook dispatchers
    # ------------------------------------------------------------------

    async def dispatch_client_message(self, payload: dict, reply=None) -> None:
        """Notify all plugins of an inbound client WS message (fire-and-forget)."""
        for plugin in self._plugins:
            try:
                await plugin.on_client_message_received(payload, reply=reply)
            except Exception:
                _log.exception("Plugin %s raised in on_client_message_received", type(plugin).__name__)

    async def dispatch_audio_rx_start(self) -> None:
        """Notify all plugins that squelch has opened."""
        for plugin in self._plugins:
            try:
                await plugin.on_audio_rx_start()
            except Exception:
                _log.exception("Plugin %s raised in on_audio_rx_start", type(plugin).__name__)

    def dispatch_audio_rx_chunk(self, chunk) -> None:
        """Dispatch audio chunk to all plugins (sync — called from STT worker thread)."""
        for plugin in self._plugins:
            try:
                plugin.on_audio_rx_chunk(chunk)
            except Exception:
                _log.exception("Plugin %s raised in on_audio_rx_chunk", type(plugin).__name__)

    async def dispatch_rx_final(self, text: str) -> None:
        """Notify all plugins of a finalized RX transcript."""
        for plugin in self._plugins:
            try:
                await plugin.on_rx_final(text)
            except Exception:
                _log.exception("Plugin %s raised in on_rx_final", type(plugin).__name__)

    async def dispatch_tx_pre_queue(self, payload: dict) -> dict | None:
        """Run the TX pre-queue hook chain.

        Plugins are called in registration order. If any returns None the chain
        stops and TX is blocked. Otherwise the (possibly modified) payload is
        returned for queuing.
        """
        for plugin in self._plugins:
            try:
                result = await plugin.on_audio_tx_pre_queue(payload)
            except Exception:
                _log.exception("Plugin %s raised in on_audio_tx_pre_queue", type(plugin).__name__)
                continue
            if result is None:
                _log.debug("TX blocked by plugin %s", type(plugin).__name__)
                return None
            payload = result
        return payload


plugin_registry = PluginRegistry()
