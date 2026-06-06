"""Radio-TTY WebSocket server.

Wires together: STTWorker, TTSSynthesizer, ContactsStore, ConnectionManager.
All clients receive broadcasts; TX messages are queued to the audio pipeline.

WebSocket message types (client → server):
    tx_message        — {"type": "tx_message", "callsign": str, "text": str,
                          "target_call"?: str, "target_name"?: str}
    standalone_id     — {"type": "standalone_id"}
    voice_preview     — {"type": "voice_preview", "text"?: str}
    add_contact       — {"type": "add_contact", "callsign": str, ...contact fields...}
    update_contact    — {"type": "update_contact", "callsign": str, "original_name"?: str, ...updates...}
    fcc_lookup        — {"type": "fcc_lookup", "callsign": str, "name"?: str}
    verify_all        — {"type": "verify_all"}
    dismiss_pending   — {"type": "dismiss_pending", "callsign": str}
    dismiss_all_pending — {"type": "dismiss_all_pending"}
    delete_contact    — {"type": "delete_contact", "callsign": str, "name"?: str}
    set_service_mode  — {"type": "set_service_mode", "service": "GMRS" | "FRS"}
    set_listen_only   — {"type": "set_listen_only", "listen_only": bool}
    list_input_devices — {"type": "list_input_devices"}
    set_input_device  — {"type": "set_input_device", "input_device": "system_monitor"|int|-1,
                          "system_monitor_sink"?: str}
    set_config        — {"type": "set_config", "filter_profanity"?: bool,
                          "fuzzy_callsign"?: bool}
    set_spectro_config — {"type": "set_spectro_config", "colormap"?: str,
                          "freq_range"?: "voice" | "full",
                          "time_window_s"?: int}
    set_admin_config  — {"type": "set_admin_config", "callsign"?: str, "name"?: str,
                          "location"?: str, "gemini_api_key"?: str, "journals_dir"?: str,
                          "tts_length_scale"?: float}
    set_server_config — {"type": "set_server_config", "vad_threshold"?: float,
                          "whisper_model"?: str, "ptt_mode"?: str, "ptt_serial_port"?: str,
                          "ptt_serial_line"?: str, "monitor_passthrough"?: bool,
                          "attendance_enabled"?: bool}
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
                          "partial": bool, "callsign_spans": [[start, end, callsign], ...]}
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
    input_devices     — {"type": "input_devices",
                          "devices": [{"label": str, "id": str|int},...],
                          "monitor_sinks": [{"label": str, "sink_id": str},...],
                          "current_input_device": str|int,
                          "current_monitor_sink": str}
    session_attendance — {"type": "session_attendance", "stations": [...]}
    journals          — {"type": "journals", "journals": [...]}
    journal_result    — {"type": "journal_result", "title": str, "summary": str,
                          "callsigns_locations": [...]}
    journal_error     — {"type": "journal_error", "detail": str}
    journal_saved     — {"type": "journal_saved", "path": str}
    journal_deleted   — {"type": "journal_deleted", "file_path": str}
    spectrogram_row   — {"type": "spectrogram_row", "row": [int, ...],
                          "vad": bool, "squelch": bool}
    voice_preview_audio — {"type": "voice_preview_audio", "data": str (base64 int16 PCM),
                          "sample_rate": int}
    tx_audio          — {"type": "tx_audio", "data": str (base64 int16 PCM),
                          "sample_rate": int}
    error             — {"type": "error", "detail": str}
"""
from __future__ import annotations

import asyncio
import base64
import collections
import dataclasses
import datetime
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response

from backend.ai.gemini_client import GeminiError
from backend.ai.gemini_client import generate_journal as _gemini_generate
from backend.audio.capture import enumerate_monitor_sources
from backend.audio.spectro_task import SpectroTask
from backend.config import ServerConfig
from backend.constants import normalize_service, utc_now_iso
from backend.fcc.auto_add import CallsignLookupWorker
from backend.fcc.crossref import apply_verification, verify_callsign
from backend.fcc.id_rule import (
    ID_INTERVAL_SECONDS,
    format_outgoing_message,
    format_standalone_id,
    format_tail_id,
)
from backend.hw_detect import detect as detect_compute
from backend.net.online import invalidate as _invalidate_online
from backend.net.online import is_online, is_online_cached
from backend import auth_routes
from backend.auth_routes import router as _auth_router
from backend.plugins import plugin_registry
from backend.persistence.attendance import AttendanceTracker, build_attendance_rows
from backend.persistence.contacts import (
    ContactsStore,
    known_callsigns,
    normalize_callsign,
)
from backend.persistence.journal import delete_journal, load_journals, load_published_manifest, publish_journal, save_journal, unpublish_journal
from backend.persistence.tokens import TokenStore
from backend.persistence.users import DEFAULT_PREFS, SENSITIVE_PROFILE_FIELDS, UsersStore
from backend.ptt.factory import make_ptt
from backend.stt.worker import STTWorker
from backend.text.callsigns import find_callsign_spans, fuzzy_match_callsign, spell_digits_in_callsigns
from backend.text.metadata import extract_name_location
from backend.text.shorthand import expand_tty_abbreviations
from backend.text.profanity import mask_profanity
from backend.text.placeholders import find_placeholders
from backend.tts.synthesizer import TTSSynthesizer

import sounddevice as sd

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singletons populated at startup
# ---------------------------------------------------------------------------

_event_loop: asyncio.AbstractEventLoop | None = None  # set in _lifespan; used for thread→asyncio bridge
_config: ServerConfig | None = None
_contacts_store: ContactsStore | None = None
_users_store: UsersStore | None = None
_token_store: TokenStore | None = None
_stt_worker: STTWorker | None = None
_synthesizer: TTSSynthesizer | None = None
_tx_audio_complete_event: asyncio.Event | None = None
_tx_abort_event: asyncio.Event = asyncio.Event()
_monitor: "Any | None" = None  # AudioMonitor, lazy-imported
_spectro: SpectroTask | None = None

# Attendance tracker — module-level so it persists across reconnects
_attendance: AttendanceTracker = AttendanceTracker()

# Monitor passthrough callback — updated by set_monitor handler
_monitor_chunk_cb = None

# Queues
_stt_out_queue: asyncio.Queue = asyncio.Queue()
_tx_queue: asyncio.Queue = asyncio.Queue()
_tts_event_queue: asyncio.Queue = asyncio.Queue()

# Background tasks — kept alive so they are not GC'd mid-run
_background_tasks: set[asyncio.Task] = set()

# Signal-quality state — written by STT worker callbacks (GIL-safe int/bool assignments)
_audio_level: int = 0
_radio_error: bool = False
_channel_clear: bool = True
_vad_active: bool = False
_stt_listening: bool = True
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

# Accumulated partial text per utterance_id — each partial slice is a delta;
# we send the running total so the frontend "replace" logic is always correct.
_utterance_partial_texts: dict[str, str] = {}

# Rolling buffer of last two finalized utterances — used to detect callsigns
# that span the boundary between consecutive transmissions.
_recent_finals: collections.deque = collections.deque(maxlen=2)

# Voice model cache — loaded once per voice path, reused across TX calls.
_voice_cache: dict[str, Any] = {}


def _load_voice(voice_name: str):
    """Return a cached PiperVoice, loading it on first use."""
    if voice_name not in _voice_cache:
        from piper import PiperVoice  # noqa: PLC0415
        _voice_cache[voice_name] = PiperVoice.load(voice_name)
    return _voice_cache[voice_name]


# ---------------------------------------------------------------------------
# ConnectionManager
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class ConnectionState:
    user_id: str
    is_admin: bool
    prefs: dict = dataclasses.field(default_factory=lambda: dict(DEFAULT_PREFS))
    # Voice PTT session
    voice_tx_active:   bool = False
    voice_tx_chunks:   list = dataclasses.field(default_factory=list)  # list[bytes]
    voice_tx_callsign: str  = ""
    voice_tx_operator: str  = ""
    voice_tx_bytes:    int  = 0  # running total for cap check


class ConnectionManager:
    """Tracks active WebSocket connections and provides broadcast helpers."""

    def __init__(self) -> None:
        self._clients: dict[WebSocket, ConnectionState] = {}

    def add(self, ws: WebSocket, state: ConnectionState) -> None:
        self._clients[ws] = state

    def remove(self, ws: WebSocket) -> None:
        self._clients.pop(ws, None)

    def get_state(self, ws: WebSocket) -> ConnectionState | None:
        return self._clients.get(ws)

    async def broadcast(self, msg: dict) -> None:
        """Send msg to every connected client. Silently drops dead sockets."""
        dead: list[WebSocket] = []
        for ws in list(self._clients):
            try:
                await ws.send_json(msg)
            except Exception as _exc:
                dead.append(ws)
                _log.debug("broadcast cleanup: %s", _exc)
        for ws in dead:
            self._clients.pop(ws, None)

    async def broadcast_rx(self, base_msg: dict, raw_text: str, filtered_text: str) -> None:
        """Broadcast rx_message with per-client profanity filtering."""
        dead: list[WebSocket] = []
        for ws, state in list(self._clients.items()):
            text = filtered_text if state.prefs.get("filter_profanity", True) else raw_text
            try:
                await ws.send_json({**base_msg, "text": text})
            except Exception as _exc:
                dead.append(ws)
                _log.debug("broadcast cleanup: %s", _exc)
        for ws in dead:
            self._clients.pop(ws, None)

    async def send_to(self, ws: WebSocket, msg: dict) -> None:
        """Send msg to a single client."""
        try:
            await ws.send_json(msg)
        except Exception as exc:
            _log.warning("send_to failed: %s", exc)
            self._clients.pop(ws, None)

    async def broadcast_to_user(self, user_id: str, msg: dict) -> None:
        """Send msg to all connections belonging to *user_id*."""
        for ws, state in list(self._clients.items()):
            if state.user_id == user_id:
                await self.send_to(ws, msg)


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
        if _event_loop is not None and _event_loop.is_running():
            _event_loop.call_soon_threadsafe(
                _event_loop.create_task,
                plugin_registry.dispatch_audio_rx_start(),
            )
    elif event == "squelch_closed":
        _channel_clear = True


def _audio_chunk_fanout(chunk) -> None:
    """Fan out audio chunks to the monitor, spectrogram task, and plugins."""
    if _monitor_chunk_cb is not None:
        _monitor_chunk_cb(chunk)
    if _spectro is not None:
        _spectro.push_chunk(chunk)
    plugin_registry.dispatch_audio_rx_chunk(chunk)


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
    """Callback fired when a background FCC lookup completes.

    Enriches the pending station entry with FCC-verified name/location so the
    operator sees better pre-fill data when they click the pill. Never
    auto-adds — the operator always decides.
    """
    global _auto_add_tasks, _pending_stations
    _auto_add_tasks.pop(callsign, None)

    if callsign not in _pending_stations:
        return

    if result.status == "verified":
        entry = _pending_stations[callsign]
        if result.license_name and not entry.get("name"):
            entry["name"] = result.license_name
        if result.license_location and not entry.get("location"):
            entry["location"] = result.license_location
        await _manager.broadcast(_build_pending_payload())
        _log.info("Enriched pending station %s from FCC (%s)", callsign, result.license_name)


# ---------------------------------------------------------------------------
# Background pump tasks
# ---------------------------------------------------------------------------

async def _synthesize_rx_audio(text: str) -> None:
    """Synthesize *text* via Piper and send rx_audio to read_aloud-enabled clients."""
    if _synthesizer is None or _config is None:
        return
    read_aloud_clients = [
        (ws, state) for ws, state in list(_manager._clients.items())
        if state.prefs.get("read_aloud", False)
    ]
    if not read_aloud_clients:
        return
    loop = asyncio.get_event_loop()
    voice = await loop.run_in_executor(None, _load_voice, _config.voice)
    audio, sample_rate = await _synthesizer.synthesize_to_buffer(
        voice, text, length_scale=_config.tts_length_scale
    )
    if audio is None:
        return
    audio_b64 = base64.b64encode(audio.tobytes()).decode("ascii")
    msg = {"type": "rx_audio", "data": audio_b64, "sample_rate": sample_rate}
    for ws, state in read_aloud_clients:
        if state.prefs.get("read_aloud", False):
            await _manager.send_to(ws, msg)


async def _rx_pump() -> None:
    """Drain the STT output queue and broadcast rx_message frames."""
    global _vad_active
    while True:
        try:
            result = await _stt_out_queue.get()
            utterance_id = result.get("utterance_id")
            partial = result.get("partial", False)
            _vad_active = bool(partial)

            chunk_text = result.get("text", "")
            source = result.get("source", "voice")

            if partial:
                # Accumulate deltas so the frontend "replace" logic always sees the
                # full running transcript rather than just the latest slice.
                prior = _utterance_partial_texts.get(utterance_id, "")
                raw_text = (prior + " " + chunk_text).strip() if prior else chunk_text
                _utterance_partial_texts[utterance_id] = raw_text
            else:
                # Final covers only the tail audio after the last partial cut.
                # Prepend accumulated partial text so the full utterance is preserved.
                prior = _utterance_partial_texts.pop(utterance_id, "")
                raw_text = (prior + " " + chunk_text).strip() if prior else chunk_text

            filtered_text = mask_profanity(raw_text)

            # Compute callsign spans from original text (handles NATO phonetic, spaced,
            # hyphenated, and compact forms). For final messages apply fuzzy correction
            # so the span carries the canonical callsign the contacts index knows about.
            raw_spans = find_callsign_spans(raw_text)

            if not partial and _contacts_store is not None and _config is not None:
                known = known_callsigns(_contacts_store.get_all())
                callsign_spans = []
                for start, end, cs in raw_spans:
                    effective = cs
                    if _config.fuzzy_callsign:
                        matched = fuzzy_match_callsign(cs, known)
                        if matched:
                            effective = matched
                    callsign_spans.append([start, end, effective])
            else:
                known = set()
                callsign_spans = [[s, e, cs] for s, e, cs in raw_spans]

            # Cross-boundary callsign detection: join with the previous final to catch
            # callsigns spoken across two separate transmissions (e.g. NATO phonetics
            # split across a PTT release).  Must run before broadcast_rx so the
            # current-entry spans are complete in the outgoing message.
            cross_prev_uid: "str | None" = None
            cross_prev_spans: list = []
            if not partial and _recent_finals:
                prev_uid, prev_text = _recent_finals[-1]
                combined = prev_text + " " + raw_text
                sep = len(prev_text)
                sep_offset = sep + 1
                for c_start, c_end, c_cs in find_callsign_spans(combined):
                    if c_start < sep and c_end > sep_offset:
                        effective = c_cs
                        if _config is not None and _config.fuzzy_callsign:
                            matched = fuzzy_match_callsign(c_cs, known)
                            if matched:
                                effective = matched
                        cross_prev_spans.append([c_start, sep, effective])
                        callsign_spans.append([0, c_end - sep_offset, effective])
                if cross_prev_spans:
                    callsign_spans.sort(key=lambda s: s[0])
                    cross_prev_uid = prev_uid

            await _manager.broadcast_rx(
                {
                    "type": "rx_message",
                    "utterance_id": utterance_id,
                    "partial": partial,
                    "callsign_spans": callsign_spans,
                    "source": source,
                },
                raw_text=raw_text,
                filtered_text=filtered_text,
            )

            if cross_prev_uid and cross_prev_spans:
                await _manager.broadcast({
                    "type": "rx_message_patch",
                    "utterance_id": cross_prev_uid,
                    "callsign_spans": cross_prev_spans,
                })

            if not partial:
                asyncio.create_task(
                    _synthesize_rx_audio(raw_text), name="rx-audio"
                )
                asyncio.create_task(
                    plugin_registry.dispatch_rx_final(raw_text), name="plugin-rx-final"
                )

            # Attendance and pending-station detection use the final (non-partial) text.
            if not partial:
                _recent_finals.append((utterance_id, raw_text))

                # Extract all detected callsigns (regular + any cross-boundary additions).
                detected = list({span[2] for span in callsign_spans})
                changed = any(_attendance.record(cs) for cs in detected)
                if changed:
                    await _manager.broadcast(_build_attendance_payload())

                # Identify unknown callsigns and drive pending-station pills + auto-add.
                if detected:
                    pending_changed = False
                    for cs in detected:
                        if cs in known:
                            continue  # already a contact — no pending pill needed
                        if cs in _pending_stations:
                            continue  # already pending — avoid duplicate pills

                        name, location = extract_name_location(raw_text, cs)
                        _pending_stations[cs] = {"name": name, "location": location}
                        pending_changed = True

                        # Kick off FCC enrichment if name is available and online.
                        if name and cs not in _auto_add_tasks and is_online_cached():
                            worker = CallsignLookupWorker(cs, name, location, _on_auto_add_result)
                            _auto_add_tasks[cs] = worker.start()

                    if pending_changed:
                        await _manager.broadcast(_build_pending_payload())

        except asyncio.CancelledError:
            break
        except Exception as exc:
            _log.error("_rx_pump error: %s", exc)


async def _tx_pump() -> None:
    """Drain tx_queue; apply text pipeline, FCC formatting, synthesize, play."""
    global _last_id_time, _has_transmitted, _tx_audio_complete_event

    while True:
        try:
            payload = await _tx_queue.get()
        except asyncio.CancelledError:
            break

        if _tx_abort_event.is_set():
            _tx_abort_event.clear()
            await _manager.broadcast({"type": "tx_status", "status": "idle"})
            continue

        if payload.get("_voice_tx"):
            await _handle_voice_tx(payload)
            continue

        if _synthesizer is None or _config is None:
            await _manager.broadcast({"type": "tx_status", "status": "idle"})
            continue

        is_preview = bool(payload.get("_voice_preview"))
        try:
            voice_name = payload.get("_voice_name") or _config.voice
            if not voice_name:
                _log.warning("No TTS voice configured; skipping TX synthesis.")
                if is_preview:
                    await _manager.broadcast({"type": "error", "detail": "No TTS voice configured. Select a voice in Admin Settings."})
                    await _manager.broadcast({"type": "voice_preview_done"})
                else:
                    await _manager.broadcast({"type": "tx_status", "status": "idle"})
                continue

            raw_text = payload.get("text", "")
            now = datetime.datetime.now(datetime.timezone.utc)

            chat_text: str | None = None
            if payload.get("_standalone_id"):
                # "This is" button — NATO-phonetic station ID, resets ID timer.
                my_call = payload.get("callsign") or _config.callsign
                my_name = payload.get("operator") or _config.name
                my_loc  = payload.get("location") if payload.get("location") is not None else _config.location
                text, _last_id_time = format_standalone_id(my_call, my_name, my_loc, now)
                text = spell_digits_in_callsigns(text)
                _has_transmitted = True
                chat_text = text

            elif payload.get("_pre_formatted") or is_preview:
                # Pre-formatted text (auto-ID pump, voice preview) — no processing.
                text = raw_text

            else:
                # Normal outgoing message: expand shorthand → mask profanity →
                # FCC-format with callsign preface → digit-isolate callsigns for TTS.
                processed = expand_tty_abbreviations(raw_text)
                if payload.get("_filter_profanity", True):
                    processed = mask_profanity(processed)
                service = normalize_service(_config.radio_service)
                text, new_id_time = format_outgoing_message(
                    processed,
                    target_call=payload.get("target_call") or "ALL",
                    target_name=payload.get("target_name") or "",
                    my_call=payload.get("callsign") or _config.callsign,
                    my_name=payload.get("operator") or _config.name,
                    now=now,
                    service=service,
                )
                if new_id_time is not None:  # FRS returns None; preserve GMRS timer
                    _last_id_time = new_id_time
                _has_transmitted = True
                # Space-isolate digits in callsigns so TTS reads them individually.
                text = spell_digits_in_callsigns(text)
                chat_text = raw_text

            if not is_preview and chat_text is not None:
                await _manager.broadcast({
                    "type": "tx_echo",
                    "ts": now.isoformat(),
                    "callsign": payload.get("callsign") or _config.callsign,
                    "operator": payload.get("operator") or _config.name,
                    "display_name": payload.get("_display_name") or "",
                    "text": chat_text,
                    "target_call": payload.get("target_call") or "ALL",
                    "target_name": payload.get("target_name") or "",
                })

            # Pause STT before keying so the radio receiver doesn't
            # transcribe TTS audio bleeding back through the radio.
            if not is_preview and _stt_worker is not None:
                _stt_worker.pause()

            voice = await asyncio.get_running_loop().run_in_executor(
                None, _load_voice, voice_name
            )
            length_scale = payload.get("_length_scale") or _config.tts_length_scale

            if is_preview:
                # Synthesize without PTT keying, then stream PCM to the browser
                # so remote users hear the preview in their own speaker.
                audio, sample_rate = await _synthesizer.synthesize_to_buffer(
                    voice, text, length_scale=length_scale
                )
                if audio is not None:
                    audio_b64 = base64.b64encode(audio.tobytes()).decode("ascii")
                    await _manager.broadcast({
                        "type": "voice_preview_audio",
                        "data": audio_b64,
                        "sample_rate": sample_rate,
                    })
            else:
                # Synthesize to buffer (including PTT lead/tail silence), key PTT
                # server-side, then stream PCM to the browser so it plays through
                # the local audio device connected to the radio.
                ptt = make_ptt(_config)
                synth_timeout = _config.tx_synthesis_timeout_seconds
                try:
                    audio, sample_rate = await asyncio.wait_for(
                        _synthesizer.synthesize_to_buffer(
                            voice, text, length_scale=length_scale,
                            lead_in_seconds=ptt.lead_in_seconds,
                            tail_seconds=ptt.tail_seconds,
                        ),
                        timeout=synth_timeout,
                    )
                except asyncio.TimeoutError:
                    _log.warning("TX synthesis timed out after %ds — PTT not keyed", synth_timeout)
                    await _manager.broadcast({"type": "error", "detail": f"TX aborted: TTS synthesis exceeded {synth_timeout}s."})
                    audio = None
                if audio is not None:
                    audio_b64 = base64.b64encode(audio.tobytes()).decode("ascii")
                    _tx_audio_complete_event = asyncio.Event()
                    max_tx = _config.tx_max_duration_seconds
                    try:
                        ptt.key()
                        await _manager.broadcast({
                            "type": "tx_audio",
                            "data": audio_b64,
                            "sample_rate": sample_rate,
                        })
                        # Race the audio-duration sleep against the operator abort
                        # event and the hard PTT cap.  Whichever fires first wins;
                        # PTT is always released in the finally block below.
                        sleep_task = asyncio.create_task(asyncio.sleep(len(audio) / sample_rate))
                        abort_task = asyncio.create_task(_tx_abort_event.wait())
                        done, pending = await asyncio.wait(
                            {sleep_task, abort_task},
                            timeout=max_tx,
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        # Capture outcome BEFORE cancellation: after gather() the
                        # tasks are marked done (CancelledError), so post-gather
                        # checks would always find sleep_task.done() == True.
                        operator_aborted = abort_task in done
                        watchdog_fired = not operator_aborted and sleep_task not in done
                        for t in pending:
                            t.cancel()
                        if pending:
                            await asyncio.gather(*pending, return_exceptions=True)
                        if operator_aborted:
                            _tx_abort_event.clear()
                            _log.warning("TX aborted by operator kill switch")
                            await _manager.broadcast({"type": "error", "detail": "TX aborted by operator."})
                        elif watchdog_fired:
                            _log.warning("TX exceeded max duration (%ds) — forcing PTT unkey", max_tx)
                            await _manager.broadcast({"type": "error", "detail": f"TX aborted: exceeded {max_tx}s limit."})
                    finally:
                        ptt.unkey()

            while True:
                try:
                    _tts_event_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

        except asyncio.CancelledError:
            break
        except Exception as exc:
            _log.error("TX synthesis error: %s", exc)
            await _manager.broadcast({"type": "error", "detail": f"TX error: {exc}"})
        finally:
            if is_preview:
                await _manager.broadcast({"type": "voice_preview_done"})
            else:
                await _manager.broadcast({"type": "tx_status", "status": "idle"})
                if _stt_worker is not None and _stt_listening:
                    # Wait for the browser to confirm audio playback has ended
                    # before resuming STT.  The duration-based sleep above only
                    # covers synthesis length; browser Web Audio API buffering +
                    # PulseAudio loopback latency means audio is still playing
                    # when that sleep expires.  We fall back to a 2 s timeout
                    # in case the browser never sends the signal (tab hidden,
                    # WS drop, etc.), then add a short tail for loopback drain.
                    evt = _tx_audio_complete_event
                    if evt is not None:
                        try:
                            await asyncio.wait_for(evt.wait(), timeout=2.0)
                        except asyncio.TimeoutError:
                            pass
                    await asyncio.sleep(0.2)
                    _stt_worker.resume()
            _tx_audio_complete_event = None


# ---------------------------------------------------------------------------
# Voice helpers
# ---------------------------------------------------------------------------

async def _handle_voice_tx(payload: dict) -> None:
    """Transcribe browser voice audio, key PTT, play raw audio, broadcast tx_echo."""
    import numpy as np

    audio_bytes:  bytes = payload["audio_bytes"]
    sample_rate:  int   = payload.get("sample_rate", 16000)
    callsign:     str   = payload.get("callsign") or (_config.callsign if _config else "")
    operator:     str   = payload.get("operator") or (_config.name if _config else "")
    display_name: str   = payload.get("_display_name") or ""
    now = datetime.datetime.now(datetime.timezone.utc)

    if _config is None:
        await _manager.broadcast({"type": "tx_status", "status": "idle"})
        return

    # Pause STT so the worker doesn't use the Whisper model concurrently
    if _stt_worker is not None:
        _stt_worker.pause()
    try:
        int16_arr   = np.frombuffer(audio_bytes, dtype=np.int16)
        float32_arr = int16_arr.astype(np.float32) / 32768.0

        transcription: str | None = None
        mc = _stt_worker.model_cache if _stt_worker else None
        if mc is not None:
            try:
                transcription = await asyncio.to_thread(mc.whisper.transcribe, float32_arr)
            except Exception as exc:
                _log.warning("voice_tx STT error: %s", exc)

        chat_text = transcription or "[unintelligible]"
        await _manager.broadcast({
            "type":         "tx_echo",
            "ts":           now.isoformat(),
            "callsign":     callsign,
            "operator":     operator,
            "display_name": display_name,
            "text":         chat_text,
            "target_call":  "ALL",
            "target_name":  "",
        })

        # Key PTT and play raw voice audio
        ptt = make_ptt(_config)
        out_dev = _config.output_device if (_config and _config.output_device != -1) else None
        max_tx = _config.tx_max_duration_seconds
        try:
            ptt.key()
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(_play_voice_blocking, int16_arr, sample_rate, out_dev),
                    timeout=max_tx,
                )
            except asyncio.TimeoutError:
                _log.warning("Voice TX exceeded max duration (%ds) — forcing PTT unkey", max_tx)
                await _manager.broadcast({"type": "error", "detail": f"Voice TX aborted: exceeded {max_tx}s limit."})
        finally:
            ptt.unkey()

    except Exception as exc:
        _log.error("_handle_voice_tx: %s", exc)
        await _manager.broadcast({"type": "error", "detail": f"Voice TX error: {exc}"})
    finally:
        await _manager.broadcast({"type": "tx_status", "status": "idle"})
        if _stt_worker is not None and _stt_listening:
            await asyncio.sleep(0.3)  # let PulseAudio output buffer drain
            _stt_worker.resume()


def _play_voice_blocking(audio: "np.ndarray", sample_rate: int, output_device) -> None:
    """Play int16 PCM audio through the configured output device, blocking until done.
    Resamples if the device's native rate differs from the input rate."""
    import math
    import numpy as np

    try:
        dev_idx   = output_device if output_device is not None else sd.default.device[1]
        native_sr = int(sd.query_devices(dev_idx)["default_samplerate"])
    except Exception:
        native_sr = sample_rate

    if native_sr != sample_rate:
        from scipy.signal import resample_poly
        gcd       = math.gcd(sample_rate, native_sr)
        resampled = resample_poly(audio.astype(np.float32), native_sr // gcd, sample_rate // gcd)
        audio     = np.clip(resampled, -32768, 32767).astype(np.int16)

    sd.play(audio, samplerate=native_sr, device=output_device)
    sd.wait()


def _voice_label(stem: str) -> str:
    """Turn 'en_US-ryan-high' into 'Ryan (High)'."""
    parts = stem.split("-")
    if len(parts) >= 3:
        return f"{parts[-2].capitalize()} ({parts[-1].capitalize()})"
    return stem.replace("-", " ").title()


def _list_voices() -> list[dict]:
    """Return all .onnx voice files in the configured voices directory."""
    if _config is None:
        return []
    from pathlib import Path as _Path
    try:
        return [
            {"id": str(p), "name": p.stem, "label": _voice_label(p.stem)}
            for p in sorted(_config.voices_dir.glob("*.onnx"))
        ]
    except OSError:
        return []


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
        "stt_listening": _stt_listening,
        "service_mode": (_config.radio_service if _config else "GMRS") or "GMRS",
        "fuzzy_callsign": bool(_config and _config.fuzzy_callsign),
        "spectro_freq_range": (_config.spectro_freq_range if _config else "full"),
        # Admin-editable identity fields
        "station_callsign": (_config.callsign if _config else "N0CALL"),
        "station_name": (_config.name if _config else ""),
        "station_location": (_config.location if _config else ""),
        "station_voice": (_config.voice if _config else ""),
        "station_length_scale": float(_config.tts_length_scale) if _config else 1.0,
        "gemini_api_key_set": bool(_config and _config.gemini_api_key),
        "journals_dir": str(_config.journals_dir) if _config else "/data/journals",
        "ncs_zone": (_config.ncs_zone if _config else ""),
        "input_device": (_config.input_device if _config else -1),
        "system_monitor_sink": (_config.system_monitor_sink if _config else ""),
        "rx_mode": (_config.rx_mode if _config else "voice"),
        "vad_threshold": float(_config.vad_threshold) if _config else 0.5,
        "whisper_model": (_config.whisper_model if _config else "small.en"),
        "ptt_mode": (_config.ptt_mode if _config else "manual"),
        "ptt_serial_port": (_config.ptt_serial_port if _config else ""),
        "ptt_serial_line": (_config.ptt_serial_line if _config else "RTS"),
        "monitor_passthrough": bool(_config.monitor_passthrough) if _config else False,
        "attendance_enabled": bool(_config.attendance_enabled) if _config else False,
    }


def _safe_profile(profile: dict) -> dict:
    return {k: v for k, v in profile.items() if k not in SENSITIVE_PROFILE_FIELDS}


def _build_user_profile_msg(profile: dict) -> dict:
    return {"type": "user_profile", "profile": _safe_profile(profile)}


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
                tail = format_tail_id(_config.callsign)
                spoken = spell_digits_in_callsigns(f"This is {tail}")
                _last_id_time = now
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


async def _voices_watcher_pump() -> None:
    """Detect changes to the voices directory and push voices_list to all clients.

    Polls every 5 seconds. Only broadcasts when the set of .onnx files changes,
    so there is no steady-state traffic. Evicts removed voices from _voice_cache
    so stale PiperVoice objects don't linger in memory.
    """
    last_ids: frozenset[str] = frozenset(v["id"] for v in _list_voices())
    while True:
        try:
            await asyncio.sleep(5.0)
            current = _list_voices()
            current_ids = frozenset(v["id"] for v in current)
            if current_ids != last_ids:
                removed = last_ids - current_ids
                for vid in removed:
                    _voice_cache.pop(vid, None)
                await _manager.broadcast({"type": "voices_list", "voices": current})
                last_ids = current_ids
        except asyncio.CancelledError:
            break
        except Exception as exc:
            _log.error("_voices_watcher_pump error: %s", exc)


# ---------------------------------------------------------------------------
# FastAPI lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Startup / shutdown wiring."""
    global _config, _contacts_store, _users_store, _token_store, _stt_worker, _synthesizer, _monitor
    global _stt_out_queue, _tx_queue, _tts_event_queue, _background_tasks, _tx_abort_event
    global _audio_level, _radio_error, _channel_clear, _last_id_time, _has_transmitted
    global _level_window, _attendance, _spectro, _monitor_chunk_cb
    global _pending_stations, _auto_add_tasks, _event_loop

    # --- startup -----------------------------------------------------------
    _event_loop = asyncio.get_running_loop()
    _config = ServerConfig.load()
    _log.info("Config loaded: callsign=%s, port=%d", _config.callsign, _config.port)

    compute = detect_compute()
    _log.info("Compute backend: %s", compute.device_label)

    _contacts_store = ContactsStore(_config.contacts_file)
    _log.info("Contacts loaded: %d entries", len(_contacts_store.get_all()))

    _users_store = UsersStore(_config.users_file)
    _token_store = TokenStore(_config.tokens_file)
    purged = _token_store.purge_expired()
    if purged:
        _log.info("Purged %d expired session tokens.", purged)

    # Headless bootstrap: if RADIO_TTY_ADMIN_PASS is set and no users exist, create admin now.
    # Without the env var, the browser first-run setup flow handles account creation.
    if _users_store.is_empty():
        admin_pass = os.environ.get("RADIO_TTY_ADMIN_PASS") or None
        if admin_pass:
            _users_store.create(
                display_name="Admin",
                password=admin_pass,
                avatar_emoji="👤",
                operator_name=_config.name or "Admin",
                callsign=_config.callsign or "N0CALL",
                location=_config.location or "",
                is_admin=True,
                prefs={
                    "dark_mode": False,
                    "panel_order": ["config", "attendance", "journal"],
                    "filter_profanity": _config.filter_profanity,
                    "listen_only": _config.listen_only,
                    "spectro_colormap": _config.spectro_colormap,
                    "spectro_time_window_s": _config.spectro_time_window_s,
                },
            )
            _log.info("Created admin account from RADIO_TTY_ADMIN_PASS.")
        else:
            _log.info("No users found — first-run setup required via browser.")

    # Wire auth routes with the live stores.
    auth_routes.init(_users_store, _token_store, _config)

    _stt_out_queue = asyncio.Queue()
    _tx_queue = asyncio.Queue()
    _tts_event_queue = asyncio.Queue()
    _tx_abort_event = asyncio.Event()

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
    _voice_cache.clear()
    _invalidate_online()  # force fresh probe on startup

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
        rx_mode=_config.rx_mode,
        on_audio_level=_on_stt_audio_level,
        on_audio_chunk=_audio_chunk_fanout,
        on_capture_event=_on_stt_capture_event,
        on_status=_on_stt_status,
        on_error=_on_stt_error,
    )
    _stt_worker.start()

    # Register plugins — must happen after _tx_queue and _config are initialised.
    from backend.plugins.ncs import NCSPlugin
    plugin_registry.register(NCSPlugin(
        broadcast_fn=_manager.broadcast,
        tx_queue=_tx_queue,
        config_getter=lambda: _config,
        channel_clear_fn=lambda: _channel_clear,
        contacts_getter=lambda: _contacts_store.get_all() if _contacts_store else [],
        add_contact_fn=lambda c: _contacts_store.add_contact(c) if _contacts_store else [],
        update_contact_fn=lambda cs, u, original_name=None: _contacts_store.update_contact(cs, u, original_name=original_name) if _contacts_store else [],
        broadcast_contacts_fn=lambda contacts: _manager.broadcast({"type": "contacts", "contacts": contacts}),
    ))

    _synthesizer = TTSSynthesizer(
        out_queue=_tts_event_queue,
        compute_backend=compute,
        output_device=_config.output_device if _config.output_device != -1 else None,
    )

    _background_tasks = {
        asyncio.create_task(_rx_pump(), name="rx-pump"),
        asyncio.create_task(_tx_pump(), name="tx-pump"),
        asyncio.create_task(_status_pump(), name="status-pump"),
        asyncio.create_task(_id_rule_pump(), name="id-rule-pump"),
        asyncio.create_task(_spectro.run(), name="spectro-pump"),
        asyncio.create_task(_online_status_pump(), name="online-status-pump"),
        asyncio.create_task(_voices_watcher_pump(), name="voices-watcher"),
    }
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

    _level_window.clear()
    _log.info("Radio-TTY server stopped.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Radio-TTY", lifespan=_lifespan)
app.include_router(_auth_router, prefix="/auth")


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict:
    return {"ok": True}


@app.get("/journal")
async def public_journal() -> Response:
    if _config is None:
        return Response("Service starting up.", media_type="text/html", status_code=503)
    path = _config.journals_dir.parent / "public" / "journal.html"
    if not path.exists():
        return Response("No journals have been published yet.", media_type="text/html", status_code=404)
    return FileResponse(path, media_type="text/html")


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

async def _ws_handle_set_admin_config(ws: WebSocket, data: dict, state: "ConnectionState") -> None:
    global _stt_worker
    if _config is None:
        await _manager.send_to(ws, {"type": "error", "detail": "Config not loaded."})
        return
    if "callsign" in data:
        _config["callsign"] = str(data["callsign"]).strip().upper() or "N0CALL"
    if "name" in data:
        _config["name"] = str(data["name"]).strip()
    if "location" in data:
        _config["location"] = str(data["location"]).strip()
    if "gemini_api_key" in data:
        key = str(data["gemini_api_key"]).strip()
        if key:
            _config["gemini_api_key"] = key
    if "journals_dir" in data:
        jdir = str(data["journals_dir"]).strip()
        if jdir:
            _config["journals_dir"] = jdir
    if "voice" in data:
        _config["voice"] = str(data["voice"]).strip()
    if "tts_length_scale" in data:
        try:
            ls = float(data["tts_length_scale"])
            if 0.1 <= ls <= 4.0:
                _config["tts_length_scale"] = ls
        except (TypeError, ValueError):
            pass
    if "ncs_zone" in data:
        _config["ncs_zone"] = str(data["ncs_zone"]).strip().upper()
    rx_mode_changed = False
    if "rx_mode" in data:
        new_mode = str(data["rx_mode"]).strip().lower()
        if new_mode in ("voice", "cw") and new_mode != _config.rx_mode:
            _config["rx_mode"] = new_mode
            rx_mode_changed = True
    _config.save()
    await _manager.broadcast(_build_status())
    if rx_mode_changed and _stt_worker is not None and _stt_listening:
        _stt_worker.stop()
        await _stt_worker.join()
        _stt_worker = STTWorker(
            out_queue=_stt_out_queue,
            input_device=_config.input_device if _config.input_device != -1 else None,
            whisper_model=_config.whisper_model,
            vad_threshold=_config.vad_threshold,
            system_monitor_sink=_config.system_monitor_sink,
            rx_mode=_config.rx_mode,
            on_audio_level=_on_stt_audio_level,
            on_audio_chunk=_audio_chunk_fanout,
            on_capture_event=_on_stt_capture_event,
            on_status=_on_stt_status,
            on_error=_on_stt_error,
        )
        _stt_worker.start()


async def _ws_handle_set_server_config(ws: WebSocket, data: dict, state: "ConnectionState") -> None:
    """Handle technical server settings that require STT worker restart on change."""
    global _stt_worker
    if _config is None:
        await _manager.send_to(ws, {"type": "error", "detail": "Config not loaded."})
        return

    stt_restart_needed = False

    if "vad_threshold" in data:
        try:
            vt = float(data["vad_threshold"])
            if 0.0 < vt < 1.0 and vt != _config.vad_threshold:
                _config["vad_threshold"] = vt
                stt_restart_needed = True
        except (TypeError, ValueError):
            pass

    if "whisper_model" in data:
        model = str(data["whisper_model"]).strip()
        valid = {"tiny.en", "base.en", "small.en", "medium.en", "large-v3"}
        if model in valid and model != _config.whisper_model:
            _config["whisper_model"] = model
            stt_restart_needed = True

    if "ptt_mode" in data:
        mode = str(data["ptt_mode"]).strip().lower()
        if mode in ("manual", "serial", "vox"):
            _config["ptt_mode"] = mode

    if "ptt_serial_port" in data:
        _config["ptt_serial_port"] = str(data["ptt_serial_port"]).strip()

    if "ptt_serial_line" in data:
        line = str(data["ptt_serial_line"]).strip().upper()
        if line in ("RTS", "DTR"):
            _config["ptt_serial_line"] = line

    if "monitor_passthrough" in data:
        pt = bool(data["monitor_passthrough"])
        _config["monitor_passthrough"] = pt
        if _monitor is not None:
            _monitor.set_passthrough(pt)

    if "attendance_enabled" in data:
        _config.attendance_enabled = bool(data["attendance_enabled"])

    _config.save()
    await _manager.broadcast(_build_status())

    if stt_restart_needed and _stt_worker is not None and _stt_listening:
        _stt_worker.stop()
        await _stt_worker.join()
        _stt_worker = STTWorker(
            out_queue=_stt_out_queue,
            input_device=_config.input_device if _config.input_device != -1 else None,
            whisper_model=_config.whisper_model,
            vad_threshold=_config.vad_threshold,
            system_monitor_sink=_config.system_monitor_sink,
            rx_mode=_config.rx_mode,
            on_audio_level=_on_stt_audio_level,
            on_audio_chunk=_audio_chunk_fanout,
            on_capture_event=_on_stt_capture_event,
            on_status=_on_stt_status,
            on_error=_on_stt_error,
        )
        _stt_worker.start()


async def _ws_handle_fcc_lookup(ws: WebSocket, data: dict, state: "ConnectionState") -> None:
    # Single callsign lookup for the Add/Edit contact dialog.
    cs = normalize_callsign(data.get("callsign", ""))
    name = (data.get("name") or "").strip()
    if not cs:
        await _manager.send_to(ws, {
            "type": "error",
            "detail": "fcc_lookup requires a non-empty 'callsign' field.",
        })
        return
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


async def _check_listen_only(ws: WebSocket, state: "ConnectionState") -> bool:
    """Return True (and send error) if the user is in listen-only mode."""
    if state.prefs.get("listen_only", False):
        await _manager.send_to(ws, {"type": "error", "detail": "You are in listen-only mode; TX disabled."})
        return True
    return False


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: str | None = Query(default=None)) -> None:
    global _stt_worker, _stt_listening

    # Validate session token — accept first so we can send a close frame.
    user_id = _token_store.validate(token) if (_token_store and token) else None
    profile = _users_store.get(user_id) if (_users_store and user_id) else None
    if not user_id or not profile:
        await ws.accept()
        await ws.close(code=4001)
        return

    await ws.accept()
    state = ConnectionState(
        user_id=user_id,
        is_admin=bool(profile.get("is_admin", False)),
        prefs={**DEFAULT_PREFS, **profile.get("prefs", {})},
    )
    _manager.add(ws, state)
    _log.info("Client connected: %s (user=%s)", ws.client, user_id)

    # Send initial state to the newly connected client.
    await _manager.send_to(ws, _build_status())
    await _manager.send_to(ws, _build_user_profile_msg(profile))
    if _contacts_store is not None:
        await _manager.send_to(ws, {
            "type": "contacts",
            "contacts": _contacts_store.get_all(),
        })
    await _manager.send_to(ws, _build_attendance_payload())
    await _manager.send_to(ws, _build_pending_payload())
    await _manager.send_to(ws, {"type": "voices_list", "voices": _list_voices()})
    cached_online = is_online_cached()
    if cached_online is not None:
        await _manager.send_to(ws, {"type": "online_status", "online": cached_online})

    try:
        while True:
            data: Any = await ws.receive_json()
            msg_type = data.get("type")

            asyncio.create_task(
                plugin_registry.dispatch_client_message(
                    dict(data),
                    reply=lambda msg: _manager.send_to(ws, msg),
                ),
                name="plugin-client-msg",
            )

            if msg_type == "tx_audio_complete":
                if _tx_audio_complete_event is not None:
                    _tx_audio_complete_event.set()
                continue

            if msg_type == "tx_message":
                callsign = (data.get("callsign") or "").strip()
                if not callsign:
                    await _manager.send_to(ws, {
                        "type": "error",
                        "detail": "tx_message requires a non-empty 'callsign' field.",
                    })
                    continue

                if await _check_listen_only(ws, state):
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

                _tx_sender_display = (
                    (_users_store.get_public_one(state.user_id) or {}).get("display_name") or ""
                ) if _users_store else ""
                tx_payload = await plugin_registry.dispatch_tx_pre_queue({
                    **data,
                    "_filter_profanity": state.prefs.get("filter_profanity", True),
                    "_voice_name": state.prefs.get("tts_voice") or None,
                    "_length_scale": state.prefs.get("tts_length_scale") or None,
                    "_display_name": _tx_sender_display,
                })
                if tx_payload is None:
                    continue  # TX blocked by a plugin
                await _tx_queue.put(tx_payload)
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

            elif msg_type == "update_contact":
                if _contacts_store is None:
                    await _manager.send_to(ws, {
                        "type": "error",
                        "detail": "Contacts store not initialised.",
                    })
                    continue
                cs = normalize_callsign(data.get("callsign", ""))
                if not cs:
                    await _manager.send_to(ws, {"type": "error", "detail": "update_contact requires 'callsign'."})
                    continue
                original_name = (data.get("original_name") or "").strip() or None
                updates = {k: v for k, v in data.items() if k not in ("type", "callsign", "original_name")}
                try:
                    updated = _contacts_store.update_contact(cs, updates, original_name=original_name)
                    await _manager.broadcast({"type": "contacts", "contacts": updated})
                except KeyError as exc:
                    await _manager.send_to(ws, {"type": "error", "detail": str(exc)})

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
                published = {
                    e.get("source_file")
                    for e in load_published_manifest(_config.journals_dir)
                }
                for j in journals:
                    j["published"] = Path(j["_file"]).name in published
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

            elif msg_type == "publish_journal":
                if _config is None:
                    await _manager.send_to(ws, {"type": "error", "detail": "Server not ready."})
                    continue
                file_path = (data.get("file_path") or "").strip()
                display_name = (
                    (_users_store.get_public_one(state.user_id) or {}).get("display_name")
                    or state.user_id
                ) if _users_store else state.user_id
                try:
                    entry = publish_journal(file_path, display_name, _config.journals_dir)
                    await _manager.send_to(ws, {
                        "type": "journal_published",
                        "title": entry["title"],
                    })
                except (ValueError, OSError) as exc:
                    await _manager.send_to(ws, {"type": "error", "detail": str(exc)})

            elif msg_type == "unpublish_journal":
                if _config is None:
                    await _manager.send_to(ws, {"type": "error", "detail": "Server not ready."})
                    continue
                file_path = (data.get("file_path") or "").strip()
                try:
                    unpublish_journal(Path(file_path).name, _config.journals_dir)
                    await _manager.send_to(ws, {
                        "type": "journal_unpublished",
                        "file_path": file_path,
                    })
                except (ValueError, OSError) as exc:
                    await _manager.send_to(ws, {"type": "error", "detail": str(exc)})

            elif msg_type == "standalone_id":
                # "This is" button — transmit a NATO-phonetic station ID.
                if await _check_listen_only(ws, state):
                    continue
                await _manager.broadcast({"type": "tx_status", "status": "transmitting"})
                await _tx_queue.put({
                    "_standalone_id": True,
                    "_filter_profanity": state.prefs.get("filter_profanity", True),
                    "operator": (data.get("operator") or "").strip(),
                    "callsign": (data.get("callsign") or "").strip(),
                    "location": (data.get("location") or "").strip(),
                    "_voice_name": state.prefs.get("tts_voice") or None,
                    "_length_scale": state.prefs.get("tts_length_scale") or None,
                })

            elif msg_type == "voice_preview":
                # Synthesize a test phrase locally (no PTT keying) so the
                # operator can audition the current voice and speech rate.
                preview_text = (
                    data.get("text") or "Radio-TTY voice test. How does this sound?"
                ).strip()
                preview_voice = (
                    data.get("voice")
                    or state.prefs.get("tts_voice")
                    or (_config.voice if _config else None)
                )
                await _tx_queue.put({
                    "text": preview_text,
                    "_voice_preview": True,
                    "_voice_name": preview_voice,
                    "_length_scale": state.prefs.get("tts_length_scale") or None,
                })

            elif msg_type == "fcc_lookup":
                await _ws_handle_fcc_lookup(ws, data, state)

            elif msg_type == "verify_all":
                # Batch-verify all unverified contacts against the FCC API.
                if _contacts_store is None:
                    await _manager.send_to(ws, {
                        "type": "error",
                        "detail": "Contacts store not ready.",
                    })
                    continue
                if not await asyncio.to_thread(is_online):
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
                                _contacts_store.update_contact(cs, updated, original_name=name or None)
                                updated_any = True
                            except Exception as exc:
                                _log.warning("verify_all: update failed for %s: %s", cs, exc)
                    if updated_any:
                        await _manager.broadcast({
                            "type": "contacts",
                            "contacts": _contacts_store.get_all(),
                        })
                    await _manager.send_to(ws, {"type": "verify_all_complete"})

                task = asyncio.create_task(_do_verify_all())
                _background_tasks.add(task)
                task.add_done_callback(_background_tasks.discard)

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
                contact_name = (data.get("name") or "").strip() or None
                try:
                    updated = _contacts_store.delete_contact(cs, name=contact_name)
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
                listen_only = bool(data.get("listen_only", False))
                state.prefs["listen_only"] = listen_only
                if _users_store is not None:
                    try:
                        updated = _users_store.update_prefs(state.user_id, {"listen_only": listen_only})
                        await _manager.send_to(ws, _build_user_profile_msg(updated))
                    except KeyError:
                        pass

            elif msg_type == "set_stt_listening":
                _stt_listening = bool(data.get("listening", True))
                if _stt_worker is not None:
                    if _stt_listening:
                        _stt_worker.resume()
                    else:
                        _stt_worker.pause()
                await _manager.broadcast(_build_status())

            elif msg_type == "list_input_devices":
                devices = [{"label": "System Default (microphone)", "id": -1}]
                try:
                    for i, dev in enumerate(sd.query_devices()):
                        if dev.get("max_input_channels", 0) > 0:
                            devices.append({"label": dev["name"], "id": i})
                except Exception:
                    pass
                devices.append({"label": "System Audio Output (loopback)", "id": "system_monitor"})
                monitor_sinks = [
                    {"label": label, "sink_id": sink_id}
                    for label, sink_id in enumerate_monitor_sources()
                ]
                await _manager.send_to(ws, {
                    "type": "input_devices",
                    "devices": devices,
                    "monitor_sinks": monitor_sinks,
                    "current_input_device": _config.input_device if _config else -1,
                    "current_monitor_sink": _config.system_monitor_sink if _config else "",
                })

            elif msg_type == "set_input_device":
                if _config is None:
                    await _manager.send_to(ws, {"type": "error", "detail": "Config not loaded."})
                    continue
                new_device = data.get("input_device", -1)
                new_sink = str(data.get("system_monitor_sink") or "").strip()
                _config["input_device"] = new_device
                _config["system_monitor_sink"] = new_sink
                _config.save()
                # Restart STT worker with new audio source.
                if _stt_worker is not None:
                    _stt_worker.stop()
                    await _stt_worker.join()
                _stt_worker = STTWorker(
                    out_queue=_stt_out_queue,
                    input_device=new_device if new_device not in (-1, None) else None,
                    whisper_model=_config.whisper_model,
                    vad_threshold=_config.vad_threshold,
                    system_monitor_sink=new_sink,
                    rx_mode=_config.rx_mode,
                    on_audio_level=_on_stt_audio_level,
                    on_audio_chunk=_audio_chunk_fanout,
                    on_capture_event=_on_stt_capture_event,
                    on_status=_on_stt_status,
                    on_error=_on_stt_error,
                )
                _stt_worker.start()
                await _manager.broadcast(_build_status())

            elif msg_type == "set_config":
                if _config is None:
                    await _manager.send_to(ws, {"type": "error", "detail": "Config not loaded."})
                    continue
                # filter_profanity is now per-user; fuzzy_callsign remains station-wide.
                if "filter_profanity" in data:
                    fp = bool(data["filter_profanity"])
                    state.prefs["filter_profanity"] = fp
                    if _users_store is not None:
                        try:
                            updated = _users_store.update_prefs(state.user_id, {"filter_profanity": fp})
                            await _manager.send_to(ws, _build_user_profile_msg(updated))
                        except KeyError:
                            pass
                if "fuzzy_callsign" in data:
                    _config["fuzzy_callsign"] = bool(data["fuzzy_callsign"])
                    _config.save()
                    await _manager.broadcast(_build_status())

            elif msg_type == "set_spectro_config":
                if _config is None:
                    await _manager.send_to(ws, {"type": "error", "detail": "Config not loaded."})
                    continue
                user_pref_updates: dict = {}
                if "colormap" in data:
                    user_pref_updates["spectro_colormap"] = str(data["colormap"])
                if "time_window_s" in data:
                    user_pref_updates["spectro_time_window_s"] = int(data["time_window_s"])
                if user_pref_updates:
                    state.prefs.update(user_pref_updates)
                    if _users_store is not None:
                        try:
                            updated = _users_store.update_prefs(state.user_id, user_pref_updates)
                            await _manager.send_to(ws, _build_user_profile_msg(updated))
                        except KeyError:
                            pass
                if "freq_range" in data:
                    freq_range = str(data["freq_range"])
                    _config["spectro_freq_range"] = freq_range
                    if _spectro is not None:
                        _spectro.set_freq_range(freq_range)
                    _config.save()
                    await _manager.broadcast(_build_status())

            elif msg_type == "set_admin_config":
                if not state.is_admin:
                    await _manager.send_to(ws, {"type": "error", "detail": "Admin access required."})
                    continue
                await _ws_handle_set_admin_config(ws, data, state)

            elif msg_type == "set_server_config":
                if not state.is_admin:
                    await _manager.send_to(ws, {"type": "error", "detail": "Admin access required."})
                    continue
                await _ws_handle_set_server_config(ws, data, state)

            elif msg_type == "save_user_prefs":
                if _users_store is None:
                    continue
                allowed = {"dark_mode", "panel_order", "filter_profanity", "listen_only",
                           "read_aloud", "notifications_enabled", "spectro_colormap", "spectro_time_window_s",
                           "tts_voice", "tts_length_scale"}
                updates = {k: v for k, v in data.get("prefs", data).items() if k in allowed}
                if updates:
                    state.prefs.update(updates)
                    try:
                        updated = _users_store.update_prefs(state.user_id, updates)
                        await _manager.send_to(ws, _build_user_profile_msg(updated))
                    except KeyError:
                        pass

            elif msg_type == "update_profile":
                if _users_store is None:
                    continue
                target_id = data.get("user_id") or state.user_id
                if target_id != state.user_id and not state.is_admin:
                    await _manager.send_to(ws, {"type": "error", "detail": "Admin access required."})
                    continue
                allowed = {"display_name", "avatar_emoji", "operator_name", "callsign", "location"}
                if state.is_admin:
                    allowed.add("is_admin")
                updates = {k: v for k, v in data.items() if k in allowed}
                new_password = data.get("new_password")
                try:
                    updated = _users_store.update_profile(target_id, updates)
                    if new_password:
                        _users_store.change_password(target_id, str(new_password))
                        updated = _users_store.get(target_id)
                    msg_out = _build_user_profile_msg(updated)
                    await _manager.broadcast_to_user(target_id, msg_out)
                    await _manager.broadcast({
                        "type": "profiles",
                        "profiles": _users_store.get_public(),
                    })
                except KeyError as exc:
                    await _manager.send_to(ws, {"type": "error", "detail": str(exc)})

            elif msg_type == "create_profile":
                if not state.is_admin:
                    await _manager.send_to(ws, {"type": "error", "detail": "Admin access required."})
                    continue
                if _users_store is None:
                    continue
                display_name = (data.get("display_name") or "").strip()
                password = (data.get("password") or "").strip()
                if not display_name or not password:
                    await _manager.send_to(ws, {"type": "error", "detail": "display_name and password are required."})
                    continue
                _users_store.create(
                    display_name=display_name,
                    password=password,
                    avatar_emoji=(data.get("avatar_emoji") or "👤"),
                    operator_name=(data.get("operator_name") or display_name),
                    callsign=(data.get("callsign") or ""),
                    location=(data.get("location") or ""),
                    is_admin=bool(data.get("is_admin", False)),
                )
                await _manager.broadcast({
                    "type": "profiles",
                    "profiles": _users_store.get_public(),
                })

            elif msg_type == "delete_profile":
                if not state.is_admin:
                    await _manager.send_to(ws, {"type": "error", "detail": "Admin access required."})
                    continue
                if _users_store is None:
                    continue
                target_id = (data.get("user_id") or "").strip()
                if target_id == state.user_id:
                    await _manager.send_to(ws, {"type": "error", "detail": "Cannot delete your own account."})
                    continue
                try:
                    _users_store.delete(target_id)
                    await _manager.broadcast({
                        "type": "profiles",
                        "profiles": _users_store.get_public(),
                    })
                except KeyError as exc:
                    await _manager.send_to(ws, {"type": "error", "detail": str(exc)})

            elif msg_type == "list_profiles":
                if _users_store is not None:
                    await _manager.send_to(ws, {
                        "type": "profiles",
                        "profiles": _users_store.get_public(),
                    })

            elif msg_type == "reset_lockout":
                if not state.is_admin:
                    await _manager.send_to(ws, {"type": "error", "detail": "Admin access required."})
                    continue
                if _users_store is None:
                    continue
                target_id = (data.get("user_id") or "").strip()
                try:
                    _users_store.reset_lockout(target_id)
                    await _manager.broadcast({
                        "type": "profiles",
                        "profiles": _users_store.get_public(),
                    })
                except KeyError as exc:
                    await _manager.send_to(ws, {"type": "error", "detail": str(exc)})

            elif msg_type == "voice_tx_start":
                if await _check_listen_only(ws, state):
                    continue
                callsign = (data.get("callsign") or "").strip()
                if not callsign:
                    await _manager.send_to(ws, {"type": "voice_tx_error", "detail": "Callsign required."})
                    continue
                state.voice_tx_active   = True
                state.voice_tx_chunks   = []
                state.voice_tx_bytes    = 0
                state.voice_tx_callsign = callsign
                state.voice_tx_operator = (data.get("operator") or "").strip()
                await _manager.send_to(ws, {"type": "voice_tx_ack"})

            elif msg_type == "voice_tx_chunk":
                if not state.voice_tx_active:
                    continue
                b64 = data.get("data") or ""
                try:
                    raw = base64.b64decode(b64)
                except Exception:
                    _log.warning("voice_tx_chunk: invalid base64")
                    continue
                state.voice_tx_chunks.append(raw)
                state.voice_tx_bytes += len(raw)
                # Safety cap: 120 s @ 16 kHz int16 = 3,840,000 bytes
                if state.voice_tx_bytes > 3_840_000:
                    state.voice_tx_active = False
                    state.voice_tx_chunks = []
                    state.voice_tx_bytes  = 0
                    await _manager.send_to(ws, {"type": "voice_tx_error", "detail": "Recording too long (120 s max)."})

            elif msg_type == "voice_tx_end":
                if not state.voice_tx_active:
                    continue
                chunks   = state.voice_tx_chunks
                callsign = state.voice_tx_callsign
                operator = state.voice_tx_operator
                # Reset immediately so a fast second press can start
                state.voice_tx_active   = False
                state.voice_tx_chunks   = []
                state.voice_tx_bytes    = 0
                state.voice_tx_callsign = ""
                state.voice_tx_operator = ""

                audio_bytes = b"".join(chunks)
                if len(audio_bytes) < 9_600:   # < 300 ms @ 16 kHz int16
                    await _manager.send_to(ws, {"type": "voice_tx_error", "detail": "Recording too short."})
                    continue

                display_name = ""
                if _users_store:
                    rec = _users_store.get_public_one(state.user_id) or {}
                    display_name = rec.get("display_name") or ""

                await _manager.broadcast({"type": "tx_status", "status": "transmitting"})
                await _tx_queue.put({
                    "_voice_tx":     True,
                    "audio_bytes":   audio_bytes,
                    "sample_rate":   16000,
                    "callsign":      callsign,
                    "operator":      operator,
                    "_display_name": display_name,
                })

            elif msg_type == "voice_tx_cancel":
                state.voice_tx_active   = False
                state.voice_tx_chunks   = []
                state.voice_tx_bytes    = 0
                state.voice_tx_callsign = ""
                state.voice_tx_operator = ""

            elif msg_type == "tx_abort":
                _tx_abort_event.set()
                drained = 0
                while not _tx_queue.empty():
                    try:
                        _tx_queue.get_nowait()
                        drained += 1
                    except asyncio.QueueEmpty:
                        break
                if drained:
                    _log.info("tx_abort: drained %d queued TX item(s)", drained)
                _log.warning("tx_abort: operator kill switch activated")
                await _manager.broadcast({"type": "tx_status", "status": "idle"})
                # Yield two event-loop cycles so any task already waiting on
                # _tx_abort_event (the PTT race's abort_task) can fire and be
                # consumed before we clear the event.  Without this, the event
                # would stay set and cause the next legitimate TX to be
                # silently discarded by the top-of-loop abort check.
                await asyncio.sleep(0)
                await asyncio.sleep(0)
                _tx_abort_event.clear()

            else:
                _log.debug("Unknown message type from client: %r", msg_type)

    except WebSocketDisconnect:
        _log.info("Client disconnected: %s", ws.client)
    except Exception as exc:
        _log.error("WebSocket error for %s: %s", ws.client, exc)
    finally:
        _manager.remove(ws)
