"""Session attendance tracking.

Ordered, deduplicated set of callsigns heard during the current session,
plus a resolver that joins against the contact list for the UI.
"""
from __future__ import annotations

from typing import Iterable

from backend.persistence.contacts import index_contacts_by_callsign, normalize_callsign


class AttendanceTracker:
    """Ordered, deduplicated set of callsigns heard this session.

    Insertion order is preserved — the first station heard sits at the top.
    """

    def __init__(self) -> None:
        self._order: list[str] = []
        self._seen: set[str] = set()

    def record(self, callsign: str) -> bool:
        """Record a callsign. Returns True if it was newly added."""
        cs = normalize_callsign(callsign)
        if not cs:
            return False
        if cs in self._seen:
            return False
        self._seen.add(cs)
        self._order.append(cs)
        return True

    def remove(self, callsign: str) -> bool:
        """Remove a callsign. Returns True if it was present."""
        cs = normalize_callsign(callsign)
        if cs not in self._seen:
            return False
        self._seen.discard(cs)
        self._order.remove(cs)
        return True

    def clear(self) -> None:
        self._order.clear()
        self._seen.clear()

    def callsigns(self) -> list[str]:
        return list(self._order)

    def __contains__(self, callsign: str) -> bool:
        return normalize_callsign(callsign) in self._seen

    def __len__(self) -> int:
        return len(self._order)


def build_attendance_rows(callsigns: Iterable[str], contacts: list[dict]) -> list[dict]:
    """Join callsigns against the contact list, returning one row per callsign.

    Each row has: callsign, name, location, gmrs, ham.
    Unknown callsigns get blank fields — the grid still records "we heard them."
    """
    index = index_contacts_by_callsign(contacts)
    rows = []
    for cs in callsigns:
        cs = normalize_callsign(cs)
        if not cs:
            continue
        entries = index.get(cs, [])
        if entries:
            c = entries[0]
            rows.append({
                "callsign": cs,
                "name": (c.get("name", "") or "").strip(),
                "location": (c.get("location", "") or "").strip(),
                "gmrs": normalize_callsign(c.get("gmrs_callsign", "")),
                "ham": normalize_callsign(c.get("ham_callsign", "")),
            })
        else:
            rows.append({"callsign": cs, "name": "", "location": "", "gmrs": "", "ham": ""})
    return rows
