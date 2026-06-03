"""NCS (Net Control Station) / SKYWARN plugin for Radio-TTY.

Implements ADR 0003: interactive roster, BREAK BREAK emergency interrupter,
15-second rolling audio replay buffer, and NWS CAP alert feed with
Listen-Before-Talk (LBT) automated announcements.

Register by calling plugin_registry.register(NCSPlugin(...)) in _lifespan.
"""
from __future__ import annotations

import asyncio
import base64
import collections
import datetime
import json as _json
import logging
import urllib.request
from typing import Callable, Optional

from backend.plugins.base import BasePlugin

_log = logging.getLogger(__name__)

_VALID_TRAFFIC = {"Routine", "Priority", "Emergency", "General", "Short Term", "IN-n-Out"}

# Bytes per sample for float32 PCM (the format captured by STTWorker)
_BYTES_PER_SAMPLE = 4
_SAMPLE_RATE = 16_000
_REPLAY_SECONDS = 15
_NWS_POLL_INTERVAL = 300  # seconds between NWS polls


def _fetch_nws_alerts_sync(zone: str) -> list:
    """Synchronous NWS CAP fetch — run inside run_in_executor."""
    url = f"https://api.weather.gov/alerts/active?zone={zone}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/geo+json",
            "User-Agent": "Radio-TTY NCS/1.0 (github.com/Xpiatio/Radio-TTY)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read())
        return data.get("features", [])
    except Exception as exc:
        _log.debug("NWS fetch error for zone %s: %s", zone, exc)
        return []


class NCSPlugin(BasePlugin):
    """Net Control Station plugin — roster management, BREAK BREAK, replay buffer, NWS alerts."""

    def __init__(
        self,
        broadcast_fn: Callable,
        tx_queue: asyncio.Queue,
        config_getter: Callable,
        channel_clear_fn: Callable[[], bool],
        contacts_getter: Optional[Callable] = None,
        add_contact_fn: Optional[Callable] = None,
        update_contact_fn: Optional[Callable] = None,
        broadcast_contacts_fn: Optional[Callable] = None,
    ) -> None:
        self._broadcast = broadcast_fn
        self._tx_queue = tx_queue
        self._get_config = config_getter
        self._channel_clear = channel_clear_fn
        self._contacts_getter = contacts_getter
        self._add_contact_fn = add_contact_fn
        self._update_contact_fn = update_contact_fn
        self._broadcast_contacts_fn = broadcast_contacts_fn

        self._active = False
        # Roster: callsign → {callsign, status, traffic, name, location, checkin_time}
        self._roster: dict[str, dict] = {}
        self._session_rx: list[str] = []

        self._break_break_pending = False

        # Rolling audio buffer: deque of raw bytes, capped at REPLAY_SECONDS
        _max_bytes = _REPLAY_SECONDS * _SAMPLE_RATE * _BYTES_PER_SAMPLE
        self._audio_buffer: collections.deque[bytes] = collections.deque()
        self._audio_buffer_bytes = 0
        self._audio_max_bytes = _max_bytes

        self._nws_task: asyncio.Task | None = None
        self._announce_task: asyncio.Task | None = None
        self._seen_alerts: set[str] = set()

    # ------------------------------------------------------------------
    # BasePlugin hooks
    # ------------------------------------------------------------------

    async def on_client_message_received(self, payload: dict, reply=None) -> None:
        msg_type = payload.get("type")

        if msg_type == "ncs_get_state":
            if reply:
                await reply(self._build_state_msg())

        elif msg_type == "ncs_start":
            await self._handle_start()

        elif msg_type == "ncs_end":
            await self._handle_end()

        elif msg_type == "ncs_checkin":
            cs = (payload.get("callsign") or "").strip().upper()
            if cs:
                await self._handle_checkin(
                    cs,
                    payload.get("traffic", "Routine"),
                    payload.get("name", ""),
                    payload.get("location", ""),
                )

        elif msg_type == "ncs_status_update":
            cs = (payload.get("callsign") or "").strip().upper()
            new_status = payload.get("status")
            if cs and cs in self._roster and new_status in ("CheckedIn", "Standby", "LoggedOut"):
                self._roster[cs]["status"] = new_status
                await self._broadcast_roster()

        elif msg_type == "ncs_remove":
            cs = (payload.get("callsign") or "").strip().upper()
            if cs in self._roster:
                del self._roster[cs]
                await self._broadcast_roster()

        elif msg_type == "ncs_break_break":
            asyncio.create_task(self._handle_break_break(), name="ncs-break-break")

        elif msg_type == "ncs_get_replay":
            if reply:
                asyncio.create_task(self._handle_get_replay(reply), name="ncs-replay")

    def on_audio_rx_chunk(self, chunk) -> None:
        """Accumulate PCM chunks into the rolling replay buffer (sync, hot path)."""
        try:
            chunk_bytes = bytes(chunk) if not isinstance(chunk, (bytes, bytearray)) else chunk
        except Exception:
            return
        self._audio_buffer.append(chunk_bytes)
        self._audio_buffer_bytes += len(chunk_bytes)
        while self._audio_buffer_bytes > self._audio_max_bytes and self._audio_buffer:
            removed = self._audio_buffer.popleft()
            self._audio_buffer_bytes -= len(removed)

    async def on_rx_final(self, text: str) -> None:
        """Accumulate transcripts for the end-of-net journal."""
        if self._active and text.strip():
            self._session_rx.append(text.strip())

    async def on_audio_tx_pre_queue(self, payload: dict) -> dict | None:
        if self._break_break_pending:
            return None  # Block TX while BREAK BREAK is active
        return payload

    # ------------------------------------------------------------------
    # Internal handlers
    # ------------------------------------------------------------------

    async def _handle_start(self) -> None:
        if self._active:
            return
        self._active = True
        self._roster.clear()
        self._session_rx.clear()
        self._seen_alerts.clear()
        config = self._get_config()
        if config.ncs_zone:
            self._nws_task = asyncio.create_task(self._nws_poll_loop(), name="ncs-nws-poll")
        self._announce_task = asyncio.create_task(
            self._announcement_loop(config.ncs_announcement_interval),
            name="ncs-announce",
        )
        await self._broadcast(self._build_state_msg())
        _log.info("NCS mode started (zone=%s)", config.ncs_zone or "none")

    async def _handle_end(self) -> None:
        if not self._active:
            return
        self._active = False
        for task in (self._nws_task, self._announce_task):
            if task:
                task.cancel()
        self._nws_task = None
        self._announce_task = None
        if self._session_rx or self._roster:
            asyncio.create_task(self._save_ncs_journal(), name="ncs-journal")
        await self._broadcast(self._build_state_msg())
        _log.info("NCS mode ended; %d stations checked in, %d RX lines", len(self._roster), len(self._session_rx))

    async def _handle_checkin(self, callsign: str, traffic: str, name: str, location: str) -> None:
        now = datetime.datetime.now(tz=datetime.timezone.utc).timestamp()
        existing = self._roster.get(callsign, {})

        verified = False
        if self._contacts_getter is not None:
            contacts_index = {
                (c.get("callsign") or "").upper(): c
                for c in self._contacts_getter()
            }
            contact = contacts_index.get(callsign)
            if contact is not None:
                verified = bool(contact.get("verified", False))
                name = name or contact.get("name", "")
                location = location or contact.get("location", "")
            else:
                new_contact: dict = {"callsign": callsign, "name": name, "location": location}
                if self._add_contact_fn is not None:
                    try:
                        updated_list = self._add_contact_fn(new_contact)
                        if self._broadcast_contacts_fn is not None:
                            asyncio.create_task(
                                self._broadcast_contacts_fn(updated_list),
                                name="ncs-broadcast-contacts",
                            )
                    except Exception as exc:
                        _log.warning("NCS auto-add contact failed for %s: %s", callsign, exc)
                if name and self._update_contact_fn is not None:
                    from backend.fcc.auto_add import CallsignLookupWorker
                    CallsignLookupWorker(callsign, name, location, self._on_fcc_result).start()

        self._roster[callsign] = {
            "callsign": callsign,
            "status": "CheckedIn",
            "traffic": traffic if traffic in _VALID_TRAFFIC else "Routine",
            "name": name or existing.get("name", ""),
            "location": location or existing.get("location", ""),
            "checkin_time": existing.get("checkin_time", now),
            "verified": verified,
        }
        await self._broadcast_roster()

    async def _on_fcc_result(self, callsign: str, name: str, location: str, result) -> None:
        from backend.fcc.crossref import apply_verification
        now_iso = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        try:
            contacts = self._contacts_getter() if self._contacts_getter is not None else []
            contact = next(
                (c for c in contacts if (c.get("callsign") or "").upper() == callsign),
                None,
            )
            if contact is None or self._update_contact_fn is None:
                return
            updated = apply_verification(contact, result, now_iso)
            updated_list = self._update_contact_fn(callsign, updated)
            if self._broadcast_contacts_fn is not None:
                await self._broadcast_contacts_fn(updated_list)
            if callsign in self._roster:
                self._roster[callsign]["verified"] = bool(updated.get("verified", False))
                await self._broadcast_roster()
        except Exception as exc:
            _log.warning("NCS FCC result callback error for %s: %s", callsign, exc)

    async def _handle_break_break(self) -> None:
        self._break_break_pending = True
        _log.warning("BREAK BREAK activated — draining TX queue")
        drained = 0
        while True:
            try:
                self._tx_queue.get_nowait()
                drained += 1
            except asyncio.QueueEmpty:
                break
        if drained:
            _log.info("BREAK BREAK drained %d TX items", drained)
        await self._broadcast({"type": "ncs_break_break_ack"})
        await self._broadcast({"type": "tx_status", "status": "idle"})
        await asyncio.sleep(2.0)
        self._break_break_pending = False

    async def _handle_get_replay(self, reply) -> None:
        if not self._audio_buffer:
            await reply({"type": "ncs_replay_audio", "data": "", "sample_rate": _SAMPLE_RATE})
            return
        try:
            import numpy as np
            all_bytes = b"".join(self._audio_buffer)
            audio_f32 = np.frombuffer(all_bytes, dtype=np.float32)
            audio_i16 = (np.clip(audio_f32, -1.0, 1.0) * 32767).astype(np.int16)
            audio_b64 = base64.b64encode(audio_i16.tobytes()).decode("ascii")
        except Exception as exc:
            _log.warning("Replay encode error: %s", exc)
            audio_b64 = ""
        await reply({"type": "ncs_replay_audio", "data": audio_b64, "sample_rate": _SAMPLE_RATE})

    async def _save_ncs_journal(self) -> None:
        from backend.persistence.journal import save_journal
        config = self._get_config()
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        title = f"NCS Net Session — {now_str}"
        roster_lines = "\n".join(
            f"  {e['callsign']} — {e['status']} — {e['traffic']}"
            + (f" — {e['name']}" if e.get("name") else "")
            for e in self._roster.values()
        ) or "  (no check-ins)"
        summary = f"Net Control Session\n\nChecked-in stations:\n{roster_lines}"
        transcript = "\n".join(self._session_rx) or "(no received transmissions)"
        callsigns_with_locations = [
            {"callsign": e["callsign"], "location": e.get("location", "")}
            for e in self._roster.values()
        ]
        try:
            path = save_journal(
                title=title,
                summary=summary,
                callsigns_with_locations=callsigns_with_locations,
                transcript=transcript,
                journals_dir=config.journals_dir,
            )
            await self._broadcast({"type": "ncs_journal_saved", "path": path})
            _log.info("NCS journal saved: %s", path)
        except Exception as exc:
            _log.error("NCS journal save failed: %s", exc)

    # ------------------------------------------------------------------
    # NWS polling loop
    # ------------------------------------------------------------------

    async def _nws_poll_loop(self) -> None:
        while self._active:
            try:
                zone = self._get_config().ncs_zone
                if zone:
                    await self._poll_nws_once(zone)
            except asyncio.CancelledError:
                return
            except Exception as exc:
                _log.warning("NWS poll loop error: %s", exc)
            await asyncio.sleep(_NWS_POLL_INTERVAL)

    async def _poll_nws_once(self, zone: str) -> None:
        loop = asyncio.get_event_loop()
        features = await loop.run_in_executor(None, _fetch_nws_alerts_sync, zone)
        for feature in features:
            props = feature.get("properties", {})
            alert_id = props.get("id") or feature.get("id") or ""
            if not alert_id or alert_id in self._seen_alerts:
                continue
            self._seen_alerts.add(alert_id)
            severity = props.get("severity", "Unknown")
            event = props.get("event", "")
            headline = (props.get("headline") or event).strip()
            await self._broadcast({
                "type": "ncs_alert",
                "id": alert_id,
                "event": event,
                "headline": headline,
                "zone": zone,
                "severity": severity,
            })
            if severity in ("Extreme", "Severe") and self._channel_clear():
                config = self._get_config()
                text = f"SKYWARN ALERT. {headline}. {config.callsign}."
                await self._tx_queue.put({"text": text, "_pre_formatted": True})
                _log.info("NCS auto-TX SKYWARN alert: %s", headline[:60])

    # ------------------------------------------------------------------
    # Auto-announcement loop
    # ------------------------------------------------------------------

    async def _announcement_loop(self, interval: int) -> None:
        await asyncio.sleep(interval)
        while self._active:
            try:
                if self._channel_clear():
                    config = self._get_config()
                    loc = config.location or "unknown location"
                    station_name = config.name or "net control"
                    text = (
                        f"Net Control Station, {config.callsign}, "
                        f"{station_name} in {loc}. "
                        f"Calling all stations. {config.callsign}."
                    )
                    await self._tx_queue.put({"text": text, "_pre_formatted": True})
                    _log.debug("NCS periodic announcement transmitted")
            except asyncio.CancelledError:
                return
            except Exception as exc:
                _log.warning("NCS announcement error: %s", exc)
            await asyncio.sleep(interval)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_state_msg(self) -> dict:
        config = self._get_config()
        return {
            "type": "ncs_state",
            "active": self._active,
            "roster": list(self._roster.values()),
            "zone": config.ncs_zone if config else "",
        }

    async def _broadcast_roster(self) -> None:
        await self._broadcast({
            "type": "ncs_roster_update",
            "roster": list(self._roster.values()),
        })
