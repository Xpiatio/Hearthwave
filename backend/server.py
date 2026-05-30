"""Radio-TTY WebSocket server.

Wires together: STTWorker, TTSSynthesizer, ContactsStore, ConnectionManager.
All clients receive broadcasts; TX messages are queued to the audio pipeline.

WebSocket message types (client → server):
    tx_message        — {"type": "tx_message", "callsign": str, "text": str,
                          "target_call"?: str, "target_name"?: str}
    standalone_id     — {"type": "standalone_id"}
    voice_preview     — {"type": "voice_preview", "text"?: str}
    add_contact       — {"type": "add_contact", "callsign": str, ...contact fields...}
    fcc_lookup        — {"type": "fcc_lookup", "callsign": str, "name"?: str}
    verify_all        — {"type": "verify_all"}
    dismiss_pending   — {"type": "dismiss_pending", "callsign": str}
    dismiss_all_pending — {"type": "dismiss_all_pending"}
    delete_contact    — {"type": "delete_contact", "callsign": str}
    set_service_mode  — {"type": "set_service_mode", "service": "GMRS" | "FRS"}
    set_listen_only   — {"type": "set_listen_only", "listen_only": bool}
    set_config        — {"type": "set_config", "filter_profanity"?: bool,
                          "fuzzy_callsign"?: bool, "system_monitor_sink"?: str}
    set_spectro_config — {"type": "set_spectro_config", "colormap"?: str,
                          "freq_range"?: "voice" | "full",
                          "time_window_s"?: int}
    enroll_speaker    — {"type": "enroll_speaker", "callsign": str, "name"?: str,
                          "utterance_id"?: str, "cluster_label"?: str}
    reset_speaker     — {"type": "reset_speaker", "callsign": str, "name"?: str}
    set_monitor       — {"type": "set_monitor", "enabled": bool}
    clear_attendance  — {"type": "clear_attendance"}
    list_journals     — {"type": "list_journals"}
    generate_journal  — {"type": "generate_journal", "transcript": str, "callsigns": [str]}
    save_journal      — {"type": "save_journal", "title": str, "summary": str,
                          "callsigns_locations": [...], "transcript": str}
    delete_journal    — {"type": "delete_journal", "file_path": str}

WebSocket message types (server → client):
    status            — {"type": "status", "radio_connected": bool,
                          "monitor_enabled": bool, ...}
    contacts          — {"type": "contacts", "contacts": [...]}
    rx_message        — {"type": "rx_message", "utterance_id": str, "text": str,
                          "partial": bool, "speaker_callsign"?: str,
                          "speaker_name"?: str, "cluster_label"?: str}
    tx_status         — {"type": "tx_status", "status": "transmitting" | "idle"}
    monitor_status    — {"type": "monitor_status", "enabled": bool}
    prompt_token      — {"type": "prompt_token", "tokens": [str], "original_text": str,
                          "target_call": str, "target_name": str,
                          "operator": str, "callsign": str}
    pending_stations  — {"type": "pending_stations",
                          "stations": [{"callsign": str, "name": str, "location": str}]}
    contact_auto_added — {"type": "contact_auto_added", "callsign": str, "name": str}
    fcc_lookup_result — {"type": "fcc_lookup_result", "callsign": str, "status": str,
                          "license_name": str, "license_location": str,
                          "license_city": str, "gmrs_callsign": str, "ham_callsign": str}
    verify_all_complete — {"type": "verify_all_complete"}
    online_status     — {"type": "online_status", "online": bool}
    speaker_enrolled  — {"type": "speaker_enrolled", "callsign": str, "name": str,
                          "sample_count": int}
    speaker_reset     — {"type": "speaker_reset", "callsign": str}
    session_attendance — {"type": "session_attendance", "stations": [...]}
    journals          — {"type": "journals", "journals": [...]}
    journal_result    — {"type": "journal_result", "title": str, "summary": str,
                          "callsigns_locations": [...]}
    journal_error     — {"type": "journal_error", "detail": str}
    journal_saved     — {"type": "journal_saved", "path": str}
    journal_deleted   — {"type": "journal_deleted", "file_path": str}
    spectrogram_row   — {"type": "spectrogram_row", "row": [int, ...],
                          "vad": bool, "squelch": bool}
    error             — {"type": "error", "detail": str}
"""
from __future__ import annotations

import asyncio
import collections
import datetime
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from backend.ai.gemini_client import GeminiError
from backend.ai.gemini_client import generate_journal as _gemini_generate
from backend.audio.spectro_task import SpectroTask
from backend.config import ServerConfig
from backend.constants import normalize_service, utc_now_iso
from backend.fcc.auto_add import CallsignLookupWorker
from backend.fcc.crossref import apply_verification, verify_callsign
from backend.fcc.id_rule import (
    ID_INTERVAL_SECONDS,
    format_outgoing_message,
    format_standalone_id,
)
from backend.hw_detect import detect as detect_compute
from backend.net.online import invalidate as _invalidate_online
from backend.net.online import is_online, is_online_cached
from backend.persistence.attendance import AttendanceTracker, build_attendance_rows
from backend.persistence.contacts import (
    ContactsStore,
    known_callsigns,
    normalize_callsign,
)
from backend.persistence.journal import delete_journal, load_journals, save_journal
from backend.ptt.factory import make_ptt
from backend.stt.worker import STTWorker
from backend.text.callsigns import detect_callsigns, fuzzy_match_callsign, spell_digits_in_callsigns
from backend.text.metadata import extract_name_location
from backend.text.shorthand import expand_tty_abbreviations
from backend.text.profanity import mask_profanity
from backend.text.placeholders import find_placeholders
from backend.tts.synthesizer import TTSSynthesizer

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singletons populated at startup
# ---------------------------------------------------------------------------

_config: ServerConfig | None = None
_contacts_store: ContactsStore | None = None
_stt_worker: STTWorker | None = None
_synthesizer: TTSSynthesizer | None = None
_monitor: "Any | None" = None  # AudioMonitor, lazy-imported
_spectro: SpectroTask | None = None

# Speaker ID singletons
_speaker_embedder: Any = None
_voiceprint_store: Any = None
_unknown_clusterer: Any = None
_recent_embeddings: dict[str, Any] = {}
_RECENT_EMBEDDINGS_MAX = 20

# Attendance tracker — module-level so it persists across reconnects
_attendance: AttendanceTracker = AttendanceTracker()

# Monitor passthrough callback — updated by set_monitor handler
_monitor_chunk_cb = None

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
_vad_active: bool = False
_LEVEL_WINDOW_SIZE = 150
_level_window: collections.deque = collections.deque(maxlen=_LEVEL_WINDOW_SIZE)

# FCC ID-rule state — asyncio-only (both writers are asyncio tasks; no cross-thread writes)
_last_id_time: datetime.datetime | None = None
_has_transmitted: bool = False

# Pending stations — unknown callsigns detected in RX transcripts this session.
# Maps CALLSIGN → {"name": str, "location": str} with heuristic values from the
# transcript; may be empty strings when no name/location could be extracted.
_pending_stations: dict[str, dict] = {}

# In-flight auto-add FCC lookup tasks — keyed by callsign to prevent duplicate lookups.
_auto_add_tasks: dict[str, asyncio.Task] = {}


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
        """Send msg to every connected client. Silently drops dead sockets."""
        dead: list[WebSocket] = []
        for ws in list(self._clients):
            try:
                await ws.send_json(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)

    async def send_to(self, ws: WebSocket, msg: dict) -> None:
        """Send msg to a single client."""
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


def _audio_chunk_fanout(chunk) -> None:
    """Fan out audio chunks to both the monitor and the spectrogram task."""
    if _monitor_chunk_cb is not None:
        _monitor_chunk_cb(chunk)
    if _spectro is not None:
        _spectro.push_chunk(chunk)


# ---------------------------------------------------------------------------
# Attendance helpers
# ---------------------------------------------------------------------------

def _build_attendance_payload() -> dict:
    contacts = _contacts_store.get_all() if _contacts_store else []
    rows = build_attendance_rows(_attendance.callsigns(), contacts)
    return {"type": "session_attendance", "stations": rows}


def _build_pending_payload() -> dict:
    stations = [
        {"callsign": cs, "name": info.get("name", ""), "location": info.get("location", "")}
        for cs, info in _pending_stations.items()
    ]
    return {"type": "pending_stations", "stations": stations}


async def _on_auto_add_result(
    callsign: str, name: str, location: str, result: "Any"
) -> None:
    """Callback fired when a background FCC auto-add lookup completes.

    If the callsign+name pair verified against the FCC database, the contact
    is persisted and all clients are notified. A mismatch or network error
    leaves the pending pill in place for the operator to decide.
    """
    global _auto_add_tasks, _pending_stations
    _auto_add_tasks.pop(callsign, None)

    if result.status != "verified" or _contacts_store is None:
        return

    contact = {"callsign": callsign, "name": name, "location": location}
    contact = apply_verification(contact, result, utc_now_iso())
    try:
        updated = _contacts_store.add_contact(contact)
    except Exception as exc:
        _log.error("Auto-add failed for %s: %s", callsign, exc)
        return

    _pending_stations.pop(callsign, None)
    await _manager.broadcast({"type": "contacts", "contacts": updated})
    await _manager.broadcast(_build_pending_payload())
    await _manager.broadcast({
        "type": "contact_auto_added",
        "callsign": callsign,
        "name": name,
    })
    await _manager.broadcast({
        "type": "system_msg",
        "text": f"Contact auto-added: {callsign}" + (f" ({name})" if name else ""),
    })
    _log.info("Auto-added contact: %s (%s)", callsign, name)


# ---------------------------------------------------------------------------
# Background pump tasks
# ---------------------------------------------------------------------------

async def _rx_pump() -> None:
    """Drain the STT output queue and broadcast rx_message frames."""
    global _stt_out_queue, _recent_embeddings, _vad_active
    while True:
        try:
            result = await _stt_out_queue.get()
            utterance_id = result.get("utterance_id")
            partial = result.get("partial", False)
            embedding = result.get("embedding")
            _vad_active = bool(partial)

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

            raw_text = result.get("text", "")
            display_text = (
                mask_profanity(raw_text)
                if (_config and _config.filter_profanity)
                else raw_text
            )

            await _manager.broadcast({
                "type": "rx_message",
                "utterance_id": utterance_id,
                "text": display_text,
                "partial": partial,
                "speaker_callsign": speaker_callsign,
                "speaker_name": speaker_name,
                "cluster_label": cluster_label,
            })

            # Callsign detection and attendance use the original unmasked text.
            if not partial:
                detected = detect_callsigns(raw_text)
                changed = any(_attendance.record(cs) for cs in detected)
                if changed:
                    await _manager.broadcast(_build_attendance_payload())

                # Identify unknown callsigns and drive pending-station pills + auto-add.
                if detected and _contacts_store is not None and _config is not None:
                    known = known_callsigns(_contacts_store.get_all())
                    pending_changed = False
                    for cs in detected:
                        # Fuzzy match: off-by-one rewrite when toggle is enabled.
                        effective_cs = cs
                        if _config.fuzzy_callsign:
                            match = fuzzy_match_callsign(cs, known)
                            if match and match != cs:
                                effective_cs = match

                        if effective_cs in known:
                            continue  # already a contact — no pending pill needed

                        if effective_cs in _pending_stations:
                            continue  # already pending — avoid duplicate pills

                        name, location = extract_name_location(raw_text, cs)
                        _pending_stations[effective_cs] = {
                            "name": name,
                            "location": location,
                        }
                        pending_changed = True

                        # Kick off FCC auto-add if name is available and online.
                        if (name
                                and effective_cs not in _auto_add_tasks
                                and is_online_cached()):
                            worker = CallsignLookupWorker(
                                effective_cs, name, location, _on_auto_add_result
                            )
                            _auto_add_tasks[effective_cs] = worker.start()

                    if pending_changed:
                        await _manager.broadcast(_build_pending_payload())

        except asyncio.CancelledError:
            break
        except Exception as exc:
            _log.error("_rx_pump error: %s", exc)


async def _tx_pump() -> None:
    """Drain tx_queue; apply text pipeline, FCC formatting, synthesize, play."""
    global _config, _synthesizer, _tx_queue, _tts_event_queue, _last_id_time, _has_transmitted

    while True:
        try:
            payload = await _tx_queue.get()
        except asyncio.CancelledError:
            break

        if _synthesizer is None or _config is None:
            await _manager.broadcast({"type": "tx_status", "status": "idle"})
            continue

        is_preview = bool(payload.get("_voice_preview"))
        try:
            from piper import PiperVoice  # lazy import — heavy on first call

            voice_name = _config.voice
            if not voice_name:
                _log.warning("No TTS voice configured; skipping TX synthesis.")
                if not is_preview:
                    await _manager.broadcast({"type": "tx_status", "status": "idle"})
                continue

            raw_text = payload.get("text", "")
            now = datetime.datetime.now(datetime.timezone.utc)

            if payload.get("_standalone_id"):
                # "This is" button — NATO-phonetic station ID, resets ID timer.
                text, _last_id_time = format_standalone_id(
                    _config.callsign, _config.name, _config.location, now
                )
                _has_transmitted = True

            elif payload.get("_pre_formatted") or is_preview:
                # Pre-formatted text (auto-ID pump, voice preview) — no processing.
                text = raw_text

            else:
                # Normal outgoing message: expand shorthand → mask profanity →
                # FCC-format with callsign preface → digit-isolate callsigns for TTS.
                processed = expand_tty_abbreviations(raw_text)
                if _config.filter_profanity:
                    processed = mask_profanity(processed)
                text, _last_id_time = format_outgoing_message(
                    processed,
                    target_call=payload.get("target_call") or "ALL",
                    target_name=payload.get("target_name") or "",
                    my_call=_config.callsign,
                    my_name=_config.name,
                    last_id_time=_last_id_time,
                    now=now,
                    service=normalize_service(_config.radio_service),
                )
                _has_transmitted = True
                # Space-isolate digits in callsigns so TTS reads them individually.
                text = spell_digits_in_callsigns(text)

            # Pause STT before keying so the radio receiver doesn't
            # transcribe TTS audio bleeding back through the radio.
            if not is_preview and _stt_worker is not None:
                _stt_worker.pause()

            voice = PiperVoice.load(voice_name)
            # Voice preview uses ManualPTT so no radio keying occurs.
            from backend.ptt.manual import ManualPTT
            ptt = ManualPTT() if is_preview else make_ptt(_config)
            length_scale = _config.tts_length_scale

            await _synthesizer.synthesize(voice, text, ptt, length_scale=length_scale)

            while not _tts_event_queue.empty():
                _tts_event_queue.get_nowait()

        except asyncio.CancelledError:
            break
        except Exception as exc:
            _log.error("TX synthesis error: %s", exc)
            await _manager.broadcast({"type": "error", "detail": f"TX error: {exc}"})
        finally:
            if not is_preview and _stt_worker is not None:
                _stt_worker.resume()
            if not is_preview:
                await _manager.broadcast({"type": "tx_status", "status": "idle"})


# ---------------------------------------------------------------------------
# Status helper
# ---------------------------------------------------------------------------

def _volume_ok() -> bool:
    if _radio_error:
        return False
    if len(_level_window) < _LEVEL_WINDOW_SIZE // 2:
        return True
    return (sum(_level_window) / len(_level_window)) > 2


def _build_status() -> dict:
    return {
        "type": "status",
        "radio_connected": _stt_worker is not None and not _radio_error,
        "volume_ok": _volume_ok(),
        "channel_clear": _channel_clear,
        "monitor_enabled": _monitor is not None and _monitor.is_active,
        "listen_only": bool(_config and _config.listen_only),
        "service_mode": (_config.radio_service if _config else "GMRS") or "GMRS",
        "filter_profanity": bool(_config and _config.filter_profanity),
        "fuzzy_callsign": bool(_config and _config.fuzzy_callsign),
        "spectro_colormap": (_config.spectro_colormap if _config else "viridis"),
        "spectro_freq_range": (_config.spectro_freq_range if _config else "full"),
        "spectro_time_window_s": (_config.spectro_time_window_s if _config else 30),
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
    """Fire a standalone station ID when FCC Part 95 requires one."""
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


async def _online_status_pump() -> None:
    """Probe FCC API reachability and broadcast online_status every 30 seconds.

    Fires immediately on startup so the first client to connect gets a cached
    result right away rather than waiting the full 30-second interval.
    """
    while True:
        try:
            online = await asyncio.to_thread(is_online)
            await _manager.broadcast({"type": "online_status", "online": online})
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            _log.error("_online_status_pump error: %s", exc)


# ---------------------------------------------------------------------------
# FastAPI lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Startup / shutdown wiring."""
    global _config, _contacts_store, _stt_worker, _synthesizer, _monitor
    global _stt_out_queue, _tx_queue, _tts_event_queue, _background_tasks
    global _audio_level, _radio_error, _channel_clear, _last_id_time, _has_transmitted
    global _speaker_embedder, _voiceprint_store, _unknown_clusterer, _recent_embeddings
    global _level_window, _attendance, _spectro, _monitor_chunk_cb
    global _pending_stations, _auto_add_tasks

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

    # Reset transient state on each startup.
    _audio_level = 0
    _radio_error = False
    _channel_clear = True
    _last_id_time = None
    _has_transmitted = False
    _level_window = collections.deque(maxlen=_LEVEL_WINDOW_SIZE)
    _attendance.clear()
    _pending_stations = {}
    _auto_add_tasks = {}
    _invalidate_online()  # force fresh probe on startup

    # Speaker ID — optional; continues without it if model or deps are missing.
    _recent_embeddings = {}
    try:
        from backend.speaker.embedder import SpeakerEmbedder
        from backend.speaker.voiceprints import VoiceprintStore
        from backend.speaker.clusterer import UnknownClusterer

        _speaker_embedder = SpeakerEmbedder()
        if _speaker_embedder.available:
            _log.info("Speaker model found; speaker ID enabled.")
        else:
            _log.warning(
                "Speaker model not found at '%s'; speaker ID disabled.",
                _speaker_embedder.model_dir,
            )
            _speaker_embedder = None
        _voiceprint_store = VoiceprintStore(_config.voiceprints_dir)
        _unknown_clusterer = UnknownClusterer()
    except Exception as exc:
        _log.warning("Speaker ID unavailable: %s", exc)
        _speaker_embedder = None
        _voiceprint_store = None
        _unknown_clusterer = None

    _monitor_chunk_cb = None
    if _config.monitor_enabled:
        in_dev = _config.input_device if _config.input_device != -1 else None
        out_dev = _config.output_device if _config.output_device != -1 else None
        if in_dev == out_dev and in_dev is not None:
            _log.warning("Monitor skipped: input and output device are the same (would feedback).")
        else:
            try:
                from backend.audio.monitor import AudioMonitor
                _monitor = AudioMonitor()
                _monitor.set_passthrough(_config.monitor_passthrough)
                _monitor.start(device=out_dev)
                _monitor_chunk_cb = _monitor.push
                _log.info("Audio monitor started on output device %s.", out_dev)
            except Exception as exc:
                _log.warning("Audio monitor failed to open output device: %s", exc)
                _monitor = None

    _spectro = SpectroTask(
        broadcast_fn=_manager.broadcast,
        freq_range=_config.spectro_freq_range if _config else "full",
        vad_fn=lambda: _vad_active,
        squelch_fn=lambda: not _channel_clear,
    )

    _stt_worker = STTWorker(
        out_queue=_stt_out_queue,
        input_device=_config.input_device if _config.input_device != -1 else None,
        whisper_model=_config.whisper_model,
        vad_threshold=_config.vad_threshold,
        system_monitor_sink=_config.system_monitor_sink,
        speaker_embedder=_speaker_embedder,
        on_audio_level=_on_stt_audio_level,
        on_audio_chunk=_audio_chunk_fanout,
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
        asyncio.create_task(_spectro.run(), name="spectro-pump"),
        asyncio.create_task(_online_status_pump(), name="online-status-pump"),
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

    if _monitor is not None:
        _monitor.stop()
        _monitor = None

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

    # Send initial state to the newly connected client.
    await _manager.send_to(ws, _build_status())
    if _contacts_store is not None:
        await _manager.send_to(ws, {
            "type": "contacts",
            "contacts": _contacts_store.get_all(),
        })
    await _manager.send_to(ws, _build_attendance_payload())
    await _manager.send_to(ws, _build_pending_payload())
    cached_online = is_online_cached()
    if cached_online is not None:
        await _manager.send_to(ws, {"type": "online_status", "online": cached_online})

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

                # If the message text contains unresolved {Token} placeholders,
                # ask the client to fill them in before transmitting.
                raw_text = (data.get("text") or "").strip()
                tokens = find_placeholders(raw_text)
                if tokens:
                    await _manager.send_to(ws, {
                        "type": "prompt_token",
                        "tokens": tokens,
                        "original_text": raw_text,
                        "target_call": data.get("target_call") or "ALL",
                        "target_name": data.get("target_name") or "",
                        "operator": data.get("operator") or "",
                        "callsign": callsign,
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

            elif msg_type == "set_monitor":
                global _monitor, _monitor_chunk_cb
                enabled = bool(data.get("enabled", False))
                if enabled:
                    if _monitor is None or not _monitor.is_active:
                        out_dev = _config.output_device if _config and _config.output_device != -1 else None
                        in_dev = _config.input_device if _config and _config.input_device != -1 else None
                        if in_dev == out_dev and in_dev is not None:
                            await _manager.send_to(ws, {
                                "type": "error",
                                "detail": "Monitor skipped: input and output device are the same.",
                            })
                            continue
                        try:
                            if _monitor is None:
                                from backend.audio.monitor import AudioMonitor
                                _monitor = AudioMonitor()
                                if _config:
                                    _monitor.set_passthrough(_config.monitor_passthrough)
                            _monitor.start(device=out_dev)
                            _monitor_chunk_cb = _monitor.push
                        except Exception as exc:
                            _log.warning("Audio monitor failed to start: %s", exc)
                            await _manager.send_to(ws, {
                                "type": "error",
                                "detail": f"Monitor failed to start: {exc}",
                            })
                            continue
                else:
                    if _monitor is not None:
                        _monitor.stop()
                    _monitor_chunk_cb = None
                await _manager.broadcast({"type": "monitor_status", "enabled": enabled})

            elif msg_type == "clear_attendance":
                _attendance.clear()
                await _manager.broadcast(_build_attendance_payload())

            elif msg_type == "list_journals":
                if _config is None:
                    await _manager.send_to(ws, {"type": "journals", "journals": []})
                    continue
                journals = load_journals(_config.journals_dir)
                await _manager.send_to(ws, {"type": "journals", "journals": journals})

            elif msg_type == "generate_journal":
                if _config is None or not _config.gemini_api_key:
                    await _manager.send_to(ws, {
                        "type": "journal_error",
                        "detail": "Gemini API key not configured in config.json (gemini_api_key).",
                    })
                    continue
                transcript = (data.get("transcript") or "").strip()
                if not transcript:
                    await _manager.send_to(ws, {
                        "type": "journal_error",
                        "detail": "transcript is required.",
                    })
                    continue
                callsigns = data.get("callsigns") or []
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                try:
                    result = await asyncio.to_thread(
                        _gemini_generate, _config.gemini_api_key, transcript, callsigns, timestamp
                    )
                    await _manager.send_to(ws, {"type": "journal_result", **result})
                except GeminiError as exc:
                    await _manager.send_to(ws, {"type": "journal_error", "detail": str(exc)})

            elif msg_type == "save_journal":
                if _config is None:
                    await _manager.send_to(ws, {"type": "error", "detail": "Server not ready."})
                    continue
                title = (data.get("title") or "").strip()
                summary = (data.get("summary") or "").strip()
                callsigns_locations = data.get("callsigns_locations") or []
                transcript = (data.get("transcript") or "").strip()
                try:
                    path = save_journal(
                        title, summary, callsigns_locations, transcript, _config.journals_dir
                    )
                    await _manager.send_to(ws, {"type": "journal_saved", "path": path})
                except Exception as exc:
                    await _manager.send_to(ws, {
                        "type": "error",
                        "detail": f"Failed to save journal: {exc}",
                    })

            elif msg_type == "delete_journal":
                if _config is None:
                    await _manager.send_to(ws, {"type": "error", "detail": "Server not ready."})
                    continue
                file_path = (data.get("file_path") or "").strip()
                try:
                    delete_journal(file_path, _config.journals_dir)
                    await _manager.send_to(ws, {
                        "type": "journal_deleted",
                        "file_path": file_path,
                    })
                except (ValueError, OSError) as exc:
                    await _manager.send_to(ws, {"type": "error", "detail": str(exc)})

            elif msg_type == "standalone_id":
                # "This is" button — transmit a NATO-phonetic station ID.
                if _config and _config.listen_only:
                    await _manager.send_to(ws, {
                        "type": "error",
                        "detail": "Radio is in listen-only mode; TX disabled.",
                    })
                    continue
                await _manager.broadcast({"type": "tx_status", "status": "transmitting"})
                await _tx_queue.put({"_standalone_id": True})

            elif msg_type == "voice_preview":
                # Synthesize a test phrase locally (no PTT keying) so the
                # operator can audition the current voice and speech rate.
                preview_text = (
                    data.get("text") or "Radio-TTY voice test. How does this sound?"
                ).strip()
                await _tx_queue.put({"text": preview_text, "_voice_preview": True})

            elif msg_type == "fcc_lookup":
                # Single callsign lookup for the Add/Edit contact dialog.
                cs = normalize_callsign(data.get("callsign", ""))
                name = (data.get("name") or "").strip()
                if not cs:
                    await _manager.send_to(ws, {
                        "type": "error",
                        "detail": "fcc_lookup requires a non-empty 'callsign' field.",
                    })
                    continue
                result = await asyncio.to_thread(verify_callsign, cs, name)
                await _manager.send_to(ws, {
                    "type": "fcc_lookup_result",
                    "callsign": cs,
                    "status": result.status,
                    "license_name": result.license_name,
                    "license_location": result.license_location,
                    "license_city": result.license_city,
                    "gmrs_callsign": result.gmrs_callsign,
                    "ham_callsign": result.ham_callsign,
                })

            elif msg_type == "verify_all":
                # Batch-verify all unverified contacts against the FCC API.
                if _contacts_store is None:
                    await _manager.send_to(ws, {
                        "type": "error",
                        "detail": "Contacts store not ready.",
                    })
                    continue
                if not is_online():
                    await _manager.send_to(ws, {
                        "type": "error",
                        "detail": "Cannot verify: offline.",
                    })
                    continue

                async def _do_verify_all(ws=ws) -> None:
                    now_iso = utc_now_iso()
                    updated_any = False
                    for contact in list(_contacts_store.get_all()):
                        if contact.get("verified") and contact.get("verified_at"):
                            continue  # skip already-verified unedited rows
                        cs = normalize_callsign(contact.get("callsign", ""))
                        name = (contact.get("name") or "").strip()
                        if not cs:
                            continue
                        result = await asyncio.to_thread(verify_callsign, cs, name)
                        updated = apply_verification(contact, result, now_iso)
                        if updated != contact:
                            try:
                                _contacts_store.update_contact(cs, updated)
                                updated_any = True
                            except Exception as exc:
                                _log.warning("verify_all: update failed for %s: %s", cs, exc)
                    if updated_any:
                        await _manager.broadcast({
                            "type": "contacts",
                            "contacts": _contacts_store.get_all(),
                        })
                    await _manager.send_to(ws, {"type": "verify_all_complete"})

                asyncio.create_task(_do_verify_all())

            elif msg_type == "dismiss_pending":
                # Remove a single pending-station pill (operator chose not to add).
                cs = normalize_callsign(data.get("callsign", ""))
                if cs and cs in _pending_stations:
                    _pending_stations.pop(cs)
                    _auto_add_tasks.pop(cs, None)
                    await _manager.broadcast(_build_pending_payload())

            elif msg_type == "dismiss_all_pending":
                _pending_stations.clear()
                _auto_add_tasks.clear()
                await _manager.broadcast(_build_pending_payload())

            elif msg_type == "delete_contact":
                if _contacts_store is None:
                    await _manager.send_to(ws, {"type": "error", "detail": "Contacts store not initialised."})
                    continue
                cs = normalize_callsign(data.get("callsign", ""))
                if not cs:
                    await _manager.send_to(ws, {"type": "error", "detail": "delete_contact requires a non-empty 'callsign' field."})
                    continue
                try:
                    updated = _contacts_store.delete_contact(cs)
                    await _manager.broadcast({"type": "contacts", "contacts": updated})
                except KeyError as exc:
                    await _manager.send_to(ws, {"type": "error", "detail": str(exc)})

            elif msg_type == "set_service_mode":
                if _config is None:
                    await _manager.send_to(ws, {"type": "error", "detail": "Config not loaded."})
                    continue
                service = normalize_service(data.get("service", ""))
                _config["radio_service"] = service
                _config.save()
                await _manager.broadcast(_build_status())

            elif msg_type == "set_listen_only":
                if _config is None:
                    await _manager.send_to(ws, {"type": "error", "detail": "Config not loaded."})
                    continue
                _config["listen_only"] = bool(data.get("listen_only", False))
                _config.save()
                await _manager.broadcast(_build_status())

            elif msg_type == "set_config":
                if _config is None:
                    await _manager.send_to(ws, {"type": "error", "detail": "Config not loaded."})
                    continue
                allowed_keys = {"filter_profanity", "fuzzy_callsign", "system_monitor_sink"}
                for key in allowed_keys:
                    if key in data:
                        _config[key] = data[key]
                _config.save()
                await _manager.broadcast(_build_status())

            elif msg_type == "set_spectro_config":
                if _config is None:
                    await _manager.send_to(ws, {"type": "error", "detail": "Config not loaded."})
                    continue
                if "colormap" in data:
                    _config["spectro_colormap"] = str(data["colormap"])
                if "freq_range" in data:
                    freq_range = str(data["freq_range"])
                    _config["spectro_freq_range"] = freq_range
                    if _spectro is not None:
                        _spectro.set_freq_range(freq_range)
                if "time_window_s" in data:
                    _config["spectro_time_window_s"] = int(data["time_window_s"])
                _config.save()
                await _manager.broadcast(_build_status())

            else:
                _log.debug("Unknown message type from client: %r", msg_type)

    except WebSocketDisconnect:
        _log.info("Client disconnected: %s", ws.client)
    except Exception as exc:
        _log.error("WebSocket error for %s: %s", ws.client, exc)
    finally:
        _manager.remove(ws)
