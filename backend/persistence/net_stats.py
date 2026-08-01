"""Attendance statistics across stored net sessions.

Pure aggregation — callers pass in the summaries from
``net_sessions.load_session_summaries`` (newest-first) and the contact list.
"""
from __future__ import annotations

from backend.persistence.contacts import index_contacts_by_callsign, normalize_callsign

# How many of the most recent nets the "attended N of last M" figure covers.
_RECENT_WINDOW = 10


def compute_attendance_stats(
    summaries: list[dict], contacts: list[dict] | None = None
) -> list[dict]:
    """Aggregate per-station attendance, busiest station first.

    ``summaries`` must be newest-first, which is what the store returns —
    ``current_streak`` and ``last_seen`` both depend on that ordering.
    """
    index = index_contacts_by_callsign(contacts or [])
    # Precompute one callsign set per session: streak and recent-window checks
    # both scan the whole list, and re-deriving the sets each time is wasteful.
    per_session = [_station_calls(s) for s in summaries]
    recent = per_session[:_RECENT_WINDOW]

    totals: dict[str, int] = {}
    names: dict[str, str] = {}
    last_seen: dict[str, str] = {}

    for session, calls in zip(summaries, per_session):
        for cs in calls:
            totals[cs] = totals.get(cs, 0) + 1
            # Newest-first means the first sighting is the most recent one.
            last_seen.setdefault(cs, session.get("started_at", ""))
        for station in session.get("stations") or []:
            cs = normalize_callsign(station.get("callsign", ""))
            name = (station.get("name") or "").strip()
            if cs and name:
                names.setdefault(cs, name)

    rows = [
        {
            "callsign": cs,
            "name": names.get(cs) or _contact_name(index, cs),
            "total_nets": total,
            "attended_of_recent": sum(1 for calls in recent if cs in calls),
            "recent_window": len(recent),
            "current_streak": _streak(per_session, cs),
            "last_seen": last_seen.get(cs, ""),
        }
        for cs, total in totals.items()
    ]
    rows.sort(key=lambda r: (-r["total_nets"], r["callsign"]))
    return rows


def _station_calls(session: dict) -> set[str]:
    """Normalized callsigns present in one session summary."""
    calls = set()
    for station in session.get("stations") or []:
        cs = normalize_callsign(station.get("callsign", ""))
        if cs:
            calls.add(cs)
    return calls


def _streak(per_session: list[set[str]], callsign: str) -> int:
    """Consecutive most-recent sessions containing callsign."""
    streak = 0
    for calls in per_session:
        if callsign not in calls:
            break
        streak += 1
    return streak


def _contact_name(index: dict, callsign: str) -> str:
    entries = index.get(callsign) or []
    return (entries[0].get("name") or "").strip() if entries else ""
