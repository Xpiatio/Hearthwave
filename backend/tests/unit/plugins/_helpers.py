"""Shared scaffolding for the example-plugin tests.

Not a conftest: these are plain callables the tests invoke with arguments
(a plugin id, a config), which fixtures would only make more indirect.
"""
from __future__ import annotations

import logging
from pathlib import Path

from backend.config import ServerConfig
from backend.plugins import loader
from backend.plugins.context import PluginContext
from backend.plugins.registry import PluginRegistry

EXAMPLES = Path(__file__).resolve().parents[4] / "examples" / "plugins"


def make_ctx(config: ServerConfig | None = None, *, report_position=None) -> PluginContext:
    async def _noop(*_a, **_k):
        return None

    return PluginContext(
        broadcast=_noop,
        enqueue_tx=_noop,
        get_config=(lambda: config) if config is not None else dict,
        channel_clear=lambda: True,
        report_position=report_position or _noop,
        data_dir=Path("/tmp"),
        logger=logging.getLogger("test.plugin"),
    )


async def load_example(plugin_id: str, config: ServerConfig | None = None, *, ctx=None):
    """Load an example plugin from examples/plugins the way a real install does."""
    inst = await loader.load_plugin(
        EXAMPLES / plugin_id, ctx or make_ctx(config), PluginRegistry()
    )
    assert inst is not None, f"example plugin {plugin_id} failed to load"
    return inst


def make_config(plugin_id: str, **values) -> ServerConfig:
    cfg = ServerConfig()
    if values:
        cfg.set_plugin_config(plugin_id, values)
    return cfg
