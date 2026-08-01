# Net Session History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist every completed net (NCS and neighborhood) as a structured JSON record, then expose a Past Nets browser with attendance stats and CSV export.

**Architecture:** A new `backend/persistence/net_sessions.py` store writes one JSON file per completed net into `net_sessions_dir` (default `/data/net_sessions`), normalizing the two existing roster shapes into one. A pure `backend/persistence/net_stats.py` aggregates attendance across those records. Three new WebSocket messages expose list/detail/delete, and a new `PastNetsTab` component renders them inside a tabbed `JournalPanel`. CSV export happens client-side, matching the existing contacts export.

**Tech Stack:** Python 3 / FastAPI / pytest (backend); React + TypeScript + MUI + Vitest + React Testing Library (frontend).

## Global Constraints

- Existing journal writes must keep working unchanged — session records are additive, never a replacement.
- A session-save failure must never block ending a net (log + warn only). The one exception already in the codebase — the incident-log wipe that aborts if journaling fails — is not the model here, because ending a net does not destroy data.
- Session records are **private**. Never route them through `publish_journal` or the public `GET /journal` page.
- Stored records use the NCS TitleCase status vocabulary (`CheckedIn`, `Standby`, `CheckedOut`, `LoggedOut`); the neighborhood net's snake_case statuses are mapped on write.
- Reading sessions is open to any authenticated user; **deleting requires admin** (`state.is_admin`), matching `neighborhood_clear_incidents`.
- No new Python or npm dependencies.
- No `Co-Authored-By` trailers on commits and no generated-with footers on PRs (standing rule for this repo).
- Do not bump version numbers or touch release files — this ships in whatever release comes next.

## Deviations From The Spec (accepted)

Each of these departs from `docs/superpowers/specs/2026-08-01-net-session-history-design.md` for a reason found while reading the code. Follow the plan, not the spec, where they disagree.

1. **CSV is built client-side, not via HTTP endpoints.** The spec proposed `GET /api/net-sessions/{id}.csv` and `all.csv`. But the existing contacts export (`ContactsDialog.tsx:233-243`) builds CSV in the browser with `contactsToCsv` + `downloadText`, and there is no backend CSV endpoint anywhere in the codebase. Adding one would require new HTTP auth plumbing, since the WebSocket is token-authed and plain HTTP downloads are not. Session data already arrives over the authenticated socket, so the browser can serialize it.

2. **WebSocket message names are verb-first.** The spec wrote `net_sessions_list` / `net_session_get` / `net_session_delete`; this plan uses `list_net_sessions` / `get_net_session` / `delete_net_session` to match the existing `list_journals` / `save_journal` / `delete_journal` family.

3. **Delete confirmation reuses the panel's click-twice pattern, not `ConfirmDialog`.** `JournalPanel.tsx` already confirms destructive actions with a second click on the same button; a modal inside the same panel would be inconsistent.

4. **A failed session save logs only — no `system_msg` warning.** The spec asked for a user-facing warning. Ending a net destroys nothing, so a warning would be noise on a path the operator cannot act on. The journal-save path in `ncs.py` behaves the same way. (The contrasting case, `neighborhood_clear_incidents`, aborts on save failure because it is about to wipe data.)

5. **Records carry an explicit `id` field instead of `journal.py`'s injected `_file`.** The id is derived from the filename either way, but storing it makes the WebSocket payload self-describing and keeps absolute host paths out of the frontend.

## File Structure

**Backend — create:**
- `backend/persistence/net_sessions.py` — save/load/delete + roster normalization. Sole owner of the on-disk format.
- `backend/persistence/net_stats.py` — pure attendance aggregation over session summaries. No I/O.
- `backend/tests/unit/persistence/test_net_sessions.py`
- `backend/tests/unit/persistence/test_net_stats.py`

**Backend — modify:**
- `backend/config.py` — add `net_sessions_dir` property beside `journals_dir` (line 287-290).
- `backend/plugins/ncs.py` — record `_started_at`; save a session in `_handle_end`; add `CheckedOut` status.
- `backend/neighborhood/net.py` — `end()` returns `started_at` / `ended_at`; accept `checked_out`.
- `backend/server.py` — save a session in `neighborhood_end`; three new WS handlers; allow `checked_out`.
- `backend/tests/unit/plugins/test_ncs.py` — session-save and `CheckedOut` coverage.
- `backend/tests/unit/neighborhood/test_net.py` — timestamp fields in `end()`.

**Frontend — create:**
- `frontend/src/utils/download.ts` — `downloadText`, extracted from `ContactsDialog.tsx` so two callers share one copy.
- `frontend/src/netsessions/csv.ts` — pure `sessionToCsv` / `allSessionsToCsv`.
- `frontend/src/netsessions/__tests__/csv.test.ts`
- `frontend/src/components/JournalPanel/PastNetsTab.tsx` — list + detail + stats + CSV + delete. Separate file because `JournalPanel.tsx` is already 375 lines.
- `frontend/src/components/JournalPanel/__tests__/PastNetsTab.test.tsx`

**Frontend — modify:**
- `frontend/src/types/ws.ts` — session types + `ServerMsg` union entries (union ends at line 750).
- `frontend/src/App.tsx` — state, switch cases, handlers, prop wiring.
- `frontend/src/components/JournalPanel/JournalPanel.tsx` — tab bar wrapping existing body.
- `frontend/src/components/DesktopApp/DesktopApp.tsx` (line 422) and `MobileApp/MobileApp.tsx` (line 439) — pass new props.
- `frontend/src/components/ContactsDialog/ContactsDialog.tsx` — import shared `downloadText`.
- `frontend/src/components/NCSPanel/NCSPanel.tsx` — `CheckedOut` in the status cycle; sort + search.
- `frontend/src/components/NeighborhoodPanel/RosterList.tsx` — sort + search.
- `README.md`, `USER_MANUAL.md` — document the feature.

---

### Task 1: Session store

**Files:**
- Create: `backend/persistence/net_sessions.py`
- Create: `backend/tests/unit/persistence/test_net_sessions.py`
- Modify: `backend/config.py:287-290`

**Interfaces:**
- Consumes: `atomic_json_write(path, data)` from `backend.persistence._utils`.
- Produces: `NET_TYPE_NCS = "ncs"`, `NET_TYPE_NEIGHBORHOOD = "neighborhood"`, `normalize_roster(rows) -> list[dict]`, `save_session(net_type, started_at, ended_at, duration_seconds, roster, transcript, sessions_dir) -> str`, `load_session_summaries(sessions_dir) -> list[dict]`, `load_session(session_id, sessions_dir) -> dict | None`, `delete_session(session_id, sessions_dir) -> None`. Config gains `net_sessions_dir -> Path`.

- [ ] **Step 1: Write failing tests**

```python
"""Unit tests for backend.persistence.net_sessions."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.persistence.net_sessions import (
    NET_TYPE_NCS,
    NET_TYPE_NEIGHBORHOOD,
    delete_session,
    load_session,
    load_session_summaries,
    normalize_roster,
    save_session,
)


@pytest.fixture()
def sessions_dir(tmp_path: Path) -> Path:
    d = tmp_path / "net_sessions"
    d.mkdir()
    return d


class TestNormalizeRoster:
    def test_ncs_row_keeps_traffic_and_converts_unix_time(self):
        rows = [{
            "callsign": "kd8abc", "status": "CheckedIn", "traffic": "Priority",
            "name": "Maria", "location": "Holland", "checkin_time": 1_700_000_000.0,
            "verified": True, "called": True,
        }]
        result = normalize_roster(rows)
        assert result[0]["callsign"] == "KD8ABC"
        assert result[0]["traffic"] == "Priority"
        assert result[0]["checkin_time"].startswith("2023-11-14T")
        assert result[0]["verified"] is True
        assert "called" not in result[0]

    def test_neighborhood_row_maps_status_and_nulls_traffic(self):
        rows = [{
            "user_id": "u1", "callsign": "WRAB123", "name": "Sam",
            "location": "Zeeland", "status": "checked_in",
            "checkin_time": "2026-08-01T19:30:00Z", "called": False,
        }]
        result = normalize_roster(rows)
        assert result[0]["status"] == "CheckedIn"
        assert result[0]["traffic"] is None
        assert result[0]["checkin_time"] == "2026-08-01T19:30:00Z"

    def test_standby_and_checked_out_map(self):
        rows = [{"status": "standby"}, {"status": "checked_out"}]
        assert [r["status"] for r in normalize_roster(rows)] == ["Standby", "CheckedOut"]

    def test_unknown_status_passes_through(self):
        assert normalize_roster([{"status": "Weird"}])[0]["status"] == "Weird"


class TestSaveSession:
    def test_writes_file_and_returns_path(self, sessions_dir: Path):
        path = save_session(
            net_type=NET_TYPE_NCS,
            started_at="2026-08-01T19:00:00Z",
            ended_at="2026-08-01T19:52:00Z",
            duration_seconds=3120,
            roster=[{"callsign": "KD8ABC", "status": "CheckedIn", "name": "Maria"}],
            transcript="KD8ABC: nothing to report",
            sessions_dir=sessions_dir,
        )
        assert Path(path).exists()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        assert data["net_type"] == "ncs"
        assert data["duration_seconds"] == 3120
        assert data["id"].endswith("_ncs")
        assert data["roster"][0]["callsign"] == "KD8ABC"
        assert data["transcript"] == "KD8ABC: nothing to report"

    def test_creates_directory_when_missing(self, tmp_path: Path):
        target = tmp_path / "nested" / "sessions"
        save_session(
            net_type=NET_TYPE_NEIGHBORHOOD, started_at="", ended_at="",
            duration_seconds=0, roster=[], transcript="", sessions_dir=target,
        )
        assert target.is_dir()
        assert len(list(target.glob("*.json"))) == 1


class TestLoadSessionSummaries:
    def test_returns_newest_first_without_transcripts(self, sessions_dir: Path):
        for name in ("20260801_190000_ncs.json", "20260802_190000_neighborhood.json"):
            (sessions_dir / name).write_text(json.dumps({
                "id": name[:-5], "net_type": "ncs", "started_at": "2026-08-01T19:00:00Z",
                "ended_at": "", "duration_seconds": 60,
                "roster": [{"callsign": "KD8ABC", "name": "Maria"}],
                "transcript": "a very long transcript",
            }), encoding="utf-8")
        summaries = load_session_summaries(sessions_dir)
        assert [s["id"] for s in summaries] == [
            "20260802_190000_neighborhood", "20260801_190000_ncs",
        ]
        assert "transcript" not in summaries[0]
        assert summaries[0]["checkin_count"] == 1
        assert summaries[0]["stations"] == [{"callsign": "KD8ABC", "name": "Maria"}]

    def test_missing_directory_returns_empty(self, tmp_path: Path):
        assert load_session_summaries(tmp_path / "nope") == []

    def test_skips_corrupt_file(self, sessions_dir: Path):
        (sessions_dir / "20260801_190000_ncs.json").write_text("{not json", encoding="utf-8")
        assert load_session_summaries(sessions_dir) == []


class TestLoadSession:
    def test_returns_full_entry(self, sessions_dir: Path):
        path = save_session(
            net_type=NET_TYPE_NCS, started_at="", ended_at="", duration_seconds=0,
            roster=[], transcript="hello", sessions_dir=sessions_dir,
        )
        session_id = Path(path).stem
        assert load_session(session_id, sessions_dir)["transcript"] == "hello"

    def test_missing_returns_none(self, sessions_dir: Path):
        assert load_session("20260801_190000_ncs", sessions_dir) is None

    def test_rejects_path_traversal(self, sessions_dir: Path):
        assert load_session("../../etc/passwd", sessions_dir) is None


class TestDeleteSession:
    def test_removes_file(self, sessions_dir: Path):
        path = save_session(
            net_type=NET_TYPE_NCS, started_at="", ended_at="", duration_seconds=0,
            roster=[], transcript="", sessions_dir=sessions_dir,
        )
        delete_session(Path(path).stem, sessions_dir)
        assert not Path(path).exists()

    def test_rejects_path_traversal(self, sessions_dir: Path):
        with pytest.raises(ValueError):
            delete_session("../secrets", sessions_dir)
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/unit/persistence/test_net_sessions.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.persistence.net_sessions'`

- [ ] **Step 3: Write the store**

Create `backend/persistence/net_sessions.py`:

```python
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
```

- [ ] **Step 4: Add the config property**

In `backend/config.py`, immediately after the `journals_dir` property (line 287-290):

```python
    @property
    def net_sessions_dir(self) -> Path:
        raw = self.get("net_sessions_dir")
        return Path(raw) if raw else Path("/data/net_sessions")
```

- [ ] **Step 5: Run tests and verify they pass**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/unit/persistence/test_net_sessions.py -v`
Expected: PASS (all tests)

- [ ] **Step 6: Commit**

```bash
git add backend/persistence/net_sessions.py backend/tests/unit/persistence/test_net_sessions.py backend/config.py
git commit -m "feat: add net session history store"
```

---

### Task 2: Attendance statistics

**Files:**
- Create: `backend/persistence/net_stats.py`
- Create: `backend/tests/unit/persistence/test_net_stats.py`

**Interfaces:**
- Consumes: session summaries from `load_session_summaries` (Task 1) — newest-first, each with a `stations` list. `index_contacts_by_callsign(contacts)` and `normalize_callsign(cs)` from `backend.persistence.contacts`.
- Produces: `compute_attendance_stats(summaries, contacts=None) -> list[dict]` where each row is `{callsign, name, total_nets, attended_of_recent, recent_window, current_streak, last_seen}`.

- [ ] **Step 1: Write failing tests**

```python
"""Unit tests for backend.persistence.net_stats."""
from __future__ import annotations

from backend.persistence.net_stats import compute_attendance_stats


def _session(session_id: str, started_at: str, *stations) -> dict:
    """Build a summary like load_session_summaries returns."""
    return {
        "id": session_id,
        "net_type": "neighborhood",
        "started_at": started_at,
        "ended_at": "",
        "duration_seconds": 600,
        "checkin_count": len(stations),
        "stations": [{"callsign": cs, "name": name} for cs, name in stations],
    }


# Newest-first, as the store returns them.
SUMMARIES = [
    _session("s3", "2026-08-15T19:00:00Z", ("KD8ABC", "Maria"), ("WRAB123", "Sam")),
    _session("s2", "2026-08-08T19:00:00Z", ("KD8ABC", "Maria")),
    _session("s1", "2026-08-01T19:00:00Z", ("KD8ABC", "Maria"), ("WRAB123", "Sam")),
]


class TestComputeAttendanceStats:
    def test_counts_total_nets(self):
        rows = {r["callsign"]: r for r in compute_attendance_stats(SUMMARIES)}
        assert rows["KD8ABC"]["total_nets"] == 3
        assert rows["WRAB123"]["total_nets"] == 2

    def test_streak_counts_consecutive_most_recent_nets(self):
        rows = {r["callsign"]: r for r in compute_attendance_stats(SUMMARIES)}
        # Maria attended all three, most recent included.
        assert rows["KD8ABC"]["current_streak"] == 3
        # Sam attended the newest net but missed the one before it.
        assert rows["WRAB123"]["current_streak"] == 1

    def test_recent_window_caps_at_ten_sessions(self):
        many = [_session(f"s{i}", "2026-01-01T00:00:00Z", ("KD8ABC", "Maria")) for i in range(14)]
        row = compute_attendance_stats(many)[0]
        assert row["recent_window"] == 10
        assert row["attended_of_recent"] == 10
        assert row["total_nets"] == 14

    def test_last_seen_is_most_recent_session_start(self):
        rows = {r["callsign"]: r for r in compute_attendance_stats(SUMMARIES)}
        assert rows["WRAB123"]["last_seen"] == "2026-08-15T19:00:00Z"

    def test_sorted_by_total_desc_then_callsign(self):
        rows = compute_attendance_stats(SUMMARIES)
        assert [r["callsign"] for r in rows] == ["KD8ABC", "WRAB123"]

    def test_name_falls_back_to_contacts(self):
        summaries = [_session("s1", "2026-08-01T19:00:00Z", ("KD8ABC", ""))]
        contacts = [{"callsign": "KD8ABC", "name": "Maria from contacts", "location": "Holland"}]
        assert compute_attendance_stats(summaries, contacts)[0]["name"] == "Maria from contacts"

    def test_empty_input_returns_empty(self):
        assert compute_attendance_stats([]) == []

    def test_blank_callsigns_ignored(self):
        summaries = [_session("s1", "2026-08-01T19:00:00Z", ("", "Anonymous"))]
        assert compute_attendance_stats(summaries) == []
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/unit/persistence/test_net_stats.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.persistence.net_stats'`

- [ ] **Step 3: Write the aggregation**

Create `backend/persistence/net_stats.py`:

```python
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
```

- [ ] **Step 4: Run tests and verify they pass**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/unit/persistence/test_net_stats.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add backend/persistence/net_stats.py backend/tests/unit/persistence/test_net_stats.py
git commit -m "feat: add net attendance statistics aggregation"
```

---

### Task 3: NCS plugin writes sessions

**Files:**
- Modify: `backend/plugins/ncs.py` (`__init__` ~line 260, `_handle_start` line 399, `_handle_end` line 417, new `_save_net_session`)
- Modify: `backend/tests/unit/plugins/test_ncs.py`

**Interfaces:**
- Consumes: `save_session`, `NET_TYPE_NCS` from `backend.persistence.net_sessions` (Task 1); `config.net_sessions_dir` (Task 1).
- Produces: NCS nets leave a session file on `ncs_end`. The plugin gains `self._started_at: float | None`.

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/unit/plugins/test_ncs.py`. Note `make_config` at the top of that file needs `net_sessions_dir` added to its `defaults` dict — do that in Step 3.

```python
class TestNCSNetSessionSave:
    @pytest.mark.asyncio
    async def test_end_saves_session_with_roster_and_transcript(self, tmp_path):
        ncs = make_ncs(config=make_config(net_sessions_dir=tmp_path, ncs_zone=""))
        await ncs._handle_start()
        ncs._roster["KD8ABC|Maria"] = {
            "callsign": "KD8ABC", "status": "CheckedIn", "traffic": "Routine",
            "name": "Maria", "location": "Holland", "checkin_time": 1_700_000_000.0,
            "verified": True, "called": False,
        }
        ncs._session_rx.append("KD8ABC: nothing to report")

        await ncs._handle_end()
        await ncs._save_net_session()

        files = list(tmp_path.glob("*_ncs.json"))
        assert len(files) == 1
        data = json.loads(files[0].read_text(encoding="utf-8"))
        assert data["net_type"] == "ncs"
        assert data["roster"][0]["callsign"] == "KD8ABC"
        assert data["roster"][0]["traffic"] == "Routine"
        assert "KD8ABC: nothing to report" in data["transcript"]
        assert data["duration_seconds"] >= 0
        assert data["started_at"]

    @pytest.mark.asyncio
    async def test_start_records_started_at(self):
        ncs = make_ncs(config=make_config(ncs_zone=""))
        assert ncs._started_at is None
        await ncs._handle_start()
        assert ncs._started_at is not None

    @pytest.mark.asyncio
    async def test_save_failure_does_not_raise(self, tmp_path):
        # A file where the directory should be makes mkdir fail.
        blocked = tmp_path / "blocked"
        blocked.write_text("not a directory", encoding="utf-8")
        ncs = make_ncs(config=make_config(net_sessions_dir=blocked, ncs_zone=""))
        await ncs._handle_start()
        ncs._roster["KD8ABC|"] = {
            "callsign": "KD8ABC", "status": "CheckedIn", "traffic": "Routine",
            "name": "", "location": "", "checkin_time": 1_700_000_000.0,
            "verified": False, "called": False,
        }
        await ncs._handle_end()
        await ncs._save_net_session()  # must not raise

    @pytest.mark.asyncio
    async def test_empty_net_saves_nothing(self, tmp_path):
        ncs = make_ncs(config=make_config(net_sessions_dir=tmp_path, ncs_zone=""))
        await ncs._handle_start()
        await ncs._handle_end()
        assert list(tmp_path.glob("*.json")) == []
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/unit/plugins/test_ncs.py -k NetSessionSave -v`
Expected: FAIL — `AttributeError: 'NCSPlugin' object has no attribute '_started_at'`

- [ ] **Step 3: Implement**

In `make_config` in `backend/tests/unit/plugins/test_ncs.py`, add to `defaults`:

```python
        net_sessions_dir="/tmp/net_sessions",
```

In `backend/plugins/ncs.py` `__init__`, after `self._session_rx: list[str] = []` (line 263):

```python
        # Wall-clock start of the current net, for the saved session record.
        self._started_at: float | None = None
```

In `_handle_start`, after `self._current_call_key = None` (line 406):

```python
        self._started_at = datetime.datetime.now(tz=datetime.timezone.utc).timestamp()
```

In `_handle_end`, replace the journal-dispatch block (lines 427-428) with:

```python
        if self._session_rx or self._roster:
            asyncio.create_task(self._save_ncs_journal(), name="ncs-journal")
            asyncio.create_task(self._save_net_session(), name="ncs-net-session")
```

Add this method immediately after `_save_ncs_journal` (after line 707):

```python
    async def _save_net_session(self) -> None:
        """Write the structured session record alongside the narrative journal.

        Failure is logged and swallowed — a net that has already ended must not
        be reported as still running because history could not be written.
        """
        from backend.persistence.net_sessions import NET_TYPE_NCS, save_session
        config = self._get_config()
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        started = self._started_at
        try:
            path = save_session(
                net_type=NET_TYPE_NCS,
                started_at=(
                    datetime.datetime.fromtimestamp(started, tz=datetime.timezone.utc)
                    .isoformat(timespec="seconds")
                    if started else ""
                ),
                ended_at=now.isoformat(timespec="seconds"),
                duration_seconds=round(now.timestamp() - started) if started else 0,
                roster=list(self._roster.values()),
                transcript="\n".join(self._session_rx),
                sessions_dir=config.net_sessions_dir,
            )
            _log.info("NCS net session saved: %s", path)
        except Exception as exc:
            _log.error("NCS net session save failed: %s", exc)
```

- [ ] **Step 4: Run tests and verify they pass**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/unit/plugins/test_ncs.py -v`
Expected: PASS (new tests plus the existing suite, which must stay green)

- [ ] **Step 5: Commit**

```bash
git add backend/plugins/ncs.py backend/tests/unit/plugins/test_ncs.py
git commit -m "feat: save a net session record when an NCS net ends"
```

---

### Task 4: Neighborhood net writes sessions

**Files:**
- Modify: `backend/neighborhood/net.py` (`end()` line 47-63)
- Modify: `backend/server.py` (`neighborhood_end` handler, lines 3890-3921)
- Modify: `backend/tests/unit/neighborhood/test_net.py`

**Interfaces:**
- Consumes: `save_session`, `NET_TYPE_NEIGHBORHOOD` (Task 1).
- Produces: `NeighborhoodNet.end()` summary gains `started_at` and `ended_at` ISO strings alongside the existing `roster` and `duration_seconds`.

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/unit/neighborhood/test_net.py`:

```python
class TestEndTimestamps:
    def test_end_reports_start_and_end_times(self):
        net = NeighborhoodNet()
        net.checkin("u1", "WRAB123", "Sam", "Zeeland")
        net.start()
        summary = net.end()
        assert summary["started_at"].endswith("Z")
        assert summary["ended_at"].endswith("Z")
        assert summary["ended_at"] >= summary["started_at"]

    def test_end_without_start_has_blank_started_at(self):
        net = NeighborhoodNet()
        net.checkin("u1", "WRAB123", "Sam", "Zeeland")
        summary = net.end()
        assert summary["started_at"] == ""
        assert summary["duration_seconds"] == 0
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/unit/neighborhood/test_net.py -k EndTimestamps -v`
Expected: FAIL — `KeyError: 'started_at'`

- [ ] **Step 3: Add timestamps to the state machine**

In `backend/neighborhood/net.py`, replace the body of `end()` (lines 55-63) with:

```python
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
        self._started_at = None
        return summary
```

Add to the imports at the top of that file (after `import time`):

```python
import datetime
```

- [ ] **Step 4: Save the session in the server handler**

In `backend/server.py`, inside the `neighborhood_end` branch, replace line 3894 with:

```python
                summary = _neighborhood.end() if _neighborhood is not None else {"roster": []}
```

(unchanged — shown for context), then insert the session save immediately after the journal `try/except` block ends (after line 3921), still inside `if roster_snapshot and _config is not None:`:

```python
                    try:
                        session_path = save_net_session(
                            net_type=NET_TYPE_NEIGHBORHOOD,
                            started_at=summary.get("started_at", ""),
                            ended_at=summary.get("ended_at", ""),
                            duration_seconds=summary.get("duration_seconds", 0),
                            roster=roster_snapshot,
                            transcript=roster_lines,
                            sessions_dir=_config.net_sessions_dir,
                        )
                        _log.info("Neighborhood net session saved: %s", session_path)
                    except Exception as exc:
                        _log.error("Neighborhood net session save failed: %s", exc)
```

Add to the imports near the other persistence imports in `backend/server.py`:

```python
from backend.persistence.net_sessions import (
    NET_TYPE_NEIGHBORHOOD,
    delete_session as delete_net_session,
    load_session as load_net_session,
    load_session_summaries as load_net_session_summaries,
    save_session as save_net_session,
)
from backend.persistence.net_stats import compute_attendance_stats
```

- [ ] **Step 5: Run tests and verify they pass**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/unit/neighborhood/ -v && python -m pytest backend/tests/ -q`
Expected: PASS — new tests green, whole backend suite still green

- [ ] **Step 6: Commit**

```bash
git add backend/neighborhood/net.py backend/server.py backend/tests/unit/neighborhood/test_net.py
git commit -m "feat: save a net session record when a neighborhood net ends"
```

---

### Task 5: WebSocket handlers

**Files:**
- Modify: `backend/server.py` (new branches beside the journal handlers, which end at line 3167)

**Interfaces:**
- Consumes: `load_net_session_summaries`, `load_net_session`, `delete_net_session`, `compute_attendance_stats` (imported in Task 4); `_contacts_store` for names; `state.is_admin` for the delete gate.
- Produces: client-bound messages `{"type": "net_sessions", "sessions": [...], "stats": [...]}`, `{"type": "net_session", "session": {...} | None}`, `{"type": "net_session_deleted", "id": "..."}`. Client-sent types accepted: `list_net_sessions`, `get_net_session`, `delete_net_session`.

- [ ] **Step 1: Add the handlers**

In `backend/server.py`, immediately after the `unpublish_journal` branch (line 3167), insert:

```python
            elif msg_type == "list_net_sessions":
                if _config is None:
                    await _manager.send_to(ws, {
                        "type": "net_sessions", "sessions": [], "stats": [],
                    })
                    continue
                summaries = load_net_session_summaries(_config.net_sessions_dir)
                contacts = _contacts_store.get_all() if _contacts_store else []
                await _manager.send_to(ws, {
                    "type": "net_sessions",
                    "sessions": summaries,
                    "stats": compute_attendance_stats(summaries, contacts),
                })

            elif msg_type == "get_net_session":
                if _config is None:
                    await _manager.send_to(ws, {"type": "net_session", "session": None})
                    continue
                session_id = (data.get("id") or "").strip()
                await _manager.send_to(ws, {
                    "type": "net_session",
                    "session": load_net_session(session_id, _config.net_sessions_dir),
                })

            elif msg_type == "delete_net_session":
                # Admin-gated: net history is the household's record of who was
                # on the air, so deleting it is a stricter act than reading it.
                if not state.is_admin:
                    await _manager.send_to(ws, {
                        "type": "error", "detail": "Admin access required.",
                    })
                    continue
                if _config is None:
                    await _manager.send_to(ws, {"type": "error", "detail": "Server not ready."})
                    continue
                session_id = (data.get("id") or "").strip()
                try:
                    delete_net_session(session_id, _config.net_sessions_dir)
                    await _manager.send_to(ws, {
                        "type": "net_session_deleted", "id": session_id,
                    })
                    if _audit_log:
                        _audit_log.log(
                            "admin_action", user_id=state.user_id, ip=client_ip,
                            detail=f"delete_net_session {session_id}",
                        )
                except (ValueError, OSError) as exc:
                    await _manager.send_to(ws, {"type": "error", "detail": str(exc)})
```

Verified against the codebase while planning: `_contacts_store.get_all()` is the accessor used elsewhere (`server.py:570`), `state.is_admin` is the admin flag (`server.py:2892`), `client_ip` is in scope for the whole WebSocket handler (`server.py:2600`), and `AuditLog.log(event, *, user_id, ip, detail)` matches the call above (`backend/persistence/audit.py:31`), with `admin_action` already used as an event name (`server.py:3065`).

- [ ] **Step 2: Verify the module imports cleanly**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -c "import backend.server" && python -m pytest backend/tests/ -q`
Expected: import succeeds, whole suite still green

- [ ] **Step 3: Commit**

```bash
git add backend/server.py
git commit -m "feat: expose net session history over the websocket"
```

---

### Task 6: Frontend types, shared download helper, CSV builders

**Files:**
- Modify: `frontend/src/types/ws.ts` (types near the journal block at line 202; union ends line 750)
- Create: `frontend/src/utils/download.ts`
- Modify: `frontend/src/components/ContactsDialog/ContactsDialog.tsx` (remove local `downloadText`, lines 97-105)
- Create: `frontend/src/netsessions/csv.ts`
- Create: `frontend/src/netsessions/__tests__/csv.test.ts`

**Interfaces:**
- Consumes: the message shapes produced in Task 5.
- Produces: TypeScript types `NetSessionStation`, `NetSessionSummary`, `NetSessionRosterRow`, `NetSessionDetail`, `AttendanceStatRow`, `NetSessionsMsg`, `NetSessionMsg`, `NetSessionDeletedMsg`; `downloadText(text, filename, mime)` from `utils/download`; `sessionToCsv(session)` and `allSessionsToCsv(sessions)` from `netsessions/csv`.

- [ ] **Step 1: Write failing CSV tests**

Create `frontend/src/netsessions/__tests__/csv.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { sessionToCsv, allSessionsToCsv } from '../csv'
import type { NetSessionDetail, NetSessionSummary } from '../../types/ws'

const SESSION: NetSessionDetail = {
  id: '20260801_190000_neighborhood',
  net_type: 'neighborhood',
  started_at: '2026-08-01T19:00:00Z',
  ended_at: '2026-08-01T19:52:00Z',
  duration_seconds: 3120,
  transcript: 'irrelevant',
  roster: [
    {
      callsign: 'KD8ABC', name: 'Maria', location: 'Holland',
      status: 'CheckedIn', traffic: 'Routine',
      checkin_time: '2026-08-01T19:01:00Z', verified: true,
    },
    {
      callsign: 'WRAB123', name: 'Sam "Radio" Jones', location: 'Zeeland',
      status: 'Standby', traffic: null,
      checkin_time: '2026-08-01T19:03:00Z', verified: false,
    },
  ],
}

describe('sessionToCsv', () => {
  it('writes a header and one row per check-in', () => {
    const lines = sessionToCsv(SESSION).split('\n')
    expect(lines[0]).toBe('callsign,name,location,status,traffic,checkin_time')
    expect(lines).toHaveLength(3)
    expect(lines[1]).toContain('"KD8ABC"')
    expect(lines[1]).toContain('"Routine"')
  })

  it('escapes embedded quotes', () => {
    expect(sessionToCsv(SESSION)).toContain('"Sam ""Radio"" Jones"')
  })

  it('renders a null traffic value as empty', () => {
    const row = sessionToCsv(SESSION).split('\n')[2]
    expect(row).toContain('"WRAB123","Sam ""Radio"" Jones","Zeeland","Standby",""')
  })

  it('returns just the header for an empty roster', () => {
    const empty = { ...SESSION, roster: [] }
    expect(sessionToCsv(empty)).toBe('callsign,name,location,status,traffic,checkin_time')
  })
})

describe('allSessionsToCsv', () => {
  const SUMMARIES: NetSessionSummary[] = [
    {
      id: '20260802_190000_ncs', net_type: 'ncs',
      started_at: '2026-08-02T19:00:00Z', ended_at: '2026-08-02T19:30:00Z',
      duration_seconds: 1800, checkin_count: 1,
      stations: [{ callsign: 'KD8ABC', name: 'Maria' }],
    },
    {
      id: '20260801_190000_neighborhood', net_type: 'neighborhood',
      started_at: '2026-08-01T19:00:00Z', ended_at: '2026-08-01T19:52:00Z',
      duration_seconds: 3120, checkin_count: 2,
      stations: [
        { callsign: 'KD8ABC', name: 'Maria' },
        { callsign: 'WRAB123', name: 'Sam' },
      ],
    },
  ]

  it('writes one row per station per net, with net columns', () => {
    const lines = allSessionsToCsv(SUMMARIES).split('\n')
    expect(lines[0]).toBe('net_id,net_type,net_date,callsign,name')
    expect(lines).toHaveLength(4)
    expect(lines[1]).toContain('"20260802_190000_ncs"')
    expect(lines[1]).toContain('"2026-08-02"')
  })

  it('returns just the header when there are no sessions', () => {
    expect(allSessionsToCsv([])).toBe('net_id,net_type,net_date,callsign,name')
  })
})
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `cd /mnt/storage/Repos/Radio-TTY/frontend && npx vitest run src/netsessions`
Expected: FAIL — cannot resolve `../csv`

- [ ] **Step 3: Add the types**

In `frontend/src/types/ws.ts`, after the journal block (after line 211), insert:

```ts
export interface NetSessionStation {
  callsign: string;
  name: string;
}

export interface NetSessionSummary {
  id: string;
  net_type: string;
  started_at: string;
  ended_at: string;
  duration_seconds: number;
  checkin_count: number;
  stations: NetSessionStation[];
}

export interface NetSessionRosterRow {
  callsign: string;
  name: string;
  location: string;
  status: string;
  traffic: string | null;
  checkin_time: string;
  verified: boolean;
}

export interface NetSessionDetail {
  id: string;
  net_type: string;
  started_at: string;
  ended_at: string;
  duration_seconds: number;
  roster: NetSessionRosterRow[];
  transcript: string;
}

export interface AttendanceStatRow {
  callsign: string;
  name: string;
  total_nets: number;
  attended_of_recent: number;
  recent_window: number;
  current_streak: number;
  last_seen: string;
}

export interface NetSessionsMsg {
  type: 'net_sessions';
  sessions: NetSessionSummary[];
  stats: AttendanceStatRow[];
}

export interface NetSessionMsg {
  type: 'net_session';
  session: NetSessionDetail | null;
}

export interface NetSessionDeletedMsg {
  type: 'net_session_deleted';
  id: string;
}
```

Then add three entries to the `ServerMsg` union — insert before the final `| VoiceTxAckMsg` / `| VoiceTxErrorMsg;` lines (749-750):

```ts
  | NetSessionsMsg
  | NetSessionMsg
  | NetSessionDeletedMsg
```

- [ ] **Step 4: Extract the shared download helper**

Create `frontend/src/utils/download.ts`:

```ts
/** Trigger a browser download of in-memory text as a file. */
export function downloadText(text: string, filename: string, mime: string) {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
```

In `frontend/src/components/ContactsDialog/ContactsDialog.tsx`, delete the local `downloadText` function (lines 97-105) and add to the imports at the top of the file:

```ts
import { downloadText } from '../../utils/download';
```

- [ ] **Step 5: Write the CSV builders**

Create `frontend/src/netsessions/csv.ts`:

```ts
import type { NetSessionDetail, NetSessionSummary } from '../types/ws';

function quote(value: string | number | null): string {
  return `"${String(value ?? '').replace(/"/g, '""')}"`;
}

/** One session's roster: header plus one row per check-in. */
export function sessionToCsv(session: NetSessionDetail): string {
  const header = 'callsign,name,location,status,traffic,checkin_time';
  const rows = session.roster.map((r) =>
    [r.callsign, r.name, r.location, r.status, r.traffic ?? '', r.checkin_time]
      .map(quote)
      .join(',')
  );
  return [header, ...rows].join('\n');
}

/** Every net: header plus one row per station per net. */
export function allSessionsToCsv(sessions: NetSessionSummary[]): string {
  const header = 'net_id,net_type,net_date,callsign,name';
  const rows = sessions.flatMap((s) =>
    s.stations.map((station) =>
      [s.id, s.net_type, s.started_at.slice(0, 10), station.callsign, station.name]
        .map(quote)
        .join(',')
    )
  );
  return [header, ...rows].join('\n');
}
```

- [ ] **Step 6: Run tests and verify they pass**

Run: `cd /mnt/storage/Repos/Radio-TTY/frontend && npx vitest run src/netsessions src/components/ContactsDialog && npx tsc --noEmit`
Expected: PASS — CSV tests green, contacts tests still green, no type errors

- [ ] **Step 7: Commit**

```bash
git add frontend/src/types/ws.ts frontend/src/utils/download.ts frontend/src/netsessions frontend/src/components/ContactsDialog/ContactsDialog.tsx
git commit -m "feat: add net session types and csv builders"
```

---

### Task 7: PastNetsTab component

**Files:**
- Create: `frontend/src/components/JournalPanel/PastNetsTab.tsx`
- Create: `frontend/src/components/JournalPanel/__tests__/PastNetsTab.test.tsx`

**Interfaces:**
- Consumes: types and CSV builders from Task 6; `downloadText` from `utils/download`.
- Produces: `<PastNetsTab sessions stats selected isAdmin onSelect onDelete />` where `onSelect(id: string)` requests one session's detail and `onDelete(id: string)` deletes it. `selected` is a `NetSessionDetail | null` supplied by the parent.

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/JournalPanel/__tests__/PastNetsTab.test.tsx`:

```tsx
import { render as rtlRender, screen, fireEvent } from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi } from 'vitest'
import { PastNetsTab } from '../PastNetsTab'
import type { NetSessionSummary, NetSessionDetail, AttendanceStatRow } from '../../../types/ws'

function render(ui: React.ReactElement) {
  return rtlRender(<ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>)
}

const SESSIONS: NetSessionSummary[] = [
  {
    id: '20260802_190000_ncs', net_type: 'ncs',
    started_at: '2026-08-02T19:00:00Z', ended_at: '2026-08-02T19:30:00Z',
    duration_seconds: 1800, checkin_count: 1,
    stations: [{ callsign: 'KD8ABC', name: 'Maria' }],
  },
  {
    id: '20260801_190000_neighborhood', net_type: 'neighborhood',
    started_at: '2026-08-01T19:00:00Z', ended_at: '2026-08-01T19:52:00Z',
    duration_seconds: 3120, checkin_count: 2,
    stations: [
      { callsign: 'KD8ABC', name: 'Maria' },
      { callsign: 'WRAB123', name: 'Sam' },
    ],
  },
]

const STATS: AttendanceStatRow[] = [
  {
    callsign: 'KD8ABC', name: 'Maria', total_nets: 2,
    attended_of_recent: 2, recent_window: 2, current_streak: 2,
    last_seen: '2026-08-02T19:00:00Z',
  },
]

const DETAIL: NetSessionDetail = {
  id: '20260802_190000_ncs', net_type: 'ncs',
  started_at: '2026-08-02T19:00:00Z', ended_at: '2026-08-02T19:30:00Z',
  duration_seconds: 1800,
  transcript: 'KD8ABC: nothing to report',
  roster: [{
    callsign: 'KD8ABC', name: 'Maria', location: 'Holland',
    status: 'CheckedIn', traffic: 'Routine',
    checkin_time: '2026-08-02T19:01:00Z', verified: true,
  }],
}

function props(overrides = {}) {
  return {
    sessions: SESSIONS, stats: STATS, selected: null, isAdmin: false,
    onSelect: vi.fn(), onDelete: vi.fn(),
    ...overrides,
  }
}

describe('PastNetsTab', () => {
  it('lists every session with its date and check-in count', () => {
    render(<PastNetsTab {...props()} />)
    expect(screen.getByText('2026-08-02')).toBeInTheDocument()
    expect(screen.getByText('2026-08-01')).toBeInTheDocument()
    expect(screen.getByText(/2 check-ins/)).toBeInTheDocument()
  })

  it('shows an empty state when there are no sessions', () => {
    render(<PastNetsTab {...props({ sessions: [], stats: [] })} />)
    expect(screen.getByText(/No nets recorded yet/i)).toBeInTheDocument()
  })

  it('requests a session detail when one is clicked', () => {
    const onSelect = vi.fn()
    render(<PastNetsTab {...props({ onSelect })} />)
    fireEvent.click(screen.getByText('2026-08-02'))
    expect(onSelect).toHaveBeenCalledWith('20260802_190000_ncs')
  })

  it('renders the selected session roster', () => {
    render(<PastNetsTab {...props({ selected: DETAIL })} />)
    expect(screen.getByText('KD8ABC')).toBeInTheDocument()
    expect(screen.getByText('Holland')).toBeInTheDocument()
    expect(screen.getByText('Routine')).toBeInTheDocument()
  })

  it('shows attendance stats', () => {
    render(<PastNetsTab {...props()} />)
    expect(screen.getByText(/Maria/)).toBeInTheDocument()
    expect(screen.getByText(/2 of last 2/)).toBeInTheDocument()
  })

  it('hides the delete control from non-admins', () => {
    render(<PastNetsTab {...props({ selected: DETAIL })} />)
    expect(screen.queryByRole('button', { name: /delete net record/i })).not.toBeInTheDocument()
  })

  it('deletes after a confirming second click for admins', () => {
    const onDelete = vi.fn()
    render(<PastNetsTab {...props({ selected: DETAIL, isAdmin: true, onDelete })} />)
    const button = screen.getByRole('button', { name: /delete net record/i })
    fireEvent.click(button)
    expect(onDelete).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: /confirm delete/i }))
    expect(onDelete).toHaveBeenCalledWith('20260802_190000_ncs')
  })
})
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `cd /mnt/storage/Repos/Radio-TTY/frontend && npx vitest run src/components/JournalPanel/__tests__/PastNetsTab.test.tsx`
Expected: FAIL — cannot resolve `../PastNetsTab`

- [ ] **Step 3: Write the component**

Create `frontend/src/components/JournalPanel/PastNetsTab.tsx`:

```tsx
import { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Chip,
  TableContainer,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import DeleteIcon from '@mui/icons-material/Delete';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import type {
  AttendanceStatRow,
  NetSessionDetail,
  NetSessionSummary,
} from '../../types/ws';
import { downloadText } from '../../utils/download';
import { sessionToCsv, allSessionsToCsv } from '../../netsessions/csv';

interface Props {
  sessions: NetSessionSummary[];
  stats: AttendanceStatRow[];
  selected: NetSessionDetail | null;
  isAdmin: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}

const NET_TYPE_LABELS: Record<string, string> = {
  ncs: 'Net Control',
  neighborhood: 'Neighborhood',
};

function formatDuration(seconds: number): string {
  const minutes = Math.round(seconds / 60);
  return `${minutes} min`;
}

export function PastNetsTab({
  sessions,
  stats,
  selected,
  isAdmin,
  onSelect,
  onDelete,
}: Props) {
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  function handleDelete(id: string) {
    if (confirmDelete === id) {
      onDelete(id);
      setConfirmDelete(null);
    } else {
      setConfirmDelete(id);
    }
  }

  return (
    <Box sx={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* Left: session list */}
      <Box
        sx={{
          width: 240,
          borderRight: 1,
          borderColor: 'divider',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          flexShrink: 0,
        }}
      >
        <Box sx={{ flex: 1, overflowY: 'auto' }}>
          {sessions.length === 0 ? (
            <Typography
              variant="body2"
              sx={{ color: 'text.secondary', p: 1.5, fontStyle: 'italic' }}
            >
              No nets recorded yet. Records appear here after a net ends.
            </Typography>
          ) : (
            <List dense disablePadding aria-label="Past nets">
              {sessions.map((s) => (
                <ListItem key={s.id} disablePadding>
                  <ListItemButton
                    selected={selected?.id === s.id}
                    onClick={() => onSelect(s.id)}
                  >
                    <ListItemText
                      primary={s.started_at.slice(0, 10)}
                      secondary={`${NET_TYPE_LABELS[s.net_type] ?? s.net_type} · ${s.checkin_count} check-ins · ${formatDuration(s.duration_seconds)}`}
                      slotProps={{
                        primary: {
                          variant: 'body2',
                          sx: { fontWeight: selected?.id === s.id ? 700 : 400 },
                        },
                        secondary: { variant: 'caption' },
                      }}
                    />
                  </ListItemButton>
                </ListItem>
              ))}
            </List>
          )}
        </Box>

        {sessions.length > 0 && (
          <Box sx={{ p: 1, borderTop: 1, borderColor: 'divider' }}>
            <Button
              fullWidth
              variant="outlined"
              size="small"
              startIcon={<DownloadIcon />}
              onClick={() =>
                downloadText(allSessionsToCsv(sessions), 'net-history.csv', 'text/csv')
              }
            >
              EXPORT ALL (CSV)
            </Button>
          </Box>
        )}
      </Box>

      {/* Right: detail + stats */}
      <Box sx={{ flex: 1, overflowY: 'auto', p: 2 }}>
        {selected ? (
          <Box sx={{ mb: 3 }}>
            <Typography variant="caption" color="text.secondary">
              {selected.started_at} → {selected.ended_at}
            </Typography>
            <Typography variant="h5" sx={{ mt: 0.5, mb: 2 }}>
              {NET_TYPE_LABELS[selected.net_type] ?? selected.net_type} net —{' '}
              {selected.started_at.slice(0, 10)}
            </Typography>

            <TableContainer component={Paper} variant="outlined" sx={{ mb: 2 }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell scope="col" sx={{ fontWeight: 700 }}>Callsign</TableCell>
                    <TableCell scope="col" sx={{ fontWeight: 700 }}>Name</TableCell>
                    <TableCell scope="col" sx={{ fontWeight: 700 }}>Location</TableCell>
                    <TableCell scope="col" sx={{ fontWeight: 700 }}>Status</TableCell>
                    <TableCell scope="col" sx={{ fontWeight: 700 }}>Traffic</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {selected.roster.map((r, i) => (
                    <TableRow key={`${r.callsign}-${r.name}-${i}`}>
                      <TableCell>{r.callsign}</TableCell>
                      <TableCell>{r.name}</TableCell>
                      <TableCell>{r.location}</TableCell>
                      <TableCell>{r.status}</TableCell>
                      <TableCell>{r.traffic ?? ''}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>

            {selected.transcript && (
              <Accordion sx={{ mb: 2 }}>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="body2">Net transcript</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Box
                    component="pre"
                    sx={{ fontSize: '0.875rem', overflowX: 'auto', whiteSpace: 'pre-wrap', m: 0 }}
                  >
                    {selected.transcript}
                  </Box>
                </AccordionDetails>
              </Accordion>
            )}

            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                variant="contained"
                size="small"
                startIcon={<DownloadIcon />}
                onClick={() =>
                  downloadText(sessionToCsv(selected), `${selected.id}.csv`, 'text/csv')
                }
              >
                DOWNLOAD CSV
              </Button>
              {isAdmin && (
                <Button
                  variant="outlined"
                  size="small"
                  color={confirmDelete === selected.id ? 'error' : 'inherit'}
                  startIcon={<DeleteIcon />}
                  onClick={() => handleDelete(selected.id)}
                  aria-label={
                    confirmDelete === selected.id ? 'Confirm delete' : 'Delete net record'
                  }
                >
                  {confirmDelete === selected.id ? 'CONFIRM DELETE' : 'DELETE'}
                </Button>
              )}
            </Box>
          </Box>
        ) : (
          <Typography sx={{ color: 'text.secondary', fontStyle: 'italic', mb: 3 }}>
            Select a net to see its roster.
          </Typography>
        )}

        {stats.length > 0 && (
          <Box>
            <Typography variant="h6" sx={{ mb: 1 }}>ATTENDANCE</Typography>
            <List dense disablePadding aria-label="Attendance statistics">
              {stats.map((row) => (
                <ListItem key={row.callsign} disableGutters>
                  <ListItemText
                    primary={`${row.name || row.callsign} (${row.callsign})`}
                    secondary={`${row.total_nets} nets · ${row.attended_of_recent} of last ${row.recent_window} · streak ${row.current_streak}`}
                    slotProps={{
                      primary: { variant: 'body2' },
                      secondary: { variant: 'caption' },
                    }}
                  />
                  {row.current_streak >= 3 && (
                    <Chip label={`${row.current_streak} in a row`} size="small" color="success" />
                  )}
                </ListItem>
              ))}
            </List>
          </Box>
        )}
      </Box>
    </Box>
  );
}
```

- [ ] **Step 4: Run tests and verify they pass**

Run: `cd /mnt/storage/Repos/Radio-TTY/frontend && npx vitest run src/components/JournalPanel/__tests__/PastNetsTab.test.tsx && npx tsc --noEmit`
Expected: PASS, no type errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/JournalPanel/PastNetsTab.tsx frontend/src/components/JournalPanel/__tests__/PastNetsTab.test.tsx
git commit -m "feat: add past nets tab component"
```

---

### Task 8: Tab bar and App wiring

**Files:**
- Modify: `frontend/src/components/JournalPanel/JournalPanel.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/DesktopApp/DesktopApp.tsx:422`
- Modify: `frontend/src/components/MobileApp/MobileApp.tsx:439`
- Modify: `frontend/src/components/JournalPanel/__tests__/JournalPanel.test.tsx`

**Interfaces:**
- Consumes: `PastNetsTab` (Task 7); the WS messages from Task 5.
- Produces: `JournalPanel` accepts six new props — `netSessions: NetSessionSummary[]`, `attendanceStats: AttendanceStatRow[]`, `selectedNetSession: NetSessionDetail | null`, `isAdmin: boolean`, `onListNetSessions: () => void`, `onSelectNetSession: (id: string) => void`, `onDeleteNetSession: (id: string) => void`.

- [ ] **Step 1: Write a failing tab test**

Append to `frontend/src/components/JournalPanel/__tests__/JournalPanel.test.tsx` (extend the existing default-props helper in that file with the new props, all inert defaults):

```tsx
describe('JournalPanel tabs', () => {
  it('shows the journal list by default', () => {
    render(<JournalPanel {...defaultProps()} />)
    expect(screen.getByText('JOURNALS')).toBeInTheDocument()
  })

  it('switches to past nets and requests the list', async () => {
    const onListNetSessions = vi.fn()
    render(<JournalPanel {...defaultProps({ onListNetSessions })} />)
    await userEvent.click(screen.getByRole('tab', { name: /past nets/i }))
    expect(screen.getByText(/No nets recorded yet/i)).toBeInTheDocument()
    expect(onListNetSessions).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `cd /mnt/storage/Repos/Radio-TTY/frontend && npx vitest run src/components/JournalPanel`
Expected: FAIL — no element with role `tab` named "Past nets"

- [ ] **Step 3: Add the tab bar to JournalPanel**

In `frontend/src/components/JournalPanel/JournalPanel.tsx`:

Add to the MUI import list (line 2-23): `Tabs`, `Tab`. Add below the existing imports:

```tsx
import { PastNetsTab } from './PastNetsTab';
import type {
  AttendanceStatRow,
  NetSessionDetail,
  NetSessionSummary,
} from '../../types/ws';
```

Add to the `Props` interface (after `fillHeight?: boolean;`, line 51):

```tsx
  netSessions: NetSessionSummary[];
  attendanceStats: AttendanceStatRow[];
  selectedNetSession: NetSessionDetail | null;
  isAdmin: boolean;
  onListNetSessions: () => void;
  onSelectNetSession: (id: string) => void;
  onDeleteNetSession: (id: string) => void;
```

Add the same names to the destructured parameter list (after `fillHeight = false,`, line 91).

Add tab state beside the other `useState` calls (after line 100):

```tsx
  const [tab, setTab] = useState<'journals' | 'nets'>('journals');
```

Replace the `return (` block's outer `<Paper>` opening (lines 167-177) so tabs sit above the existing two-column body. The existing body becomes the content of the `journals` tab:

```tsx
  return (
    <Paper
      square
      elevation={0}
      sx={{
        display: 'flex',
        flexDirection: 'column',
        borderBottom: 1,
        borderColor: 'divider',
        ...(fillHeight ? { height: '100%' } : { maxHeight: 360 }),
        overflow: 'hidden',
      }}
    >
      <Tabs
        value={tab}
        onChange={(_, next) => {
          setTab(next);
          if (next === 'nets') onListNetSessions();
        }}
        sx={{ borderBottom: 1, borderColor: 'divider', minHeight: 40 }}
      >
        <Tab value="journals" label="Journal" sx={{ minHeight: 40 }} />
        <Tab value="nets" label="Past Nets" sx={{ minHeight: 40 }} />
      </Tabs>

      {tab === 'nets' ? (
        <PastNetsTab
          sessions={netSessions}
          stats={attendanceStats}
          selected={selectedNetSession}
          isAdmin={isAdmin}
          onSelect={onSelectNetSession}
          onDelete={onDeleteNetSession}
        />
      ) : (
        <Box sx={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
```

…then close that new `<Box>` and the conditional immediately before the final `</Paper>` (line 372):

```tsx
        </Box>
      )}
    </Paper>
  );
}
```

The two existing children (the 240px list column and the detail column) stay exactly as they are, now nested inside the new `<Box>`.

- [ ] **Step 4: Wire state and messages in App.tsx**

In `frontend/src/App.tsx`, add state beside the journal state (after line 330):

```tsx
  const [netSessions, setNetSessions] = useState<NetSessionSummary[]>([]);
  const [attendanceStats, setAttendanceStats] = useState<AttendanceStatRow[]>([]);
  const [selectedNetSession, setSelectedNetSession] = useState<NetSessionDetail | null>(null);
```

Add those three type names to the existing `import type { … } from './types/ws'` list.

Add message cases beside the journal cases (after the `journal_deleted` case, line 762):

```tsx
      case 'net_sessions':
        setNetSessions(msg.sessions);
        setAttendanceStats(msg.stats);
        break;

      case 'net_session':
        setSelectedNetSession(msg.session);
        break;

      case 'net_session_deleted':
        setSelectedNetSession(null);
        sendRef.current({ type: 'list_net_sessions' });
        break;
```

Add handlers beside the journal handlers (after the `unpublish_journal` handler, line 1444):

```tsx
  const handleListNetSessions = useCallback(() => {
    send({ type: 'list_net_sessions' });
  }, [send]);

  const handleSelectNetSession = useCallback((id: string) => {
    send({ type: 'get_net_session', id });
  }, [send]);

  const handleDeleteNetSession = useCallback((id: string) => {
    send({ type: 'delete_net_session', id });
  }, [send]);
```

Match the surrounding handlers' style — if the neighbours are plain functions rather than `useCallback`, write plain functions instead.

Add to the props object returned to the app shells (beside `journals`, line 1612):

```tsx
    netSessions,
    attendanceStats,
    selectedNetSession,
    onListNetSessions: handleListNetSessions,
    onSelectNetSession: handleSelectNetSession,
    onDeleteNetSession: handleDeleteNetSession,
```

- [ ] **Step 5: Pass the props through both shells**

In `frontend/src/components/DesktopApp/DesktopApp.tsx`, extend the props interface (beside `journals: JournalEntry[];`, line 64) and the destructuring (line 181-198) with the six new names, then extend the `<JournalPanel …>` call (line 422):

```tsx
          netSessions={netSessions} attendanceStats={attendanceStats}
          selectedNetSession={selectedNetSession} isAdmin={!!profile.is_admin}
          onListNetSessions={onListNetSessions}
          onSelectNetSession={onSelectNetSession}
          onDeleteNetSession={onDeleteNetSession}
```

Apply the identical change to `frontend/src/components/MobileApp/MobileApp.tsx` at line 439.

Both shells already receive `profile: UserProfile` (`DesktopApp.tsx:36`, destructured at `:181`), and `MobileApp.tsx:383` already passes `isAdmin={!!profile.is_admin}` to another child. So `isAdmin` needs no new threading from `App.tsx` — read it off `profile` in each shell.

- [ ] **Step 6: Run the full frontend suite**

Run: `cd /mnt/storage/Repos/Radio-TTY/frontend && npx tsc --noEmit && npx vitest run && npm run build`
Expected: no type errors, all tests pass, build succeeds

- [ ] **Step 7: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/JournalPanel frontend/src/components/DesktopApp/DesktopApp.tsx frontend/src/components/MobileApp/MobileApp.tsx
git commit -m "feat: add past nets tab to the journal panel"
```

---

### Task 9: CheckedOut status (stretch)

**Files:**
- Modify: `backend/plugins/ncs.py:316` (status validation), `:648-652` (`_handle_call_next`)
- Modify: `backend/server.py:3875` (neighborhood status validation)
- Modify: `backend/neighborhood/net.py:104` (`call_next` filter — already filters on `checked_in`, so verify no change is needed)
- Modify: `frontend/src/components/NCSPanel/NCSPanel.tsx:34,46-48,183-184,388-392`
- Modify: `backend/tests/unit/plugins/test_ncs.py`, `frontend/src/components/NCSPanel/__tests__/NCSPanel.test.tsx`

**Interfaces:**
- Produces: `CheckedOut` accepted by `ncs_status_update`; `checked_out` accepted by `neighborhood_status`. `CheckedOut` rows stay in the roster and the saved record but are skipped by the round-table caller. The status cycle in the UI becomes CheckedIn → Standby → CheckedOut → CheckedIn.

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/unit/plugins/test_ncs.py`:

```python
class TestCheckedOutStatus:
    @pytest.mark.asyncio
    async def test_status_update_accepts_checked_out(self):
        ncs = make_ncs(config=make_config(ncs_zone=""))
        ncs._roster["KD8ABC|Maria"] = {
            "callsign": "KD8ABC", "status": "CheckedIn", "traffic": "Routine",
            "name": "Maria", "location": "", "checkin_time": 0.0,
            "verified": False, "called": False,
        }
        await ncs.on_client_message_received({
            "type": "ncs_status_update", "callsign": "KD8ABC",
            "name": "Maria", "status": "CheckedOut",
        })
        assert ncs._roster["KD8ABC|Maria"]["status"] == "CheckedOut"

    @pytest.mark.asyncio
    async def test_call_next_skips_checked_out(self):
        ncs = make_ncs(config=make_config(ncs_zone=""))
        await ncs._handle_start()
        ncs._roster["KD8ABC|Maria"] = {
            "callsign": "KD8ABC", "status": "CheckedOut", "traffic": "Routine",
            "name": "Maria", "location": "", "checkin_time": 0.0,
            "verified": False, "called": False,
        }
        ncs._roster["WRAB123|Sam"] = {
            "callsign": "WRAB123", "status": "CheckedIn", "traffic": "Routine",
            "name": "Sam", "location": "", "checkin_time": 0.0,
            "verified": False, "called": False,
        }
        await ncs._handle_call_next()
        assert ncs._roster["KD8ABC|Maria"]["called"] is False
        assert ncs._roster["WRAB123|Sam"]["called"] is True
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/unit/plugins/test_ncs.py -k CheckedOut -v`
Expected: FAIL — status stays `CheckedIn` because `CheckedOut` is not in the accepted tuple

- [ ] **Step 3: Implement the backend**

In `backend/plugins/ncs.py` line 316, extend the accepted statuses:

```python
            if cs and key in self._roster and new_status in ("CheckedIn", "Standby", "CheckedOut", "LoggedOut"):
```

`_handle_call_next` (lines 648-652) already selects only `status == "CheckedIn"`, so `CheckedOut` rows are skipped with no change — the test above pins that behaviour.

In `backend/server.py` line 3875, extend the neighborhood statuses:

```python
                if status not in ("checked_in", "standby", "checked_out"):
```

`NeighborhoodNet.call_next` (net.py line 104) filters on `status == "checked_in"`, so it skips `checked_out` unchanged.

- [ ] **Step 4: Implement the frontend**

In `frontend/src/components/NCSPanel/NCSPanel.tsx`:

Line 34 — extend the union:

```tsx
type StationStatus = 'CheckedIn' | 'Standby' | 'CheckedOut' | 'LoggedOut';
```

Lines 46-48 — add the label:

```tsx
  CheckedIn: '✓ In',
  Standby: 'Stby',
  CheckedOut: 'C/O',
  LoggedOut: 'Out',
```

Lines 182-185 — `handleStatusToggle` cycles three states instead of toggling two. Add a module-level cycle above the component so the tooltip can share it:

```tsx
const STATUS_CYCLE: StationStatus[] = ['CheckedIn', 'Standby', 'CheckedOut'];

function nextStatus(current: string): StationStatus {
  const at = STATUS_CYCLE.indexOf(current as StationStatus);
  return STATUS_CYCLE[(at + 1) % STATUS_CYCLE.length];
}
```

Then replace the body of `handleStatusToggle`:

```tsx
  const handleStatusToggle = useCallback((entry: NCSEntry) => {
    send({
      type: 'ncs_status_update',
      callsign: entry.callsign,
      name: entry.name ?? '',
      status: nextStatus(entry.status),
    });
  }, [send]);
```

Line 388 — the tooltip currently hardcodes the two-state toggle; make it name the real next state:

```tsx
                    <Tooltip title={`Click to set ${nextStatus(entry.status)}`}>
```

Line 392 — give `CheckedOut` its own colour:

```tsx
                        color={entry.status === 'CheckedIn' ? 'success' : entry.status === 'Standby' ? 'warning' : entry.status === 'CheckedOut' ? 'info' : 'default'}
```

Add a matching test to `frontend/src/components/NCSPanel/__tests__/NCSPanel.test.tsx` asserting that clicking a `Standby` chip sends `status: 'CheckedOut'`, following the send-assertion pattern already used in that file.

- [ ] **Step 5: Run tests and verify they pass**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/ -q && cd frontend && npx vitest run && npx tsc --noEmit`
Expected: PASS on both sides

- [ ] **Step 6: Commit**

```bash
git add backend/plugins/ncs.py backend/server.py backend/tests/unit/plugins/test_ncs.py frontend/src/components/NCSPanel
git commit -m "feat: add checked-out status for net rosters"
```

---

### Task 10: Roster sort and search (stretch)

**Files:**
- Modify: `frontend/src/components/NCSPanel/NCSPanel.tsx`
- Modify: `frontend/src/components/NeighborhoodPanel/RosterList.tsx`
- Create: `frontend/src/netsessions/rosterView.ts`
- Create: `frontend/src/netsessions/__tests__/rosterView.test.ts`

**Interfaces:**
- Produces: `filterRoster(rows, query)` and `sortRoster(rows, column, direction)` — generic over any object with string fields, so both panels and the past-net table share one implementation.

- [ ] **Step 1: Write failing tests**

Create `frontend/src/netsessions/__tests__/rosterView.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { filterRoster, sortRoster } from '../rosterView'

const ROWS = [
  { callsign: 'WRAB123', name: 'Sam', location: 'Zeeland' },
  { callsign: 'KD8ABC', name: 'Maria', location: 'Holland' },
  { callsign: 'KE8XYZ', name: 'Alex', location: 'Holland' },
]

describe('filterRoster', () => {
  it('returns every row for a blank query', () => {
    expect(filterRoster(ROWS, '')).toHaveLength(3)
  })

  it('matches a callsign case-insensitively', () => {
    expect(filterRoster(ROWS, 'kd8')).toEqual([ROWS[1]])
  })

  it('matches any string field', () => {
    expect(filterRoster(ROWS, 'holland')).toHaveLength(2)
  })

  it('returns nothing when no row matches', () => {
    expect(filterRoster(ROWS, 'nobody')).toEqual([])
  })
})

describe('sortRoster', () => {
  it('sorts ascending by a column', () => {
    expect(sortRoster(ROWS, 'callsign', 'asc').map((r) => r.callsign))
      .toEqual(['KD8ABC', 'KE8XYZ', 'WRAB123'])
  })

  it('sorts descending', () => {
    expect(sortRoster(ROWS, 'name', 'desc').map((r) => r.name))
      .toEqual(['Sam', 'Maria', 'Alex'])
  })

  it('does not mutate the input', () => {
    const copy = [...ROWS]
    sortRoster(ROWS, 'callsign', 'asc')
    expect(ROWS).toEqual(copy)
  })

  it('returns the original order for a null column', () => {
    expect(sortRoster(ROWS, null, 'asc')).toEqual(ROWS)
  })
})
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `cd /mnt/storage/Repos/Radio-TTY/frontend && npx vitest run src/netsessions/__tests__/rosterView.test.ts`
Expected: FAIL — cannot resolve `../rosterView`

- [ ] **Step 3: Write the helpers**

Create `frontend/src/netsessions/rosterView.ts`:

```ts
export type SortDirection = 'asc' | 'desc';

/** Rows whose string fields contain `query` (case-insensitive). Blank query passes everything. */
export function filterRoster<T extends object>(rows: T[], query: string): T[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return rows;
  return rows.filter((row) =>
    Object.values(row).some(
      (value) => typeof value === 'string' && value.toLowerCase().includes(needle)
    )
  );
}

/** A copy of `rows` sorted by `column`. A null column preserves the original order. */
export function sortRoster<T extends object>(
  rows: T[],
  column: keyof T | null,
  direction: SortDirection
): T[] {
  if (!column) return rows;
  const factor = direction === 'desc' ? -1 : 1;
  return [...rows].sort((a, b) => {
    const left = String(a[column] ?? '');
    const right = String(b[column] ?? '');
    return left.localeCompare(right) * factor;
  });
}
```

- [ ] **Step 4: Use them in both roster tables**

In `frontend/src/components/NCSPanel/NCSPanel.tsx`, add `TableSortLabel` to the MUI imports (`TextField` is already imported) plus:

```tsx
import { filterRoster, sortRoster, type SortDirection } from '../../netsessions/rosterView';
```

Add state and the derived rows beside the other hooks (after `handleRemove`, line 189):

```tsx
  type RosterColumn = 'callsign' | 'status' | 'traffic';

  const [rosterQuery, setRosterQuery] = useState('');
  const [sortColumn, setSortColumn] = useState<RosterColumn | null>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

  const handleSort = useCallback((column: RosterColumn) => {
    if (sortColumn === column) {
      setSortDirection((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortColumn(column);
      setSortDirection('asc');
    }
  }, [sortColumn]);

  const visibleRoster = useMemo(
    () => sortRoster(filterRoster(roster, rosterQuery), sortColumn, sortDirection),
    [roster, rosterQuery, sortColumn, sortDirection],
  );
```

Add `useMemo` to the React import if it is not already there.

Insert a search field directly above the roster table (before the `{roster.length > 0 ? (` at line 349):

```tsx
      {roster.length > 2 && (
        <Box sx={{ px: 2, pb: 1 }}>
          <TextField
            size="small"
            fullWidth
            placeholder="Filter roster"
            value={rosterQuery}
            onChange={(e) => setRosterQuery(e.target.value)}
            aria-label="Filter roster"
          />
        </Box>
      )}
```

Wrap the three sortable header cells (lines 353-355) in `TableSortLabel`:

```tsx
                <TableCell sx={{ fontWeight: 700, py: 0.5 }}>
                  <TableSortLabel
                    active={sortColumn === 'callsign'}
                    direction={sortColumn === 'callsign' ? sortDirection : 'asc'}
                    onClick={() => handleSort('callsign')}
                  >
                    Callsign
                  </TableSortLabel>
                </TableCell>
```

Repeat for `Status` (`'status'`) and `Traffic` (`'traffic'`); leave the `Time` and action cells as plain headers.

Change the body map (line 361) from `roster.map((entry) => (` to `visibleRoster.map((entry) => (`.

Apply the same three pieces — filter field, `TableSortLabel` headers, derived rows — to `frontend/src/components/NeighborhoodPanel/RosterList.tsx` and to the roster table in `PastNetsTab.tsx`, using each file's own column names.

Add a test to `NCSPanel.test.tsx` asserting that typing a callsign into the search field hides the non-matching row.

- [ ] **Step 5: Run tests and verify they pass**

Run: `cd /mnt/storage/Repos/Radio-TTY/frontend && npx vitest run && npx tsc --noEmit && npm run build`
Expected: PASS, no type errors, build succeeds

- [ ] **Step 6: Commit**

```bash
git add frontend/src/netsessions frontend/src/components/NCSPanel frontend/src/components/NeighborhoodPanel frontend/src/components/JournalPanel
git commit -m "feat: sort and search net rosters"
```

---

### Task 11: Documentation

**Files:**
- Modify: `README.md`
- Modify: `USER_MANUAL.md`

**Interfaces:** none — prose only.

- [ ] **Step 1: Find where net features are documented**

Run: `cd /mnt/storage/Repos/Radio-TTY && grep -n "Net Control\|neighborhood net\|Journal" README.md USER_MANUAL.md | head -20`
Expected: the section anchors to extend

- [ ] **Step 2: Document the feature**

Add to `README.md` in the feature list, matching the surrounding entry style:

```markdown
- **Net session history** — every net that ends is recorded as a structured roster
  under `/data/net_sessions`. Browse past nets, per-station attendance (totals,
  recent turnout, streaks), and export any net or the whole history as CSV from the
  **Past Nets** tab of the Journal panel. Records are private and never published to
  the public journal page. Deleting a record requires an admin.
```

Add to `USER_MANUAL.md`, under the journal/net section, a short walkthrough: end a net → open the Journal panel → **Past Nets** tab → pick a date to see its roster and transcript → **DOWNLOAD CSV** for one net or **EXPORT ALL (CSV)** for the full history. Note that the attendance list sits below the roster and that `net_sessions_dir` in `config.json` moves the storage location (default `/data/net_sessions`).

- [ ] **Step 3: Commit**

```bash
git add README.md USER_MANUAL.md
git commit -m "docs: document net session history"
```

---

## Verification

Run the whole suite plus a manual end-to-end pass before opening the PR.

- [ ] **Automated**

```bash
cd /mnt/storage/Repos/Radio-TTY
python -m pytest backend/tests/ -q
cd frontend && npx tsc --noEmit && npx vitest run && npm run build
```

All green, no type errors.

- [ ] **Manual end-to-end**

1. Start the dev instance and sign in as an admin.
2. Start an NCS net, check in two stations (one with traffic `Priority`), end the net.
3. Start a neighborhood net, check in from a second browser profile, end it.
4. Confirm two files exist: `docker exec <container> ls /data/net_sessions` — one `*_ncs.json`, one `*_neighborhood.json`.
5. Open the Journal panel → **Past Nets**. Both nets appear newest-first with the right type label, check-in count, and duration.
6. Click each net: roster renders with callsign/name/location/status/traffic; the NCS net shows its transcript.
7. **DOWNLOAD CSV** opens in a spreadsheet with one row per check-in; **EXPORT ALL (CSV)** has one row per station per net.
8. The attendance list shows both stations with sensible totals and streaks.
9. As an admin, delete a net: it disappears from the list. Sign in as a non-admin and confirm the delete button is absent, and that a hand-sent `delete_net_session` is rejected with "Admin access required."
10. Set a station to `CheckedOut` mid-net and press **CALL NEXT STATION** — that station is skipped but still appears in the saved record.
11. Type into the roster search box and click column headers; rows filter and sort.

- [ ] **Regression**

1. Ending a net still writes a journal entry (Journal tab, alongside the session record).
2. Make the sessions directory unwritable (`chmod 000`), end a net: the net ends normally, the journal still saves, and the log shows `net session save failed`. Nothing surfaces as a user-facing failure.
3. Contacts CSV/JSON export still works after `downloadText` moved to `utils/download.ts`.
