"""Check-in reminder gating — pure logic, no I/O.

Mirrors backend/beacon/monitoring.py's style: pure helpers only. The async
pump that drives these (polling FamilyStore + PresenceStore on a timer) lives
in server.py as _family_reminder_pump / _family_reminder_tick.
"""
from __future__ import annotations

from datetime import datetime, time


def _parse_hhmm(value: str) -> time | None:
    """Parse an "HH:MM" string into a time, or None if malformed."""
    try:
        h, m = value.split(":")
        return time(int(h), int(m))
    except (ValueError, AttributeError):
        return None


def is_checkin_missed(reminder: dict, last_ok_iso: str | None, now_local: datetime) -> bool:
    """True when a check-in reminder has been missed.

    Missed means: the reminder is enabled, *now_local* is at or past the
    reminder's deadline time, and there has been no "I'm OK" check-in
    (`last_ok_iso`) *today* (in now_local's local day) — a check-in earlier
    today, even before the deadline, still counts and clears the miss.
    Before the deadline, or on a fresh day before any check-in, missed is
    always False (day rollover resets the flag).
    """
    if not reminder.get("enabled"):
        return False
    deadline = _parse_hhmm(reminder.get("time", ""))
    if deadline is None or now_local.time() < deadline:
        return False
    if not last_ok_iso:
        return True
    try:
        last_ok = datetime.fromisoformat(last_ok_iso.replace("Z", "+00:00"))
    except ValueError:
        return True
    if now_local.tzinfo is not None:
        last_ok = last_ok.astimezone(now_local.tzinfo)
    elif last_ok.tzinfo is not None:
        last_ok = last_ok.replace(tzinfo=None)
    return last_ok.date() != now_local.date()
