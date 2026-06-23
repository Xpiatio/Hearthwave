"""Dynamic plugin loader — discovers and (hot-)loads plugins from a directory.

A plugin is a directory under the plugins dir (default /data/plugins, override with
RADIO_TTY_PLUGINS_DIR) containing a `plugin.py`. From it the loader resolves a
BasePlugin instance via, in priority order:

  1. a module-level `PLUGIN` that is a BasePlugin instance, or
  2. a module-level `get_plugin()` factory returning one, or
  3. a single concrete BasePlugin subclass defined in the module (instantiated no-arg).

The module is imported under a unique name `hw_plugin_<id>` with its directory on
the package search path, so multi-file plugins can use relative imports
(`from . import helpers`). Loading is fully isolated per plugin: any failure is
recorded as a load error (surfaced in the Plugins UI) and never crashes the host.

Loading does NOT open the plugin's external connections — that happens when the
caller dispatches on_config_changed (which respects the enable/disable lifecycle).
"""
from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path

from backend.plugins.base import BasePlugin
from backend.plugins.context import PluginContext
from backend.plugins.mesh_forwarder import MeshForwarderPlugin

_log = logging.getLogger(__name__)

MODULE_PREFIX = "hw_plugin_"

#: Base classes that are scaffolding, never the plugin itself.
_ABSTRACT_BASES = (BasePlugin, MeshForwarderPlugin)


def discover(plugins_dir: Path) -> list[Path]:
    """Return plugin directories (each containing a plugin.py), sorted by name."""
    if not plugins_dir.is_dir():
        return []
    return [
        child
        for child in sorted(plugins_dir.iterdir())
        if child.is_dir() and (child / "plugin.py").is_file()
    ]


def _purge_modules(plugin_id: str) -> None:
    """Drop the plugin's modules from the import cache so a reload re-execs them."""
    prefix = f"{MODULE_PREFIX}{plugin_id}"
    for name in [n for n in list(sys.modules) if n == prefix or n.startswith(prefix + ".")]:
        del sys.modules[name]


def _import_module(plugin_dir: Path, plugin_id: str):
    module_name = f"{MODULE_PREFIX}{plugin_id}"
    _purge_modules(plugin_id)  # ensure a fresh exec on reload
    plugin_file = plugin_dir / "plugin.py"
    # module_from_spec gives the module a __path__ (from submodule_search_locations)
    # and __package__, so multi-file plugins can use relative imports. We then exec
    # the source ourselves rather than via the loader, so a re-uploaded plugin.py is
    # always re-read fresh — the bytecode cache would otherwise serve stale code when
    # the file changes within the same filesystem-mtime tick (hot-reload).
    spec = importlib.util.spec_from_file_location(
        module_name, plugin_file, submodule_search_locations=[str(plugin_dir)]
    )
    if spec is None:
        raise RuntimeError(f"could not create import spec for {plugin_dir}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        source = plugin_file.read_text(encoding="utf-8")
        exec(compile(source, str(plugin_file), "exec"), module.__dict__)
    except Exception:
        _purge_modules(plugin_id)
        raise
    return module, module_name


def _resolve_plugin(module, module_name: str) -> BasePlugin:
    plugin = getattr(module, "PLUGIN", None)
    if isinstance(plugin, BasePlugin):
        return plugin
    factory = getattr(module, "get_plugin", None)
    if callable(factory):
        inst = factory()
        if isinstance(inst, BasePlugin):
            return inst
        raise RuntimeError("get_plugin() did not return a BasePlugin")
    candidates = [
        obj
        for obj in vars(module).values()
        if isinstance(obj, type)
        and issubclass(obj, BasePlugin)
        and obj not in _ABSTRACT_BASES
        and obj.__module__ == module_name
    ]
    # Prefer a manifest-bearing class so the plugin is listable/configurable.
    candidates.sort(key=lambda c: c.manifest is None)
    if candidates:
        return candidates[0]()
    raise RuntimeError(
        "no plugin found — expected a PLUGIN instance, a get_plugin() factory, "
        "or a BasePlugin subclass in plugin.py"
    )


async def load_plugin(plugin_dir: Path, ctx: PluginContext, registry) -> BasePlugin | None:
    """Load, bind, set up, and register one plugin. Returns the instance, or None
    on failure (the error is recorded on the registry, never raised)."""
    plugin_id = plugin_dir.name
    try:
        module, module_name = _import_module(plugin_dir, plugin_id)
        instance = _resolve_plugin(module, module_name)
        # Honour the directory name as the canonical id even if the manifest differs,
        # so config namespacing + install/uninstall line up with the folder.
        if instance.manifest is not None and instance.manifest.id != plugin_id:
            _log.warning(
                "Plugin in %s declares id %r; using directory name %r",
                plugin_dir, instance.manifest.id, plugin_id,
            )
        instance.ctx = ctx.for_plugin(plugin_id)
        await instance.setup()
        registry.register(instance)
        registry.clear_load_error(plugin_id)
        _log.info("Loaded plugin %r from %s", plugin_id, plugin_dir)
        return instance
    except Exception as exc:  # isolate: one bad plugin must not break the rest
        registry.record_load_error(plugin_id, f"{type(exc).__name__}: {exc}")
        _log.exception("Failed to load plugin %r from %s", plugin_id, plugin_dir)
        return None


async def unload_plugin(plugin_id: str, registry) -> None:
    """Unregister a plugin (running its on_unload) and purge its modules."""
    inst = registry.get(plugin_id)
    if inst is not None:
        await registry.unregister(inst)
    registry.clear_load_error(plugin_id)
    _purge_modules(plugin_id)


async def reload_plugin(plugin_dir: Path, ctx: PluginContext, registry) -> BasePlugin | None:
    """Unload (if present) then load a plugin fresh."""
    await unload_plugin(plugin_dir.name, registry)
    return await load_plugin(plugin_dir, ctx, registry)


async def discover_and_load(plugins_dir: Path, ctx: PluginContext, registry) -> list[BasePlugin]:
    """Discover and load every plugin under *plugins_dir*. Returns loaded instances."""
    loaded: list[BasePlugin] = []
    for plugin_dir in discover(plugins_dir):
        inst = await load_plugin(plugin_dir, ctx, registry)
        if inst is not None:
            loaded.append(inst)
    return loaded
