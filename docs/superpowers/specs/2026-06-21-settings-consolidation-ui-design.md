# Settings Consolidation, Panel Cleanup & Tablet Layout — Design

**Date:** 2026-06-21
**Status:** Approved design, pending implementation plan
**Scope:** Frontend (React/MUI) UI/UX changes only. No backend protocol changes beyond removing one persisted pref field's usage.

## Problem

Five related UI/UX issues:

1. The per-user **Settings** (`ConfigPanel`, a side panel) and the admin **Admin Settings** (`SettingsDialog` with Station/System tabs) are separate surfaces and should be one.
2. In the admin dialog, **Save** lives inside each tab's body; it should sit next to **Close** in the footer.
3. The admin dialog is not small-screen friendly (fixed `maxWidth="sm"`, fixed-`minWidth` controls that overflow).
4. The **moveable panel** feature (drag-to-reorder via @dnd-kit, plus move up/down arrows) is no longer needed.
5. Tablets currently match `pointer: coarse` and fall into the phone (`MobileApp`) layout, wasting screen space. They should get a tablet-appropriate UI.

## Current State (verified)

- `ConfigPanel` (`frontend/src/components/ConfigPanel/ConfigPanel.tsx`) — a fully **controlled** side panel. Every control fires a callback that mutates App state and applies **instantly** (no Save). Contents: profanity filter, fuzzy callsign, audio input device, output sink (loopback only), audio output device, spectrogram colormap/freq-range/time-window. Opened via AccountMenu → `showConfig`.
- `SettingsDialog` (`frontend/src/components/SettingsDialog/SettingsDialog.tsx`) — admin-only dialog, `maxWidth="sm"`, two tabs: **Station** (`AdminPanel` embedded) and **System** (`ServerConfigPanel` embedded). Both panels stay mounted across tab switches to preserve unsaved edits. Each embedded panel renders its **own** Save button (`AdminPanel.tsx:287-298`, `ServerConfigPanel.tsx:~595`) calling distinct handlers (`set_admin_config` vs `set_server_config`). Footer has a single **Close** button. Opened via AccountMenu → `showAdmin`.
- `DraggablePanel` (`frontend/src/components/DraggablePanel/DraggablePanel.tsx`) — @dnd-kit `useSortable` wrapper with a drag handle and optional move up/down arrows.
- `DesktopApp.tsx` wraps the panel list in `DndContext` + `SortableContext` (`:385-481`), rendering each panel in `panelOrder` via `DraggablePanel` with `onMoveUp`/`onMoveDown`.
- `App.tsx` holds `panelOrder` state (`:174`, default `["config","attendance","journal"]`, NCS appended conditionally), `handlePanelDragEnd` and `handlePanelMove` (`:911-934`), persisting to `localStorage['radio_tty_panel_order']` and `send({type:'save_user_prefs', prefs:{panel_order}})`.
- `useMobileDetect()` (`frontend/src/hooks/useMobileDetect.ts`) — returns `true` if `pointer: coarse` OR `max-width: 600px`. `App.tsx` swaps `MobileApp` vs `DesktopApp` on this single boolean.

## Decisions (from brainstorming)

- **Merge shape:** one dialog, tabs gated by permission.
- **Save scope:** one footer Save commits **all dirty tabs at once**.
- **Post-save:** dialog **stays open** with a confirmation.
- **Preferences save behavior:** **Option B** — Preferences edits are *staged* in the dialog and committed only on Save (uniform with the admin tabs; no more instant-apply).
- **Tablet:** touch-friendly **desktop** layout (reuse `DesktopApp`), detected by **width + coarse pointer**.
- **Panel order:** fixed order; the moveable feature (drag + arrows + persistence) is removed entirely.

## Design

### 1. Unified Settings dialog

`SettingsDialog` becomes the single settings surface for all users.

- AccountMenu collapses its two items ("Settings", "Admin Settings") into **one "Settings"** item driving a single open-state (replace `showConfig`/`showAdmin` with one `showSettings`; keep the admin gating internally).
- Title: "Admin Settings" → **"Settings"**.
- Tabs:
  - **Preferences** (all users) — hosts the former `ConfigPanel` content.
  - **Station** (admins only) — `AdminPanel`.
  - **System** (admins only) — `ServerConfigPanel`.
- For non-admins, only Preferences renders and the tab bar is hidden (single-tab → no `Tabs` chrome).
- The standalone `ConfigPanel` side panel is **removed** from `DesktopApp`'s layout (and from `panelOrder`). Its spectrogram/device/toggle controls now live in the Preferences tab.

`ConfigPanel` is refactored from "controlled, instant-apply" to "controlled by **draft state**": it keeps the same visual layout and props *shape*, but its `onChange` callbacks now update the dialog's local draft rather than App state directly. (We may keep `ConfigPanel` as a presentational component and feed it draft values + draft setters.)

### 2. Draft state & unified footer Save

`SettingsDialog` owns a draft model with three slices and per-slice dirty tracking:

```
draftPrefs   (seeded from App's current preference values)
draftAdmin   (seeded from adminConfig)
draftServer  (seeded from serverConfig)
```

- Drafts are **(re)seeded from props whenever the dialog opens** (`open` false→true), so each session starts clean.
- Each tab edits only its slice. Dirty = slice differs from its seed (shallow per-field compare; deep where values are arrays/objects like saved phrases / meshcore config).
- Footer: `DialogActions` = `[ Save ]` (contained, primary) + `[ Close ]` (outlined). Layout right-aligned; Save first per the request ("save button next to the close button").
- **Save** commits every dirty slice:
  - dirty Prefs → apply via the existing preference callbacks / `save_user_prefs` (the same effects that previously fired on each instant change), re-seed draftPrefs.
  - dirty Admin → `onAdminSave(draftAdmin)`.
  - dirty Server → `onServerConfigSave(draftServer)`.
  - After commit, show a confirmation (MUI `Snackbar`/toast or inline message), re-seed all slices from the just-saved values, and **keep the dialog open**. Save is disabled when nothing is dirty.
- **Close**: if any slice is dirty, confirm discard ("Discard unsaved changes?") before closing; otherwise close immediately. On close, drafts are dropped.
- The per-tab Save buttons in `AdminPanel` and `ServerConfigPanel` (embedded mode) are **removed**; in embedded mode these panels become pure controlled forms over the draft (`value` + `onChange`), no internal save. Their standalone (non-embedded) Dialog mode, if still used anywhere, is left intact or removed if unused (verify during planning).

> **Note on Preferences instant-apply loss:** audio input/output device selection previously applied live (useful for "switch and hear it"). Under Option B the change applies on Save. Accepted tradeoff for a uniform save model.

### 3. Small-screen friendliness

- Dialog: `fullScreen` when viewport is phone-width (e.g. `useMediaQuery(theme.breakpoints.down('sm'))`); otherwise `maxWidth="md"` `fullWidth`.
- `Tabs`: `variant="scrollable"` `allowScrollButtonsMobile` so the three tabs never overflow.
- Tab content: replace fixed `minWidth` horizontal-wrap layouts with a vertical stack (`display: flex; flexDirection: column; gap`) and **full-width** controls on narrow screens. On wider screens, controls may sit in a responsive grid.
- Footer stays pinned (`DialogActions`), content area scrolls (`DialogContent dividers`), so Save/Close are always reachable.

### 4. Remove moveable panels

- Delete `DraggablePanel/` component.
- In `DesktopApp.tsx`: remove `DndContext`, `SortableContext`, sensors, and the `DraggablePanel` wrappers. Render the panels directly in a **fixed order**: `attendance`, `journal`, `ncs` (config removed → now in the dialog). Each panel keeps its `PanelHeader` but loses the drag handle / arrows.
- In `App.tsx`: remove `panelOrder` state, `handlePanelDragEnd`, `handlePanelMove`, the `radio_tty_panel_order` localStorage read/write, and the `panel_order` field from `save_user_prefs` sends. Backend may still accept the field; we simply stop sending/consuming it (note for backend cleanup, out of scope here).
- Remove `@dnd-kit/core`, `@dnd-kit/sortable`, `@dnd-kit/utilities` from `package.json` if no other usage remains (grep to confirm).
- Stale `radio_tty_panel_order` keys in users' localStorage are harmless and ignored.

### 5. Tablet layout & device detection

Replace the boolean `useMobileDetect` with a three-way `useDeviceClass()` hook returning `'phone' | 'tablet' | 'desktop'`:

- `phone` — `(pointer: coarse)` **and** `max-width: 600px`.
- `tablet` — `(pointer: coarse)` **and** width `601px–1200px`.
- `desktop` — otherwise (fine pointer, or width > 1200px).

Hook listens to `matchMedia` changes (not just `useMemo` once) so rotating a tablet / resizing updates the class.

`App.tsx` routing:
- `phone` → `MobileApp` (unchanged).
- `tablet` → `DesktopApp` with a `touch` flag (prop or context).
- `desktop` → `DesktopApp` (no touch flag).

**Touch mode** in `DesktopApp` (driven by the flag): larger tap targets (buttons/switches/toggles sized up, increased row spacing / hit areas), and no hover-only affordances. Since drag is already gone, the desktop layout is otherwise touch-safe. Implement via a `touch` prop threaded to a small set of `sx` adjustments or a theme density tweak; avoid a forked layout.

To preserve the existing `useMobileDetect` consumers cheaply, `useMobileDetect` can be reimplemented as `useDeviceClass() === 'phone'` (or kept as a thin wrapper) so only `App.tsx` needs the three-way value.

## Components & boundaries

| Unit | Responsibility | Depends on |
|------|----------------|------------|
| `SettingsDialog` | Own draft state for 3 slices, dirty tracking, footer Save/Close, tab gating | AdminPanel, ServerConfigPanel, ConfigPanel (presentational), App callbacks |
| `ConfigPanel` | Presentational Preferences form over draft values | draft props |
| `AdminPanel` (embedded) | Presentational Station form over draftAdmin | draft props |
| `ServerConfigPanel` (embedded) | Presentational System form over draftServer | draft props |
| `useDeviceClass` | Map viewport+pointer → `phone\|tablet\|desktop`, reactive | matchMedia |
| `DesktopApp` | Fixed-order panel layout; `touch` density flag | panels |

## Testing

- `useDeviceClass`: unit tests mocking `matchMedia` for each of the three classes + a resize/orientation change.
- `SettingsDialog`: draft seeding on open; per-tab dirty detection; Save commits only dirty slices and calls the right handlers; Save disabled when clean; stays open + re-seeds after save; Close confirms when dirty; non-admin sees only Preferences (no tabs).
- `DesktopApp`: panels render in fixed order; no drag handles / DndContext present; `touch` flag applies larger targets.
- Regression: removing ConfigPanel side panel does not break spectrogram (controls now in dialog).
- Existing `ServerConfigPanel/__tests__` updated for the embedded-no-save-button change.

## Out of scope

- Backend removal of the `panel_order` pref field (frontend simply stops using it).
- Any redesign of `MobileApp` internals beyond it remaining the phone target.
- Reworking which settings are admin vs per-user.

## Open questions / verify during planning

- Exact current placement of `ConfigPanel` (top fixed section vs in `panelOrder`) and how `MobileApp` currently surfaces preferences — ensure the merged dialog is reachable on phone too.
- Whether `AdminPanel`/`ServerConfigPanel` non-embedded Dialog modes are still referenced anywhere (remove if dead).
- Confirm no other consumer of `@dnd-kit/*` before removing the deps.
