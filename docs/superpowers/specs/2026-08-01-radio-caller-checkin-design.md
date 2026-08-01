# Radio-Caller Check-In (Coordinator-Side) — Design

**Date:** 2026-08-01
**Status:** approved design, not yet planned or implemented

## Problem

A neighborhood net runs on GMRS. Some neighbors check in **on the air only** — they
have no Hearthwave account, or no computer at all. Today the neighborhood net has no
way to record them: `neighborhood_checkin` (`backend/server.py:3913-3928`) reads
identity from the *connection's own* profile, so a check-in requires an account and a
browser session. The coordinator hears "WRAB123, Maria on Maple" over the radio and
has nowhere to put it. The net record, attendance history, and round-table caller all
silently omit everyone who called in by radio.

The NCS plugin already has this (`ncs_checkin` takes an arbitrary
`callsign`/`name`/`location`, `backend/plugins/ncs.py:303-311`). The neighborhood net
deliberately does not, and that design choice is what this spec revisits — for the
neighborhood net only. NCS needs nothing.

## Goal

A neighborhood-net coordinator can check in a station that has no account, maintain
its status through the net, remove a mis-entered one, and have it appear in the live
roster, the round-table call order, the saved session record, and attendance history
exactly like an account holder.

## Decisions made with Benjamin (2026-08-01)

1. **Callers are both recurring and one-off** — a stable core of radio-only neighbors
   plus occasional strangers. So identity must be reusable for the core without
   blocking ad-hoc entry.
2. **Identity source: Contacts-backed with free entry** — pick a known contact, or
   type a new one, with an opt-in "save to contacts" so next week's net is a pick
   rather than a retype. Without this, the recurring core's attendance streaks
   fragment on typos (`Marie` vs `Maria`), because attendance keys on
   `(callsign, name)`.
3. **Radio rows are marked everywhere** — live roster chip, saved session record
   field, and per-session CSV column.
4. **Both removal and check-out** — remove for a mistake (never reaches the record),
   `CheckedOut` status for "they signed off early" (recorded).
5. **Storage approach B** — a separate radio dict inside `NeighborhoodNet`, merged in
   `roster()`, rather than synthetic ids sharing the account dict.

## Dependency and sequencing

This design touches `backend/persistence/net_sessions.py`,
`frontend/src/netsessions/csv.ts`, and the Past Nets tab — **all of which exist only
on the unmerged `feat/net-session-history` branch** (`247aef1`, 25 commits off
master). Implementation therefore starts **after** that branch is smoke-tested and
merged, on a fresh `feat/radio-caller-checkin` off master. If it turns out this work
must start first, it branches off `feat/net-session-history` instead and the record/CSV
items ride along with it — but the default is: merge that first.

## Architecture

### 1. State — `backend/neighborhood/net.py`

`NeighborhoodNet` gains a second store, `self._radio: dict[str, dict]`, beside
`_roster`. Radio rows use the same row shape as account rows and still carry a
`user_id` field holding their **station key**:

```
radio:<NORMALIZED CALLSIGN>:<name casefolded, whitespace collapsed>
```

plus `"via": "radio"`. Account rows are unchanged and carry no `via` key.

Keeping `user_id` on the wire means `neighborhood_state.roster` stays one flat list
and `RosterList` keeps keying on `row.user_id` — the account/radio split is internal
storage, not a second keyspace clients must learn. The key is deterministic so
re-adding the same station updates its row instead of duplicating it, matching the
idempotency `checkin()` already has per `user_id`.

**Ordering.** Both stores stamp a shared monotonic `seq` on a row at first check-in,
and every merged view (`roster()`, `call_next()`) iterates by `seq`. A radio neighbor
who checked in first must be called first. Sorting on `checkin_time` instead would
silently reorder an account holder who re-checks in (today's insertion-order
behavior does not), so `seq` is what interleaves correctly while leaving existing
account behavior identical.

A private `_find(key)` looks in `_roster` then `_radio`, so `set_status` and the
round-table's `called` bookkeeping stay single-path.

Method semantics:

| method | behavior for radio rows |
|---|---|
| `start()` | `called` reset, same as accounts |
| `end()` | included in the roster snapshot, then cleared |
| `clear_checkins()` | cleared too — it wipes the whole board |
| `remove(user_id)` (account-deletion path) | untouched; accounts only |
| `call_next()` | eligible, in `seq` order, `checked_in` only — same rule as accounts |
| `checkin_radio(callsign, name, location)` **new** | idempotent per station key; returns the row |
| `remove_station(key)` **new** | radio only; returns False for a non-`radio:` key or unknown key |

`remove_station` also clears `current_call` when it pointed at the removed row, the
same guard `remove()` already has.

### 2. WS layer — `backend/server.py`

Two new messages, both gated by the existing `_is_coordinator(state)` (which already
rejects kid accounts by virtue of `set_neighborhood_coordinator` never granting the
pref to one):

**`neighborhood_checkin_radio`** — `{callsign, name, location?, save_contact?}`

- `callsign` normalized through `normalize_callsign`; required.
- `name` required, non-blank after strip. Required here even though self-check-in
  falls back to `"Operator"`: attendance keys on `(callsign, name)`, and
  `neighborhood_call_next` speaks the name on the air, so an unnamed radio row is
  useless in both places.
- Blank callsign or name → `{"type": "error", "detail": "Callsign and name are required."}`
- Field caps, truncating rather than erroring (the `vox_primer_word` idiom at
  `server.py:2207`): callsign 16, name 64, location 64. Profile fields enforce no
  caps today; these are new limits for client-supplied values, not a copy of an
  existing rule.
- **Identity is client-supplied by design.** This is the first neighborhood handler
  where it is. The comment at `server.py:3914-3917` explaining kid-rename protection
  gets a sibling note here: there is no account behind a radio row, so there is
  nobody to impersonate, and the coordinator gate is the whole control.
- Check the station in **first**, broadcast state, **then** attempt the contact save.
  A contacts failure must never lose the check-in.
- `save_contact: true` → `_contacts_store.add_contact({"callsign", "name", "location"})`
  in `try/except ValueError`, then broadcast `{"type": "contacts", ...}` and call
  `_rebuild_stt_vocabulary()`, mirroring the `add_contact` handler at
  `server.py:2992-3005`. Side benefit: the callsign enters the STT vocabulary bias,
  so Whisper starts recognizing that neighbor on the air.
- On a contacts `ValueError`, send the error to the requesting socket only; the
  check-in stands.

**`neighborhood_remove_station`** — `{user_id}`

- Refuses any id not starting `radio:` with
  `{"type": "error", "detail": "Only radio check-ins can be removed."}` — so it can
  never be used to bump an account holder off the board.
- Then `remove_station(key)`, broadcast `neighborhood_state`.

**No new message for status.** `neighborhood_status` (`server.py:3930-3941`) already
takes a `user_id` behind a coordinator gate and routes through `set_status`, which
`_find` now resolves for radio rows too.

The message-catalogue docstring at `server.py:44-60` gains both entries with their
gates.

### 3. Record and export

`normalize_roster` (`backend/persistence/net_sessions.py:60-77`) carries `via`
through, defaulting to `""` — so NCS rows and account rows both store `via: ""` and
existing records read back unchanged.

`sessionToCsv` (`frontend/src/netsessions/csv.ts:9-17`) gains a `via` column. The
Past Nets detail roster table gains a `Via` column.

`allSessionsToCsv` is **unchanged**: it builds from summaries' `stations`, which
carry only `callsign`/`name`. Widening that shape would touch the attendance-stats
path for a column nobody exports per-net.

Attendance stats need no change — `compute_attendance_stats` reads
`(callsign, name)` off `stations`, and a radio station is a station.

### 4. Frontend

**New `frontend/src/components/NeighborhoodPanel/RadioCheckinForm.tsx`**, rendered
inside the existing coordinator block (`NeighborhoodPanel.tsx:210-258`, below the net
buttons):

- A "Pick a neighbor" `Select` over known contacts (`CALLSIGN — Name`); choosing one
  fills the three fields, which stay editable.
- Callsign / Name / Location text fields.
- A "Save to contacts" checkbox, shown only when the typed callsign is not already in
  the contact book.
- "Check in station" button, disabled until callsign and name are both non-blank.
  Clears the form on submit.
- A `Select` rather than an `Autocomplete` because the codebase contains no
  `Autocomplete` anywhere yet and a household's contact book is short. Same MUI parts
  `RosterList` already uses. No new dependency either way.

`NeighborhoodPanel` gains a `contacts` prop; `App.tsx:168` already holds the list and
just doesn't thread it to this panel.

**`RosterList.tsx`:**

- A row with `via === 'radio'` gets a `By radio` chip beside the callsign.
- New props `isCoordinator`, `onStationStatusChange(userId, status)`,
  `onRemoveStation(userId)`.
- The status-cycle button (today `isSelf`-only, `RosterList.tsx:205`) also appears on
  radio rows when the viewer is coordinator — nobody else can press it for a caller
  with no browser. Other account holders' rows stay untouched: a coordinator still
  cannot toggle another account from this list.
- Remove is a small icon button on radio rows, coordinator-only, **with no confirm
  dialog**: the row is a typo that never reached disk and re-adding costs one Select
  click. Confirms stay for the genuinely destructive controls (`Clear check-ins`,
  street alerts).

**Types** (`frontend/src/types/ws.ts`): `NeighborhoodRosterRow.via?: 'radio'`;
`NetSessionRosterRow.via?: string`.

**`App.tsx`**: two new senders wired to the new WS messages. `isCoordinator` already
exists at `App.tsx:1596`.

## Error handling

| case | behavior |
|---|---|
| non-coordinator sends either new message | `{"type":"error","detail":"Coordinator access required"}`, no state change |
| blank callsign or name | single validation error, no row created |
| over-long field | truncated silently, row created |
| `save_contact` on a callsign already in the book | no contact write, no error; check-in proceeds |
| contacts store raises / is `None` | check-in stands, error sent to that socket only |
| `remove_station` with an account `user_id` | refused with the radio-only error |
| `remove_station` with an unknown radio key | no-op, state re-broadcast (idempotent) |
| session save fails at net end | unchanged from today: logged, never blocks ending the net |

## Testing

**Backend unit — `backend/tests/unit/neighborhood/test_net.py`:**
- `checkin_radio` creates a row with `via: "radio"` and the deterministic key
- re-`checkin_radio` of the same callsign+name updates in place, no duplicate row
- same callsign, different name → two rows (the GMRS-family case)
- `seq` ordering: radio row checked in between two accounts is called between them by
  `call_next`
- `remove_station` returns False for an account `user_id`; True for a radio key;
  clears `current_call` when it pointed at that row
- `end()` snapshot includes radio rows; both stores clear afterward
- `clear_checkins()` clears both stores
- `remove(user_id)` leaves radio rows alone

**Backend unit — `backend/tests/unit/persistence/test_net_sessions.py`:**
- `normalize_roster` carries `via` through and defaults it to `""` for NCS and
  account rows

**Backend integration — `backend/tests/integration/test_server_ws.py`:**
- non-coordinator `neighborhood_checkin_radio` → coordinator error, roster unchanged
- coordinator check-in appears in the broadcast `neighborhood_state`
- blank name → validation error, no row
- `save_contact: true` writes the contact and broadcasts `contacts`
- `save_contact: true` when the contacts store raises → check-in still present
- `neighborhood_status` from a coordinator changes a radio row's status
- `neighborhood_remove_station` on an account id → refused, row still present
- ending a net with a radio row writes it into the session record with `via: "radio"`

**Frontend — Vitest/RTL:**
- `RadioCheckinForm`: button disabled until callsign+name; contact pick fills fields;
  "Save to contacts" hidden for a known callsign; submit payload shape; form clears
- `RosterList`: `By radio` chip on radio rows only; remove button coordinator-only
  and radio-only; status button on a radio row for a coordinator and not for a
  non-coordinator; no remove button on account rows
- `csv.ts`: `sessionToCsv` emits the `via` column and escapes it; `allSessionsToCsv`
  unchanged
- `PastNetsTab`: `Via` column renders

**Manual smoke:** run a net with one account holder and two radio callers, call the
round table and confirm order matches check-in order, check one radio caller out,
remove the other, end the net, confirm the record in `/data/net_sessions` and the CSV.

## Global constraints

- No new Python or npm dependencies.
- No version bumps, no release files touched — unreleased work rides master until the
  next version cut (`/release` skill runs before any tag, per `CLAUDE.md`).
- Net session records stay **private**: never routed through `publish_journal` or the
  public `GET /journal`.
- No `Co-Authored-By` trailers on commits, no generated-with footers on PRs.
- Coordinator gate is `_is_coordinator(state)`; admin-only stays admin-only
  (`clear_checkins`). The server re-checks every gate — frontend hiding is cosmetic.

## Explicitly out of scope

- NCS net changes (it already has manual check-in).
- Preloading regulars onto the board before a net.
- `/display` kiosk integration (the kiosk does not consume the roster today).
- Any account or login path for radio callers.
- `allSessionsToCsv` column widening.
