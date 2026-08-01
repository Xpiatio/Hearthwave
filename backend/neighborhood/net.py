"""Pure state machine for the neighborhood net: check-ins and round-table calling.

No I/O — the server (backend/server.py) owns broadcasting, TX enqueue, and
journal persistence. This class only tracks in-memory state and returns
plain dicts for the server to act on.
"""
from __future__ import annotations

import datetime
import time
from typing import Optional

from backend.constants import utc_now_iso

RADIO_KEY_PREFIX = "radio:"


def radio_station_key(callsign: str, name: str) -> str:
    """Deterministic roster key for a station with no account.

    Folding case and collapsing whitespace means the same neighbor typed
    twice lands on one row instead of two, which is what makes a re-checkin
    of a radio caller idempotent the way `checkin()` is for an account.
    """
    folded_name = " ".join((name or "").split()).casefold()
    return f"{RADIO_KEY_PREFIX}{(callsign or '').strip().upper()}:{folded_name}"


class NeighborhoodNet:
    """Tracks the roster and call order for an in-progress (or just-ended) net.

    Roster rows are keyed by user_id and shaped:
        {"user_id", "callsign", "name", "location", "status", "checkin_time", "called"}
    status is "checked_in" (default) or "standby".

    Two stores back the roster: `_roster` holds account holders keyed by their
    real user_id, and `_radio` holds stations a coordinator checked in off the
    air, keyed by `radio_station_key(...)` and additionally carrying
    ``"via": "radio"``. Both are merged by `roster()` in check-in order using a
    shared monotonic `seq`, so a radio caller who checked in first is called
    first. Rows keep the station key in the `user_id` field so clients see one
    flat roster with one keyspace.

    Check-ins are accepted whether or not the net is active — a "tap" before
    `start()` is an early check-in (a spot reserved ahead of the net), and it
    must survive into the started net rather than being wiped by it.
    """

    def __init__(self) -> None:
        self.active: bool = False
        self.current_call: Optional[str] = None
        self._roster: dict[str, dict] = {}
        self._radio: dict[str, dict] = {}
        self._seq: int = 0
        self._started_at: float | None = None

    def _next_seq(self) -> int:
        """Stamp check-in order across both stores.

        Sorting on `checkin_time` instead would silently reorder an account
        holder who re-checks in (`checkin()` refreshes that field); insertion
        order, which this preserves, does not.
        """
        self._seq += 1
        return self._seq

    def _find(self, key: str) -> Optional[dict]:
        """Resolve a roster key in either store."""
        row = self._roster.get(key)
        if row is None:
            row = self._radio.get(key)
        return row

    def _ordered_rows(self) -> list[dict]:
        return sorted(
            [*self._roster.values(), *self._radio.values()],
            key=lambda row: row["seq"],
        )

    def start(self) -> None:
        """Begin a new net: open check-ins.

        Does NOT clear the roster — check-ins made before `start()` (early
        check-ins) are preserved. Only the round-table progress (called
        flags and the current call) is reset so a prior round doesn't leak
        into the new net.
        """
        self.active = True
        self.current_call = None
        for row in self._ordered_rows():
            row["called"] = False
        self._started_at = time.time()

    def end(self) -> dict:
        """Close the net, snapshot the roster for journaling, then clear it.

        Returns a dict with ``roster``, ``duration_seconds``, ``started_at``,
        and ``ended_at``. The summary's roster reflects the full just-ended
        roster. ``started_at``/``ended_at`` are ISO-8601 UTC strings
        (``started_at`` is blank if the net was never `start()`ed). The live
        roster is cleared afterward so `roster()` / `neighborhood_state`
        go empty immediately, and the next `start()` begins from a clean
        slate (aside from any new early check-ins that land before it).
        """
        self.active = False
        self.current_call = None
        started_at = self._started_at
        duration_seconds = (time.time() - started_at) if started_at else 0.0
        summary = {
            "roster": self.roster(),
            "duration_seconds": round(duration_seconds),
            "started_at": (
                datetime.datetime.fromtimestamp(started_at, datetime.timezone.utc)
                .strftime("%Y-%m-%dT%H:%M:%SZ")
                if started_at else ""
            ),
            "ended_at": utc_now_iso(),
        }
        self._roster = {}
        self._radio = {}
        self._started_at = None
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
                "seq": self._next_seq(),
            }
            self._roster[user_id] = row
        else:
            row["callsign"] = callsign
            row["name"] = name
            row["location"] = location
            row["checkin_time"] = now
        return row

    def checkin_radio(self, callsign: str, name: str, location: str) -> dict:
        """Check in a station that has no account (idempotent per station key).

        Identity is supplied by the coordinator, not by a connection's own
        profile — see the `neighborhood_checkin_radio` handler in
        backend/server.py for why that is safe here.
        """
        # Normalize first, then key off the normalized fields, so the stored
        # name is exactly what the key was built from. Attendance history keys
        # on (callsign, name) without collapsing internal whitespace, so a row
        # storing "Maria  Lopez" under a "maria lopez" key would fragment that
        # neighbor's streak across nets.
        callsign = (callsign or "").strip().upper()
        name = " ".join((name or "").split())
        location = (location or "").strip()
        key = radio_station_key(callsign, name)
        row = self._radio.get(key)
        now = utc_now_iso()
        if row is None:
            row = {
                "user_id": key,
                "callsign": callsign,
                "name": name,
                "location": location,
                "status": "checked_in",
                "checkin_time": now,
                "called": False,
                "via": "radio",
                "seq": self._next_seq(),
            }
            self._radio[key] = row
        else:
            row["callsign"] = callsign
            row["name"] = name
            row["location"] = location
            row["checkin_time"] = now
        return row

    def set_status(self, user_id: str, status: str) -> None:
        """Set a roster row's status ('checked_in', 'standby', or 'checked_out'); no-op if unknown user."""
        row = self._find(user_id)
        if row is not None:
            row["status"] = status

    def call_next(self) -> Optional[dict]:
        """Mark the first checked-in, not-yet-called row as current and return it.

        Walks both stores in check-in order, so a radio caller takes their
        turn where they actually checked in.

        Returns None (and clears current_call) when the round is complete.
        """
        for row in self._ordered_rows():
            if row["status"] == "checked_in" and not row["called"]:
                row["called"] = True
                self.current_call = row["user_id"]
                return row
        self.current_call = None
        return None

    def call_reset(self) -> None:
        """Clear all called flags and the current call, starting a fresh round."""
        for row in self._ordered_rows():
            row["called"] = False
        self.current_call = None

    def clear_checkins(self) -> int:
        """Drop every roster row, account and radio alike, returning how many were removed.

        Unlike `end()`, this leaves `active` alone: an admin wiping a board
        that filled up with yesterday's check-ins (or a test run) should not
        also close a net that is currently running. Round-table progress goes
        with the rows, since `current_call` would otherwise point at a row
        that no longer exists.
        """
        removed = len(self._roster) + len(self._radio)
        self._roster = {}
        self._radio = {}
        self.current_call = None
        return removed

    def remove_station(self, key: str) -> bool:
        """Remove a radio check-in (a coordinator fixing a mis-typed station).

        Refuses anything that isn't a radio station key, so this can never be
        used to bump an account holder off the board — that is `remove()`'s
        job, on account deletion. Returns True if a row was removed.
        """
        if not key.startswith(RADIO_KEY_PREFIX):
            return False
        removed = self._radio.pop(key, None) is not None
        if removed and self.current_call == key:
            self.current_call = None
        return removed

    def remove(self, user_id: str) -> bool:
        """Remove a user's roster row entirely (e.g. on account deletion).

        Clears current_call too if it pointed at the removed user, so a
        deleted user's round-table turn can't leave current_call dangling
        on a user_id nothing else refers to. Returns True if a row was
        removed, False if the user had no row (no-op).
        """
        removed = self._roster.pop(user_id, None) is not None
        if removed and self.current_call == user_id:
            self.current_call = None
        return removed

    def roster(self) -> list[dict]:
        """Both stores merged in check-in order, without internal bookkeeping.

        Rows are shallow copies: `seq` is an implementation detail that has no
        business on the wire or in a saved session record.
        """
        return [
            {k: v for k, v in row.items() if k != "seq"}
            for row in self._ordered_rows()
        ]
