"""Hearthwave WebSocket server.

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
    list_output_devices — {"type": "list_output_devices"}
    set_output_device — {"type": "set_output_device", "output_device": int|-1}
    set_config        — {"type": "set_config", "filter_profanity"?: bool,
                          "fuzzy_callsign"?: bool, "fuzzy_callsign_rewrite"?: bool}
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
                          "sample_rate": int}  (sent only to the requesting user)
    output_devices    — {"type": "output_devices",
                          "devices": [{"label": str, "id": int},...],
                          "current_output_device": int}
    error             — {"type": "error", "detail": str}

Transmitted TTS audio is played server-side out the configured output device
(wired to the radio); it is NOT streamed to browsers.
"""
from __future__ import annotations

import asyncio
import base64
import collections
import dataclasses
import datetime
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import (
    FastAPI, File, Header, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect,
)
from fastapi.responses import FileResponse, Response

from backend.ai.gemini_client import GeminiError
from backend.ai.gemini_client import generate_journal as _gemini_generate
from backend.audio.capture import enumerate_monitor_sources
from backend.audio.spectro_task import SpectroTask
from backend.audio.vad import load_vad_model, make_vad_iterator
from backend.config import ServerConfig
from backend.constants import (
    GAIN_MODES,
    VALID_FINAL_MODELS,
    VALID_WHISPER_MODELS,
    normalize_service,
    utc_now_iso,
)
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
from backend import __version__
from backend import auth_routes
from backend.auth_routes import router as _auth_router
from backend.plugins import loader as plugin_loader
from backend.plugins import plugin_registry
from backend.persistence.attendance import AttendanceTracker, build_attendance_rows
from backend.persistence.contacts import (
    ContactsStore,
    known_callsigns,
    normalize_callsign,
    ordered_callsigns,
)
from backend.persistence.audit import AuditLog
from backend.auth_ratelimit import _extract_ip, get_client_ip
from backend.family.reminders import is_checkin_missed
from backend.persistence.family import FamilyStore
from backend.persistence.journal import delete_journal, load_journals, load_published_manifest, publish_journal, save_journal, unpublish_journal
from backend.persistence.presence import PresenceStore
from backend.persistence.tokens import TokenStore
from backend.persistence.users import (
    DEFAULT_PREFS,
    ROLES,
    SENSITIVE_PROFILE_FIELDS,
    UsersStore,
    effective_prefs as _effective_prefs,
)
from backend.ptt.factory import make_ptt
from backend.stt.calibration import CalibrationCapture, PREAMBLE_TEXT, run_sweep
from backend.stt.transcriber import WhisperTranscriber
from backend.stt.worker import STTWorker
from backend.text.callsigns import (
    correct_callsigns,
    detect_callsigns,
    find_callsign_spans,
    fuzzy_match_callsign,
    spell_digits_in_callsigns,
)
from backend.text.metadata import extract_name_location
from backend.text.shorthand import expand_tty_abbreviations
from backend.text.profanity import mask_profanity
from backend.text.placeholders import find_placeholders
from backend.text.primer import prepend_primer_word
from backend.tts.synthesizer import TTSSynthesizer
from backend.beacon.monitoring import format_monitoring_call, should_emit_beacon

import sounddevice as sd

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singletons populated at startup
# ---------------------------------------------------------------------------

_event_loop: asyncio.AbstractEventLoop | None = None  # set in _lifespan; used for thread→asyncio bridge
_config: ServerConfig | None = None
# Directory scanned for installable plugins (each subdir with a plugin.py).
_PLUGINS_DIR = Path(os.environ.get("RADIO_TTY_PLUGINS_DIR", "/data/plugins"))
# PluginContext bound at startup; reused by the install/reload/uninstall endpoints.
_plugin_ctx = None
_contacts_store: ContactsStore | None = None
_users_store: UsersStore | None = None
_token_store: TokenStore | None = None
_presence_store: PresenceStore | None = None
_family_store: FamilyStore | None = None
_audit_log: AuditLog | None = None
_stt_worker: STTWorker | None = None
_synthesizer: TTSSynthesizer | None = None
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

# STT calibration wizard — set while a capture session is running; tapped from
# the same raw-chunk fanout the spectrogram/monitor already consume.
_calibration_capture: "CalibrationCapture | None" = None

# FCC ID-rule state — asyncio-only (both writers are asyncio tasks; no cross-thread writes)
_last_id_time: datetime.datetime | None = None
_has_transmitted: bool = False

# Monitoring-beacon state — asyncio-only (single writer: the beacon pump task).
_last_beacon_time: datetime.datetime | None = None

# Set at startup to the live NCSPlugin instance so the beacon can suppress
# itself while a net is active.
_ncs_plugin = None

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
    role: str = "adult"
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

    async def disconnect_user(self, user_id: str) -> None:
        """Close all active WebSocket connections for *user_id* with code 4001."""
        targets = [ws for ws, state in list(self._clients.items()) if state.user_id == user_id]
        for ws in targets:
            try:
                await ws.close(code=4001)
            except Exception:
                pass
            self._clients.pop(ws, None)


# Cap on the shared stream backfill — most-recent N messages kept since the
# last clear. High enough to cover a long net, bounded so memory can't grow
# without limit.
_STREAM_HISTORY_MAX = 2000


class StreamHistory:
    """Shared, in-memory record of the message stream (rx/tx/chat).

    Every message the server broadcasts to the log is recorded here so a client
    that connects later can be backfilled with everything since the last clear.
    Profanity-filterable entries keep both the raw and masked text so each
    joining client sees the variant matching its own ``filter_profanity`` pref
    (mirroring :meth:`ConnectionManager.broadcast_rx`).

    In-memory only by design — a backend restart starts with an empty stream.
    All access happens on the single asyncio event loop, so no lock is needed.

    Bounded to the most recent ``max_entries`` messages so a long-running net
    can't grow the buffer without limit; the oldest entries roll off (logged at
    debug) once the cap is reached.
    """

    def __init__(self, max_entries: int = _STREAM_HISTORY_MAX) -> None:
        self._entries: list[dict] = []
        self._max_entries = max_entries

    def _trim(self) -> None:
        overflow = len(self._entries) - self._max_entries
        if overflow > 0:
            del self._entries[:overflow]
            _log.debug("StreamHistory: dropped %d oldest entries (cap %d)",
                       overflow, self._max_entries)

    def record_rx(self, base_msg: dict, raw_text: str, filtered_text: str) -> None:
        """Record a profanity-filterable message (rx_message final / chat_echo)."""
        msg = dict(base_msg)
        msg.setdefault("ts", utc_now_iso())
        self._entries.append({
            "msg": msg,
            "raw": raw_text,
            "filtered": filtered_text,
            "utterance_id": base_msg.get("utterance_id"),
        })
        self._trim()

    def record_plain(self, msg: dict) -> None:
        """Record a message broadcast verbatim to all clients (tx_echo)."""
        self._entries.append({
            "msg": dict(msg),
            "raw": None,
            "filtered": None,
            "utterance_id": None,
        })
        self._trim()

    def patch(self, utterance_id: str, callsign_spans: list) -> None:
        """Update the callsign spans of a previously recorded rx entry."""
        for rec in reversed(self._entries):
            if rec["utterance_id"] == utterance_id:
                rec["msg"]["callsign_spans"] = callsign_spans
                return

    def clear(self) -> None:
        self._entries = []

    def render_for(self, filter_profanity: bool) -> list[dict]:
        """Return the stream as a list of messages, text resolved per pref."""
        out: list[dict] = []
        for rec in self._entries:
            msg = dict(rec["msg"])
            if rec["raw"] is not None:
                msg["text"] = rec["filtered"] if filter_profanity else rec["raw"]
            out.append(msg)
        return out


_manager = ConnectionManager()
_stream_history = StreamHistory()


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
    """Fan out audio chunks to the monitor, spectrogram task, plugins, and any
    running STT calibration capture."""
    if _monitor_chunk_cb is not None:
        _monitor_chunk_cb(chunk)
    if _spectro is not None:
        _spectro.push_chunk(chunk)
    if _calibration_capture is not None:
        _calibration_capture.feed_raw(chunk)
    plugin_registry.dispatch_audio_rx_chunk(chunk)


def _assemble_stt_phrases() -> "list[str]":
    """Assemble the full STT bias list (curated vocab + saved phrases + contact
    callsigns) ordered lowest-priority-first. Shared by worker construction and
    live rebuilds."""
    from backend.stt import vocab
    contacts = _contacts_store.get_all() if _contacts_store else []
    callsigns = ordered_callsigns(contacts)
    phrases = _config.saved_phrases if _config else []
    max_cs = _config.stt_vocab_max_callsigns if _config else 100
    return vocab.assemble_phrases(callsigns, phrases, max_callsigns=max_cs)


def _rebuild_stt_vocabulary() -> int:
    """Push a freshly assembled bias list to the live worker. Returns the term
    count (0 if no worker yet).

    Runs synchronously on the asyncio event loop and re-tokenizes via the model
    tokenizer.  This is acceptable at LAN scale (tens-to-hundreds of contacts).
    If contact counts grow large, offloading to a thread pool executor is a
    documented follow-up.
    """
    if _stt_worker is None:
        return 0
    phrases = _assemble_stt_phrases()
    _stt_worker.update_phrases(phrases)
    return len(phrases)


def _make_stt_worker() -> STTWorker:
    """Build an STTWorker from the current _config and module callbacks.

    Single construction point so config plumbing only has to change here.
    Callers that change audio settings must write them into _config first.
    """
    return STTWorker(
        out_queue=_stt_out_queue,
        input_device=_config.input_device if _config.input_device not in (-1, None) else None,
        whisper_model=_config.whisper_model,
        vad_threshold=_config.vad_threshold,
        system_monitor_sink=_config.system_monitor_sink,
        rx_mode=_config.rx_mode,
        saved_phrases=_assemble_stt_phrases(),
        debug_capture=_config.stt_debug_capture,
        debug_dir=_config.stt_debug_dir,
        squelch_open_threshold=_config.squelch_open_threshold,
        squelch_adaptive=_config.squelch_adaptive,
        pre_roll_s=_config.stt_pre_roll_s,
        min_speech_s=_config.stt_min_speech_s,
        whisper_model_final=_config.whisper_model_final,
        final_max_s=_config.stt_final_max_s,
        stt_final_device=_config.stt_final_device,
        gain_mode=_config.stt_gain_mode,
        noise_profile=_config.stt_noise_profile,
        on_audio_level=_on_stt_audio_level,
        on_audio_chunk=_audio_chunk_fanout,
        on_capture_event=_on_stt_capture_event,
        on_status=_on_stt_status,
        on_error=_on_stt_error,
    )


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


_NO_PRESENCE_RECORD: dict = {"last_heard": None, "last_ok": None, "missed_checkin": False}


def _build_family_presence_msg() -> dict:
    """Join presence records onto every known user profile.

    Users with no presence record yet (never transmitted or checked in) still
    get an entry, with null last_heard/last_ok and missed_checkin=False, so
    the client can render the full family roster.
    """
    entries = []
    profiles = _users_store.get_public() if _users_store else []
    for prof in profiles:
        e = _presence_store.get(prof["id"]) if _presence_store else dict(_NO_PRESENCE_RECORD)
        entries.append({
            "user_id": prof["id"],
            "display_name": prof.get("display_name"),
            "avatar_emoji": prof.get("avatar_emoji"),
            "last_heard": e["last_heard"],
            "last_ok": e["last_ok"],
            "missed_checkin": e["missed_checkin"],
        })
    return {"type": "family_presence", "entries": entries}


def _build_family_reminders_msg() -> dict:
    reminders = _family_store.get_reminders() if _family_store else {}
    return {"type": "family_reminders", "reminders": reminders}


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


# A replacing second pass must retain at least this fraction of the
# first-pass text. The whole-utterance final pass occasionally truncates long
# messages to the first bit (or drops them entirely); when its result is this
# much shorter than the partials it already produced, treat it as truncated
# and keep the complete first-pass transcript instead of overwriting it.
_FINAL_REPLACE_MIN_RATIO = 0.5


def _resolve_final_text(prior: str, chunk_text: str, replace: bool) -> str:
    """Final transcript for an utterance. A replacing final (second-pass
    full-utterance re-transcription) supersedes the accumulated partials;
    a plain final covers only the tail audio after the last partial cut, so
    the partial text is prepended. An empty replace falls back to the
    partials — a failed final pass must never erase the transcript. A
    replacing final that is drastically shorter than the partials is treated
    as a truncated second pass and discarded in favor of the first-pass text."""
    if replace and chunk_text:
        prior_len = len(prior.strip())
        if prior_len and len(chunk_text.strip()) < _FINAL_REPLACE_MIN_RATIO * prior_len:
            return prior
        return chunk_text
    return (prior + " " + chunk_text).strip() if prior else chunk_text


def _detected_callsigns(callsign_spans, prior_text: str, known, *, fuzzy: bool) -> set:
    """Callsigns to drive attendance + pending pills for a finalized utterance.

    Unions the callsigns highlighted in the displayed (final) text with any
    found in the first-pass (prior) text. A replacing second pass sometimes
    drops or truncates a callsign the first pass heard cleanly; detecting on
    both passes means a callsign caught by either survives."""
    detected = {span[2] for span in callsign_spans}
    for cs in detect_callsigns(prior_text):
        effective = cs
        if fuzzy:
            matched = fuzzy_match_callsign(cs, known)
            if matched:
                effective = matched
        detected.add(effective)
    return detected


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
                prior = _utterance_partial_texts.pop(utterance_id, "")
                raw_text = _resolve_final_text(prior, chunk_text, result.get("replace", False))

            # Roster-based callsign rewrite (finals only, both toggles on):
            # splice the corrected canonical over misheard callsigns BEFORE
            # profanity masking, so broadcast, stream history, TTS read-aloud,
            # plugins, and attendance all see the corrected text. Corrected
            # spans carry the original heard text as a 4th element.
            corrected_spans: "list | None" = None
            if (
                not partial
                and _config is not None
                and _config.fuzzy_callsign
                and _config.fuzzy_callsign_rewrite
                and _contacts_store is not None
            ):
                known = known_callsigns(_contacts_store.get_all())
                raw_text, rewritten = correct_callsigns(raw_text, known)
                corrected_spans = [list(span) for span in rewritten]

            filtered_text = mask_profanity(raw_text)

            # Compute callsign spans from original text (handles NATO phonetic, spaced,
            # hyphenated, and compact forms). For final messages apply fuzzy correction
            # so the span carries the canonical callsign the contacts index knows about.
            if corrected_spans is not None:
                callsign_spans = corrected_spans
            elif not partial and _contacts_store is not None and _config is not None:
                known = known_callsigns(_contacts_store.get_all())
                callsign_spans = []
                for start, end, cs in find_callsign_spans(raw_text):
                    effective = cs
                    if _config.fuzzy_callsign:
                        matched = fuzzy_match_callsign(cs, known)
                        if matched:
                            effective = matched
                    callsign_spans.append([start, end, effective])
            else:
                known = set()
                callsign_spans = [[s, e, cs] for s, e, cs in find_callsign_spans(raw_text)]

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
            if not partial:
                _stream_history.record_rx(
                    {
                        "type": "rx_message",
                        "utterance_id": utterance_id,
                        "callsign_spans": callsign_spans,
                        "source": source,
                    },
                    raw_text,
                    filtered_text,
                )

            if cross_prev_uid and cross_prev_spans:
                await _manager.broadcast({
                    "type": "rx_message_patch",
                    "utterance_id": cross_prev_uid,
                    "callsign_spans": cross_prev_spans,
                })
                _stream_history.patch(cross_prev_uid, cross_prev_spans)

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

                # All detected callsigns: spans (regular + cross-boundary) unioned
                # with the first-pass text, so a callsign the replacing second
                # pass dropped or truncated still drives attendance + pending.
                fuzzy = _config is not None and _config.fuzzy_callsign
                detected = list(_detected_callsigns(callsign_spans, prior, known, fuzzy=fuzzy))
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
    global _last_id_time, _has_transmitted

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

            # Discard transmission if the channel is already occupied — but an
            # operator-initiated transmit (Transmit button / "THIS IS") overrides
            # the squelch, like the voice-test path: the operator decides when to
            # key.  Automatic transmits (auto station-ID) still wait for a clear
            # channel to avoid talking over a received signal.
            if (
                not is_preview
                and not payload.get("_operator_initiated")
                and _stt_worker is not None
                and _stt_worker.channel_busy.is_set()
            ):
                _log.warning("TX discarded: channel busy (squelch open)")
                continue

            if not is_preview and chat_text is not None:
                tx_echo_msg = {
                    "type": "tx_echo",
                    "ts": now.isoformat(),
                    "callsign": payload.get("callsign") or _config.callsign,
                    "operator": payload.get("operator") or _config.name,
                    "display_name": payload.get("_display_name") or "",
                    "text": chat_text,
                    "target_call": payload.get("target_call") or "ALL",
                    "target_name": payload.get("target_name") or "",
                }
                await _manager.broadcast(tx_echo_msg)
                _stream_history.record_plain(tx_echo_msg)

            # Pause STT before keying so the radio receiver doesn't
            # transcribe TTS audio bleeding back through the radio.
            if not is_preview and _stt_worker is not None:
                _stt_worker.pause()

            voice = await asyncio.get_running_loop().run_in_executor(
                None, _load_voice, voice_name
            )
            length_scale = payload.get("_length_scale") or _config.tts_length_scale

            if is_preview:
                # Synthesize without PTT keying, then stream PCM only to the
                # requesting user's connections so they audition it locally.
                audio, sample_rate = await _synthesizer.synthesize_to_buffer(
                    voice, text, length_scale=length_scale
                )
                if audio is not None:
                    audio_b64 = base64.b64encode(audio.tobytes()).decode("ascii")
                    await _manager.broadcast_to_user(payload.get("_user_id", ""), {
                        "type": "voice_preview_audio",
                        "data": audio_b64,
                        "sample_rate": sample_rate,
                    })
            else:
                # Synthesize to buffer (including PTT lead/tail silence), key PTT
                # server-side, then play the audio out the local sound device wired
                # to the radio.  Browsers are text-only for TX; nothing is streamed
                # to clients (that would double-key audio on the base station, which
                # runs a browser AND the radio).
                if _config.vox_primer_word_enabled:
                    text = prepend_primer_word(text, _config.vox_primer_word)
                ptt = make_ptt(_config)
                synth_timeout = _config.tx_synthesis_timeout_seconds
                try:
                    audio, sample_rate = await asyncio.wait_for(
                        _synthesizer.synthesize_to_buffer(
                            voice, text, length_scale=length_scale,
                            lead_in_seconds=ptt.lead_in_seconds,
                            tail_seconds=ptt.tail_seconds,
                            vox_primer_ms=(_config.vox_primer_ms if _config.vox_primer_enabled else 0),
                        ),
                        timeout=synth_timeout,
                    )
                except asyncio.TimeoutError:
                    _log.warning("TX synthesis timed out after %ds — PTT not keyed", synth_timeout)
                    await _manager.broadcast({"type": "error", "detail": f"TX aborted: TTS synthesis exceeded {synth_timeout}s."})
                    audio = None
                if audio is not None:
                    out_dev = _config.output_device if _config.output_device != -1 else None
                    max_tx = _config.tx_max_duration_seconds
                    try:
                        ptt.key()
                        if _audit_log:
                            _audit_log.log(
                                "tx",
                                user_id=payload.get("_user_id", ""),
                                detail=(
                                    f"callsign={payload.get('callsign', '')} "
                                    f"text={payload.get('text', '')!r}"
                                ),
                            )
                        # Play server-side, blocking until the device finishes.
                        # Race the playback against the operator abort event and the
                        # hard PTT cap.  sd.stop() unblocks sd.wait() in the worker
                        # thread; we never cancel play_task (cancelling a to_thread
                        # future doesn't kill the underlying thread) — instead we stop
                        # the device and await the task so the thread drains.  PTT is
                        # always released in the finally block below.
                        play_task  = asyncio.ensure_future(
                            asyncio.to_thread(_play_voice_blocking, audio, sample_rate, out_dev)
                        )
                        abort_task = asyncio.ensure_future(_tx_abort_event.wait())
                        done, pending = await asyncio.wait(
                            {play_task, abort_task},
                            timeout=max_tx,
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        # Capture outcome BEFORE stopping/draining.
                        operator_aborted = abort_task in done
                        watchdog_fired = not operator_aborted and play_task not in done
                        if operator_aborted or watchdog_fired:
                            # sd.stop() is process-global; safe — TX is serialized
                            # through the single _tx_queue consumer.
                            sd.stop()
                        if abort_task in pending:
                            abort_task.cancel()
                        # Always await playback so the executor thread is fully drained.
                        try:
                            await play_task
                        except Exception as exc:
                            _log.warning("TX playback error: %s", exc)
                        await asyncio.gather(abort_task, return_exceptions=True)
                        if operator_aborted:
                            _tx_abort_event.clear()
                            _log.warning("TX aborted by operator kill switch")
                            await _manager.broadcast({"type": "error", "detail": "TX aborted by operator."})
                        elif watchdog_fired:
                            _log.warning("TX exceeded max duration (%ds) — forcing PTT unkey", max_tx)
                            await _manager.broadcast({"type": "error", "detail": f"TX aborted: exceeded {max_tx}s limit."})
                    finally:
                        ptt.unkey()

                    # A monitoring beacon leads with the callsign, so once it has
                    # keyed and aired it satisfies the FCC 15-minute ID. Reset the
                    # ID timer here (confirmed air) rather than at enqueue — a beacon
                    # discarded for a busy channel must not disarm the ID pump.
                    if payload.get("_beacon") and not operator_aborted:
                        _last_id_time = now
                        _has_transmitted = False

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
                await _manager.broadcast_to_user(
                    payload.get("_user_id", ""), {"type": "voice_preview_done"}
                )
            else:
                await _manager.broadcast({"type": "tx_status", "status": "idle"})
                if _stt_worker is not None and _stt_listening:
                    # Playback above blocked until the device finished (sd.wait),
                    # so just add a short tail for the PulseAudio loopback to drain
                    # before resuming STT.
                    await asyncio.sleep(0.3)
                    _stt_worker.resume()


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
        tx_echo_msg = {
            "type":         "tx_echo",
            "ts":           now.isoformat(),
            "callsign":     callsign,
            "operator":     operator,
            "display_name": display_name,
            "text":         chat_text,
            "target_call":  "ALL",
            "target_name":  "",
        }
        await _manager.broadcast(tx_echo_msg)
        _stream_history.record_plain(tx_echo_msg)

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


def _resolve_tx_voice(display_name: str) -> tuple[str | None, float | None]:
    """Map a display name to that user's (tts_voice, tts_length_scale).

    Used when a client transmits on behalf of a named operator (the `voice_as`
    field).  Returns (None, None) when the name is unknown or the user has not
    overridden the station defaults — tts_voice="" / tts_length_scale=0 are the
    DEFAULT_PREFS "inherit station default" sentinels — so the caller's
    `or _config.voice` / `or _config.tts_length_scale` fallbacks apply.
    """
    if _users_store is None:
        return None, None
    profile = _users_store.get_by_display_name(display_name)
    if not profile:
        return None, None
    prefs = profile.get("prefs") or {}
    return (prefs.get("tts_voice") or None, prefs.get("tts_length_scale") or None)


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

    dur = len(audio) / native_sr if native_sr else 0.0
    _log.info(
        "TX audio → output device %s: %.2fs @ %dHz (%d samples)",
        output_device if output_device is not None else "default",
        dur, native_sr, len(audio),
    )
    sd.play(audio, samplerate=native_sr, device=output_device)
    sd.wait()


async def _enumerate_devices(kind: str) -> list[dict]:
    """Enumerate sound devices of the given kind ('input' or 'output') as a list
    of {"label", "id"}.  The blocking PortAudio query runs off the event loop."""
    channel_key = "max_input_channels" if kind == "input" else "max_output_channels"

    def _query() -> list[dict]:
        out: list[dict] = []
        try:
            for i, dev in enumerate(sd.query_devices()):
                if dev.get(channel_key, 0) > 0:
                    out.append({"label": dev["name"], "id": i})
        except Exception:
            pass
        return out

    return await asyncio.to_thread(_query)


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
        "fuzzy_callsign_rewrite": bool(_config and _config.fuzzy_callsign_rewrite),
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
        "ncs_preamble_text": (_config.ncs_preamble_text if _config else ""),
        "ncs_closing_text": (_config.ncs_closing_text if _config else ""),
        "input_device": (_config.input_device if _config else -1),
        "output_device": (_config.output_device if _config else -1),
        "system_monitor_sink": (_config.system_monitor_sink if _config else ""),
        "rx_mode": (_config.rx_mode if _config else "voice"),
        "vad_threshold": float(_config.vad_threshold) if _config else 0.5,
        "whisper_model": (_config.whisper_model if _config else "small.en"),
        "whisper_model_final": (_config.whisper_model_final if _config else ""),
        # Read-only: what "auto" resolved to on the live worker ("" when off,
        # no model staged, or listening hasn't started). The settings select
        # round-trips the configured value above, never this. The isinstance
        # guard keeps the payload JSON-safe when the worker is a test double.
        "whisper_model_final_resolved": (
            _stt_worker.whisper_model_final
            if _stt_worker is not None
            and isinstance(getattr(_stt_worker, "whisper_model_final", None), str)
            else ""
        ),
        "stt_gain_mode": (_config.stt_gain_mode if _config else "agc"),
        "stt_noise_profile": bool(_config.stt_noise_profile) if _config else False,
        "squelch_adaptive": bool(_config.squelch_adaptive) if _config else False,
        "stt_debug_capture": bool(_config.stt_debug_capture) if _config else False,
        "tx_conditioning": bool(_config.tx_conditioning) if _config else False,
        "vox_primer_enabled": bool(_config.vox_primer_enabled) if _config else False,
        "vox_primer_ms": int(_config.vox_primer_ms) if _config else 300,
        "vox_primer_word_enabled": bool(_config.vox_primer_word_enabled) if _config else False,
        "vox_primer_word": (_config.vox_primer_word if _config else "transmit"),
        "ptt_mode": (_config.ptt_mode if _config else "manual"),
        "ptt_serial_port": (_config.ptt_serial_port if _config else ""),
        "ptt_serial_line": (_config.ptt_serial_line if _config else "RTS"),
        "monitor_passthrough": bool(_config.monitor_passthrough) if _config else False,
        "attendance_enabled": bool(_config.attendance_enabled) if _config else False,
        "saved_phrases": _config.saved_phrases if _config else [],
        # Installed-plugin manifests — id, name, version, enabled, conflicts_with,
        # config_schema + current config values, tx_composition, and any load error.
        # Drives the admin Plugins manager (list, enable/disable, settings form).
        "plugins": plugin_registry.manifests(_config) if _config else [],
    }


def _safe_profile(profile: dict) -> dict:
    safe = {k: v for k, v in profile.items() if k not in SENSITIVE_PROFILE_FIELDS}
    safe["prefs"] = _effective_prefs(profile)
    return safe


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
                tail = format_tail_id(_config.callsign, _config.name)
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


async def _monitoring_beacon_pump() -> None:
    """Emit a periodic presence beacon when enabled and the channel is clear.

    Unlike _id_rule_pump (activity-gated), this fires on a fixed cadence. It is
    suppressed while NCS mode is active. When the transmission actually airs,
    `_tx_pump` resets the FCC ID timer (the phrase leads with the callsign, so it
    satisfies the ID); the reset happens on confirmed air, not here, so a beacon
    discarded for a busy channel never disarms the ID pump.
    """
    global _last_beacon_time
    while True:
        try:
            await asyncio.sleep(60)
            if _config is None:
                continue
            now = datetime.datetime.now(datetime.timezone.utc)
            elapsed = (now - _last_beacon_time).total_seconds() if _last_beacon_time else float("inf")
            ncs_active = _ncs_plugin.is_active() if _ncs_plugin is not None else False
            if not should_emit_beacon(
                enabled=_config.monitoring_beacon_enabled,
                ncs_active=ncs_active,
                channel_clear=_channel_clear,
                elapsed=elapsed,
                interval=_config.monitoring_beacon_interval,
            ):
                continue
            spoken = format_monitoring_call(_config.monitoring_beacon_text, _config.callsign)
            _last_beacon_time = now
            _log.info("Monitoring beacon: broadcasting presence announcement.")
            await _manager.broadcast({"type": "tx_status", "status": "transmitting"})
            await _tx_queue.put({"text": spoken, "_pre_formatted": True, "_beacon": True})
        except asyncio.CancelledError:
            break
        except Exception as exc:
            _log.error("_monitoring_beacon_pump error: %s", exc)


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


async def _family_reminder_tick() -> None:
    """One pass over configured check-in reminders vs. presence.

    Extracted from _family_reminder_pump so tests can invoke a single pass
    directly, without the sleep loop. Broadcasts family_presence only when
    at least one user's missed_checkin flag actually flipped. Tolerates a
    reminder for a user whose profile/presence record no longer exists —
    PresenceStore.get()/set_missed() both handle unknown user_ids gracefully.
    """
    if _family_store is None or _presence_store is None:
        return
    changed = False
    now_local = datetime.datetime.now().astimezone()
    for uid, reminder in _family_store.get_reminders().items():
        last_ok = _presence_store.get(uid)["last_ok"]
        missed = is_checkin_missed(reminder, last_ok, now_local)
        if _presence_store.set_missed(uid, missed):
            changed = True
    if changed:
        await _manager.broadcast(_build_family_presence_msg())


async def _family_reminder_pump() -> None:
    """Recompute missed-checkin status for every reminder every 30 seconds."""
    while True:
        try:
            await _family_reminder_tick()
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            _log.error("_family_reminder_pump error: %s", exc)


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
    global _config, _contacts_store, _users_store, _token_store, _presence_store, _family_store, _stt_worker, _synthesizer, _monitor, _plugin_ctx
    global _stt_out_queue, _tx_queue, _tts_event_queue, _background_tasks, _tx_abort_event
    global _audio_level, _radio_error, _channel_clear, _last_id_time, _has_transmitted, _last_beacon_time, _ncs_plugin
    global _level_window, _attendance, _spectro, _monitor_chunk_cb
    global _pending_stations, _auto_add_tasks, _event_loop, _audit_log
    global _calibration_capture

    # --- startup -----------------------------------------------------------
    # Surface the app's own INFO logs (TX playback, station ID, monitor state,
    # "server ready"). uvicorn configures only its own loggers, not the root —
    # so backend.* records otherwise hit Python's lastResort handler, which
    # emits at WARNING. Attach an INFO handler so operational info (including
    # TX-audio confirmation) is visible. Honour LOG_LEVEL if the operator sets it.
    _backend_logger = logging.getLogger("backend")
    _backend_logger.setLevel(
        getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    )
    if not _backend_logger.handlers:
        _h = logging.StreamHandler()
        _h.setFormatter(logging.Formatter("%(levelname)s:     %(name)s — %(message)s"))
        _backend_logger.addHandler(_h)
        # Keep propagate=True so pytest's caplog (a root handler) still captures
        # backend.* records. The handler above is what makes INFO visible in
        # production; the root logger has no handler, so there's no double-emit.
    _event_loop = asyncio.get_running_loop()
    _config = ServerConfig.load()
    _log.info("Config loaded: callsign=%s, port=%d", _config.callsign, _config.port)

    compute = detect_compute()
    _log.info("Compute backend: %s", compute.device_label)

    _contacts_store = ContactsStore(_config.contacts_file)
    _log.info("Contacts loaded: %d entries", len(_contacts_store.get_all()))

    _users_store = UsersStore(_config.users_file)
    _token_store = TokenStore(_config.tokens_file)
    _presence_store = PresenceStore(_config.presence_file)
    _family_store = FamilyStore(_config.family_file)
    purged = _token_store.purge_expired()
    if purged:
        _log.info("Purged %d expired session tokens.", purged)

    _audit_log = AuditLog()

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
    auth_routes.init(
        _users_store,
        _token_store,
        _config,
        audit_log=_audit_log,
        disconnect_user_fn=_manager.disconnect_user,
    )

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
    _last_beacon_time = None
    _level_window = collections.deque(maxlen=_LEVEL_WINDOW_SIZE)
    _attendance.clear()
    _stream_history.clear()
    _pending_stations = {}
    _auto_add_tasks = {}
    _calibration_capture = None
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

    _stt_worker = _make_stt_worker()
    _stt_worker.start()

    # Register plugins — must happen after _tx_queue and _config are initialised.
    from backend.plugins.ncs import NCSPlugin
    _ncs_plugin = NCSPlugin(
        broadcast_fn=_manager.broadcast,
        tx_queue=_tx_queue,
        config_getter=lambda: _config,
        channel_clear_fn=lambda: _channel_clear,
        contacts_getter=lambda: _contacts_store.get_all() if _contacts_store else [],
        add_contact_fn=lambda c: _contacts_store.add_contact(c) if _contacts_store else [],
        update_contact_fn=lambda cs, u, original_name=None: _contacts_store.update_contact(cs, u, original_name=original_name) if _contacts_store else [],
        broadcast_contacts_fn=lambda contacts: _manager.broadcast({"type": "contacts", "contacts": contacts}),
    )
    plugin_registry.register(_ncs_plugin)

    # External / 3rd-party plugins (incl. the MeshCore + Meshtastic examples) load
    # from the plugins directory AFTER built-in NCS, so the TX gate chain still
    # stops on NCS BREAK-BREAK before any mesh forward. Each plugin loads in
    # isolation; a bad one is recorded as a load error, never crashing startup.
    from backend.plugins.context import PluginContext

    async def _enqueue_tx(payload: dict) -> None:
        await _tx_queue.put(payload)

    _plugin_ctx = PluginContext(
        broadcast=_manager.broadcast,
        enqueue_tx=_enqueue_tx,
        get_config=lambda: _config,
        channel_clear=lambda: _channel_clear,
        data_dir=_PLUGINS_DIR.parent,
        logger=logging.getLogger("hearthwave.plugin"),
    )
    await plugin_loader.discover_and_load(_PLUGINS_DIR, _plugin_ctx, plugin_registry)

    # Gate active hooks on each plugin's enabled state (read live from config).
    plugin_registry.set_config_getter(lambda: _config)

    # Let plugins open connections / start pollers from the loaded config.
    await plugin_registry.dispatch_config_changed(_config)

    _synthesizer = TTSSynthesizer(
        out_queue=_tts_event_queue,
        compute_backend=compute,
        output_device=_config.output_device if _config.output_device != -1 else None,
        tx_conditioning=_config.tx_conditioning,
    )

    _background_tasks = {
        asyncio.create_task(_rx_pump(), name="rx-pump"),
        asyncio.create_task(_tx_pump(), name="tx-pump"),
        asyncio.create_task(_status_pump(), name="status-pump"),
        asyncio.create_task(_id_rule_pump(), name="id-rule-pump"),
        asyncio.create_task(_monitoring_beacon_pump(), name="monitoring-beacon-pump"),
        asyncio.create_task(_spectro.run(), name="spectro-pump"),
        asyncio.create_task(_online_status_pump(), name="online-status-pump"),
        asyncio.create_task(_voices_watcher_pump(), name="voices-watcher"),
        asyncio.create_task(_family_reminder_pump(), name="family-reminder-pump"),
    }
    _log.info("Hearthwave server ready.")

    yield

    # --- shutdown ----------------------------------------------------------
    _log.info("Shutting down Hearthwave server...")
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
    _log.info("Hearthwave server stopped.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Hearthwave", lifespan=_lifespan)
app.include_router(_auth_router, prefix="/auth")


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict:
    return {"ok": True, "version": __version__}


# ---------------------------------------------------------------------------
# Plugin install / reload / uninstall (admin only).
#
# Plugins run with full server privileges — these endpoints are admin-gated and a
# trust warning is shown in the UI. Newly installed plugins load live (hot-reload);
# a server restart is always a safe fallback.
# ---------------------------------------------------------------------------

def _safe_plugin_id(raw: str) -> str:
    """Sanitise a plugin id to a single safe path segment, or 400."""
    import re
    pid = re.sub(r"[^A-Za-z0-9_-]", "", raw or "")
    if not pid:
        raise HTTPException(status_code=400, detail="Invalid plugin id")
    return pid


def _plugin_load_error(plugin_id: str) -> str | None:
    for m in plugin_registry.manifests(_config):
        if m["id"] == plugin_id:
            return m.get("error")
    return None


@app.post("/plugins/install")
async def install_plugin(
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
) -> dict:
    auth_routes._require_admin(authorization)
    if _plugin_ctx is None or _config is None:
        raise HTTPException(status_code=503, detail="Plugins not initialised")

    import io
    import shutil
    import tempfile
    import zipfile

    data = await file.read()
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Not a valid .zip archive")

    # Zip-slip guard: reject absolute paths or parent-directory escapes.
    for name in archive.namelist():
        if name.startswith("/") or ".." in Path(name).parts:
            raise HTTPException(status_code=400, detail="Unsafe path in archive")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        archive.extractall(tmp_path)
        plugin_files = list(tmp_path.rglob("plugin.py"))
        if not plugin_files:
            raise HTTPException(status_code=400, detail="Archive contains no plugin.py")
        # Shallowest plugin.py wins; its directory is the plugin package root.
        src = min(plugin_files, key=lambda p: len(p.relative_to(tmp_path).parts)).parent
        raw_id = (Path(file.filename or "plugin").stem if src == tmp_path else src.name)
        plugin_id = _safe_plugin_id(raw_id)
        target = _PLUGINS_DIR / plugin_id
        # Replace any existing install of the same id (unload first if loaded).
        await plugin_loader.unload_plugin(plugin_id, plugin_registry)
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        _PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, target)

    await plugin_loader.reload_plugin(target, _plugin_ctx, plugin_registry)
    await plugin_registry.dispatch_config_changed(_config)
    await _manager.broadcast(_build_status())
    error = _plugin_load_error(plugin_id)
    if error:
        raise HTTPException(status_code=400, detail=f"Plugin installed but failed to load: {error}")
    return {"ok": True, "id": plugin_id}


@app.post("/plugins/{plugin_id}/reload")
async def reload_plugin_endpoint(
    plugin_id: str, authorization: str | None = Header(default=None)
) -> dict:
    auth_routes._require_admin(authorization)
    if _plugin_ctx is None or _config is None:
        raise HTTPException(status_code=503, detail="Plugins not initialised")
    pid = _safe_plugin_id(plugin_id)
    plugin_dir = _PLUGINS_DIR / pid
    if not (plugin_dir / "plugin.py").is_file():
        raise HTTPException(status_code=404, detail="Plugin not found")
    await plugin_loader.reload_plugin(plugin_dir, _plugin_ctx, plugin_registry)
    await plugin_registry.dispatch_config_changed(_config)
    await _manager.broadcast(_build_status())
    error = _plugin_load_error(pid)
    return {"ok": error is None, "id": pid, "error": error}


@app.delete("/plugins/{plugin_id}")
async def uninstall_plugin_endpoint(
    plugin_id: str, authorization: str | None = Header(default=None)
) -> dict:
    auth_routes._require_admin(authorization)
    pid = _safe_plugin_id(plugin_id)
    await plugin_loader.unload_plugin(pid, plugin_registry)
    import shutil
    plugin_dir = _PLUGINS_DIR / pid
    if plugin_dir.is_dir():
        shutil.rmtree(plugin_dir, ignore_errors=True)
    if _config is not None:
        await _manager.broadcast(_build_status())
    return {"ok": True, "id": pid}


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
    if "ncs_preamble_text" in data:
        _config["ncs_preamble_text"] = str(data["ncs_preamble_text"])
    if "ncs_closing_text" in data:
        _config["ncs_closing_text"] = str(data["ncs_closing_text"])
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
        _stt_worker = _make_stt_worker()
        _stt_worker.start()


def _coerce_plugin_value(spec: dict, val):
    """Coerce a plugin config value to its declared schema type, clamping numbers
    and validating selects. Returns None to skip an invalid value."""
    field_type = spec.get("type")
    if field_type == "bool":
        return bool(val)
    if field_type == "number":
        try:
            num = float(val)
        except (TypeError, ValueError):
            return None
        if spec.get("minimum") is not None:
            num = max(float(spec["minimum"]), num)
        if spec.get("maximum") is not None:
            num = min(float(spec["maximum"]), num)
        default = spec.get("default")
        # Keep integers integral (baud, channel idx) per the field's default type.
        if isinstance(default, int) and not isinstance(default, bool):
            return int(num)
        return num
    if field_type == "select":
        text = str(val)
        allowed = {opt[0] for opt in spec.get("options", []) if opt}
        return text if (not allowed or text in allowed) else None
    return str(val)[:512]


async def _ws_handle_set_server_config(ws: WebSocket, data: dict, state: "ConnectionState") -> None:
    """Handle technical server settings that require STT worker restart on change."""
    global _stt_worker
    if _config is None:
        await _manager.send_to(ws, {"type": "error", "detail": "Config not loaded."})
        return

    stt_restart_needed = False

    # Snapshot plugin enabled-state so we can detect which plugins were just
    # turned on and enforce mutual exclusion (resolve_conflicts) after merging.
    _plugins_enabled_before = {m["id"]: m["enabled"] for m in plugin_registry.manifests(_config)}

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
        if model in VALID_WHISPER_MODELS and model != _config.whisper_model:
            _config["whisper_model"] = model
            stt_restart_needed = True

    if "whisper_model_final" in data:
        model = str(data["whisper_model_final"]).strip()
        # Empty string disables the second pass.
        if (model == "" or model in VALID_FINAL_MODELS) and model != _config.whisper_model_final:
            _config["whisper_model_final"] = model
            stt_restart_needed = True

    if "stt_gain_mode" in data:
        mode = str(data["stt_gain_mode"]).strip().lower()
        if mode in GAIN_MODES and mode != _config.stt_gain_mode:
            _config["stt_gain_mode"] = mode
            stt_restart_needed = True

    if "stt_noise_profile" in data:
        enabled = bool(data["stt_noise_profile"])
        if enabled != _config.stt_noise_profile:
            _config["stt_noise_profile"] = enabled
            stt_restart_needed = True

    if "tx_conditioning" in data:
        enabled = bool(data["tx_conditioning"])
        _config["tx_conditioning"] = enabled
        if _synthesizer is not None:
            _synthesizer.tx_conditioning = enabled

    if "vox_primer_enabled" in data:
        _config["vox_primer_enabled"] = bool(data["vox_primer_enabled"])

    if "vox_primer_ms" in data:
        try:
            ms = int(data["vox_primer_ms"])
            _config["vox_primer_ms"] = max(0, min(2000, ms))
        except (TypeError, ValueError):
            pass

    if "vox_primer_word_enabled" in data:
        _config["vox_primer_word_enabled"] = bool(data["vox_primer_word_enabled"])

    if "vox_primer_word" in data and isinstance(data["vox_primer_word"], str):
        _config["vox_primer_word"] = data["vox_primer_word"].strip()[:64]

    if "stt_debug_capture" in data:
        enabled = bool(data["stt_debug_capture"])
        if enabled != _config.stt_debug_capture:
            _config["stt_debug_capture"] = enabled
            stt_restart_needed = True

    if "squelch_adaptive" in data:
        adaptive = bool(data["squelch_adaptive"])
        if adaptive != _config.squelch_adaptive:
            _config["squelch_adaptive"] = adaptive
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

    if "saved_phrases" in data:
        phrases = data["saved_phrases"]
        if isinstance(phrases, list) and all(isinstance(p, str) for p in phrases):
            _config["saved_phrases"] = [
                p.strip()[:120] for p in phrases[:50] if p.strip()
            ]
            if _stt_worker is not None:
                _rebuild_stt_vocabulary()

    # Plugin settings — generic, namespaced. The frontend sends
    #   data["plugins"] = {plugin_id: {"enabled": bool, "<field>": value, ...}}
    # Each value is coerced/clamped against that plugin's declared config_schema;
    # unknown keys are ignored so clients can't write arbitrary config.
    incoming_plugins = data.get("plugins")
    if isinstance(incoming_plugins, dict):
        schema_by_id = {
            m["id"]: {f["key"]: f for f in m["config_schema"]}
            for m in plugin_registry.manifests(_config)
        }
        for pid, values in incoming_plugins.items():
            if not isinstance(values, dict) or pid not in schema_by_id:
                continue
            fields = schema_by_id[pid]
            clean: dict = {}
            for key, val in values.items():
                if key == "enabled":
                    clean["enabled"] = bool(val)
                    continue
                spec = fields.get(key)
                if spec is None:
                    continue
                clean[key] = _coerce_plugin_value(spec, val)
            clean = {k: v for k, v in clean.items() if v is not None}
            if clean:
                _config.set_plugin_config(pid, clean)

    # Enforce mutual exclusion: any plugin just turned on disables its conflicts.
    _enabled_after = {m["id"]: m["enabled"] for m in plugin_registry.manifests(_config)}
    _newly_enabled = [
        pid for pid, on in _enabled_after.items()
        if on and not _plugins_enabled_before.get(pid)
    ]
    plugin_registry.resolve_conflicts(_config, _newly_enabled)

    _config.save()
    await _manager.broadcast(_build_status())
    # Let plugins react to the new config (mesh bridges connect/disconnect here).
    await plugin_registry.dispatch_config_changed(_config)

    if stt_restart_needed and _stt_worker is not None and _stt_listening:
        _stt_worker.stop()
        await _stt_worker.join()
        _stt_worker = _make_stt_worker()
        _stt_worker.start()


# ---------------------------------------------------------------------------
# STT calibration wizard
# ---------------------------------------------------------------------------

async def _ws_handle_calibration_start(ws: WebSocket, state: "ConnectionState") -> None:
    """Begin buffering raw RX audio for a calibration reading. Requires a
    listening STT worker — the capture taps the same raw-chunk fanout it
    already feeds (_audio_chunk_fanout)."""
    global _calibration_capture
    if _stt_worker is None or not _stt_listening:
        await _manager.send_to(ws, {
            "type": "calibration_error",
            "detail": "STT must be listening to run calibration.",
        })
        return
    _calibration_capture = CalibrationCapture(sample_rate=STTWorker.SAMPLE_RATE)
    _calibration_capture.start()
    await _manager.send_to(ws, {"type": "calibration_started"})


async def _run_calibration_sweep(ws: WebSocket, audio, sample_rate: int) -> None:
    """Sweep gain mode / noise profile / Whisper model against the captured
    audio and report results back to the requesting client. Runs off the
    event loop thread (model loading + transcription are blocking); progress
    callbacks are marshalled back via call_soon_threadsafe."""
    # Sweep only models staged on disk — faster-whisper treats a missing
    # local path as a Hugging Face repo id and tries to download it, and
    # Hearthwave never downloads models at runtime.
    models = [
        m for m in sorted(VALID_WHISPER_MODELS)
        if (STTWorker._MODELS_DIR / m).is_dir()
    ]
    if not models:
        await _manager.send_to(ws, {
            "type": "calibration_error",
            "detail": (
                "No Whisper models found in Models/STT. Run "
                "'python bootstrap_models.py' on an internet-connected "
                "machine, then copy Models/ here."
            ),
        })
        return
    skipped = sorted(VALID_WHISPER_MODELS - set(models))
    if skipped:
        _log.info(
            "Calibration sweep skipping models not staged on disk: %s",
            ", ".join(skipped),
        )
    vad_threshold = _config.vad_threshold if _config is not None else 0.5
    vad_model = await asyncio.to_thread(load_vad_model)

    def transcriber_loader(model: str):
        return WhisperTranscriber.load(str(STTWorker._MODELS_DIR / model))

    def vad_iterator_factory():
        return make_vad_iterator(vad_model, sample_rate=sample_rate, threshold=vad_threshold)

    loop = asyncio.get_running_loop()

    def progress_cb(entry: dict) -> None:
        asyncio.run_coroutine_threadsafe(
            _manager.send_to(ws, {"type": "calibration_progress", **entry}), loop,
        )

    try:
        results = await asyncio.to_thread(
            run_sweep, audio,
            models=models,
            transcriber_loader=transcriber_loader,
            vad_iterator_factory=vad_iterator_factory,
            progress_cb=progress_cb,
        )
    except Exception as exc:
        _log.error("Calibration sweep failed: %s", exc)
        await _manager.send_to(ws, {"type": "calibration_error", "detail": str(exc)})
        return

    await _manager.send_to(ws, {
        "type": "calibration_result",
        "results": results,
        "recommended": results[0] if results else None,
    })


async def _ws_handle_calibration_stop(ws: WebSocket, state: "ConnectionState") -> None:
    """Stop capture and, if enough audio was heard, run the sweep in the
    background — results stream back as calibration_progress/_result."""
    global _calibration_capture
    if _calibration_capture is None:
        await _manager.send_to(ws, {
            "type": "calibration_error", "detail": "No calibration in progress.",
        })
        return
    audio = _calibration_capture.stop()
    _calibration_capture = None
    min_samples = int(2.0 * STTWorker.SAMPLE_RATE)
    if audio.size < min_samples:
        await _manager.send_to(ws, {
            "type": "calibration_error",
            "detail": "No audio captured — key up and read the passage before stopping.",
        })
        return
    task = asyncio.create_task(_run_calibration_sweep(ws, audio, STTWorker.SAMPLE_RATE))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def _ws_handle_calibration_apply(ws: WebSocket, data: dict, state: "ConnectionState") -> None:
    """Apply a chosen sweep combo by delegating to the same validated
    set_server_config path every other STT setting goes through."""
    payload: dict = {}
    if "whisper_model" in data:
        payload["whisper_model"] = data["whisper_model"]
    if "gain_mode" in data:
        payload["stt_gain_mode"] = data["gain_mode"]
    if "noise_profile" in data:
        payload["stt_noise_profile"] = data["noise_profile"]
    await _ws_handle_set_server_config(ws, payload, state)
    await _manager.send_to(ws, {"type": "calibration_applied"})


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


# Kid-role connections may only self-serve cosmetic prefs via save_user_prefs;
# filter_profanity/ui_level/listen_only are server-enforced (see _effective_prefs).
KID_ALLOWED_PREF_KEYS = {"dark_mode", "font_scale", "high_contrast"}


def _is_kid(state: "ConnectionState") -> bool:
    return getattr(state, "role", "adult") == "kid"


async def _enqueue_family_tts(text: str) -> None:
    """Enqueue a pre-formatted family_status phrase for TTS/PTT.

    Mirrors the NCS spot-report/net-script enqueue idiom: operator-initiated
    (keys even over a busy channel), pre-formatted (no further TTS templating).
    """
    await _tx_queue.put({"text": text, "_pre_formatted": True, "_operator_initiated": True})


async def _broadcast_family_chat(text: str, display_name: str) -> None:
    """Broadcast a family_status phrase to the shared chat log.

    Mirrors the chat_message idiom: broadcast_rx + StreamHistory.record_rx
    raw/filtered split, so each client's own filter_profanity pref applies.
    """
    chat_echo_base = {
        "type": "chat_echo",
        "ts": utc_now_iso(),
        "display_name": display_name,
        "operator": "",
        "callsign": "",
    }
    await _manager.broadcast_rx(chat_echo_base, text, mask_profanity(text))
    _stream_history.record_rx(chat_echo_base, text, mask_profanity(text))


def _validate_quick_messages(value) -> list[str] | None:
    """Return sanitized list or None if invalid."""
    if not isinstance(value, list) or not (1 <= len(value) <= 20):
        return None
    out = []
    for item in value:
        if not isinstance(item, str):
            return None
        item = item.strip()
        if not (1 <= len(item) <= 200) or any(ord(c) < 32 for c in item):
            return None
        out.append(item)
    return out


@app.websocket("/ws")
async def websocket_endpoint(
    ws: WebSocket,
    ticket: str | None = Query(default=None),
    token:  str | None = Query(default=None),
) -> None:
    global _stt_worker, _stt_listening

    # Prefer a one-time ticket (keeps long-lived token out of access logs).
    # Fall back to raw token for backward compatibility during rolling deploys.
    if _token_store and ticket:
        user_id = _token_store.validate_ticket(ticket)
    elif _token_store and token:
        user_id = _token_store.validate(token)
    else:
        user_id = None

    profile = _users_store.get(user_id) if (_users_store and user_id) else None
    if not user_id or not profile:
        await ws.accept()
        await ws.close(code=4001)
        return

    await ws.accept()
    role = profile.get("role") or ("admin" if profile.get("is_admin") else "adult")
    conn_prefs = {**DEFAULT_PREFS, **profile.get("prefs", {})}
    if role == "kid":
        conn_prefs["filter_profanity"] = True
        conn_prefs["ui_level"] = "simple"
        conn_prefs["listen_only"] = False
    state = ConnectionState(
        user_id=user_id,
        is_admin=bool(profile.get("is_admin", False)),
        prefs=conn_prefs,
        role=role,
    )
    # Snapshot the stream backfill *before* registering the socket (no await in
    # between, so no interleaving): anything broadcast after `add` reaches this
    # client live only, anything before is in the snapshot only — never both.
    history_msgs = _stream_history.render_for(state.prefs.get("filter_profanity", True))
    _manager.add(ws, state)
    client_ip = _extract_ip(ws.headers, str(ws.client.host) if ws.client else "unknown")
    _log.info("Client connected: %s (user=%s)", ws.client, user_id)
    if _audit_log:
        _audit_log.log("ws_connect", user_id=user_id, ip=client_ip)

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
    await _manager.send_to(ws, _build_family_presence_msg())
    if not _is_kid(state):
        await _manager.send_to(ws, _build_family_reminders_msg())
    await _manager.send_to(ws, {"type": "voices_list", "voices": _list_voices()})
    # Backfill the shared message stream accumulated since the last clear
    # (snapshotted above, before this socket joined the broadcast set).
    await _manager.send_to(ws, {"type": "chat_history", "messages": history_msgs})
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

                if _is_kid(state):
                    presets = state.prefs.get("quick_messages") or []
                    if (data.get("text") or "").strip() not in presets:
                        await _manager.send_to(ws, {"type": "error", "detail": "TX not allowed for this account"})
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
                # `voice_as` lets a client transmit on behalf of a named
                # operator (the [tx] [name] chat convention): voice the message
                # in that user's profile voice/speed.  Absent → voice as the
                # sending connection's own profile (legacy behavior).
                voice_as = (data.get("voice_as") or "").strip()
                if voice_as:
                    tx_voice, tx_scale = _resolve_tx_voice(voice_as)
                    tx_display = voice_as
                else:
                    tx_voice = state.prefs.get("tts_voice") or None
                    tx_scale = state.prefs.get("tts_length_scale") or None
                    tx_display = _tx_sender_display
                tx_payload = await plugin_registry.dispatch_tx_pre_queue({
                    **data,
                    "_filter_profanity": state.prefs.get("filter_profanity", True),
                    "_voice_name": tx_voice,
                    "_length_scale": tx_scale,
                    "_display_name": tx_display,
                    "_user_id": state.user_id,
                    # Operator pressed Transmit — overrides the channel-busy squelch.
                    "_operator_initiated": True,
                })
                if tx_payload is None:
                    continue  # TX blocked by a plugin
                await _tx_queue.put(tx_payload)
                await _manager.broadcast({"type": "tx_status", "status": "transmitting"})
                if _presence_store is not None:
                    _presence_store.touch_heard(state.user_id, utc_now_iso())
                    await _manager.broadcast(_build_family_presence_msg())

            elif msg_type == "chat_message":
                # Chat-only: shared to all operators in the log but never keyed
                # over the radio (no synthesis, no PTT, no STT pause).  Only
                # [tx]-prefixed lines (sent as tx_message) reach the air.
                text = (data.get("text") or "").strip()
                if not text:
                    continue
                # Listen-only is fully silent — no chat either.
                if await _check_listen_only(ws, state):
                    continue
                sender_display = (
                    (_users_store.get_public_one(state.user_id) or {}).get("display_name") or ""
                ) if _users_store else ""
                chat_echo_base = {
                    "type": "chat_echo",
                    "ts": utc_now_iso(),
                    "display_name": sender_display,
                    "operator": data.get("operator") or "",
                    "callsign": data.get("callsign") or "",
                }
                await _manager.broadcast_rx(
                    chat_echo_base,
                    text,
                    mask_profanity(text),
                )
                _stream_history.record_rx(chat_echo_base, text, mask_profanity(text))

            elif msg_type == "family_status":
                # "I'm OK" check-in — a safety feature, so kids CAN send this
                # (no _is_kid gate) and listen-only users still get recorded;
                # listen-only only skips the TTS/PTT leg, not the chat entry,
                # the presence update, or the broadcast.
                if data.get("status") != "ok":
                    await _manager.send_to(ws, {"type": "error", "detail": "Unknown family status"})
                    continue
                profile_rec = (
                    (_users_store.get_public_one(state.user_id) or {}) if _users_store else {}
                )
                name = (profile_rec.get("operator_name") or profile_rec.get("display_name") or "Operator").strip()
                text = f"Family status: {name} is okay."
                if not state.prefs.get("listen_only", False):
                    await _enqueue_family_tts(text)
                await _broadcast_family_chat(text, profile_rec.get("display_name") or "")
                if _presence_store is not None:
                    _presence_store.mark_ok(state.user_id, utc_now_iso())
                    await _manager.broadcast(_build_family_presence_msg())

            elif msg_type == "set_family_reminder":
                if not state.is_admin:
                    await _manager.send_to(ws, {"type": "error", "detail": "Admin access required."})
                    continue
                if _family_store is None:
                    continue
                target_user_id = data.get("user_id", "")
                if not target_user_id:
                    await _manager.send_to(ws, {"type": "error", "detail": "user_id is required."})
                    continue
                try:
                    _family_store.set_reminder(
                        target_user_id, data.get("time"), bool(data.get("enabled", False))
                    )
                except ValueError as exc:
                    await _manager.send_to(ws, {"type": "error", "detail": str(exc)})
                    continue
                await _manager.broadcast(_build_family_reminders_msg())

            elif msg_type == "get_family_reminders":
                if _is_kid(state):
                    await _manager.send_to(ws, {"type": "error", "detail": "Check-in reminders not available for this account."})
                    continue
                await _manager.send_to(ws, _build_family_reminders_msg())

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
                    _rebuild_stt_vocabulary()
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
                    _rebuild_stt_vocabulary()
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

            elif msg_type == "clear_chat":
                # Admin-only, and global: wipe the shared stream for everyone.
                if not state.is_admin:
                    await _manager.send_to(ws, {"type": "error", "detail": "Admin access required."})
                    continue
                _stream_history.clear()
                await _manager.broadcast({"type": "chat_cleared"})
                if _audit_log:
                    _audit_log.log("admin_action", user_id=state.user_id, ip=client_ip, detail="clear_chat")

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
                    "_operator_initiated": True,
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
                    data.get("text") or "Hearthwave voice test. How does this sound?"
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
                    "_user_id": state.user_id,
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
                        _rebuild_stt_vocabulary()
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
                    _rebuild_stt_vocabulary()
                except KeyError as exc:
                    await _manager.send_to(ws, {"type": "error", "detail": str(exc)})

            elif msg_type == "rescan_vocabulary":
                count = _rebuild_stt_vocabulary()
                contacts = _contacts_store.get_all() if _contacts_store else []
                max_cs = _config.stt_vocab_max_callsigns if _config else 100
                cs_count = min(len(ordered_callsigns(contacts)), max_cs)
                await _manager.send_to(ws, {
                    "type": "vocabulary_rescanned",
                    "term_count": count,
                    "callsign_count": cs_count,
                })

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
                devices += await _enumerate_devices("input")
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
                if not state.is_admin:
                    await _manager.send_to(ws, {"type": "error", "detail": "Admin only."})
                    continue
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
                _stt_worker = _make_stt_worker()
                _stt_worker.start()
                await _manager.broadcast(_build_status())

            elif msg_type == "list_output_devices":
                devices = [{"label": "System Default (speaker)", "id": -1}]
                devices += await _enumerate_devices("output")
                await _manager.send_to(ws, {
                    "type": "output_devices",
                    "devices": devices,
                    "current_output_device": _config.output_device if _config else -1,
                })

            elif msg_type == "set_output_device":
                if not state.is_admin:
                    await _manager.send_to(ws, {"type": "error", "detail": "Admin only."})
                    continue
                if _config is None:
                    await _manager.send_to(ws, {"type": "error", "detail": "Config not loaded."})
                    continue
                new_device = data.get("output_device", -1)
                _config["output_device"] = new_device
                _config.save()
                # Keep the synthesizer's cached device in sync (used by its own
                # internal playback path).  TX playback reads _config at send time.
                if _synthesizer is not None:
                    _synthesizer.output_device = new_device if new_device != -1 else None
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
                if "fuzzy_callsign_rewrite" in data:
                    _config["fuzzy_callsign_rewrite"] = bool(data["fuzzy_callsign_rewrite"])
                if "fuzzy_callsign" in data or "fuzzy_callsign_rewrite" in data:
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

            elif msg_type == "calibration_get_text":
                if not state.is_admin:
                    await _manager.send_to(ws, {"type": "error", "detail": "Admin access required."})
                    continue
                await _manager.send_to(ws, {"type": "calibration_text", "text": PREAMBLE_TEXT})

            elif msg_type == "calibration_start":
                if not state.is_admin:
                    await _manager.send_to(ws, {"type": "error", "detail": "Admin access required."})
                    continue
                await _ws_handle_calibration_start(ws, state)

            elif msg_type == "calibration_stop":
                if not state.is_admin:
                    await _manager.send_to(ws, {"type": "error", "detail": "Admin access required."})
                    continue
                await _ws_handle_calibration_stop(ws, state)

            elif msg_type == "calibration_apply":
                if not state.is_admin:
                    await _manager.send_to(ws, {"type": "error", "detail": "Admin access required."})
                    continue
                await _ws_handle_calibration_apply(ws, data, state)

            elif msg_type == "save_user_prefs":
                if _users_store is None:
                    continue
                allowed = {"dark_mode", "filter_profanity", "listen_only",
                           "read_aloud", "notifications_enabled", "spectro_colormap", "spectro_time_window_s",
                           "tts_voice", "tts_length_scale", "aac_mode", "aac_grid",
                           "ui_level", "font_scale", "high_contrast", "quick_messages"}
                updates = {k: v for k, v in data.get("prefs", data).items() if k in allowed}
                if _is_kid(state):
                    updates = {k: v for k, v in updates.items() if k in KID_ALLOWED_PREF_KEYS}
                grid = updates.get("aac_grid")
                if grid is not None and (
                    not isinstance(grid, dict) or len(json.dumps(grid)) > 65536
                ):
                    await _manager.send_to(ws, {"type": "error", "detail": "Invalid aac_grid (must be an object under 64 KB)."})
                    updates.pop("aac_grid")
                if "ui_level" in updates and updates["ui_level"] not in ("simple", "operator"):
                    updates.pop("ui_level")
                if "font_scale" in updates and updates["font_scale"] not in (1, 1.25, 1.5, 2):
                    updates.pop("font_scale")
                if "high_contrast" in updates and not isinstance(updates["high_contrast"], bool):
                    updates.pop("high_contrast")
                if "quick_messages" in updates:
                    qm = _validate_quick_messages(updates["quick_messages"])
                    if qm is None:
                        updates.pop("quick_messages")
                    else:
                        updates["quick_messages"] = qm
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
                if target_id == state.user_id and "is_admin" in updates and not updates["is_admin"]:
                    await _manager.send_to(ws, {"type": "error", "detail": "Cannot remove your own admin access."})
                    continue
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
                except (KeyError, ValueError) as exc:
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
                role = data.get("role")
                if role is not None and role not in ROLES:
                    await _manager.send_to(ws, {"type": "error", "detail": f"Unknown role: {role!r}."})
                    continue
                _users_store.create(
                    display_name=display_name,
                    password=password,
                    avatar_emoji=(data.get("avatar_emoji") or "👤"),
                    operator_name=(data.get("operator_name") or display_name),
                    callsign=(data.get("callsign") or ""),
                    location=(data.get("location") or ""),
                    is_admin=bool(data.get("is_admin", False)),
                    role=role,
                )
                await _manager.broadcast({
                    "type": "profiles",
                    "profiles": _users_store.get_public(),
                })

            elif msg_type == "set_role":
                if not state.is_admin:
                    await _manager.send_to(ws, {"type": "error", "detail": "Admin access required."})
                    continue
                if _users_store is None:
                    continue
                target_role_id = data.get("user_id", "")
                if target_role_id == state.user_id and data.get("role") != "admin":
                    await _manager.send_to(ws, {"type": "error", "detail": "Cannot change your own role away from admin."})
                    continue
                try:
                    updated = _users_store.set_role(target_role_id, data.get("role"))
                except ValueError:
                    updated = None
                if updated is None:
                    await _manager.send_to(ws, {"type": "error", "detail": "Unknown user or role."})
                    continue
                await _manager.broadcast({
                    "type": "profiles",
                    "profiles": _users_store.get_public(),
                })

            elif msg_type == "set_user_quick_messages":
                if not state.is_admin:
                    await _manager.send_to(ws, {"type": "error", "detail": "Admin access required."})
                    continue
                if _users_store is None:
                    continue
                qm = _validate_quick_messages(data.get("quick_messages"))
                if qm is None:
                    await _manager.send_to(ws, {"type": "error", "detail": "Invalid quick_messages (must be 1-20 non-empty strings, each 1-200 chars)."})
                    continue
                target_user_id = data.get("user_id", "")
                target_profile = _users_store.get(target_user_id)
                if (
                    target_profile is not None
                    and target_profile.get("role") == "kid"
                    and any("{" in msg or "}" in msg for msg in qm)
                ):
                    await _manager.send_to(ws, {"type": "error", "detail": "Kid presets cannot contain placeholders"})
                    continue
                try:
                    updated = _users_store.update_prefs(target_user_id, {"quick_messages": qm})
                except KeyError:
                    updated = None
                if updated is None:
                    await _manager.send_to(ws, {"type": "error", "detail": "Unknown user."})
                    continue
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
                # Intentionally ungated (no admin check): the roster is meant to be
                # visible to every connected user, including the Family presence
                # board. get_public() routes prefs through effective_prefs(), so
                # kid pref locks still apply here.
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
        if _audit_log:
            _audit_log.log("ws_disconnect", user_id=user_id, ip=client_ip)
