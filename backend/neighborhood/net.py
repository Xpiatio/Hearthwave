"""Pure state machine for the neighborhood net: check-ins and round-table calling.

No I/O — the server (backend/server.py) owns broadcasting, TX enqueue, and
journal persistence. This class only tracks in-memory state and returns
plain dicts for the server to act on.
"""
from __future__ import annotations

import time
from typing import Optional


class NeighborhoodNet:
    """Tracks the roster and call order for an in-progress (or just-ended) net.

    Roster rows are keyed by user_id and shaped:
        {"user_id", "callsign", "name", "location", "status", "called"}
    status is "checked_in" (default) or "standby".
    """

    def __init__(self) -> None:
        self.active: bool = False
        self.current_call: Optional[str] = None
        self._roster: dict[str, dict] = {}
        self._started_at: float | None = None

    def start(self) -> None:
        """Begin a new net: open check-ins and clear any previous roster."""
        self.active = True
        self.current_call = None
        self._roster = {}
        self._started_at = time.time()

    def end(self) -> dict:
        """Close the net and return a summary for journaling.

        The roster is left intact (not cleared) so `roster()` /
        `neighborhood_state` continue to reflect the just-ended net until
        the next `start()` resets it.
        """
        self.active = False
        self.current_call = None
        duration_seconds = (time.time() - self._started_at) if self._started_at else 0.0
        return {
            "roster": self.roster(),
            "duration_seconds": round(duration_seconds),
        }

    def checkin(self, user_id: str, callsign: str, name: str, location: str) -> dict:
        """Add or update the check-in row for user_id (idempotent per user_id)."""
        row = self._roster.get(user_id)
        if row is None:
            row = {
                "user_id": user_id,
                "callsign": callsign,
                "name": name,
                "location": location,
                "status": "checked_in",
                "called": False,
            }
            self._roster[user_id] = row
        else:
            row["callsign"] = callsign
            row["name"] = name
            row["location"] = location
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
