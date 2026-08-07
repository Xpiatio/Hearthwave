"""Hearthwave plugin SDK — the stable public surface for writing plugins.

Third-party plugins should import everything from here:

    from backend.plugins.sdk import BasePlugin, PluginManifest, ConfigField

Internal modules (base, context, mesh_forwarder, position_source) may be
reorganised; this module is the contract that stays stable. See docs/plugins.md
for the authoring guide.

A plugin lives at /data/plugins/<id>/plugin.py and exposes a BasePlugin subclass
(or a module-level `PLUGIN` instance / `get_plugin()` factory). The loader binds a
PluginContext to `self.ctx`, calls `await setup()`, registers it, then dispatches
`on_config_changed`. Its settings live under config["plugins"][<id>] and are
described declaratively via the manifest's `config_schema`.
"""
from __future__ import annotations

from backend.plugins.base import BasePlugin, ConfigField, PluginManifest
from backend.plugins.context import PluginContext
from backend.plugins.mesh_forwarder import (
    MeshForwardConfig,
    MeshForwarderPlugin,
    MeshTransport,
)
from backend.plugins.position_source import MIN_POLL_SECONDS, PositionPoller

__all__ = [
    "BasePlugin",
    "PluginManifest",
    "ConfigField",
    "PluginContext",
    "MeshForwarderPlugin",
    "MeshTransport",
    "MeshForwardConfig",
    "PositionPoller",
    "MIN_POLL_SECONDS",
]
