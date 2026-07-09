# AAC Mode — Design

**Date:** 2026-07-08
**Status:** Implemented on `feat/aac-mode`

## Problem

Non-speaking operators (e.g. autistic people who use AAC — Augmentative and Alternative Communication — devices) cannot use voice radio directly. Hearthwave already turns typed text into on-air speech, but the standard UI assumes fluent typing and dense controls. An AAC-style interface — big symbol buttons that build a sentence, then speak it — lets a non-speaking radio operator participate on GMRS/ham nets independently.

## Decisions

| Question | Decision |
|---|---|
| Core use case | Non-speaking radio operator transmits via TTS TX path |
| Button visuals | Emoji + text label (no symbol-set licensing, offline, user-pickable) |
| Vocabulary | User-editable grid; starter set = radio phrases + core words |
| Layout scope | Full-screen AAC layout replacing the normal UI when toggled |
| Interaction | Taps append to a sentence strip; big SEND transmits (no instant-send) |
| Grid structure | Category tabs (Core / Radio / Status / About me by default) |
| Persistence | Server-side per-user prefs (`aac_mode`, `aac_grid`) — follows user across devices |
| Toggle & editing | Settings→Preferences switch; in-AAC edit mode for buttons/categories |
| Architecture | New `AACApp` shell beside `DesktopApp`/`MobileApp`; pure presentation swap |

Safety defaults: Exit requires a large-button confirm dialog (only path back to normal UI); unresolved `{...}` tokens are stripped at SEND so the typing-based TokenPromptDialog never fires in AAC mode; server rejects `aac_grid` payloads that are not objects or exceed 64 KB.

## Data model

`frontend/src/types/aac.ts`: `AACGrid { version: 1, categories: AACCategory[] }`, `AACCategory { id, name, emoji, buttons }`, `AACButton { id, emoji, label, text }`. `text` may contain `{Name}` / `{callsign}` tokens, resolved client-side at SEND (`resolveTokens`). Caps: 20 categories, 40 buttons each. `sanitizeAacGrid()` defensively loads server data and falls back to the default grid — a corrupt pref can never brick the AAC screen. `aac_grid: null` means "use the client's built-in default grid".

## Components

- `frontend/src/components/AACApp/AACApp.tsx` — full-screen shell: header (identity, status chips, edit toggle, exit) → `IncomingStrip` (last 3 messages, aria-live) → `SentenceStrip` (chunk chips, Undo/Clear) → category `Tabs` → `ButtonGrid` → send bar (SEND / ABORT while transmitting). Owns strip + edit-mode state.
- `ButtonGrid.tsx` / `AACGridButton.tsx` — auto-fill grid of ≥88 px emoji+label buttons; edit mode shows dashed borders and an Add cell.
- `ButtonEditorDialog.tsx` — add/edit/delete a button (emoji, label, spoken text).
- Category add/rename/delete via a small dialog inside `AACApp`; deletes confirm via `window.confirm` (repo convention).
- `defaultGrid.ts` — starter grid, sanitizer, token resolver.

## Wiring

- Backend: `aac_mode` / `aac_grid` added to `DEFAULT_PREFS` (`backend/persistence/users.py`) and the `save_user_prefs` whitelist with a type/size guard (`backend/server.py`). Grid rides the existing `user_profile` message; no new WS types.
- `App.tsx`: renders `AACApp` instead of Mobile/Desktop when `aacMode`; hydrates from `user_profile` prefs; mirrors `aac_mode` to `localStorage radio_tty_aac_mode` so reloads land straight on the AAC screen; applies `withTouchDensity` theme in AAC mode on any device. SEND uses the existing `tx_message` path (`handleSend`); grid edits save whole-grid via `save_user_prefs` (atomic replace, last-writer-wins).
- Settings: "AAC Interface (symbol buttons)" switch in Preferences (`ConfigPanel`), staged through `SettingsDialog`'s draft/Save pattern.

## Testing

- `AACApp/__tests__/` — 26 tests: compose/backspace/clear, token-resolved SEND, listen-only + disconnected disable, ABORT, exit confirmation, edit flows, jest-axe on normal + edit views.
- Backend — prefs defaults + grid round-trip (unit), oversized/non-dict `aac_grid` rejection (integration).

## Known limitations (v1)

- Cross-device simultaneous grid edits are last-writer-wins.
- No button reordering UI yet (delete + re-add, or a future up/down control).
- Word-by-word local speech preview (speaking each button aloud locally) not included; radio TX only.
