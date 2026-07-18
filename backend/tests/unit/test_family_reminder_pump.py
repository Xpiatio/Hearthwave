"""Unit tests for backend.server._family_reminder_tick (extracted pump body).

Mirrors backend/tests/unit/test_server_beacon.py's style: arm module globals
directly, invoke the tick body once, assert on the mocked _manager.broadcast
and _presence_store side effects. No sleep loop involved.
"""
from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock

# backend.server transitively imports sounddevice (and other audio/ML deps) at
# module load time. Stub them out so tests run without audio hardware.
for _stub in ("sounddevice", "faster_whisper", "silero_vad", "piper"):
    sys.modules.setdefault(_stub, MagicMock())
_piper_config_stub = MagicMock()
_piper_config_stub.SynthesisConfig = MagicMock
sys.modules.setdefault("piper.config", _piper_config_stub)

import backend.server as server
from backend.persistence.family import FamilyStore
from backend.persistence.presence import PresenceStore


def _arm_server(tmp_path, *, reminders: dict, presence: dict | None = None):
    family_path = tmp_path / "family.json"
    presence_path = tmp_path / "presence.json"
    fam = FamilyStore(str(family_path))
    for uid, rem in reminders.items():
        fam.set_reminder(uid, rem["time"], rem["enabled"])
    pres = PresenceStore(str(presence_path))
    for uid, ok_iso in (presence or {}).items():
        if ok_iso is not None:
            pres.mark_ok(uid, ok_iso)
    server._family_store = fam
    server._presence_store = pres
    server._users_store = MagicMock()
    server._users_store.get_public.return_value = [
        {"id": uid, "display_name": uid, "avatar_emoji": "👤"} for uid in reminders
    ]
    server._manager = MagicMock()
    server._manager.broadcast = AsyncMock()
    return fam, pres


class TestFamilyReminderTick:
    async def test_flips_missed_and_broadcasts(self, tmp_path):
        fam, pres = _arm_server(
            tmp_path,
            reminders={"alice": {"time": "00:00", "enabled": True}},
        )
        await server._family_reminder_tick()
        assert pres.get("alice")["missed_checkin"] is True
        server._manager.broadcast.assert_awaited_once()
        (msg,), _ = server._manager.broadcast.call_args
        assert msg["type"] == "family_presence"
        entry = next(e for e in msg["entries"] if e["user_id"] == "alice")
        assert entry["missed_checkin"] is True

    async def test_no_change_does_not_broadcast(self, tmp_path):
        _arm_server(
            tmp_path,
            reminders={"alice": {"time": "23:59", "enabled": True}},
        )
        await server._family_reminder_tick()
        server._manager.broadcast.assert_not_awaited()

    async def test_disabled_reminder_never_flips(self, tmp_path):
        _arm_server(
            tmp_path,
            reminders={"alice": {"time": "00:00", "enabled": False}},
        )
        await server._family_reminder_tick()
        server._manager.broadcast.assert_not_awaited()

    async def test_ok_today_clears_previously_missed_flag(self, tmp_path):
        from backend.constants import utc_now_iso

        fam, pres = _arm_server(
            tmp_path,
            reminders={"alice": {"time": "00:00", "enabled": True}},
            presence={"alice": utc_now_iso()},
        )
        pres.set_missed("alice", True)
        await server._family_reminder_tick()
        assert pres.get("alice")["missed_checkin"] is False
        server._manager.broadcast.assert_awaited_once()

    async def test_reminder_for_unknown_user_does_not_crash(self, tmp_path):
        """A reminder can outlive its user (deleted profile) — the tick must
        tolerate it: PresenceStore.get()/set_missed() both handle unknown
        user_ids gracefully, so this should flip missed_checkin for that
        user_id without raising, and still broadcast."""
        _arm_server(
            tmp_path,
            reminders={"ghost": {"time": "00:00", "enabled": True}},
        )
        server._users_store.get_public.return_value = []  # profile is gone
        await server._family_reminder_tick()
        server._manager.broadcast.assert_awaited_once()

    async def test_no_reminders_configured_is_noop(self, tmp_path):
        _arm_server(tmp_path, reminders={})
        await server._family_reminder_tick()
        server._manager.broadcast.assert_not_awaited()

    async def test_missing_stores_is_noop(self, tmp_path):
        _arm_server(tmp_path, reminders={"alice": {"time": "00:00", "enabled": True}})
        server._family_store = None
        await server._family_reminder_tick()
        server._manager.broadcast.assert_not_awaited()
