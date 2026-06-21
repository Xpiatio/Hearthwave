# Settings Consolidation, Panel Cleanup & Tablet Layout — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge per-user Settings and Admin Settings into one permission-gated dialog with a single footer Save, remove the moveable-panel feature, and route tablets to a touch-friendly desktop layout.

**Architecture:** `SettingsDialog` becomes the single settings surface, rendered once in `App.tsx` (lifted out of `DesktopApp`/`MobileApp`). It owns draft state for Preferences and drives the two admin panels via refs. A new `useDeviceClass` hook splits viewport into phone/tablet/desktop; tablets get `DesktopApp` under a touch-density theme. The @dnd-kit moveable-panel feature is deleted.

**Tech Stack:** React 18 + TypeScript, MUI v5/v6, Vitest + React Testing Library, Vite.

## Global Constraints

- No Claude co-author trailers or PR footers in commits (repo convention).
- Frontend only. Do **not** change backend WebSocket handlers; the `panel_order` field is simply no longer sent (backend may keep accepting it).
- Follow existing MUI patterns; reuse existing prop names/types verbatim (listed per task).
- TDD: write the failing test first, watch it fail, implement, watch it pass, commit.
- Run frontend tests from `frontend/` with `npm test -- --run <path>` (Vitest). Run the full suite with `npm test -- --run` before the final task's commit.
- All component files live under `frontend/src/components/<Name>/<Name>.tsx` with tests in `frontend/src/components/<Name>/__tests__/<Name>.test.tsx`.

---

## File Structure

| File | Responsibility | Task |
|------|----------------|------|
| `frontend/src/hooks/useDeviceClass.ts` (new) | Reactive viewport → `'phone'\|'tablet'\|'desktop'` | A |
| `frontend/src/hooks/useMobileDetect.ts` (modify) | Thin wrapper: `useDeviceClass() === 'phone'` | A |
| `frontend/src/theme.ts` (modify) | Add `withTouchDensity(theme)` | B |
| `frontend/src/components/ConfigPanel/ConfigPanel.tsx` (modify) | Add `hideHeader` prop for in-dialog use | C |
| `frontend/src/components/AdminPanel/AdminPanel.tsx` (modify) | `forwardRef` imperative `save()`, `onDirtyChange`, `hideSaveButton` | D |
| `frontend/src/components/ServerConfigPanel/ServerConfigPanel.tsx` (modify) | Same ref/dirty/hideSaveButton additions | E |
| `frontend/src/components/SettingsDialog/SettingsDialog.tsx` (rewrite) | Draft Preferences tab, gated admin tabs, footer Save/Close, snackbar | F |
| `frontend/src/App.tsx` (modify) | Render dialog once; merge open state; route by device class; touch theme; remove panel-order state | G, H, I |
| `frontend/src/components/AccountMenu/AccountMenu.tsx` (modify) | Single "Settings" item | G |
| `frontend/src/components/DesktopApp/DesktopApp.tsx` (modify) | Remove dnd + ConfigPanel + dialog; fixed-order panels | H |
| `frontend/src/components/MobileApp/MobileApp.tsx` (modify) | Remove SettingsDialog render + its props | G |
| `frontend/src/components/DraggablePanel/**` (delete) | Removed feature | H |
| `frontend/package.json` (modify) | Drop `@dnd-kit/*` deps | H |

---

## Task A: `useDeviceClass` hook

**Files:**
- Create: `frontend/src/hooks/useDeviceClass.ts`
- Modify: `frontend/src/hooks/useMobileDetect.ts`
- Test: `frontend/src/hooks/__tests__/useDeviceClass.test.ts` (new)

**Interfaces:**
- Produces: `type DeviceClass = 'phone' | 'tablet' | 'desktop'`; `function useDeviceClass(): DeviceClass`. Classification: phone = `(pointer: coarse) and (max-width: 600px)`; tablet = `(pointer: coarse) and (min-width: 601px) and (max-width: 1200px)`; desktop = otherwise. Reactive to `matchMedia` `change` events.
- Produces: `useMobileDetect(): boolean` unchanged signature, now `=== 'phone'`.

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/hooks/__tests__/useDeviceClass.test.ts
import { renderHook } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useDeviceClass } from '../useDeviceClass';

type Listener = (e: MediaQueryListEvent) => void;

/** Install a matchMedia mock where `trueQueries` match. Returns a fire() to flip state. */
function installMatchMedia(matchFor: (q: string) => boolean) {
  const listeners: Listener[] = [];
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: matchFor(query),
    media: query,
    addEventListener: (_: string, cb: Listener) => listeners.push(cb),
    removeEventListener: (_: string, cb: Listener) => {
      const i = listeners.indexOf(cb); if (i >= 0) listeners.splice(i, 1);
    },
    addListener: (cb: Listener) => listeners.push(cb),
    removeListener: () => {},
    dispatchEvent: () => true,
  })) as unknown as typeof window.matchMedia;
  return listeners;
}

describe('useDeviceClass', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('returns "phone" for coarse pointer at narrow width', () => {
    installMatchMedia((q) => q.includes('pointer: coarse') || q.includes('max-width: 600px'));
    const { result } = renderHook(() => useDeviceClass());
    expect(result.current).toBe('phone');
  });

  it('returns "tablet" for coarse pointer in the mid width band', () => {
    installMatchMedia((q) =>
      q.includes('pointer: coarse') ||
      (q.includes('min-width: 601px') && q.includes('max-width: 1200px')));
    const { result } = renderHook(() => useDeviceClass());
    expect(result.current).toBe('tablet');
  });

  it('returns "desktop" for a fine pointer', () => {
    installMatchMedia(() => false);
    const { result } = renderHook(() => useDeviceClass());
    expect(result.current).toBe('desktop');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --run src/hooks/__tests__/useDeviceClass.test.ts`
Expected: FAIL — cannot find module `../useDeviceClass`.

- [ ] **Step 3: Create the hook**

```ts
// frontend/src/hooks/useDeviceClass.ts
import { useEffect, useState } from 'react';

export type DeviceClass = 'phone' | 'tablet' | 'desktop';

const PHONE_Q = '(pointer: coarse) and (max-width: 600px)';
const TABLET_Q = '(pointer: coarse) and (min-width: 601px) and (max-width: 1200px)';

function classify(): DeviceClass {
  if (window.matchMedia(PHONE_Q).matches) return 'phone';
  if (window.matchMedia(TABLET_Q).matches) return 'tablet';
  return 'desktop';
}

export function useDeviceClass(): DeviceClass {
  const [deviceClass, setDeviceClass] = useState<DeviceClass>(() => classify());

  useEffect(() => {
    const queries = [PHONE_Q, TABLET_Q].map((q) => window.matchMedia(q));
    const onChange = () => setDeviceClass(classify());
    queries.forEach((mql) => mql.addEventListener('change', onChange));
    onChange(); // resync in case it changed before listeners attached
    return () => queries.forEach((mql) => mql.removeEventListener('change', onChange));
  }, []);

  return deviceClass;
}
```

- [ ] **Step 4: Rewrite `useMobileDetect` on top of it**

```ts
// frontend/src/hooks/useMobileDetect.ts
import { useDeviceClass } from './useDeviceClass';

export function useMobileDetect(): boolean {
  return useDeviceClass() === 'phone';
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npm test -- --run src/hooks/__tests__/useDeviceClass.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/hooks/useDeviceClass.ts frontend/src/hooks/useMobileDetect.ts frontend/src/hooks/__tests__/useDeviceClass.test.ts
git commit -m "feat(frontend): add useDeviceClass hook (phone/tablet/desktop)"
```

---

## Task B: `withTouchDensity` theme helper

**Files:**
- Modify: `frontend/src/theme.ts`
- Test: `frontend/src/__tests__/theme.test.ts` (new)

**Interfaces:**
- Consumes: existing `makeTheme(dark: boolean): Theme` in `theme.ts`.
- Produces: `function withTouchDensity(theme: Theme): Theme` — returns a new theme that bumps touch targets (button `minHeight` 48→56, icon button min 44→52) and is otherwise identical. Used by App for the tablet class.

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/__tests__/theme.test.ts
import { describe, it, expect } from 'vitest';
import { makeTheme, withTouchDensity } from '../theme';

describe('withTouchDensity', () => {
  it('raises button and icon-button minimum touch targets', () => {
    const base = makeTheme(false);
    const touch = withTouchDensity(base);
    expect((touch.components?.MuiButton?.styleOverrides?.root as any).minHeight).toBe(56);
    expect((touch.components?.MuiIconButton?.styleOverrides?.root as any).minHeight).toBe(52);
    expect((touch.components?.MuiIconButton?.styleOverrides?.root as any).minWidth).toBe(52);
  });

  it('preserves palette mode', () => {
    expect(withTouchDensity(makeTheme(true)).palette.mode).toBe('dark');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --run src/__tests__/theme.test.ts`
Expected: FAIL — `withTouchDensity` is not exported.

- [ ] **Step 3: Implement `withTouchDensity`**

Add to `frontend/src/theme.ts` (after the existing `makeTheme` export). Use `createTheme` to merge so the base theme is not mutated:

```ts
import { createTheme, type Theme } from '@mui/material/styles';
// ^ ensure `createTheme` and `Theme` are imported (createTheme already is; add the type import if missing)

export function withTouchDensity(theme: Theme): Theme {
  return createTheme(theme, {
    components: {
      MuiButton: {
        styleOverrides: {
          root: { minHeight: 56 },
          sizeLarge: { minHeight: 64 },
        },
      },
      MuiIconButton: {
        styleOverrides: {
          root: { minHeight: 52, minWidth: 52 },
        },
      },
    },
  });
}
```

> Note: `createTheme(base, overrides)` deep-merges, so palette/typography from `base` are retained and only the listed component minimums are raised.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --run src/__tests__/theme.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/theme.ts frontend/src/__tests__/theme.test.ts
git commit -m "feat(frontend): add withTouchDensity theme helper for tablet layout"
```

---

## Task C: `ConfigPanel` `hideHeader` prop

**Files:**
- Modify: `frontend/src/components/ConfigPanel/ConfigPanel.tsx`
- Test: `frontend/src/components/ConfigPanel/__tests__/ConfigPanel.test.tsx` (add cases)

**Interfaces:**
- Produces: `ConfigPanel` accepts optional `hideHeader?: boolean` (default `false`). When `true`, it renders the controls without the `PanelHeader` and without the bordered `Paper` chrome (plain `Box`), for use inside the Settings dialog.

- [ ] **Step 1: Write the failing test**

```tsx
// add inside the existing describe('ConfigPanel', ...) in ConfigPanel.test.tsx
it('renders the Configuration header by default', () => {
  render(<ConfigPanel {...makeDefaultProps()} />)
  expect(screen.getByText('Configuration')).toBeInTheDocument()
})

it('hides the header when hideHeader is set', () => {
  render(<ConfigPanel {...makeDefaultProps()} hideHeader />)
  expect(screen.queryByText('Configuration')).not.toBeInTheDocument()
  // controls still present
  expect(screen.getByLabelText('Profanity Filter')).toBeInTheDocument()
})
```

> If `Profanity Filter` is rendered as a switch label, `getByLabelText` resolves the `FormControlLabel`. If this selector fails when you run it, fall back to `screen.getByText('Profanity Filter')`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --run src/components/ConfigPanel/__tests__/ConfigPanel.test.tsx`
Expected: FAIL — header still shown / `hideHeader` not a prop.

- [ ] **Step 3: Implement the prop**

In `ConfigPanel.tsx`:

1. Add to the `Props` interface: `hideHeader?: boolean;`
2. Add `hideHeader = false,` to the destructured params.
3. Replace the outer `Paper` + `PanelHeader` wrapper so that when `hideHeader` is true it renders a plain `Box` with the same inner content and no header:

```tsx
const body = (
  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center', px: 2, py: 1.5 }}>
    {/* ...existing inner controls unchanged... */}
  </Box>
);

if (hideHeader) {
  return (
    <Box role="region" aria-label="Configuration" sx={{ overflow: 'hidden' }}>
      {body}
    </Box>
  );
}

return (
  <Paper elevation={0} square sx={{ borderBottom: 1, borderColor: 'divider', overflow: 'hidden' }} role="region" aria-label="Configuration">
    <PanelHeader title="Configuration" gradient="linear-gradient(135deg, #1A3A5C 0%, #1E4976 100%)" />
    {body}
  </Paper>
);
```

> Mechanical extraction: move the current `<Box sx={{ display:'flex'... }}>...</Box>` (lines 74–191) into `body`, leave its children identical.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- --run src/components/ConfigPanel/__tests__/ConfigPanel.test.tsx`
Expected: PASS (existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ConfigPanel/ConfigPanel.tsx frontend/src/components/ConfigPanel/__tests__/ConfigPanel.test.tsx
git commit -m "feat(frontend): add hideHeader prop to ConfigPanel for in-dialog use"
```

---

## Task D: `AdminPanel` — imperative save, dirty reporting, hideable save button

**Files:**
- Modify: `frontend/src/components/AdminPanel/AdminPanel.tsx`
- Test: `frontend/src/components/AdminPanel/__tests__/AdminPanel.test.tsx` (add cases)

**Interfaces:**
- Produces: `export interface AdminPanelHandle { save(): void }`. `AdminPanel` is wrapped in `forwardRef<AdminPanelHandle, Props>`. New optional props: `hideSaveButton?: boolean` (default `false`) and `onDirtyChange?: (dirty: boolean) => void`.
- The imperative `save()` calls `onSave(buildValues())` and updates the internal seed snapshot but does **not** call `onClose`.
- `onDirtyChange` fires whenever the form differs from the values it was seeded with on open.
- Consumed by: Task F (`SettingsDialog`).

- [ ] **Step 1: Write the failing test**

```tsx
// add to AdminPanel.test.tsx
import { createRef } from 'react'
import type { AdminPanelHandle } from '../AdminPanel'

it('exposes an imperative save() that calls onSave without closing', async () => {
  const onSave = vi.fn(); const onClose = vi.fn()
  const ref = createRef<AdminPanelHandle>()
  render(<AdminPanel {...makeDefaultProps()} ref={ref} onSave={onSave} onClose={onClose} embedded />)
  ref.current!.save()
  expect(onSave).toHaveBeenCalledTimes(1)
  expect(onClose).not.toHaveBeenCalled()
})

it('reports dirty state via onDirtyChange when a field changes', async () => {
  const onDirtyChange = vi.fn()
  render(<AdminPanel {...makeDefaultProps()} embedded onDirtyChange={onDirtyChange} />)
  // initial mount reports clean
  expect(onDirtyChange).toHaveBeenLastCalledWith(false)
  const nameField = screen.getByLabelText(/station name/i)
  await userEvent.type(nameField, 'X')
  expect(onDirtyChange).toHaveBeenLastCalledWith(true)
})

it('hides the embedded Save button when hideSaveButton is set', () => {
  render(<AdminPanel {...makeDefaultProps()} embedded hideSaveButton />)
  expect(screen.queryByRole('button', { name: /^save$/i })).not.toBeInTheDocument()
})
```

> Confirm the station-name field's accessible label when running; adjust the `/station name/i` matcher to the actual `TextField` label if needed.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --run src/components/AdminPanel/__tests__/AdminPanel.test.tsx`
Expected: FAIL — no `AdminPanelHandle` export / ref not forwarded / props missing.

- [ ] **Step 3: Refactor AdminPanel**

In `AdminPanel.tsx`:

1. Add to imports: `import { forwardRef, useImperativeHandle, useRef, useEffect } from 'react';` (merge with existing React imports).
2. Export the handle type and add props:

```tsx
export interface AdminPanelHandle { save(): void }
// in Props interface add:
//   hideSaveButton?: boolean;
//   onDirtyChange?: (dirty: boolean) => void;
```

3. Convert the component to `forwardRef`:

```tsx
export const AdminPanel = forwardRef<AdminPanelHandle, Props>(function AdminPanel(
  { embedded, open, onClose, config, voices, voicePreviewBusy, onSave, onPreviewVoice,
    hideSaveButton = false, onDirtyChange, children }, ref) {
  // ...existing useState hooks unchanged...
```

4. Factor the payload builder out of `handleSave`:

```tsx
function buildValues() {
  return {
    callsign: callsign.trim().toUpperCase() || 'N0CALL',
    name: name.trim(),
    location: location.trim(),
    voice: voice.trim(),
    tts_length_scale: lengthScale,
    gemini_api_key: geminiKey.trim(),
    journals_dir: journalsDir.trim(),
    ncs_zone: ncsZone.trim().toUpperCase(),
    rx_mode: rxMode,
  };
}

const seedRef = useRef<string>('');
```

5. In the existing open-seeding `useEffect` (the one that resets local state when the dialog opens), after seeding the state, also snapshot the seed. Because state setters are async, compute the seed from `config` directly:

```tsx
// inside the open effect, after the setState calls:
seedRef.current = JSON.stringify({
  callsign: (config.stationCallsign || '').toUpperCase() || 'N0CALL',
  name: config.stationName, location: config.stationLocation, voice: config.stationVoice,
  tts_length_scale: config.stationLengthScale, gemini_api_key: '', // key is write-only (geminiApiKeySet)
  journals_dir: config.journalsDir, ncs_zone: (config.ncsZone || '').toUpperCase(),
  rx_mode: config.rxMode,
});
```

> The seed must be computed the same way `buildValues()` serializes, so an untouched form compares equal. `geminiKey` initializes to `''` on open (the panel only shows whether a key is set, not the value), so seed uses `''` to match.

6. Report dirty on every render (cheap; React bails out on equal state):

```tsx
useEffect(() => {
  onDirtyChange?.(JSON.stringify(buildValues()) !== seedRef.current);
});
```

7. Rework save handlers and imperative handle:

```tsx
function commitValues() {
  const values = buildValues();
  onSave(values);
  seedRef.current = JSON.stringify(values);
}
useImperativeHandle(ref, () => ({ save: commitValues }), [/* recreated each render is fine */]);

function handleSave() { // used only by the embedded/standalone button
  commitValues();
  onClose();
}
```

8. Gate the embedded Save button:

```tsx
const saveButton = hideSaveButton ? null : (
  <Button onClick={handleSave} variant="contained">Save</Button>
);
// keep the existing embedded/standalone render blocks; when saveButton is null the flex row renders empty (harmless)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- --run src/components/AdminPanel/__tests__/AdminPanel.test.tsx`
Expected: PASS (existing + 3 new).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/AdminPanel/AdminPanel.tsx frontend/src/components/AdminPanel/__tests__/AdminPanel.test.tsx
git commit -m "feat(frontend): AdminPanel imperative save + dirty reporting"
```

---

## Task E: `ServerConfigPanel` — imperative save, dirty reporting, hideable save button

**Files:**
- Modify: `frontend/src/components/ServerConfigPanel/ServerConfigPanel.tsx`
- Test: `frontend/src/components/ServerConfigPanel/__tests__/ServerConfigPanel.test.tsx` (add cases)

**Interfaces:**
- Produces: `export interface ServerConfigPanelHandle { save(): void }`. `ServerConfigPanel` wrapped in `forwardRef<ServerConfigPanelHandle, Props>`. New optional props: `hideSaveButton?: boolean`, `onDirtyChange?: (dirty: boolean) => void`. `save()` calls `onSave(buildValues())` (the existing `ServerConfigSaveValues` payload) and updates the seed; no `onClose`.
- Consumed by: Task F.

- [ ] **Step 1: Write the failing test**

```tsx
// add to ServerConfigPanel.test.tsx
import { createRef } from 'react'
import type { ServerConfigPanelHandle } from '../ServerConfigPanel'

it('exposes imperative save() that calls onSave without closing', () => {
  const onSave = vi.fn(); const onClose = vi.fn()
  const ref = createRef<ServerConfigPanelHandle>()
  render(<ServerConfigPanel {...makeDefaultProps()} ref={ref} onSave={onSave} onClose={onClose} embedded />)
  ref.current!.save()
  expect(onSave).toHaveBeenCalledTimes(1)
  expect(onClose).not.toHaveBeenCalled()
})

it('hides the embedded Save button when hideSaveButton is set', () => {
  render(<ServerConfigPanel {...makeDefaultProps()} embedded hideSaveButton />)
  expect(screen.queryByRole('button', { name: /^save$/i })).not.toBeInTheDocument()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --run src/components/ServerConfigPanel/__tests__/ServerConfigPanel.test.tsx`
Expected: FAIL — no handle export / ref not forwarded.

- [ ] **Step 3: Refactor ServerConfigPanel**

Apply the same pattern as Task D:

1. Add `forwardRef, useImperativeHandle, useRef, useEffect` to the React import.
2. Export `export interface ServerConfigPanelHandle { save(): void }` and add `hideSaveButton?: boolean; onDirtyChange?: (dirty: boolean) => void;` to `Props`.
3. Wrap as `export const ServerConfigPanel = forwardRef<ServerConfigPanelHandle, Props>(function ServerConfigPanel({ open, onClose, config, onSave, embedded = false, onRescanVocabulary, hideSaveButton = false, onDirtyChange }, ref) { ... })`.
4. Factor `buildValues()` returning the exact `ServerConfigSaveValues` object currently built inline in `handleSave` (lines 180–204) — move that object literal into `buildValues()`.
5. Add `const seedRef = useRef<string>('');` and, inside the existing open-seeding effect, set `seedRef.current = JSON.stringify(buildValues());` **after** the state has been seeded — but since setState is async, instead compute the seed from `config` mirroring `buildValues()`'s serialization. Define a helper that maps a `ServerConfig` to the save-values shape and use it both to seed local state and to compute `seedRef`:

```tsx
function valuesFromConfig(c: ServerConfig) {
  return {
    vad_threshold: c.vadThreshold, whisper_model: c.whisperModel, whisper_model_final: c.whisperModelFinal,
    squelch_adaptive: c.squelchAdaptive, stt_debug_capture: c.sttDebugCapture, tx_conditioning: c.txConditioning,
    vox_primer_enabled: c.voxPrimerEnabled, vox_primer_ms: c.voxPrimerMs,
    vox_primer_word_enabled: c.voxPrimerWordEnabled, vox_primer_word: c.voxPrimerWord.trim(),
    ptt_mode: c.pttMode, ptt_serial_port: c.pttSerialPort.trim(), ptt_serial_line: c.pttSerialLine,
    monitor_passthrough: c.monitorPassthrough, attendance_enabled: c.attendanceEnabled, saved_phrases: c.savedPhrases,
    meshcore_enabled: c.meshcoreEnabled, meshcore_serial_port: c.meshcoreSerialPort.trim(),
    meshcore_baud: c.meshcoreBaud, meshcore_max_packet_length: c.meshcoreMaxPacketLength,
    meshcore_prefix_separator: c.meshcorePrefixSeparator, meshcore_channel_idx: c.meshcoreChannelIdx,
  };
}
// in the open effect: seedRef.current = JSON.stringify(valuesFromConfig(config));
```

6. Add the dirty-reporting effect: `useEffect(() => { onDirtyChange?.(JSON.stringify(buildValues()) !== seedRef.current); });`
7. Add `commitValues()`/`useImperativeHandle`/gated `saveButton` exactly as in Task D step 7–8.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- --run src/components/ServerConfigPanel/__tests__/ServerConfigPanel.test.tsx`
Expected: PASS (existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ServerConfigPanel/ServerConfigPanel.tsx frontend/src/components/ServerConfigPanel/__tests__/ServerConfigPanel.test.tsx
git commit -m "feat(frontend): ServerConfigPanel imperative save + dirty reporting"
```

---

## Task F: Rewrite `SettingsDialog` — Preferences tab, gated admin tabs, footer Save/Close

**Files:**
- Modify: `frontend/src/components/SettingsDialog/SettingsDialog.tsx`
- Test: `frontend/src/components/SettingsDialog/__tests__/SettingsDialog.test.tsx` (new — create `__tests__` dir if absent)

**Interfaces:**
- Consumes: `ConfigPanel` (`hideHeader`), `AdminPanel`+`AdminPanelHandle`, `ServerConfigPanel`+`ServerConfigPanelHandle`.
- Produces: new `SettingsDialog` props (full list below). The dialog owns Preferences draft state, holds refs to the two admin panels, renders one footer `Save` (left) + `Close` (right), keeps itself open after Save (shows a confirmation Snackbar), and only renders Station/System tabs when `isAdmin`.

New `Props` (replace the existing interface):

```tsx
interface Props {
  open: boolean;
  onClose: () => void;
  isAdmin: boolean;

  // Preferences tab (per-user, applied on Save)
  filterProfanity: boolean;
  fuzzyCallsign: boolean;
  inputDevice: string | number;
  systemMonitorSink: string;
  inputDevices: InputDeviceOption[];
  monitorSinks: MonitorSinkOption[];
  outputDevice: number;
  outputDevices: OutputDeviceOption[];
  spectroColormap: 'viridis' | 'grayscale';
  spectroFreqRange: 'voice' | 'full';
  spectroTimeWindowS: number;
  onToggleProfanity: () => void;
  onToggleFuzzy: () => void;
  onInputDeviceChange: (device: string | number, sink: string) => void;
  onOutputDeviceChange: (device: number) => void;
  onSpectroColormapChange: (cm: 'viridis' | 'grayscale') => void;
  onSpectroFreqRangeChange: (range: 'voice' | 'full') => void;
  onSpectroTimeWindowChange: (s: number) => void;

  // Station tab (admin only)
  adminConfig: React.ComponentProps<typeof AdminPanel>['config'];
  voices: React.ComponentProps<typeof AdminPanel>['voices'];
  voicePreviewBusy: boolean;
  onAdminSave: React.ComponentProps<typeof AdminPanel>['onSave'];
  onPreviewVoice: React.ComponentProps<typeof AdminPanel>['onPreviewVoice'];
  usersPanel?: React.ReactNode;

  // System tab (admin only)
  serverConfig: React.ComponentProps<typeof ServerConfigPanel>['config'];
  onServerConfigSave: React.ComponentProps<typeof ServerConfigPanel>['onSave'];
  onRescanVocabulary?: () => void;
}
```

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/SettingsDialog/__tests__/SettingsDialog.test.tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { SettingsDialog } from '../SettingsDialog'

function makeProps(overrides = {}) {
  return {
    open: true, onClose: vi.fn(), isAdmin: true,
    filterProfanity: false, fuzzyCallsign: false, inputDevice: -1, systemMonitorSink: '',
    inputDevices: [], monitorSinks: [], outputDevice: -1, outputDevices: [],
    spectroColormap: 'viridis' as const, spectroFreqRange: 'full' as const, spectroTimeWindowS: 30,
    onToggleProfanity: vi.fn(), onToggleFuzzy: vi.fn(), onInputDeviceChange: vi.fn(),
    onOutputDeviceChange: vi.fn(), onSpectroColormapChange: vi.fn(),
    onSpectroFreqRangeChange: vi.fn(), onSpectroTimeWindowChange: vi.fn(),
    adminConfig: {
      stationCallsign: 'N0CALL', stationName: '', stationLocation: '', stationVoice: '',
      stationLengthScale: 1, geminiApiKeySet: false, journalsDir: '', ncsZone: '', rxMode: 'voice',
    },
    voices: [], voicePreviewBusy: false, onAdminSave: vi.fn(), onPreviewVoice: vi.fn(),
    serverConfig: {
      vadThreshold: 0.5, whisperModel: 'base', whisperModelFinal: '', squelchAdaptive: false,
      sttDebugCapture: false, txConditioning: false, voxPrimerEnabled: false, voxPrimerMs: 0,
      voxPrimerWordEnabled: false, voxPrimerWord: '', pttMode: 'manual', pttSerialPort: '',
      pttSerialLine: 'RTS', monitorPassthrough: false, attendanceEnabled: false, savedPhrases: [],
      meshcoreEnabled: false, meshcoreSerialPort: '', meshcoreBaud: 115200,
      meshcoreMaxPacketLength: 180, meshcorePrefixSeparator: ': ', meshcoreChannelIdx: 0,
    },
    onServerConfigSave: vi.fn(), onRescanVocabulary: vi.fn(),
    ...overrides,
  }
}

describe('SettingsDialog', () => {
  it('shows all three tabs for an admin', () => {
    render(<SettingsDialog {...makeProps()} />)
    expect(screen.getByRole('tab', { name: 'Preferences' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Station' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'System' })).toBeInTheDocument()
  })

  it('shows only Preferences for a non-admin (no tab bar)', () => {
    render(<SettingsDialog {...makeProps({ isAdmin: false })} />)
    expect(screen.queryByRole('tab', { name: 'Station' })).not.toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: 'System' })).not.toBeInTheDocument()
  })

  it('disables Save until something changes, then applies a preference on Save and stays open', async () => {
    const onToggleProfanity = vi.fn(); const onClose = vi.fn()
    render(<SettingsDialog {...makeProps({ onToggleProfanity, onClose })} />)
    const save = screen.getByRole('button', { name: /^save$/i })
    expect(save).toBeDisabled()
    await userEvent.click(screen.getByText('Profanity Filter'))
    expect(save).toBeEnabled()
    await userEvent.click(save)
    expect(onToggleProfanity).toHaveBeenCalledTimes(1)
    expect(onClose).not.toHaveBeenCalled()        // stays open
    expect(screen.getByText(/settings saved/i)).toBeInTheDocument()
  })

  it('titles the dialog "Settings"', () => {
    render(<SettingsDialog {...makeProps()} />)
    expect(screen.getByText('Settings')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --run src/components/SettingsDialog/__tests__/SettingsDialog.test.tsx`
Expected: FAIL — props/behavior not implemented.

- [ ] **Step 3: Rewrite `SettingsDialog.tsx`**

```tsx
import React, { useEffect, useRef, useState } from 'react';
import {
  Dialog, DialogTitle, DialogContent, DialogActions, Button, Tabs, Tab, Box, Snackbar, Alert,
  useMediaQuery, useTheme,
} from '@mui/material';
import { ConfigPanel } from '../ConfigPanel/ConfigPanel';
import { AdminPanel, type AdminPanelHandle } from '../AdminPanel/AdminPanel';
import { ServerConfigPanel, type ServerConfigPanelHandle } from '../ServerConfigPanel/ServerConfigPanel';
import type { InputDeviceOption, MonitorSinkOption, OutputDeviceOption } from '../../types/ws';

// ...Props interface from the Interfaces section above...

interface PrefsDraft {
  filterProfanity: boolean; fuzzyCallsign: boolean; inputDevice: string | number;
  systemMonitorSink: string; outputDevice: number;
  spectroColormap: 'viridis' | 'grayscale'; spectroFreqRange: 'voice' | 'full'; spectroTimeWindowS: number;
}

export function SettingsDialog(props: Props) {
  const { open, onClose, isAdmin } = props;
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'));
  const [tab, setTab] = useState(0);
  const [saved, setSaved] = useState(false);

  const adminRef = useRef<AdminPanelHandle>(null);
  const serverRef = useRef<ServerConfigPanelHandle>(null);
  const [adminDirty, setAdminDirty] = useState(false);
  const [serverDirty, setServerDirty] = useState(false);

  // Preferences draft, (re)seeded each time the dialog opens.
  const seedPrefs = (): PrefsDraft => ({
    filterProfanity: props.filterProfanity, fuzzyCallsign: props.fuzzyCallsign,
    inputDevice: props.inputDevice, systemMonitorSink: props.systemMonitorSink,
    outputDevice: props.outputDevice, spectroColormap: props.spectroColormap,
    spectroFreqRange: props.spectroFreqRange, spectroTimeWindowS: props.spectroTimeWindowS,
  });
  const [draft, setDraft] = useState<PrefsDraft>(seedPrefs);
  const [prefsSeed, setPrefsSeed] = useState<PrefsDraft>(seedPrefs);

  useEffect(() => {
    if (open) {
      const s = seedPrefs();
      setDraft(s); setPrefsSeed(s); setTab(0); setAdminDirty(false); setServerDirty(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const prefsDirty = JSON.stringify(draft) !== JSON.stringify(prefsSeed);
  const dirty = prefsDirty || (isAdmin && (adminDirty || serverDirty));

  function applyPrefs() {
    if (draft.filterProfanity !== prefsSeed.filterProfanity) props.onToggleProfanity();
    if (draft.fuzzyCallsign !== prefsSeed.fuzzyCallsign) props.onToggleFuzzy();
    if (draft.inputDevice !== prefsSeed.inputDevice || draft.systemMonitorSink !== prefsSeed.systemMonitorSink)
      props.onInputDeviceChange(draft.inputDevice, draft.systemMonitorSink);
    if (draft.outputDevice !== prefsSeed.outputDevice) props.onOutputDeviceChange(draft.outputDevice);
    if (draft.spectroColormap !== prefsSeed.spectroColormap) props.onSpectroColormapChange(draft.spectroColormap);
    if (draft.spectroFreqRange !== prefsSeed.spectroFreqRange) props.onSpectroFreqRangeChange(draft.spectroFreqRange);
    if (draft.spectroTimeWindowS !== prefsSeed.spectroTimeWindowS) props.onSpectroTimeWindowChange(draft.spectroTimeWindowS);
  }

  function handleSave() {
    if (prefsDirty) { applyPrefs(); setPrefsSeed(draft); }
    if (isAdmin && adminDirty) { adminRef.current?.save(); setAdminDirty(false); }
    if (isAdmin && serverDirty) { serverRef.current?.save(); setServerDirty(false); }
    setSaved(true);
  }

  function handleClose() {
    if (dirty && !window.confirm('Discard unsaved changes?')) return;
    onClose();
  }

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth fullScreen={fullScreen}>
      <DialogTitle sx={{ fontWeight: 700, pb: 0 }}>Settings</DialogTitle>

      {isAdmin && (
        <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="scrollable" allowScrollButtonsMobile
              sx={{ px: 3, borderBottom: 1, borderColor: 'divider' }} aria-label="Settings sections">
          <Tab label="Preferences" />
          <Tab label="Station" />
          <Tab label="System" />
        </Tabs>
      )}

      <DialogContent dividers>
        <Box role="tabpanel" hidden={isAdmin && tab !== 0}>
          <ConfigPanel
            hideHeader
            filterProfanity={draft.filterProfanity}
            fuzzyCallsign={draft.fuzzyCallsign}
            inputDevice={draft.inputDevice}
            systemMonitorSink={draft.systemMonitorSink}
            inputDevices={props.inputDevices}
            monitorSinks={props.monitorSinks}
            outputDevice={draft.outputDevice}
            outputDevices={props.outputDevices}
            spectroColormap={draft.spectroColormap}
            spectroFreqRange={draft.spectroFreqRange}
            spectroTimeWindowS={draft.spectroTimeWindowS}
            onToggleProfanity={() => setDraft((d) => ({ ...d, filterProfanity: !d.filterProfanity }))}
            onToggleFuzzy={() => setDraft((d) => ({ ...d, fuzzyCallsign: !d.fuzzyCallsign }))}
            onInputDeviceChange={(device, sink) => setDraft((d) => ({ ...d, inputDevice: device, systemMonitorSink: sink }))}
            onOutputDeviceChange={(device) => setDraft((d) => ({ ...d, outputDevice: device }))}
            onSpectroColormapChange={(cm) => setDraft((d) => ({ ...d, spectroColormap: cm }))}
            onSpectroFreqRangeChange={(range) => setDraft((d) => ({ ...d, spectroFreqRange: range }))}
            onSpectroTimeWindowChange={(s) => setDraft((d) => ({ ...d, spectroTimeWindowS: s }))}
          />
        </Box>

        {isAdmin && (
          <Box role="tabpanel" hidden={tab !== 1}>
            <AdminPanel
              ref={adminRef} embedded hideSaveButton open={open} onClose={onClose}
              config={props.adminConfig} voices={props.voices} voicePreviewBusy={props.voicePreviewBusy}
              onSave={props.onAdminSave} onPreviewVoice={props.onPreviewVoice}
              onDirtyChange={setAdminDirty}
            >
              {props.usersPanel}
            </AdminPanel>
          </Box>
        )}

        {isAdmin && (
          <Box role="tabpanel" hidden={tab !== 2}>
            <ServerConfigPanel
              ref={serverRef} embedded hideSaveButton open={open} onClose={onClose}
              config={props.serverConfig} onSave={props.onServerConfigSave}
              onRescanVocabulary={props.onRescanVocabulary} onDirtyChange={setServerDirty}
            />
          </Box>
        )}
      </DialogContent>

      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={handleSave} variant="contained" disabled={!dirty}>Save</Button>
        <Button onClick={handleClose} variant="outlined">Close</Button>
      </DialogActions>

      <Snackbar open={saved} autoHideDuration={2500} onClose={() => setSaved(false)}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
        <Alert severity="success" variant="filled" onClose={() => setSaved(false)}>Settings saved</Alert>
      </Snackbar>
    </Dialog>
  );
}
```

> Note: both admin panels stay mounted (only `hidden` toggles), preserving unsaved edits across tab switches — same behavior as today. The `onDirtyChange` effect in each panel reports its current dirty state on mount, so `adminDirty`/`serverDirty` initialize correctly.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- --run src/components/SettingsDialog/__tests__/SettingsDialog.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/SettingsDialog/SettingsDialog.tsx frontend/src/components/SettingsDialog/__tests__/SettingsDialog.test.tsx
git commit -m "feat(frontend): unified Settings dialog with Preferences tab + footer Save"
```

---

## Task G: Lift the dialog to App, merge open state, single AccountMenu item

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/AccountMenu/AccountMenu.tsx`
- Modify: `frontend/src/components/MobileApp/MobileApp.tsx`
- Modify: `frontend/src/components/DesktopApp/DesktopApp.tsx` (remove its `<SettingsDialog>` render only)
- Test: update `frontend/src/components/AccountMenu/__tests__/AccountMenu.test.tsx`

**Interfaces:**
- Consumes: `SettingsDialog` (Task F props).
- Produces: `App` owns a single `showSettings` boolean and renders `<SettingsDialog>` once. `AccountMenu` exposes `showSettings: boolean; onToggleSettings: () => void;` (replacing `showConfig/onToggleConfig/showAdmin/onToggleAdmin`) and renders one "Settings" `MenuItem` for all users.

- [ ] **Step 1 (AccountMenu): Write/adjust the failing test**

```tsx
// AccountMenu.test.tsx — replace tests referencing showConfig/showAdmin/"Admin Settings"
it('renders a single Settings item that toggles settings', async () => {
  const onToggleSettings = vi.fn()
  render(<AccountMenu {...baseProps} showSettings={false} onToggleSettings={onToggleSettings} />)
  await userEvent.click(screen.getByRole('button', { name: /account/i })) // open the menu (adjust to actual trigger)
  await userEvent.click(screen.getByText('Settings'))
  expect(onToggleSettings).toHaveBeenCalled()
  expect(screen.queryByText('Admin Settings')).not.toBeInTheDocument()
})
```

> Adjust `baseProps` and the menu-trigger selector to the existing test's helpers.

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && npm test -- --run src/components/AccountMenu/__tests__/AccountMenu.test.tsx`
Expected: FAIL — props renamed / two items still present.

- [ ] **Step 3 (AccountMenu): Implement**

In `AccountMenu.tsx`:
1. In `Props`, replace `showConfig/onToggleConfig/showAdmin/onToggleAdmin` with `showSettings: boolean; onToggleSettings: () => void;`.
2. Update the destructured params accordingly.
3. Replace both menu items (lines 173–182) with one (shown to everyone):

```tsx
<MenuItem selected={showSettings} onClick={() => { onToggleSettings(); handleClose(); }}>
  <ListItemIcon><SettingsIcon fontSize="small" /></ListItemIcon>
  Settings
</MenuItem>
```

4. Remove the now-unused `AdminPanelSettingsIcon` import.

- [ ] **Step 4 (App.tsx): merge state + render dialog once**

In `App.tsx`:
1. Replace `const [showConfig, setShowConfig] = useState(false);` and `const [showAdmin, setShowAdmin] = useState(false);` (lines 146–147) with:

```tsx
const [showSettings, setShowSettings] = useState(false);
```

2. Add a toggle handler near the other handlers: `const handleToggleSettings = () => setShowSettings((v) => !v);`
3. In `sharedProps` (≈ lines 1048–1133), remove `showConfig, showAdmin, onToggleConfig, onToggleAdmin` and add `showSettings, onToggleSettings: handleToggleSettings`. (The pref values/callbacks stay available in App for the dialog.)
4. Import `SettingsDialog` and `UsersPanel` into App (UsersPanel currently imported in MobileApp/DesktopApp). Build the dialog once, just inside the routing area (sibling of the `{isMobile ? ... : ...}` block):

```tsx
<SettingsDialog
  open={showSettings}
  onClose={handleToggleSettings}
  isAdmin={!!profile?.is_admin}
  filterProfanity={filterProfanity}
  fuzzyCallsign={fuzzyCallsign}
  inputDevice={inputDevice}
  systemMonitorSink={systemMonitorSink}
  inputDevices={inputDevices}
  monitorSinks={monitorSinks}
  outputDevice={outputDevice}
  outputDevices={outputDevices}
  spectroColormap={spectroColormap}
  spectroFreqRange={spectroFreqRange}
  spectroTimeWindowS={spectroTimeWindowS}
  onToggleProfanity={handleToggleProfanity}
  onToggleFuzzy={handleToggleFuzzy}
  onInputDeviceChange={handleInputDeviceChange}
  onOutputDeviceChange={handleOutputDeviceChange}
  onSpectroColormapChange={handleSpectroColormapChange}
  onSpectroFreqRangeChange={handleSpectroFreqRangeChange}
  onSpectroTimeWindowChange={handleSpectroTimeWindowChange}
  adminConfig={adminConfig}
  voices={voices}
  voicePreviewBusy={voicePreviewBusy}
  onAdminSave={handleAdminSave}
  onPreviewVoice={handlePreviewVoice}
  serverConfig={serverConfig}
  onServerConfigSave={handleServerConfigSave}
  onRescanVocabulary={handleRescanVocabulary}
  usersPanel={profile?.is_admin && (
    <UsersPanel
      profiles={profiles}
      currentUserId={profile.id}
      onCreateProfile={(data) => send({ type: 'create_profile', ...data })}
      onDeleteProfile={(userId) => send({ type: 'delete_profile', user_id: userId })}
      onResetLockout={(userId) => send({ type: 'reset_lockout', user_id: userId })}
    />
  )}
/>
```

> Use the exact handler names already defined in App for `onAdminSave`/`onServerConfigSave`/`onPreviewVoice`/`onRescanVocabulary` — these are whatever App currently passes into `sharedProps` as `onAdminSave`, `onServerConfigSave`, `onPreviewVoice`, `onRescanVocabulary`. If they exist only as `sharedProps` keys, reference those same identifiers.

5. Remove `showConfig`/`showAdmin` from the props passed to `DesktopApp` (the explicit list around lines 1151–1187 doesn't pass them, but `sharedProps` did — handled in step 3).

- [ ] **Step 5 (MobileApp): remove its SettingsDialog**

In `MobileApp.tsx`:
1. Delete the `<SettingsDialog .../>` render block (lines ≈379–399) and the `import { SettingsDialog }`.
2. Remove now-unused props from `MobileAppProps` and the destructure: `showConfig, showAdmin, onToggleConfig, onToggleAdmin, onAdminSave, onServerConfigSave, adminConfig, serverConfig, onRescanVocabulary` — **but** keep any of these still used elsewhere in MobileApp. Check usages first (`grep -n` within the file); remove only the ones whose sole use was the dialog. Keep `voices`, `voicePreviewBusy`, `onPreviewVoice` if used by other mobile UI.
3. Ensure the AccountMenu rendered inside MobileApp now receives `showSettings`/`onToggleSettings` (from `sharedProps`) instead of the old four props.

- [ ] **Step 6 (DesktopApp): remove its SettingsDialog render**

In `DesktopApp.tsx`: delete the `<SettingsDialog .../>` render and its import. (ConfigPanel/dnd removal happens in Task H.) Update the AccountMenu usage in DesktopApp to pass `showSettings`/`onToggleSettings`.

- [ ] **Step 7: Run the affected suites**

Run: `cd frontend && npm test -- --run src/components/AccountMenu src/components/SettingsDialog`
Expected: PASS. Then `npx tsc --noEmit` (from `frontend/`) to confirm the App/MobileApp/DesktopApp prop changes typecheck.
Expected: no type errors. Fix any prop mismatches surfaced (these guide which `MobileAppProps`/`DesktopAppProps` fields to drop).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/AccountMenu frontend/src/components/MobileApp/MobileApp.tsx frontend/src/components/DesktopApp/DesktopApp.tsx
git commit -m "feat(frontend): render unified Settings dialog once in App; single menu entry"
```

---

## Task H: Remove the moveable-panel feature and the ConfigPanel side panel

**Files:**
- Delete: `frontend/src/components/DraggablePanel/DraggablePanel.tsx`, `frontend/src/components/DraggablePanel/__tests__/DraggablePanel.test.tsx`
- Modify: `frontend/src/components/DesktopApp/DesktopApp.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/package.json`

**Interfaces:**
- Produces: `DesktopApp` renders Attendance → Journal → NCS in fixed order (config panel removed; it now lives in the Settings dialog). `App` no longer has `panelOrder`/`handlePanelDragEnd`/`handlePanelMove`.

- [ ] **Step 1: Remove dnd + ConfigPanel from DesktopApp**

In `DesktopApp.tsx`:
1. Delete imports: `DndContext, useSensors, useSensor, PointerSensor, KeyboardSensor` (line 2), `SortableContext, verticalListSortingStrategy, sortableKeyboardCoordinates` (line 4), `DraggablePanel` (line 5), `ConfigPanel` (line 21), and the `arrayMove` import if present.
2. Remove the `sensors` setup.
3. Remove from `DesktopAppProps`: the 18 ConfigPanel pref props (lines 94–112: `filterProfanity` … `onSpectroTimeWindowChange`), and `panelOrder`, `onPanelDragEnd`, `onPanelMove`. Keep `adminConfig`/`serverConfig`/admin save props only if still used by DesktopApp — after Task G's dialog removal they are not, so remove `adminConfig, serverConfig, voices, voicePreviewBusy, onAdminSave, onServerConfigSave, onRescanVocabulary` too if no remaining reference (grep within the file to confirm).
4. Replace the `<DndContext>…</DndContext>` block (lines 385–481) with a plain fixed-order render (drop the `config` branch entirely):

```tsx
<>
  {showAttendance && (
    <AttendancePanel stations={attendanceStations} onClear={onClearAttendance} />
  )}
  {showJournal && (
    <JournalPanel
      journals={journals} pendingResult={journalResult} generating={journalGenerating}
      journalError={journalError} rxTexts={rxTexts} rxCallsigns={rxCallsigns}
      onListJournals={onListJournals} onGenerate={onGenerate} onSave={onSaveJournal}
      onDelete={onDeleteJournal} onPublish={onPublishJournal} onUnpublish={onUnpublishJournal}
      onDismissResult={onDismissJournalResult}
    />
  )}
  {showNcs && (
    <NCSPanel send={send} lastMessage={lastMessage} contacts={contacts}
              channelClear={channelClear} transmitting={transmitting} />
  )}
</>
```

> Each panel keeps its own `PanelHeader`; only the `DraggablePanel` wrapper and move arrows are gone. Confirm each panel's props match the originals copied above.

- [ ] **Step 2: Remove panel-order state from App**

In `App.tsx`:
1. Delete `panelOrder` state (lines 174–180), `handlePanelDragEnd` (≈911–922) and `handlePanelMove` (≈924–934).
2. Delete the `panelOrder`, `onPanelDragEnd`, `onPanelMove` props from the `<DesktopApp>` render, and the 18 ConfigPanel pref props from the `<DesktopApp>` render (they now feed `SettingsDialog` only). Keep the pref **state and handlers** in App (the dialog uses them).
3. Remove `@dnd-kit` imports from App (`DragEndEvent`, `arrayMove`, etc.).

- [ ] **Step 3: Delete DraggablePanel and its test**

```bash
git rm -r frontend/src/components/DraggablePanel
```

- [ ] **Step 4: Drop the @dnd-kit dependencies**

```bash
cd frontend && npm uninstall @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities
```

Verify nothing else imports them:

Run: `cd frontend && grep -rn "@dnd-kit" src`
Expected: no output.

- [ ] **Step 5: Typecheck + run the suite**

Run: `cd frontend && npx tsc --noEmit && npm test -- --run`
Expected: no type errors; all tests pass. Fix any dangling references the compiler flags.

- [ ] **Step 6: Commit**

```bash
git add -A frontend
git commit -m "refactor(frontend): remove moveable panels and ConfigPanel side panel; fixed panel order"
```

---

## Task I: Route tablets to the touch-friendly desktop layout

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/__tests__/theme.test.ts` already covers `withTouchDensity`; device routing is covered by `useDeviceClass` unit tests (Task A). Add a light App-routing assertion only if an App test harness already exists; otherwise rely on manual verification (Step 3).

**Interfaces:**
- Consumes: `useDeviceClass`, `withTouchDensity`.

- [ ] **Step 1: Wire device class + touch theme in App**

In `App.tsx`:
1. Replace `import { useMobileDetect } from './hooks/useMobileDetect';` with `import { useDeviceClass } from './hooks/useDeviceClass';` and add `withTouchDensity` to the `./theme` import.
2. Replace `const isMobile = useMobileDetect();` (line 1010) with:

```tsx
const deviceClass = useDeviceClass();
const isMobile = deviceClass === 'phone';
```

3. Find the `ThemeProvider` / `makeTheme(darkMode)` usage in App and apply touch density for tablets:

```tsx
const baseTheme = useMemo(() => makeTheme(darkMode), [darkMode]);
const theme = useMemo(
  () => (deviceClass === 'tablet' ? withTouchDensity(baseTheme) : baseTheme),
  [baseTheme, deviceClass],
);
// <ThemeProvider theme={theme}> ...
```

> If App currently inlines `<ThemeProvider theme={makeTheme(darkMode)}>`, refactor it to use the `theme` memo above. `useMemo` is likely already imported; add it if not.

4. The `{isMobile ? <MobileApp/> : <DesktopApp/>}` routing stays as-is — tablets now fall into the `DesktopApp` branch automatically and receive the touch theme via the provider.

- [ ] **Step 2: Typecheck + run the full suite**

Run: `cd frontend && npx tsc --noEmit && npm test -- --run`
Expected: no type errors; all tests pass.

- [ ] **Step 3: Manual verification (responsive)**

Run the dev server (`cd frontend && npm run dev`) and, using browser devtools device emulation:
- Phone (e.g. iPhone, <600px, touch) → `MobileApp`.
- Tablet (e.g. iPad, ~768–1024px, touch) → `DesktopApp` with visibly larger buttons.
- Desktop (mouse, >1200px) → `DesktopApp`, standard sizing.
- Open **Settings** as a non-admin → only Preferences; as an admin → Preferences + Station + System; edit a field → Save enables; Save → toast + stays open; narrow the window → dialog goes full-screen.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat(frontend): route tablets to touch-friendly desktop layout"
```

---

## Self-Review

**Spec coverage:**
- Merge Settings + Admin Settings → Tasks C, F, G. ✓
- Save next to Close → Task F footer (`Save` then `Close`). ✓
- Save-all-tabs / stay open / Option B staged Preferences → Task F (`handleSave` applies prefs + admin + server; Snackbar; no `onClose`). ✓
- Small-screen friendly → Task F (`fullScreen` below `sm`, scrollable tabs). ✓
- Remove moveable panels → Task H. ✓
- Tablet detection + UI → Tasks A, B, I. ✓
- Non-admins see only Preferences → Task F (gated tabs) + Task G (menu item shown to all). ✓
- Mobile users gain Preferences access (side benefit) → Task G renders the dialog once in App for both layouts. ✓

**Placeholder scan:** No "TBD"/"handle edge cases"/vague steps — every code step shows code. Selector/label confirmations are flagged inline where the exact accessible name must be verified at implementation time.

**Type consistency:** `AdminPanelHandle`/`ServerConfigPanelHandle` defined in D/E and consumed in F. `onDirtyChange: (dirty: boolean) => void` and `hideSaveButton?: boolean` consistent across D/E/F. `PrefsDraft` field names match `ConfigPanel` props and App handler signatures verbatim. `withTouchDensity(theme: Theme): Theme` defined in B, used in I.

**Out of scope (noted):** backend removal of `panel_order`; version bump / `/release` (run at tag time per CLAUDE.md); MobileApp internal redesign.
