"""Base class for Hearthwave plugins.

Subclass BasePlugin and register an instance with plugin_registry to hook into
the core message and audio pipeline. All hook methods are no-ops by default —
override only what the plugin needs.

This is the stable contract 3rd-party plugins are written against. Import it (and
the rest of the public surface) from `backend.plugins.sdk`, not from internal
modules directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoid an import cycle at runtime (context imports nothing from us)
    from backend.plugins.context import PluginContext


@dataclass(frozen=True)
class ConfigField:
    """One declarative setting a plugin exposes in the admin Plugins page.

    The frontend renders a generic form from these — no plugin-supplied UI code.

      key      identifier within the plugin's config namespace (config["plugins"][id][key])
      label    human label for the form field
      type     'bool' | 'text' | 'number' | 'select'
      default  value used when the key is absent (the plugin's effective default)
      help     optional helper text shown beneath the field
      options  for 'select': tuple of (value, label) pairs
      minimum/maximum  optional bounds for 'number'
    """

    key: str
    label: str
    type: str = "text"
    default: object = ""
    help: str = ""
    options: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    minimum: float | None = None
    maximum: float | None = None


@dataclass(frozen=True)
class PluginManifest:
    """Describes an installed plugin for the Plugins manager / registry.

    The manifest makes a plugin self-describing: the admin Plugins page lists it,
    toggles it on/off, and renders its settings form; the registry gates hook
    dispatch on its enabled state and enforces mutual exclusion.

      id              stable identifier (e.g. "meshcore"); used in config + the UI
      name            human label shown in the Plugins manager
      description     one-line summary of what the plugin does
      version         plugin version string (independent of the app version)
      default_enabled master-toggle value when this plugin has no stored config yet
      conflicts_with  other plugin ids that cannot be co-enabled (enabling this
                      one disables them — see PluginRegistry.resolve_conflicts)
      config_schema   declarative settings the frontend renders into a form
      tx_composition  optional capability: this plugin caps the message input like a
                      mesh bridge. {"max_len_key", "separator_key", "hint"} — keys
                      reference fields in this plugin's config namespace.

    A plugin's state lives under config["plugins"][id]: the master toggle at the
    fixed key "enabled", and each config_schema field at its own key.
    """

    id: str
    name: str
    description: str
    version: str = "1.0.0"
    default_enabled: bool = False
    conflicts_with: tuple[str, ...] = field(default_factory=tuple)
    config_schema: tuple[ConfigField, ...] = field(default_factory=tuple)
    tx_composition: dict | None = None


class BasePlugin:
    """Lifecycle hooks for Hearthwave plugins (ADR 0003).

    Hook summary:
      on_client_message_received  — every inbound WS client message (async)
      on_audio_rx_start           — squelch opens / incoming transmission begins (async)
      on_audio_rx_chunk           — each raw audio chunk from input device (sync, hot path)
      on_rx_final                 — each finalized RX transcript (async)
      on_audio_tx_pre_queue       — before TX text enters synthesis queue (async, can block TX)
      on_config_changed           — server config (re)loaded at startup / after admin save (async)

    Plugins declare a `manifest` so the registry can list them, gate active-hook
    dispatch on their enabled state, and enforce mutual exclusion. `on_config_changed`
    is always dispatched regardless of enabled state so a plugin can tear down its
    resources when it transitions to disabled.
    """

    #: Subclasses override with a concrete PluginManifest.
    manifest: PluginManifest | None = None

    #: Injected by the loader before setup(); gives access to core services.
    ctx: "PluginContext | None" = None

    def is_enabled(self, config) -> bool:
        """Whether this plugin's master toggle is on. Reads
        config["plugins"][id]["enabled"], defaulting to manifest.default_enabled.
        Plugins with no manifest are treated as always-enabled (core/unlisted)."""
        if self.manifest is None:
            return True
        section = (config.get("plugins") or {}).get(self.manifest.id) or {}
        return bool(section.get("enabled", self.manifest.default_enabled))

    async def setup(self) -> None:
        """Called once after the plugin is constructed and `self.ctx` is bound,
        before it is registered. Use for cheap init; open external connections in
        `on_config_changed` (which fires right after registration) so they follow
        the enable/disable lifecycle. Default no-op."""

    async def on_unload(self) -> None:
        """Called when the plugin is being unloaded (uninstall / reload / shutdown).
        Cancel background tasks and close connections here. Default no-op."""

    async def on_client_message_received(self, payload: dict, reply=None) -> None:
        """Called for every WebSocket message received from any connected client.

        payload — copy of the decoded JSON dict (mutations have no effect).
        reply   — optional async callable: reply(msg: dict) sends msg back to the
                  specific client that sent this message.
        """

    async def on_audio_rx_start(self) -> None:
        """Called when the squelch detector opens (incoming radio carrier detected).

        Bridged from the STT worker thread to the asyncio event loop automatically.
        """

    def on_audio_rx_chunk(self, chunk) -> None:
        """Called for each raw audio chunk captured from the input device.

        chunk — numpy array (float32) of audio samples at STTWorker.SAMPLE_RATE (16 kHz).

        This hook is synchronous and runs on the STT worker thread — keep it fast and
        non-blocking. Do not await or call asyncio APIs here.
        """

    async def on_rx_final(self, text: str) -> None:
        """Called after each finalized (non-partial) RX transcript is broadcast."""

    async def on_audio_tx_pre_queue(self, payload: dict) -> dict | None:
        """Called before TX text is pushed onto the synthesis queue.

        Return the payload (optionally modified) to allow TX, or None to block it.
        Plugins are called in registration order; the first to return None wins.

        Modifiable fields: 'text', '_filter_profanity', '_voice_name', '_length_scale'.
        """
        return payload

    async def on_config_changed(self, config) -> None:
        """Called after server config is (re)loaded — once at startup (after the
        plugin is registered) and again whenever an admin saves settings.

        Plugins react to config changes here — open/close external connections,
        restart pollers, re-read tunables. config is the live ServerConfig.
        """
