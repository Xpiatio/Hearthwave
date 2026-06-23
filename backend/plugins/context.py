"""PluginContext — the stable service surface handed to every plugin.

A plugin never reaches into server internals; it receives a PluginContext (bound
to `self.ctx` by the loader before `setup()`) and uses only what's here. Keeping
this the single injection point lets the host evolve without breaking plugins.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable


@dataclass(frozen=True)
class PluginContext:
    """Core services available to a plugin.

      broadcast(msg)     — send a JSON-able dict to every connected client (async)
      enqueue_tx(payload)— push a transmission onto the TX synthesis queue (async).
                           payload is the same dict shape the TX hooks see, e.g.
                           {"text": ..., "_pre_formatted": True}.
      get_config()       — the live ServerConfig (dict-like). Read tunables here;
                           a plugin's own settings live under config["plugins"][id].
      channel_clear()    — True when the channel is idle (safe to transmit).
      data_dir           — the writable data directory (e.g. for plugin state files).
      logger             — a logger namespaced to the plugin.
    """

    broadcast: Callable[[dict], Awaitable[None]]
    enqueue_tx: Callable[[dict], Awaitable[None]]
    get_config: Callable[[], object]
    channel_clear: Callable[[], bool]
    data_dir: Path
    logger: logging.Logger

    def for_plugin(self, plugin_id: str) -> "PluginContext":
        """Return a copy with a logger namespaced to `plugin_id`."""
        return PluginContext(
            broadcast=self.broadcast,
            enqueue_tx=self.enqueue_tx,
            get_config=self.get_config,
            channel_clear=self.channel_clear,
            data_dir=self.data_dir,
            logger=logging.getLogger(f"hearthwave.plugin.{plugin_id}"),
        )

    def plugin_config(self, plugin_id: str) -> dict:
        """Convenience: this plugin's config namespace (config["plugins"][id])."""
        config = self.get_config()
        return (config.get("plugins") or {}).get(plugin_id) or {}
