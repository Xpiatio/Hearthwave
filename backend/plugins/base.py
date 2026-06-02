"""Base class for Radio-TTY plugins.

Subclass BasePlugin and register an instance with plugin_registry to hook into
the core message and audio pipeline. All hook methods are no-ops by default —
override only what the plugin needs.
"""
from __future__ import annotations


class BasePlugin:
    """Lifecycle hooks for Radio-TTY plugins.

    Backend hook points (ADR 0003):
      on_client_message_received  — every inbound WS client message
      on_audio_rx_start           — squelch opens (incoming transmission begins)
      on_audio_tx_pre_queue       — before TX text enters the synthesis queue
    """

    async def on_client_message_received(self, payload: dict) -> None:
        """Called for every WebSocket message received from any connected client.

        payload is a copy of the decoded JSON dict (safe to read; mutations have
        no effect on the original message dispatch).
        """

    async def on_audio_rx_start(self) -> None:
        """Called when the squelch detector opens (incoming radio carrier detected).

        Bridged from the STT worker thread to the asyncio event loop automatically.
        """

    async def on_audio_tx_pre_queue(self, payload: dict) -> dict | None:
        """Called before TX text is pushed onto the synthesis queue.

        Return the payload (optionally modified) to allow TX, or None to block it.
        Plugins are called in registration order; the first to return None wins.

        Modifiable fields: 'text', '_filter_profanity', '_voice_name', '_length_scale'.
        """
        return payload
