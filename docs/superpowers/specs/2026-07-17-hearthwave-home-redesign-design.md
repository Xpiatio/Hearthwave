# Hearthwave Home — Full UI/UX Redesign Concept

## Context

Brainstorm request: identify Hearthwave's user base and redesign the UI around three audiences — accessibility-first operators, neighborhood watch (GMRS neighborhood net), and family hub. Decisions made during brainstorm:

- **Goal**: full redesign concept (not incremental feature picks)
- **Structure**: one unified UI, **two-tier** — simple default surface + explicit operator tier; no feature loss, power tools behind the operator tier
- **Neighborhood watch** = GMRS neighborhood net (check-ins, incident reports, street alerts)
- **Family hub** = both shared always-on wall display *and* personal devices with logins
- **Accessibility targets**: low vision, motor, cognitive/simple, hearing (AAC for non-speaking operators already shipped)
- **Chosen shape**: **Hub + Activities** — home dashboard of large cards opening full-screen activities

## Personas

1. **Operator** — ham/GMRS power user; NCS, round-table, STT tuning, plugins. Density + speed.
2. **Non-speaking operator** — AAC grid user (exists). Symbol UI, large targets.
3. **Elderly relative** — low vision/tremor; sees family messages, sends "I'm OK", hears alerts.
4. **Parent / hub admin** — station setup, accounts, kid-safe defaults, "everyone OK" glance.
5. **Kid** — quick messages only, icons, no settings, TX gated.
6. **Watch coordinator** — weekly neighborhood net; roster, incident reports, one-tap street alert. NCS-lite, plain language.
7. **Neighbor participant** — casual GMRS user; alert status, last messages, big check-in button.
8. **Wall display (passive)** — kitchen tablet; glanceable presence/alerts/messages.

## Current-state anchors (from exploration)

- React 18 + MUI v9; three shells: `DesktopApp`, `MobileApp`, `AACApp` — routed in `frontend/src/App.tsx` (~line 1090-1245) via `useDeviceClass` + `aacMode`
- Theme factory `frontend/src/theme.ts` (`makeTheme(dark)`, `withTouchDensity`) — already parameterized, extend for font scale/contrast
- Per-user prefs synced via `user_profile` WS msg / `save_user_prefs` (`App.tsx` 436-458)
- `NCSPanel/NCSPanel.tsx`: check-in roster, round-table caller, `ncs_alert` NWS banner, BREAK BREAK — reuse for Watch activity
- `NCSPanel/SpotReportDialog.tsx`: structured hazard form pattern — template for incident reports
- `JournalPanel/JournalPanel.tsx` + `/data/journals` — pattern for incident log persistence
- `QuickMessages` component — reuse for family/kid presets
- Auth: token-based, `is_admin` boolean only (`useAuth.ts`); server enforces
- jest-axe already in ~9 test files; snackbars/AAC use aria-live

## Design

### 1. Navigation: Hub + Activities

New `HomeScreen` shell replaces `DesktopApp` as default. Large cards open full-screen activities:

- 💬 **Chat** (always), 🏠 **Family** (new), 🏘 **Neighborhood** (new), 🎙 **Net Control** (existing NCSPanel promoted), 📻 **Radio Tools** (waterfall, meters, calibration, plugins, journal), Settings via avatar.

New per-user pref `ui_level: simple | operator`:
- **simple**: Chat/Family/Neighborhood cards only; no waterfall/jargon
- **operator**: + Net Control, Radio Tools; denser in-activity chrome (status row, channel-clear, TX queue)

Persistent glance header everywhere: presence chips, NWS alert state, channel-activity dot. Cards show live summaries ("3 new", "everyone OK", "net Tue 7pm"). Mobile: activities as bottom nav. `AACApp` unchanged as third shell; home grid adopts AAC large-target styling.

### 2. Family activity

- **Presence board**: member cards (avatar, last-heard, status on-air/OK/no-word) — backed by attendance/roster data + new structured status message
- **"I'm OK" button**: giant one-tap — TTS status on air + chat post + presence update
- **Check-in reminders**: scheduled ("Grandma by 9am"); missed = amber card + optional notification
- **Family quick messages**: per-user presets (reuse `QuickMessages`)
- **Kid accounts**: new role gates TX to quick-messages-only, profanity filter locked, no settings

### 3. Neighborhood activity

- **Watch roster + check-ins**: reuse NCS roster machinery, plain-language relabel; coordinator gets simplified round-table caller
- **Incident report**: structured form modeled on `SpotReportDialog` — categories (suspicious activity, hazard, medical, lost pet/person, utility outage), location, description; transmits standardized voice report + logs
- **Street alert**: coordinator one-tap broadcast — TTS on air + banner + browser notifications (reuse `ncs_alert` path)
- **Incident log**: journal-backed, filterable
- **Net schedule card**: next net; tap = early check-in

### 4. Accessibility system (cross-cutting)

- **Font scale** pref 100/125/150/200% — extend `makeTheme`
- **High-contrast** theme variant alongside dark mode
- **Keyboard**: full global nav, roving tabindex (home grid + AAC grid), visible focus rings, shortcut overlay
- **Switch scanning**: single-switch auto-scan for home cards + AAC grid
- **Hearing**: visual twin for every audio cue — screen-edge flash on RX/alert, mobile vibration
- **Cognitive**: simple tier + plain-language pass; AAC huge-yes/no confirm pattern generalized to destructive actions
- **Screen reader**: extend jest-axe to all new screens

### 5. Wall display (kiosk)

- `/display` route: presence board, NWS banner, last 3 messages, next net, clock; auto-dark at dusk, burn-in-safe drift
- Tap wakes limited interaction: "I'm OK" + household quick messages
- **Device token** auth: admin-issued, read + limited-TX scope, no login screen

### 6. Backend implications

- New prefs: `ui_level`, `font_scale`, `high_contrast`
- Role field `admin | adult | kid` + server-side TX permission gating
- Structured status message type + presence store (last-heard per user)
- Incident report message type + persistence (journal-dir pattern)
- Device-token auth for kiosk

## Phasing

1. Home shell + tiers + a11y theme (font scale, contrast, keyboard)
2. Family activity + roles
3. Neighborhood activity
4. Kiosk display + device tokens
5. Switch scanning + a11y polish

Each phase = own branch/PR/release per existing project release flow (`/release` skill before tagging).

## Verification

- Per phase: vitest + jest-axe on new components; manual run via docker compose (`-p hearthwave`), check `/health`
- Tier check: simple user sees no operator surface; operator toggle restores everything
- A11y: keyboard-only walkthrough of home → each activity; axe clean; font-scale 200% no overflow
- Kiosk: `/display` loads unauthenticated-with-device-token, survives overnight (no memory growth/burn-in drift working)
- Family/Watch flows end-to-end on real radio loopback: "I'm OK" heard on air + presence updates; incident report transmits standardized phrasing

## Next step after approval

This is a design concept. Implementation begins with Phase 1 only; write detailed per-phase implementation plan first (superpowers:writing-plans), then execute phase-by-phase.
