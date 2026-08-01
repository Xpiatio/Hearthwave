"""Net session history — structured records of completed nets.

One JSON file per session in ``net_sessions_dir``. Distinct from journals:
journals are narrative text that an operator may publish to a public page,
while these are structured rosters kept private for attendance history and
CSV export. The two roster shapes in the codebase (NCS plugin and
NeighborhoodNet) are flattened here so one reader handles both.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from backend.persistence._utils import atomic_json_write

NET_TYPE_NCS = "ncs"
NET_TYPE_NEIGHBORHOOD = "neighborhood"

# NeighborhoodNet uses snake_case statuses; stored records standardize on the
# NCS TitleCase vocabulary. Unrecognized values pass through untouched.
_STATUS_MAP = {
    "checked_in": "CheckedIn",
    "standby": "Standby",
    "checked_out": "CheckedOut",
    "logged_out": "LoggedOut",
}


def _iso(value: object) -> str:
    """Coerce a unix timestamp (NCS) or ISO string (neighborhood) to ISO-8601 UTC."""
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat(timespec="seconds")
    return str(value or "")


def normalize_roster(rows: list[dict]) -> list[dict]:
    """Flatten NCS or neighborhood roster rows into the stored shape.

    Round-table bookkeeping (``called``, ``user_id``) is dropped — it describes
    a net in progress, not what happened.
    """
    return [
        {
            "callsign": (row.get("callsign") or "").upper(),
            "name": (row.get("name") or "").strip(),
            "location": (row.get("location") or "").strip(),
            "status": _STATUS_MAP.get(row.get("status", ""), row.get("status", "")),
            "traffic": row.get("traffic"),
            "checkin_time": _iso(row.get("checkin_time")),
            "verified": bool(row.get("verified", False)),
        }
        for row in rows
    ]


def save_session(
    net_type: str,
    started_at: str,
    ended_at: str,
    duration_seconds: int,
    roster: list[dict],
    transcript: str,
    sessions_dir: Path,
) -> str:
    """Write one completed net session and return its file path."""
    sessions_dir = Path(sessions_dir)
    sessions_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    session_id = f"{stamp}_{net_type}"
    path = sessions_dir / f"{session_id}.json"
    atomic_json_write(path, {
        "id": session_id,
        "net_type": net_type,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_seconds": int(duration_seconds),
        "roster": normalize_roster(roster),
        "transcript": transcript,
    })
    return str(path)


def load_session_summaries(sessions_dir: Path) -> list[dict]:
    """Return every session newest-first, without transcripts.

    Summaries carry each roster row's identity (``stations``) because both the
    list UI and the attendance stats need it. The transcript is the only large
    field and stays on disk until a caller asks for one specific session.
    """
    sessions_dir = Path(sessions_dir)
    if not sessions_dir.is_dir():
        return []
    summaries = []
    for name in sorted(os.listdir(sessions_dir), reverse=True):
        if not name.endswith(".json"):
            continue
        try:
            with open(sessions_dir / name, encoding="utf-8") as fh:
                entry = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        roster = entry.get("roster") or []
        summaries.append({
            "id": entry.get("id") or name[:-5],
            "net_type": entry.get("net_type", ""),
            "started_at": entry.get("started_at", ""),
            "ended_at": entry.get("ended_at", ""),
            "duration_seconds": entry.get("duration_seconds", 0),
            "checkin_count": len(roster),
            "stations": [
                {"callsign": r.get("callsign", ""), "name": r.get("name", "")}
                for r in roster
            ],
        })
    return summaries


def load_session(session_id: str, sessions_dir: Path) -> dict | None:
    """Return one full session including its transcript, or None if unreadable."""
    path = _resolve(session_id, Path(sessions_dir))
    if path is None or not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def delete_session(session_id: str, sessions_dir: Path) -> None:
    """Delete one session. Raises ValueError for an id outside sessions_dir."""
    path = _resolve(session_id, Path(sessions_dir))
    if path is None:
        raise ValueError(f"Invalid session id: {session_id}")
    os.remove(path)


def _resolve(session_id: str, sessions_dir: Path) -> Path | None:
    """Map a session id to its file path, or None if it escapes sessions_dir."""
    if not session_id or "/" in session_id or "\\" in session_id:
        return None
    target = (sessions_dir / f"{session_id}.json").resolve()
    if not target.is_relative_to(sessions_dir.resolve()):
        return None
    return target
