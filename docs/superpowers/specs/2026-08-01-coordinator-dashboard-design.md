# Coordinator Dashboard for the Neighborhood Net — Design

**Date:** 2026-08-01
**Status:** Approved (brainstorm with Benjamin)
**Branch plan:** stacks on `feat/radio-caller-checkin` (which stacks on unmerged `feat/net-session-history`)

## Problem

The Neighborhood panel is one long vertical stack: header, alerts, a 96px
check-in button, incident button, roster grid, incident log, and — at the very
bottom — the coordinator tools (net controls, radio check-in form, street
alert). The coordinator runs the net from a desktop and scrolls constantly
between the roster at the top and the controls at the bottom. Radio traffic
(the net's primary input) isn't visible at all; the coordinator alt-tabs to
the main desktop view to read the RX transcript.

Separately, the round-table has no way to record "tried this station, no
answer." `called` is a plain boolean, so an unreachable station either burns
its turn silently or blocks the coordinator's bookkeeping.

## Decision summary

A desktop-only **coordinator dashboard**: a single-viewport ops console shown
automatically to coordinators on wide screens. Participants (phones, kids,
narrow windows) keep the current stacked view unchanged. Layout is
**radio-first**: the RX transcript and TX input take the left half of the
screen; roster and incidents take the right.

Alongside it, the round-table gains **no-answer tracking** and **per-row
call**, in both views (RosterList is shared).

## 1. Entry and scope

- New `CoordinatorDashboard` component in
  `frontend/src/components/NeighborhoodPanel/`.
- `NeighborhoodPanel` renders it when `isCoordinator && !isKid` **and** the
  viewport is ≥ 1200px (`useMediaQuery`). Anything else renders the existing
  stacked view, untouched.
- No new route, no toggle, no persisted preference. A coordinator on a phone
  falls back to the stacked view (which retains the coordinator section).

## 2. Layout (option C — radio-first split)

Full-viewport CSS grid (`100vh`); the page itself never scrolls — each zone
scrolls internally when content grows.

```
+----------------------------------------------------------------------+
| Command bar: back | status chip | Start/End net | Call next |        |
|   New round | Street alert… | current turn: <name> | N checked in |  |
|   [self check-in chip]                                               |
+----------------------------------------------------------------------+
| Street-alert banner(s) — only when active                            |
+---------------------------------+------------------------------------+
| RX transcript (ChatDisplay)     | Roster (RosterList, ~60% height)   |
|   … scrolls …                   |   … scrolls …                      |
| TX input (MessageInput)         +------------------------------------+
+---------------------------------+ Incident log (IncidentLog)         |
| Radio check-in form             |   header: [Report an incident]     |
| (callsign/name/location/save)   |   … scrolls …                      |
+---------------------------------+------------------------------------+
```

- **Command bar:** back-home arrow, "Net running / No net" status chip,
  Start/End net, Call next, New round, **Street alert** button (opens a
  dialog holding the message field + confirm — the inline field goes away in
  this view), current-turn readout, checked-in count, and the coordinator's
  own check-in reduced to a small chip/button (they check in once; no
  billboard needed).
- **Alert banner:** the existing `Alert` list, full width, only when
  `alerts.length > 0`.
- **Left half:** `ChatDisplay` + `MessageInput` (transmit-capable), the same
  components DesktopApp mounts; `RadioCheckinForm` docked beneath so the
  coordinator can read a callsign off the transcript and type it in without
  eye travel.
- **Right half:** roster on top (~60%), incident log below. "Report an
  incident" moves into the incident-zone header. Admin-only clear buttons
  stay in their respective zone headers, gated by `isAdmin` as today.
- Existing confirm dialogs (street alert, clear check-ins, clear incidents)
  are reused as-is.

## 3. Transcript / TX wiring

`App.tsx` already owns everything the pane needs — `messages`, `handleSend`,
`transmitting`, `handleTxAbort` (see the `AACApp` branch around
App.tsx:1772). Pass them into `NeighborhoodPanel` as new optional props,
consumed only by the dashboard. No new client state, no new WS traffic.

## 4. No-answer tracking + per-row call

### Backend (`backend/neighborhood/net.py`)

- Roster rows gain `no_answer: bool` (default `False`), alongside the
  existing `called` flag.
- Two new WS ops, coordinator-only (server re-checks the grant, mirroring
  `neighborhood_status`):
  - **`neighborhood_no_answer`** `{user_id}` — toggle the flag. Setting it
    also sets `called = True`, so `call_next` skips the station for the rest
    of the round. It does **not** touch `current_call` — the coordinator
    advances with Call next as usual. Clearing it leaves `called` untouched.
  - **`neighborhood_call_station`** `{user_id}` — out-of-order call: set
    `current_call` to that station, `called = True`, `no_answer = False`.
- `call_reset` (New round) clears `no_answer` along with `called` and
  `current_call`.
- `call_next` is unchanged — no-answer rows carry `called = True` and are
  skipped. Re-calling them is manual only (Benjamin's ruling: no
  auto-revisit; surprises the coordinator).

### Frontend (`RosterList`, shared by both views)

- Coordinator-only row controls (participants see none of this):
  - **Call** button on every row — fires `neighborhood_call_station`.
  - **No answer** button on the current-turn row — fires
    `neighborhood_no_answer`.
  - On a flagged row, the "No answer" chip (warning color, replaces
    "Called ✓") is the toggle back: clicking it clears the flag.
- Chip precedence per row: `Current turn` > `No answer` > `Called ✓`.

### Persistence

- Net-session history snapshots include `no_answer`; the Past Nets table and
  CSV export gain a no-answer column so "checked in, never reached" survives
  the net.

## 5. Files touched

| Area | Files |
|---|---|
| New | `frontend/src/components/NeighborhoodPanel/CoordinatorDashboard.tsx` |
| Frontend edits | `NeighborhoodPanel.tsx` (view switch), `RosterList.tsx` (call / no-answer controls), `App.tsx` (prop plumbing), `types/ws.ts` (row field + new ops) |
| Backend edits | `neighborhood/net.py` (flag + two ops), `server.py` (WS routing + permission checks), net-session store (snapshot field), CSV/Past Nets (column) |

## 6. Testing

- **Vitest:** dashboard gating (coordinator + width shows dashboard; kid,
  participant, or narrow shows stacked view); zones render with internal
  scroll containers; Call / No answer buttons appear only for coordinators
  and fire the right handlers; chip precedence.
- **Pytest:** both new ops (happy path + non-coordinator rejection);
  no-answer sets `called`; `call_next` skips flagged rows; `call_station`
  clears the flag; New round wipes it; snapshot + CSV carry the column.

## Out of scope

- Participant/stacked view redesign (unchanged by design).
- NCS panel round-table (separate plugin; may inherit the pattern later).
- Auto-revisit of no-answer stations (explicitly rejected).
- Coordinator-view toggle or preference (auto by role + width only).

## Risks / notes

- Three-deep branch stack: this work sits on two unmerged branches
  (`feat/net-session-history` → `feat/radio-caller-checkin`), both complete
  and green but awaiting Benjamin's manual smoke. Merging those first keeps
  this branch's diff reviewable.
- `RosterList` is shared: new coordinator controls must not disturb the
  participant self-toggle row or the density grid
  (`neighborhood/density.ts`).
- `MessageInput` in the dashboard must carry the same TX semantics as
  DesktopApp (chat-vs-transmit split, voice_as) — reuse, don't fork.
