# /display kiosk — layout rework, tile sorting, durable pairing

Date: 2026-07-25
Status: approved, in implementation
Branch: `feat/display-layout-and-pairing`

## Problem

The wall kiosk (`/display`, shipped v2.18.0; e-ink v2.20.0) has three daily-use problems.

**Layout.** The radio log is a footer showing only the last 5 messages, oldest-first, with no
scroll. The presence grid takes the whole page with 220px-minimum tiles that never adapt to
household size.

**No tile ordering.** Tiles render in `users.json` iteration order
(`backend/persistence/users.py:161-165`) — arbitrary, and there is no way to change it.

**Re-pairing every visit.** The operator re-enters the device token each time the page opens.

There is no "API key" in this codebase — the field is a *device token*, and it already persists to
`localStorage['radio_tty_device_token']`. The only path that erases it is a WebSocket close with
code `4001`. The live install has a valid token whose `last_seen` is current with its successful
connects, so the store works; a *transient* rejection is what un-pairs the kiosk.

The root cause is that `4001` is ambiguous. `server.py` guards on
`if _device_token_store and device_token:` — when the store is `None` a device token falls through
to the session-token block and receives a bare, reasonless `4001`, which the client reads as
"revoked" and wipes. A revoked token and a not-yet-ready server are indistinguishable to the client.

## Goals

A wall display that reads like a radio console (newest traffic top-left), a people band that scales
with household size and can be hand-sorted, and a pairing that survives restarts, races, and a token
typed only once.

## Design

### Layout

Root stays a `100vh` flex column with the burn-in drift. Two rows:

```
┌─────────────────────┬──────────────┐  row 1: flexGrow 1, minHeight 0
│ RADIO LOG (newest ↑)│  14:32       │  grid minmax(0,2fr) minmax(280px,1fr)
│  ...scrolls...      │  ⚠ alert     │
│                     │  Net: Tue 7p │
├─────────────────────┴──────────────┤  row 2: flex 0 0 auto, maxHeight 38vh,
│ PEOPLE (scrollable)             ↕  │          overflowY auto
├────────────────────────────────────┤
│ [quick messages — awake only]      │
└────────────────────────────────────┘
```

Clock, date, reconnect chip, alert, and the next-net label all move into the right sidebar; the
console header keeps only its on-air dot and title.

### Radio log

Newest-first, fully scrollable, cap raised 20 → 50. Stick-to-top only when already at the top
(`scrollTop < 24`), so an operator reading history is not yanked back by new traffic. E-ink keeps
its finalized-only filter and gets no smooth scrolling.

### Tile sizing

A pure `tileMetrics(count)` in `frontend/src/display/tileSize.ts`, matching the existing
`display/autoDark.ts` / `family/presence.ts` pattern:

| Count | minWidth | emoji |
|---|---|---|
| ≤ 4 | 240px | 3rem |
| 5–8 | 190px | 2.4rem |
| 9–12 | 155px | 1.9rem |
| ≥ 13 | 130px (floor) | 1.6rem |

Nothing shrinks below the floor — the band scrolls instead.

### Drag-to-sort

`@dnd-kit/core` + `sortable` + `utilities`, chosen over HTML5 DnD (no touch support) and hand-rolled
pointer code (no keyboard sorting; this project has an active a11y track). Long-press activation
(350ms delay, 8px tolerance) so a short tap still opens Mark-OK, enabled only during the 45s awake
window, disabled entirely in e-ink mode.

Order lives **server-side on the device-token record**, not in localStorage — localStorage is
exactly what is proving unreliable, and per-token storage lets each wall display differ.
`applyTileOrder(presence, order)` puts known ids in stored order first (filtered to those still
present), then appends anyone unlisted in server order, so a new family member shows up rather than
disappearing.

### Durable pairing

Three independent layers, all requested:

1. **Precise close codes.** A supplied `device_token` never falls through to the session block. Store
   not ready → `1013` (try again later) plus a `_log.warning`. Genuinely unknown token → `4001` with
   `reason="device_token_invalid"`. Session path → `4001 reason="auth_required"`. The client treats
   only the explicit device-token reason as fatal; everything else reconnects with backoff.
2. **No silent wipe.** A fatal auth failure keeps the shell mounted behind a persistent "no longer
   paired" banner with a **Re-pair** button. Only a human clears the stored token.
3. **`?token=` URL.** Read on mount, written to storage, stripped from the address bar via
   `history.replaceState`. A bookmark or kiosk homepage becomes the durable source of truth and
   self-heals after any browser data wipe. Trade-off to document: the token lands in bookmarks,
   history, and reverse-proxy access logs — the same exposure as today's WS query param.
4. **Short pairing code.** Admin token creation also mints a 6-digit, single-use, 10-minute
   in-memory code, exchanged at `POST /display/pair` for the real token. Rate limiting is mandatory
   (per-IP 5/min, global lockout after 20 failures) — six digits is trivially brute-forceable. The
   gate shows the code field first with "paste a token instead" under an expander, so existing
   devices and scripted setups keep working.

## Out of scope

Version bump (handled by `/release`), HttpOnly-cookie WS auth (recorded as a follow-up; it would
also remove the token from access logs), and the pre-existing display-WS-flap issue.
