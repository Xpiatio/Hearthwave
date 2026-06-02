"""Base class for Radio-TTY plugins.

Subclass BasePlugin and register an instance with plugin_registry to hook into
the core message and audio pipeline. All hook methods are no-ops by default —
override only what the plugin needs.
"""
from __future__ import annotations


class BasePlugin:
    """Lifecycle hooks for Radio-TTY plugins (ADR 0003).

    Hook summary:
      on_client_message_received  — every inbound WS client message (async)
      on_audio_rx_start           — squelch opens / incoming transmission begins (async)
      on_audio_rx_chunk           — each raw audio chunk from input device (sync, hot path)
      on_rx_final                 — each finalized RX transcript (async)
      on_audio_tx_pre_queue       — before TX text enters synthesis queue (async, can block TX)
    """

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
