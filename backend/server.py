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
    list_input_devices — {"type": "list_input_devices"}
    set_input_device  — {"type": "set_input_device", "input_device": "system_monitor"|int|-1,
                          "system_monitor_sink"?: str}
    set_config        — {"type": "set_config", "filter_profanity"?: bool,
                          "fuzzy_callsign"?: bool}
    set_spectro_config — {"type": "set_spectro_config", "colormap"?: str,
                          "freq_range"?: "voice" | "full",
                          "time_window_s"?: int}
    set_admin_config  — {"type": "set_admin_config", "callsign"?: str, "name"?: str,
                          "location"?: str, "gemini_api_key"?: str, "journals_dir"?: str}
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
                          "partial": bool}
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
    error             — {"type": "error", "detail": str}
"""
from __future__ import annotations

import asyncio
import collections
import dataclasses
import datetime
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect

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
)
from backend.hw_detect import detect as detect_compute
from backend.net.online import invalidate as _invalidate_online
from backend.net.online import is_online, is_online_cached
from backend import auth_routes
from backend.auth_routes import router as _auth_router
from backend.persistence.attendance import AttendanceTracker, build_attendance_rows
from backend.persistence.contacts import (
    ContactsStore,
    known_callsigns,
    normalize_callsign,
)
from backend.persistence.journal import delete_journal, load_journals, publish_journal, save_journal
from backend.persistence.tokens import TokenStore
from backend.persistence.users import DEFAULT_PREFS, SENSITIVE_PROFILE_FIELDS, UsersStore
from backend.ptt.factory import make_ptt
from backend.stt.worker import STTWorker
from backend.text.callsigns import detect_callsigns, fuzzy_match_callsign, spell_digits_in_callsigns
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

_config: ServerConfig | None = None
_contacts_store: ContactsStore | None = None
_users_store: UsersStore | None = None
_token_store: TokenStore | None = None
_stt_worker: STTWorker | None = None
_synthesizer: TTSSynthesizer | None = None
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
    global _vad_active
    while True:
        try:
            result = await _stt_out_queue.get()
            utterance_id = result.get("utterance_id")
            partial = result.get("partial", False)
            _vad_active = bool(partial)

            raw_text = result.get("text", "")
            filtered_text = mask_profanity(raw_text)

            await _manager.broadcast_rx(
                {"type": "rx_message", "utterance_id": utterance_id, "partial": partial},
                raw_text=raw_text,
                filtered_text=filtered_text,
            )

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
    global _last_id_time, _has_transmitted
    from backend.ptt.manual import ManualPTT

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
            voice_name = payload.get("_voice_name") or _config.voice
            if not voice_name:
                _log.warning("No TTS voice configured; skipping TX synthesis.")
                if not is_preview:
                    await _manager.broadcast({"type": "tx_status", "status": "idle"})
                continue

            raw_text = payload.get("text", "")
            now = datetime.datetime.now(datetime.timezone.utc)

            if payload.get("_standalone_id"):
                # "This is" button — NATO-phonetic station ID, resets ID timer.
                my_call = payload.get("callsign") or _config.callsign
                my_name = payload.get("operator") or _config.name
                my_loc  = payload.get("location") if payload.get("location") is not None else _config.location
                text, _last_id_time = format_standalone_id(my_call, my_name, my_loc, now)
                text = spell_digits_in_callsigns(text)
                _has_transmitted = True

            elif payload.get("_pre_formatted") or is_preview:
                # Pre-formatted text (auto-ID pump, voice preview) — no processing.
                text = raw_text

            else:
                # Normal outgoing message: expand shorthand → mask profanity →
                # FCC-format with callsign preface → digit-isolate callsigns for TTS.
                processed = expand_tty_abbreviations(raw_text)
                if payload.get("_filter_profanity", True):
                    processed = mask_profanity(processed)
                text, _last_id_time = format_outgoing_message(
                    processed,
                    target_call=payload.get("target_call") or "ALL",
                    target_name=payload.get("target_name") or "",
                    my_call=payload.get("callsign") or _config.callsign,
                    my_name=payload.get("operator") or _config.name,
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

            voice = await asyncio.get_running_loop().run_in_executor(
                None, _load_voice, voice_name
            )
            # Voice preview uses ManualPTT so no radio keying occurs.
            ptt = ManualPTT() if is_preview else make_ptt(_config)
            length_scale = _config.tts_length_scale

            await _synthesizer.synthesize(voice, text, ptt, length_scale=length_scale)

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
            if not is_preview and _stt_worker is not None and _stt_listening:
                _stt_worker.resume()
            if not is_preview:
                await _manager.broadcast({"type": "tx_status", "status": "idle"})


# ---------------------------------------------------------------------------
# Voice helpers
# ---------------------------------------------------------------------------

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
        "gemini_api_key_set": bool(_config and _config.gemini_api_key),
        "journals_dir": str(_config.journals_dir) if _config else "/data/journals",
        "input_device": (_config.input_device if _config else -1),
        "system_monitor_sink": (_config.system_monitor_sink if _config else ""),
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
    global _config, _contacts_store, _users_store, _token_store, _stt_worker, _synthesizer, _monitor
    global _stt_out_queue, _tx_queue, _tts_event_queue, _background_tasks
    global _audio_level, _radio_error, _channel_clear, _last_id_time, _has_transmitted
    global _level_window, _attendance, _spectro, _monitor_chunk_cb
    global _pending_stations, _auto_add_tasks

    # --- startup -----------------------------------------------------------
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

    _background_tasks = {
        asyncio.create_task(_rx_pump(), name="rx-pump"),
        asyncio.create_task(_tx_pump(), name="tx-pump"),
        asyncio.create_task(_status_pump(), name="status-pump"),
        asyncio.create_task(_id_rule_pump(), name="id-rule-pump"),
        asyncio.create_task(_spectro.run(), name="spectro-pump"),
        asyncio.create_task(_online_status_pump(), name="online-status-pump"),
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


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

async def _ws_handle_set_admin_config(ws: WebSocket, data: dict, state: "ConnectionState") -> None:
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
    _config.save()
    await _manager.broadcast(_build_status())


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

                await _tx_queue.put({
                    **data,
                    "_filter_profanity": state.prefs.get("filter_profanity", True),
                    "_voice_name": state.prefs.get("tts_voice") or None,
                })
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
                await _tx_queue.put({"text": preview_text, "_voice_preview": True, "_voice_name": preview_voice})

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

            elif msg_type == "save_user_prefs":
                if _users_store is None:
                    continue
                allowed = {"dark_mode", "panel_order", "filter_profanity", "listen_only",
                           "spectro_colormap", "spectro_time_window_s", "tts_voice"}
                updates = {k: v for k, v in data.items() if k in allowed}
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

            else:
                _log.debug("Unknown message type from client: %r", msg_type)

    except WebSocketDisconnect:
        _log.info("Client disconnected: %s", ws.client)
    except Exception as exc:
        _log.error("WebSocket error for %s: %s", ws.client, exc)
    finally:
        _manager.remove(ws)
