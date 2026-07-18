"""Pure state machine for the neighborhood net: check-ins and round-table calling.

No I/O — the server (backend/server.py) owns broadcasting, TX enqueue, and
journal persistence. This class only tracks in-memory state and returns
plain dicts for the server to act on.
"""
from __future__ import annotations

import time
from typing import Optional

from backend.constants import utc_now_iso


class NeighborhoodNet:
    """Tracks the roster and call order for an in-progress (or just-ended) net.

    Roster rows are keyed by user_id and shaped:
        {"user_id", "callsign", "name", "location", "status", "checkin_time", "called"}
    status is "checked_in" (default) or "standby".

    Check-ins are accepted whether or not the net is active — a "tap" before
    `start()` is an early check-in (a spot reserved ahead of the net), and it
    must survive into the started net rather than being wiped by it.
    """

    def __init__(self) -> None:
        self.active: bool = False
        self.current_call: Optional[str] = None
        self._roster: dict[str, dict] = {}
        self._started_at: float | None = None

    def start(self) -> None:
        """Begin a new net: open check-ins.

        Does NOT clear the roster — check-ins made before `start()` (early
        check-ins) are preserved. Only the round-table progress (called
        flags and the current call) is reset so a prior round doesn't leak
        into the new net.
        """
        self.active = True
        self.current_call = None
        for row in self._roster.values():
            row["called"] = False
        self._started_at = time.time()

    def end(self) -> dict:
        """Close the net, snapshot the roster for journaling, then clear it.

        The summary's roster reflects the full just-ended roster. The live
        roster is cleared afterward so `roster()` / `neighborhood_state`
        go empty immediately, and the next `start()` begins from a clean
        slate (aside from any new early check-ins that land before it).
        """
        self.active = False
        self.current_call = None
        duration_seconds = (time.time() - self._started_at) if self._started_at else 0.0
        summary = {
            "roster": self.roster(),
            "duration_seconds": round(duration_seconds),
        }
        self._roster = {}
        return summary

    def checkin(self, user_id: str, callsign: str, name: str, location: str) -> dict:
        """Add or update the check-in row for user_id (idempotent per user_id).

        Works regardless of `active` — this is how early check-ins happen.
        `checkin_time` is updated to now on every call (re-checking in is
        the honest, latest signal of presence).
        """
        row = self._roster.get(user_id)
        now = utc_now_iso()
        if row is None:
            row = {
                "user_id": user_id,
                "callsign": callsign,
                "name": name,
                "location": location,
                "status": "checked_in",
                "checkin_time": now,
                "called": False,
            }
            self._roster[user_id] = row
        else:
            row["callsign"] = callsign
            row["name"] = name
            row["location"] = location
            row["checkin_time"] = now
        return row

    def set_status(self, user_id: str, status: str) -> None:
        """Set a roster row's status ('checked_in' or 'standby'); no-op if unknown user."""
        row = self._roster.get(user_id)
        if row is not None:
            row["status"] = status

    def call_next(self) -> Optional[dict]:
        """Mark the first checked-in, not-yet-called row as current and return it.

        Returns None (and clears current_call) when the round is complete.
        """
        for row in self._roster.values():
            if row["status"] == "checked_in" and not row["called"]:
                row["called"] = True
                self.current_call = row["user_id"]
                return row
        self.current_call = None
        return None

    def call_reset(self) -> None:
        """Clear all called flags and the current call, starting a fresh round."""
        for row in self._roster.values():
            row["called"] = False
        self.current_call = None

    def roster(self) -> list[dict]:
        return list(self._roster.values())
