"""Radio-TTY WebSocket server.

Wires together: STTWorker, TTSSynthesizer, ContactsStore, ConnectionManager.
All clients receive broadcasts; TX messages are queued to the audio pipeline.

WebSocket message types (client → server):
    tx_message      — {"type": "tx_message", "callsign": str, "text": str}
    add_contact     — {"type": "add_contact", "callsign": str, ...contact fields...}
    enroll_speaker  — {"type": "enroll_speaker", "callsign": str, "name"?: str,
                        "utterance_id"?: str, "cluster_label"?: str}
    reset_speaker   — {"type": "reset_speaker", "callsign": str, "name"?: str}

WebSocket message types (server → client):
    status           — {"type": "status", "radio_connected": bool, ...}
    contacts         — {"type": "contacts", "contacts": [...]}
    rx_message       — {"type": "rx_message", "utterance_id": str, "text": str,
                         "partial": bool, "speaker_callsign"?: str,
                         "speaker_name"?: str, "cluster_label"?: str}
    tx_status        — {"type": "tx_status", "status": "transmitting" | "idle"}
    speaker_enrolled — {"type": "speaker_enrolled", "callsign": str, "name": str,
                         "sample_count": int}
    speaker_reset    — {"type": "speaker_reset", "callsign": str}
    error            — {"type": "error", "detail": str}
"""
from __future__ import annotations

import asyncio
import collections
import datetime
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from backend.config import ServerConfig
from backend.constants import normalize_service
from backend.fcc.id_rule import (
    ID_INTERVAL_SECONDS,
    format_outgoing_message,
    format_standalone_id,
)
from backend.hw_detect import detect as detect_compute
from backend.persistence.contacts import ContactsStore
from backend.ptt.factory import make_ptt
from backend.stt.worker import STTWorker
from backend.tts.synthesizer import TTSSynthesizer

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singletons populated at startup
# ---------------------------------------------------------------------------

_config: ServerConfig | None = None
_contacts_store: ContactsStore | None = None
_stt_worker: STTWorker | None = None
_synthesizer: TTSSynthesizer | None = None

# Speaker ID singletons
_speaker_embedder: Any = None
_voiceprint_store: Any = None
_unknown_clusterer: Any = None
_recent_embeddings: dict[str, Any] = {}
_RECENT_EMBEDDINGS_MAX = 20

# Queues
_stt_out_queue: asyncio.Queue = asyncio.Queue()
_tx_queue: asyncio.Queue = asyncio.Queue()
_tts_event_queue: asyncio.Queue = asyncio.Queue()

# Background tasks — kept alive so they are not GC'd mid-run
_background_tasks: list[asyncio.Task] = []

# Signal-quality state — written by STT worker callbacks (GIL-safe int/bool assignments)
_audio_level: int = 0
_radio_error: bool = False
_channel_clear: bool = True
_LEVEL_WINDOW_SIZE = 150
_level_window: collections.deque = collections.deque(maxlen=_LEVEL_WINDOW_SIZE)

# FCC ID-rule state — asyncio-only (both writers are asyncio tasks; no cross-thread writes)
_last_id_time: datetime.datetime | None = None
_has_transmitted: bool = False


# ---------------------------------------------------------------------------
# ConnectionManager
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Tracks active WebSocket connections and provides broadcast helpers."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    def add(self, ws: WebSocket) -> None:
        self._clients.add(ws)

    def remove(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def broadcast(self, msg: dict) -> None:
        """Send *msg* to every connected client.  Silently drops dead sockets."""
        dead: list[WebSocket] = []
        for ws in list(self._clients):
            try:
                await ws.send_json(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)

    async def send_to(self, ws: WebSocket, msg: dict) -> None:
        """Send *msg* to a single client."""
        try:
            await ws.send_json(msg)
        except Exception as exc:
            _log.warning("send_to failed: %s", exc)
            self._clients.discard(ws)


_manager = ConnectionManager()


# ---------------------------------------------------------------------------
# STT worker callbacks (called from the STT thread — keep non-blocking)
# ---------------------------------------------------------------------------

def _on_stt_audio_level(level: int) -> None:
    global _audio_level
    _audio_level = level
    _level_window.append(level)


def _on_stt_status(msg: str) -> None:
    global _radio_error
    if "listening" in msg.lower():
        _radio_error = False


def _on_stt_error(msg: str) -> None:
    global _radio_error
    _log.error("STT worker error: %s", msg)
    _radio_error = True


def _on_stt_capture_event(event: str) -> None:
    global _channel_clear
    if event == "squelch_opened":
        _channel_clear = False
    elif event == "squelch_closed":
        _channel_clear = True


# ---------------------------------------------------------------------------
# Background pump tasks
# ---------------------------------------------------------------------------

async def _rx_pump() -> None:
    """Drain the STT output queue and broadcast rx_message frames."""
    global _stt_out_queue, _recent_embeddings
    while True:
        try:
            result = await _stt_out_queue.get()
            utterance_id = result.get("utterance_id")
            partial = result.get("partial", False)
            embedding = result.get("embedding")

            speaker_callsign: str | None = None
            speaker_name: str | None = None
            cluster_label: str | None = None

            if embedding is not None and not partial:
                if utterance_id is not None:
                    _recent_embeddings[utterance_id] = embedding
                    if len(_recent_embeddings) > _RECENT_EMBEDDINGS_MAX:
                        oldest = next(iter(_recent_embeddings))
                        del _recent_embeddings[oldest]

                if _voiceprint_store is not None:
                    callsign, name, _score = _voiceprint_store.best_match(
                        embedding, _config.speaker_match_threshold if _config else 0.75
                    )
                    if callsign is not None:
                        speaker_callsign = callsign
                        speaker_name = name
                    elif _unknown_clusterer is not None:
                        cluster_label = _unknown_clusterer.assign(embedding)

            await _manager.broadcast({
                "type": "rx_message",
                "utterance_id": utterance_id,
                "text": result.get("text", ""),
                "partial": partial,
                "speaker_callsign": speaker_callsign,
                "speaker_name": speaker_name,
                "cluster_label": cluster_label,
            })
        except asyncio.CancelledError:
            break
        except Exception as exc:
            _log.error("_rx_pump error: %s", exc)


async def _tx_pump() -> None:
    """Drain tx_queue; apply FCC formatting, synthesize, play, then broadcast idle."""
    global _config, _synthesizer, _tx_queue, _tts_event_queue, _last_id_time, _has_transmitted

    while True:
        try:
            payload = await _tx_queue.get()
        except asyncio.CancelledError:
            break

        if _synthesizer is None or _config is None:
            await _manager.broadcast({"type": "tx_status", "status": "idle"})
            continue

        try:
            from piper import PiperVoice  # lazy import — heavy on first call

            voice_name = _config.voice
            if not voice_name:
                _log.warning("No TTS voice configured; skipping TX synthesis.")
                await _manager.broadcast({"type": "tx_status", "status": "idle"})
                continue

            raw_text = payload.get("text", "")

            if payload.get("_pre_formatted"):
                # Station-ID messages from _id_rule_pump are already formatted.
                text = raw_text
            else:
                now = datetime.datetime.now(datetime.timezone.utc)
                text, _last_id_time = format_outgoing_message(
                    raw_text,
                    target_call=payload.get("target_call") or "ALL",
                    target_name=payload.get("target_name") or "",
                    my_call=_config.callsign,
                    my_name=_config.name,
                    last_id_time=_last_id_time,
                    now=now,
                    service=normalize_service(_config.radio_service),
                )
                _has_transmitted = True

            voice = PiperVoice.load(voice_name)
            ptt = make_ptt(_config)
            length_scale = _config.tts_length_scale

            await _synthesizer.synthesize(voice, text, ptt, length_scale=length_scale)

            # Drain TTS events so the queue doesn't grow unbounded.
            while not _tts_event_queue.empty():
                _tts_event_queue.get_nowait()

        except asyncio.CancelledError:
            break
        except Exception as exc:
            _log.error("TX synthesis error: %s", exc)
            await _manager.broadcast({"type": "error", "detail": f"TX error: {exc}"})
        finally:
            await _manager.broadcast({"type": "tx_status", "status": "idle"})


# ---------------------------------------------------------------------------
# Status helper
# ---------------------------------------------------------------------------

def _volume_ok() -> bool:
    if _radio_error:
        return False
    if len(_level_window) < _LEVEL_WINDOW_SIZE // 2:
        return True  # not enough data yet — assume ok
    return (sum(_level_window) / len(_level_window)) > 2


def _build_status() -> dict:
    return {
        "type": "status",
        "radio_connected": _stt_worker is not None and not _radio_error,
        "volume_ok": _volume_ok(),
        "channel_clear": _channel_clear,
    }


async def _status_pump() -> None:
    """Broadcast live signal-quality status to all clients every 5 seconds."""
    while True:
        try:
            await asyncio.sleep(5)
            await _manager.broadcast(_build_status())
        except asyncio.CancelledError:
            break
        except Exception as exc:
            _log.error("_status_pump error: %s", exc)


async def _id_rule_pump() -> None:
    """Fire a standalone station ID when FCC Part 95 requires one.

    Checks every 60 s: if the station has transmitted since the last ID and
    the ID interval has elapsed, synthesizes a standalone ID via _tx_queue.
    """
    global _last_id_time, _has_transmitted
    while True:
        try:
            await asyncio.sleep(60)
            if not _has_transmitted or _config is None:
                continue
            now = datetime.datetime.now(datetime.timezone.utc)
            elapsed = (now - _last_id_time).total_seconds() if _last_id_time else float("inf")
            if elapsed > ID_INTERVAL_SECONDS:
                spoken, new_ts = format_standalone_id(
                    _config.callsign, _config.name, _config.location, now
                )
                _last_id_time = new_ts
                _has_transmitted = False
                _log.info("FCC ID rule: broadcasting station identification.")
                await _manager.broadcast({"type": "tx_status", "status": "transmitting"})
                await _tx_queue.put({"text": spoken, "_pre_formatted": True})
        except asyncio.CancelledError:
            break
        except Exception as exc:
            _log.error("_id_rule_pump error: %s", exc)


# ---------------------------------------------------------------------------
# FastAPI lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Startup / shutdown wiring."""
    global _config, _contacts_store, _stt_worker, _synthesizer
    global _stt_out_queue, _tx_queue, _tts_event_queue, _background_tasks
    global _audio_level, _radio_error, _channel_clear, _last_id_time, _has_transmitted
    global _speaker_embedder, _voiceprint_store, _unknown_clusterer, _recent_embeddings
    global _level_window

    # --- startup -----------------------------------------------------------
    _config = ServerConfig.load()
    _log.info("Config loaded: callsign=%s, port=%d", _config.callsign, _config.port)

    compute = detect_compute()
    _log.info("Compute backend: %s", compute.device_label)

    _contacts_store = ContactsStore(_config.contacts_file)
    _log.info("Contacts loaded: %d entries", len(_contacts_store.get_all()))

    _stt_out_queue = asyncio.Queue()
    _tx_queue = asyncio.Queue()
    _tts_event_queue = asyncio.Queue()

    # Reset signal-quality and FCC ID state on each startup.
    _audio_level = 0
    _radio_error = False
    _channel_clear = True
    _last_id_time = None
    _has_transmitted = False
    _level_window = collections.deque(maxlen=_LEVEL_WINDOW_SIZE)

    # Speaker ID setup — optional; continues without it if model or deps are missing.
    _recent_embeddings = {}
    try:
        from backend.speaker.embedder import SpeakerEmbedder
        from backend.speaker.voiceprints import VoiceprintStore
        from backend.speaker.clusterer import UnknownClusterer

        _speaker_embedder = SpeakerEmbedder()
        if _speaker_embedder.available:
            _log.info("Speaker model found; speaker ID enabled.")
        else:
            _log.warning("Speaker model not found at '%s'; speaker ID disabled.", _speaker_embedder.model_dir)
            _speaker_embedder = None
        _voiceprint_store = VoiceprintStore(_config.voiceprints_dir)
        _unknown_clusterer = UnknownClusterer()
    except Exception as exc:
        _log.warning("Speaker ID unavailable: %s", exc)
        _speaker_embedder = None
        _voiceprint_store = None
        _unknown_clusterer = None

    _stt_worker = STTWorker(
        out_queue=_stt_out_queue,
        input_device=_config.input_device if _config.input_device != -1 else None,
        whisper_model=_config.whisper_model,
        vad_threshold=_config.vad_threshold,
        system_monitor_sink=_config.system_monitor_sink,
        speaker_embedder=_speaker_embedder,
        on_audio_level=_on_stt_audio_level,
        on_capture_event=_on_stt_capture_event,
        on_status=_on_stt_status,
        on_error=_on_stt_error,
    )
    _stt_worker.start()

    _synthesizer = TTSSynthesizer(
        out_queue=_tts_event_queue,
        compute_backend=compute,
        output_device=_config.output_device if _config.output_device != -1 else None,
    )

    _background_tasks = [
        asyncio.create_task(_rx_pump(), name="rx-pump"),
        asyncio.create_task(_tx_pump(), name="tx-pump"),
        asyncio.create_task(_status_pump(), name="status-pump"),
        asyncio.create_task(_id_rule_pump(), name="id-rule-pump"),
    ]
    _log.info("Radio-TTY server ready.")

    yield

    # --- shutdown ----------------------------------------------------------
    _log.info("Shutting down Radio-TTY server...")
    for task in _background_tasks:
        task.cancel()
    await asyncio.gather(*_background_tasks, return_exceptions=True)
    _background_tasks.clear()

    if _stt_worker is not None:
        _stt_worker.stop()
        await _stt_worker.join()

    _speaker_embedder = None
    _voiceprint_store = None
    _unknown_clusterer = None
    _recent_embeddings = {}
    _level_window.clear()
    _log.info("Radio-TTY server stopped.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Radio-TTY", lifespan=_lifespan)


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict:
    return {"ok": True}


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    _manager.add(ws)
    _log.info("Client connected: %s", ws.client)

    # Send initial state to the newly connected client
    await _manager.send_to(ws, _build_status())
    if _contacts_store is not None:
        await _manager.send_to(ws, {
            "type": "contacts",
            "contacts": _contacts_store.get_all(),
        })

    try:
        while True:
            data: Any = await ws.receive_json()
            msg_type = data.get("type")

            if msg_type == "tx_message":
                callsign = (data.get("callsign") or "").strip()
                if not callsign:
                    await _manager.send_to(ws, {
                        "type": "error",
                        "detail": "tx_message requires a non-empty 'callsign' field.",
                    })
                    continue

                if _config and _config.listen_only:
                    await _manager.send_to(ws, {
                        "type": "error",
                        "detail": "Radio is in listen-only mode; TX disabled.",
                    })
                    continue

                await _tx_queue.put(data)
                await _manager.broadcast({"type": "tx_status", "status": "transmitting"})

            elif msg_type == "add_contact":
                if _contacts_store is None:
                    await _manager.send_to(ws, {
                        "type": "error",
                        "detail": "Contacts store not initialised.",
                    })
                    continue
                try:
                    contact = {k: v for k, v in data.items() if k != "type"}
                    updated = _contacts_store.add_contact(contact)
                    await _manager.broadcast({"type": "contacts", "contacts": updated})
                except ValueError as exc:
                    await _manager.send_to(ws, {"type": "error", "detail": str(exc)})

            elif msg_type == "enroll_speaker":
                callsign = (data.get("callsign") or "").strip()
                if not callsign:
                    await _manager.send_to(ws, {
                        "type": "error",
                        "detail": "enroll_speaker requires a non-empty 'callsign' field.",
                    })
                    continue
                if _voiceprint_store is None:
                    await _manager.send_to(ws, {
                        "type": "error",
                        "detail": "Speaker ID not available.",
                    })
                    continue
                name = (data.get("name") or "").strip()
                utterance_id = data.get("utterance_id")
                cluster_label = data.get("cluster_label")
                embeddings_to_enroll: list[Any] = []
                if utterance_id and utterance_id in _recent_embeddings:
                    embeddings_to_enroll = [_recent_embeddings[utterance_id]]
                elif cluster_label and _unknown_clusterer is not None:
                    embeddings_to_enroll = _unknown_clusterer.pop_cluster(cluster_label)
                if not embeddings_to_enroll:
                    await _manager.send_to(ws, {
                        "type": "error",
                        "detail": "No embedding found for the given utterance_id or cluster_label.",
                    })
                    continue
                for emb in embeddings_to_enroll:
                    _voiceprint_store.enroll(callsign, name, emb)
                sample_count = _voiceprint_store.sample_count(callsign, name)
                await _manager.broadcast({
                    "type": "speaker_enrolled",
                    "callsign": callsign,
                    "name": name,
                    "sample_count": sample_count,
                })

            elif msg_type == "reset_speaker":
                callsign = (data.get("callsign") or "").strip()
                if not callsign:
                    await _manager.send_to(ws, {
                        "type": "error",
                        "detail": "reset_speaker requires a non-empty 'callsign' field.",
                    })
                    continue
                if _voiceprint_store is None:
                    await _manager.send_to(ws, {
                        "type": "error",
                        "detail": "Speaker ID not available.",
                    })
                    continue
                name = (data.get("name") or "").strip()
                _voiceprint_store.reset_contact(callsign, name)
                await _manager.broadcast({
                    "type": "speaker_reset",
                    "callsign": callsign,
                })

            else:
                _log.debug("Unknown message type from client: %r", msg_type)

    except WebSocketDisconnect:
        _log.info("Client disconnected: %s", ws.client)
    except Exception as exc:
        _log.error("WebSocket error for %s: %s", ws.client, exc)
    finally:
        _manager.remove(ws)
