"""Plugin registry — collects BasePlugin instances and dispatches hook calls."""
from __future__ import annotations

import logging

from backend.plugins.base import BasePlugin

_log = logging.getLogger(__name__)


class PluginRegistry:
    """Singleton registry that dispatches lifecycle hooks to all registered plugins.

    Active hooks (client message, audio RX, TX pre-queue) are dispatched only to
    plugins whose master toggle is enabled — disabling a plugin stops its
    functionality. `on_config_changed` is the exception: it is always dispatched
    so a plugin can tear down its resources (e.g. close a serial link) on the
    transition to disabled.
    """

    def __init__(self) -> None:
        # An immutable tuple so the sync rx-chunk dispatch (STT worker thread) can
        # iterate a stable snapshot while register/unregister (event loop) swap it.
        self._plugins: tuple[BasePlugin, ...] = ()
        self._config_getter = None
        # Plugins that failed to load/setup: id -> error string, surfaced in the UI.
        self._load_errors: dict[str, str] = {}

    def register(self, plugin: BasePlugin) -> None:
        """Add a plugin to the registry. Call before the server accepts connections."""
        self._plugins = self._plugins + (plugin,)
        _log.info("Plugin registered: %s", type(plugin).__name__)

    async def unregister(self, plugin: BasePlugin) -> None:
        """Remove a plugin and run its teardown hook (hot-reload / uninstall)."""
        self._plugins = tuple(p for p in self._plugins if p is not plugin)
        try:
            await plugin.on_unload()
        except Exception:
            _log.exception("Plugin %s raised in on_unload", type(plugin).__name__)

    def get(self, plugin_id: str) -> BasePlugin | None:
        """Find a registered plugin by its manifest id."""
        for p in self._plugins:
            if p.manifest is not None and p.manifest.id == plugin_id:
                return p
        return None

    def record_load_error(self, plugin_id: str, error: str) -> None:
        self._load_errors[plugin_id] = error

    def clear_load_error(self, plugin_id: str) -> None:
        self._load_errors.pop(plugin_id, None)

    def set_config_getter(self, getter) -> None:
        """Provide a callable returning the live ServerConfig, used to gate active
        hooks by each plugin's enabled state. Until set, all plugins are treated
        as enabled (preserves behaviour for tests that dispatch without config)."""
        self._config_getter = getter

    def _is_enabled(self, plugin: BasePlugin) -> bool:
        if self._config_getter is None:
            return True
        try:
            return plugin.is_enabled(self._config_getter())
        except Exception:
            _log.exception("Plugin %s is_enabled() raised; treating as disabled", type(plugin).__name__)
            return False

    # ------------------------------------------------------------------
    # Manifest / enable-disable management
    # ------------------------------------------------------------------

    @staticmethod
    def _plugin_section(config, plugin_id: str) -> dict:
        return (config.get("plugins") or {}).get(plugin_id) or {}

    def manifests(self, config) -> list[dict]:
        """Manifest + current enabled state + config values for each registered
        plugin, plus a stub entry per plugin that failed to load. Drives the admin
        Plugins manager (list, enable/disable, render settings, show load errors)."""
        out: list[dict] = []
        for plugin in self._plugins:
            m = plugin.manifest
            if m is None:
                continue
            section = self._plugin_section(config, m.id)
            schema = [
                {
                    "key": f.key, "label": f.label, "type": f.type, "default": f.default,
                    "help": f.help, "options": [list(o) for o in f.options],
                    "minimum": f.minimum, "maximum": f.maximum,
                }
                for f in m.config_schema
            ]
            out.append({
                "id": m.id,
                "name": m.name,
                "description": m.description,
                "version": m.version,
                "enabled": bool(section.get("enabled", m.default_enabled)),
                "conflicts_with": list(m.conflicts_with),
                "config_schema": schema,
                "config": {f.key: section.get(f.key, f.default) for f in m.config_schema},
                "tx_composition": m.tx_composition,
            })
        for pid, err in self._load_errors.items():
            out.append({
                "id": pid, "name": pid, "description": "", "version": "",
                "enabled": False, "conflicts_with": [], "config_schema": [],
                "config": {}, "tx_composition": None, "error": err,
            })
        return out

    def resolve_conflicts(self, config, newly_enabled_ids) -> None:
        """Enforce mutual exclusion in `config` (mutated in place).

        For each plugin that was just enabled, force every plugin it conflicts
        with to disabled (under config["plugins"][peer]["enabled"]). The
        just-enabled plugin always wins, so independent toggles can never leave
        two conflicting plugins co-enabled."""
        by_id = {p.manifest.id: p.manifest for p in self._plugins if p.manifest is not None}
        plugins_cfg = config.setdefault("plugins", {})
        for pid in newly_enabled_ids:
            manifest = by_id.get(pid)
            if manifest is None:
                continue
            for peer_id in manifest.conflicts_with:
                peer = plugins_cfg.get(peer_id)
                if peer is not None and peer.get("enabled"):
                    peer["enabled"] = False
                    _log.info("Plugin %s enabled — auto-disabled conflicting plugin %s", pid, peer_id)

    # ------------------------------------------------------------------
    # Hook dispatchers
    # ------------------------------------------------------------------

    async def dispatch_client_message(self, payload: dict, reply=None) -> None:
        """Notify enabled plugins of an inbound client WS message (fire-and-forget)."""
        for plugin in self._plugins:
            if not self._is_enabled(plugin):
                continue
            try:
                await plugin.on_client_message_received(payload, reply=reply)
            except Exception:
                _log.exception("Plugin %s raised in on_client_message_received", type(plugin).__name__)

    async def dispatch_audio_rx_start(self) -> None:
        """Notify enabled plugins that squelch has opened."""
        for plugin in self._plugins:
            if not self._is_enabled(plugin):
                continue
            try:
                await plugin.on_audio_rx_start()
            except Exception:
                _log.exception("Plugin %s raised in on_audio_rx_start", type(plugin).__name__)

    def dispatch_audio_rx_chunk(self, chunk) -> None:
        """Dispatch audio chunk to enabled plugins (sync — called from STT worker thread)."""
        for plugin in self._plugins:
            if not self._is_enabled(plugin):
                continue
            try:
                plugin.on_audio_rx_chunk(chunk)
            except Exception:
                _log.exception("Plugin %s raised in on_audio_rx_chunk", type(plugin).__name__)

    async def dispatch_rx_final(self, text: str) -> None:
        """Notify enabled plugins of a finalized RX transcript."""
        for plugin in self._plugins:
            if not self._is_enabled(plugin):
                continue
            try:
                await plugin.on_rx_final(text)
            except Exception:
                _log.exception("Plugin %s raised in on_rx_final", type(plugin).__name__)

    async def dispatch_tx_pre_queue(self, payload: dict) -> dict | None:
        """Run the TX pre-queue hook chain over enabled plugins.

        Plugins are called in registration order. If any returns None the chain
        stops and TX is blocked. Otherwise the (possibly modified) payload is
        returned for queuing.
        """
        for plugin in self._plugins:
            if not self._is_enabled(plugin):
                continue
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

    async def dispatch_config_changed(self, config) -> None:
        """Notify all plugins that server config was (re)loaded (fire-and-forget)."""
        for plugin in self._plugins:
            try:
                await plugin.on_config_changed(config)
            except Exception:
                _log.exception("Plugin %s raised in on_config_changed", type(plugin).__name__)


plugin_registry = PluginRegistry()
