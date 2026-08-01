# Net Session History — Design

**Date:** 2026-08-01
**Status:** Approved for planning
**Inspiration:** NetLogger (netlogger.org) feature review

## Problem

Hearthwave covers most of NetLogger's live-net surface (roster, statuses, round-table
caller, callsign verification, net scripts) but keeps no persistent net history. The NCS
plugin roster is in-memory and wiped on `ncs_start` and on restart; `NeighborhoodNet`
clears its roster on `end()`. Nothing stores "callsign X checked into net Y on date Z" in
a queryable form. The journal is a narrative text blob with public HTML-publish
semantics, so it is the wrong home for structured, private participation records.

## Goals

- Persist every completed net (NCS and neighborhood) as a structured session record.
- Browse past nets: roster plus transcript for any previous session.
- Attendance stats per station: totals, recent attendance, streaks.
- CSV export of any session's roster and of all check-ins combined.
- Stretch: sort/search in roster tables; a `CheckedOut` status.

## Non-goals (decided 2026-08-01)

- ADIF/Cabrillo export, QRZ links, LoTW/eQSL/awards (ham-contest territory; primary use
  is the neighborhood/family GMRS net).
- Logger handoff, cross-instance shared live log, nets-in-progress directory.
- Preloading regulars from a previous net (considered, not selected).
- /display net-night attendance integration (deferred as future work).

## Design

### 1. Session store — `backend/persistence/net_sessions.py` (new)

Modeled on `backend/persistence/journal.py` (directory scan, newest-first, `_file`
injection). One JSON file per session in `/data/net_sessions/`, named
`YYYYMMDD_HHMMSS_<net_type>.json`.

```json
{
  "id": "20260801_193000_neighborhood",
  "net_type": "ncs | neighborhood",
  "started_at": "<ISO UTC>",
  "ended_at": "<ISO UTC>",
  "duration_seconds": 3120,
  "roster": [
    {"callsign": "", "name": "", "location": "", "status": "",
     "traffic": null, "checkin_time": "<ISO UTC>", "verified": false}
  ],
  "transcript": "..."
}
```

API: `save_session`, `load_session_summaries()` (id, type, started_at, duration,
check-in count — never loads transcripts), `load_session(id)`, `delete_session(id)`.
All files kept; no retention cap (expected volume 50–100 sessions/year). Directory
configurable via a config key following the `journals_dir` pattern in
`backend/config.py`.

Roster normalization to one shape:

- NCS rows: `callsign, status, traffic, name, location, checkin_time` (unix float),
  `verified` — convert `checkin_time` to ISO UTC.
- Neighborhood rows: `user_id, callsign, name, location, status, checkin_time` (ISO) —
  `traffic` stored as `null`; statuses mapped `checked_in` → `CheckedIn`,
  `standby` → `Standby`.

### 2. Writers

- `backend/plugins/ncs.py` `_handle_end`: alongside the existing `_save_ncs_journal()`,
  save a session from the roster and `_session_rx` transcript. `_handle_start` records
  `started_at`.
- `backend/server.py` `neighborhood_end` handler: `end()` already returns
  `{roster, duration_seconds}`; save a session using the same transcript text that
  reaches the neighborhood journal write.

A session-save failure must not block ending the net: log the error and emit a
`system_msg` warning, mirroring journal-save error handling.

### 3. Past Nets browser — Journal panel tab

- WebSocket messages: `net_sessions_list` (summaries), `net_session_get {id}` (full),
  `net_session_delete {id}` (admin-gated, following the existing admin-check pattern in
  `server.py`). Types added to `frontend/src/types/ws.ts`.
- `frontend/src/components/JournalPanel/JournalPanel.tsx` gains a tab bar
  ("Journal" | "Past Nets"). The Past Nets tab lists sessions (date, type badge,
  duration, check-in count); selecting one shows the roster table, transcript, a CSV
  download button, and an admin-only delete using the existing `ConfirmDialog`.
- Access: any authenticated user may read; only admins may delete.

### 4. Attendance stats

- Backend aggregation on demand across stored sessions, keyed by `(callsign, name)`
  with the same normalization as `build_attendance_rows` in
  `backend/persistence/attendance.py`, joined to contacts for display names. Computed
  fields per station: `total_nets`, `attended_of_last_10`, `current_streak`,
  `last_seen`.
- Delivered via a `net_attendance_stats` WebSocket message (or folded into
  `net_sessions_list` — implementer's choice, documented in code).
- Frontend: a summary section inside the Past Nets tab, e.g.
  "Maria — 12 nets, 8 of last 10, streak 3".

### 5. CSV export

- `GET /api/net-sessions/{id}.csv` — one session's roster. Columns:
  `callsign,name,location,status,traffic,checkin_time`.
- `GET /api/net-sessions/all.csv` — one row per check-in across all sessions; adds
  `net_id,net_type,net_date`.
- Both authenticated; implementation follows `backend/persistence/contacts_io.py` and
  the download UI pattern in `ContactsDialog.tsx`.

### 6. Stretch: roster quality-of-life

- **Sort + search:** column-header sorting and a filter box in the live roster tables
  (`NCSPanel.tsx`, `NeighborhoodPanel/RosterList.tsx`) and the past-net roster view.
  Client-side only.
- **CheckedOut status:** new status in the NCS plugin (`CheckedOut`) and neighborhood
  net (`checked_out`). The row stays in the roster and the saved record, is excluded
  from `_handle_call_next` round-table selection, and renders with a distinct chip.
  Requires `NCSEntry` type updates, status-toggle UI, and tests.

## Testing

- Unit: store round-trip; summary listing excludes transcripts; normalization of both
  roster shapes; stats math (streaks, last-10 windows); CSV columns and escaping;
  `CheckedOut` excluded from `call_next`.
- Integration: start and end one NCS net and one neighborhood net; session files appear;
  Past Nets tab lists both; detail view renders; CSV downloads open in a spreadsheet;
  delete works as admin and is rejected otherwise.
- Regression: `ncs_end` still writes the journal; ending a net succeeds when the
  sessions directory is unwritable (warning only); frontend tests and `npm run build`;
  backend pytest suite.
