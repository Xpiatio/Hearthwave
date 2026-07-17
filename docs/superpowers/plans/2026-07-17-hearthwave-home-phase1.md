# Hearthwave Home — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Home-screen shell with activity cards, a per-user `ui_level` (simple/operator) tier, and an accessibility theme layer (font scale, high contrast, keyboard navigation).

**Architecture:** Extend `makeTheme` with font-scale and high-contrast options; add three new per-user prefs (`ui_level`, `font_scale`, `high_contrast`) through the existing `save_user_prefs` → `DEFAULT_PREFS` → `user_profile` round-trip; insert a new `HomeScreen` card-grid shell between login and the existing `DesktopApp` (which becomes the "station" activity), gated by `ui_level`.

**Tech Stack:** React 18 + TypeScript, MUI v9 (`sx` styling), Vitest + Testing Library + jest-axe (frontend); Python/FastAPI-style WS handler + pytest (backend).

**Spec:** `docs/superpowers/specs/2026-07-17-hearthwave-home-redesign-design.md`

## Global Constraints

- Branch: `feat/hearthwave-home-redesign` (already created; spec committed).
- Commits: conventional-commit style; **NO Co-Authored-By trailers** (project rule).
- All styling via MUI theme/`sx` — no new CSS files.
- New prefs must flow through the existing pattern: `save_user_prefs` allowlist in `backend/server.py` (~line 2779), `DEFAULT_PREFS` in `backend/persistence/users.py:34`, applied client-side in the `user_profile` case in `frontend/src/App.tsx:436`.
- `ui_level` values: `"simple" | "operator"`. Default `"simple"`.
- `font_scale` values: `1 | 1.25 | 1.5 | 2`. Default `1`.
- `high_contrast`: boolean. Default `false`.
- localStorage keys keep the legacy prefix: `radio_tty_ui_level`, `radio_tty_font_scale`, `radio_tty_high_contrast`.
- Frontend tests: run from `frontend/` with `npx vitest run <path>`. Backend: from `backend/` with `python -m pytest <path> -v`.
- Do not bump version numbers — release flow (`/release` skill) handles that later.

---

### Task 1: Theme options — font scale, high contrast, focus rings

**Files:**
- Modify: `frontend/src/theme.ts`
- Test: `frontend/src/__tests__/theme.test.ts` (new)

**Interfaces:**
- Consumes: existing `makeTheme(dark: boolean)` / `withTouchDensity(theme)`.
- Produces: `makeTheme(dark: boolean, opts?: ThemeOptionsExtra)` where `export interface ThemeOptionsExtra { fontScale?: number; highContrast?: boolean }`. Back-compatible: `makeTheme(true)` behaves exactly as today.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/__tests__/theme.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { makeTheme } from '../theme';

describe('makeTheme', () => {
  it('defaults unchanged: body1 1.125rem, light background', () => {
    const t = makeTheme(false);
    expect(t.typography.body1.fontSize).toBe('1.125rem');
    expect(t.palette.background.default).toBe('#E8EEF7');
  });

  it('fontScale multiplies typography sizes', () => {
    const t = makeTheme(false, { fontScale: 2 });
    expect(t.typography.body1.fontSize).toBe('2.25rem');
    expect(t.typography.body2.fontSize).toBe('2rem');
    expect(t.typography.fontSize).toBe(28);
  });

  it('highContrast dark uses pure black background and white text', () => {
    const t = makeTheme(true, { highContrast: true });
    expect(t.palette.background.default).toBe('#000000');
    expect(t.palette.text.primary).toBe('#FFFFFF');
  });

  it('highContrast light uses pure white background and black text', () => {
    const t = makeTheme(false, { highContrast: true });
    expect(t.palette.background.default).toBe('#FFFFFF');
    expect(t.palette.text.primary).toBe('#000000');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/__tests__/theme.test.ts`
Expected: FAIL — fontScale/highContrast assertions fail (signature accepts one arg; extra opts ignored by JS, so scale/contrast expectations mismatch).

- [ ] **Step 3: Implement theme options**

In `frontend/src/theme.ts`, replace the `makeTheme` signature and body header (keep everything not shown here as-is):

```typescript
export interface ThemeOptionsExtra {
  /** Multiplier for all font sizes: 1 | 1.25 | 1.5 | 2 */
  fontScale?: number;
  /** WCAG-oriented palette: pure black/white surfaces, stronger dividers */
  highContrast?: boolean;
}

export function makeTheme(dark: boolean, opts: ThemeOptionsExtra = {}) {
  const s = opts.fontScale ?? 1;
  const hc = opts.highContrast ?? false;
  return createTheme({
    palette: {
      mode: dark ? 'dark' : 'light',
      primary: {
        main: hc ? (dark ? '#99CCFF' : '#003399') : dark ? '#60A5FA' : '#2563EB',
        dark: hc ? (dark ? '#66B2FF' : '#002266') : dark ? '#2563EB' : '#1D4ED8',
      },
      info: { main: dark ? '#93C5FD' : '#1E4976' },
      warning: { main: dark ? '#FBBF24' : '#7a4a00' },
      error: { main: hc ? (dark ? '#FF6666' : '#990000') : dark ? '#F87171' : '#B91C1C' },
      success: { main: dark ? '#4ADE80' : '#15803D' },
      background: {
        default: hc ? (dark ? '#000000' : '#FFFFFF') : dark ? '#0F2540' : '#E8EEF7',
        paper: hc ? (dark ? '#0A0A0A' : '#F5F5F5') : dark ? '#1A3A5C' : '#C8D8EC',
      },
      text: {
        primary: hc ? (dark ? '#FFFFFF' : '#000000') : dark ? '#F9FAFB' : '#0F2540',
      },
      divider: hc
        ? dark ? 'rgba(255,255,255,0.6)' : 'rgba(0,0,0,0.7)'
        : dark ? 'rgba(37,99,235,0.3)' : 'rgba(30,73,118,0.25)',
    },
    typography: {
      htmlFontSize: 16,
      fontSize: 14 * s,
      fontFamily:
        "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      body1: { fontSize: `${1.125 * s}rem` },
      body2: { fontSize: `${1 * s}rem` },
    },
```

In the `components` block, update `MuiOutlinedInput` and add a global focus-visible ring via `MuiButtonBase` (keep the other component overrides untouched):

```typescript
      MuiButtonBase: {
        styleOverrides: {
          root: ({ theme }) => ({
            '&.Mui-focusVisible': {
              outline: `3px solid ${theme.palette.primary.main}`,
              outlineOffset: 2,
            },
          }),
        },
      },
      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            fontSize: `${1.125 * s}rem`,
          },
        },
      },
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/__tests__/theme.test.ts`
Expected: PASS (4 tests). Also run full frontend suite to catch regressions: `npx vitest run`. Expected: all green (existing call site `makeTheme(darkMode)` still valid).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/theme.ts frontend/src/__tests__/theme.test.ts
git commit -m "feat(theme): font scale, high-contrast palette, global focus rings"
```

---

### Task 2: Backend prefs — `ui_level`, `font_scale`, `high_contrast`

**Files:**
- Modify: `backend/persistence/users.py:34` (DEFAULT_PREFS)
- Modify: `backend/server.py:2776-2796` (save_user_prefs handler)
- Test: `backend/tests/integration/test_server_ws.py` (append), `backend/tests/unit/persistence/test_users.py` (append)

**Interfaces:**
- Consumes: existing `save_user_prefs` WS message + `UsersStore.update_prefs`.
- Produces: prefs dict on every `user_profile` message now includes `ui_level: str`, `font_scale: float`, `high_contrast: bool`. Invalid values are silently dropped (matching the handler's filter-not-error style), except nothing valid → no-op.

- [ ] **Step 1: Write failing unit test for defaults**

Append to `backend/tests/unit/persistence/test_users.py` (match the file's existing store fixture/style — it already tests `DEFAULT_PREFS` merging; follow the same pattern):

```python
def test_default_prefs_include_ui_level_and_a11y(tmp_path):
    store = UsersStore(tmp_path / "users.json")
    u = store.create(display_name="Ann", password="pw12345678")
    assert u["prefs"]["ui_level"] == "simple"
    assert u["prefs"]["font_scale"] == 1
    assert u["prefs"]["high_contrast"] is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/unit/persistence/test_users.py -v -k ui_level`
Expected: FAIL with `KeyError: 'ui_level'`.

Note: `store.create(...)` keyword names above must match the real signature at `backend/persistence/users.py:137` — check it and adjust the call (it may require operator_name/callsign args).

- [ ] **Step 3: Add defaults**

In `backend/persistence/users.py`, extend `DEFAULT_PREFS`:

```python
    "aac_mode": False,
    "aac_grid": None,  # None = client renders its built-in default grid
    "ui_level": "simple",   # "simple" | "operator" — home-screen tier
    "font_scale": 1,        # 1 | 1.25 | 1.5 | 2
    "high_contrast": False,
```

Run: `python -m pytest tests/unit/persistence/test_users.py -v` — Expected: PASS.

- [ ] **Step 4: Write failing integration test for allowlist + validation**

Append to `backend/tests/integration/test_server_ws.py`, following the existing `save_user_prefs — aac_grid validation` test at line 285 (reuse its connection/auth fixture pattern verbatim):

```python
def test_save_user_prefs_ui_level_and_a11y(client_authed):
    ws = client_authed
    ws.send_json({"type": "save_user_prefs",
                  "prefs": {"ui_level": "operator", "font_scale": 1.5, "high_contrast": True}})
    msg = recv_until(ws, "user_profile")
    assert msg["profile"]["prefs"]["ui_level"] == "operator"
    assert msg["profile"]["prefs"]["font_scale"] == 1.5
    assert msg["profile"]["prefs"]["high_contrast"] is True

def test_save_user_prefs_rejects_bad_values(client_authed):
    ws = client_authed
    ws.send_json({"type": "save_user_prefs",
                  "prefs": {"ui_level": "root", "font_scale": 9}})
    # invalid values dropped -> no updates -> no user_profile reply; a valid key still works
    ws.send_json({"type": "save_user_prefs", "prefs": {"ui_level": "operator"}})
    msg = recv_until(ws, "user_profile")
    assert msg["profile"]["prefs"]["ui_level"] == "operator"
    assert msg["profile"]["prefs"]["font_scale"] == 1  # unchanged default
```

Adapt fixture/helper names (`client_authed`, `recv_until`) to the file's actual helpers around line 285 — copy exactly what the aac_grid tests use.

- [ ] **Step 5: Run to verify it fails**

Run: `cd backend && python -m pytest tests/integration/test_server_ws.py -v -k ui_level`
Expected: FAIL — new keys filtered out by allowlist, so no `user_profile` reply / prefs missing.

- [ ] **Step 6: Extend handler**

In `backend/server.py` `save_user_prefs` branch, extend the allowlist and add validation next to the aac_grid check:

```python
                allowed = {"dark_mode", "filter_profanity", "listen_only",
                           "read_aloud", "notifications_enabled", "spectro_colormap", "spectro_time_window_s",
                           "tts_voice", "tts_length_scale", "aac_mode", "aac_grid",
                           "ui_level", "font_scale", "high_contrast"}
                updates = {k: v for k, v in data.get("prefs", data).items() if k in allowed}
                if updates.get("ui_level") not in (None, "simple", "operator"):
                    updates.pop("ui_level")
                if "font_scale" in updates and updates["font_scale"] not in (1, 1.25, 1.5, 2):
                    updates.pop("font_scale")
                if "high_contrast" in updates and not isinstance(updates["high_contrast"], bool):
                    updates.pop("high_contrast")
```

- [ ] **Step 7: Run tests**

Run: `cd backend && python -m pytest tests/integration/test_server_ws.py tests/unit/persistence/test_users.py -v`
Expected: PASS, including pre-existing tests.

- [ ] **Step 8: Commit**

```bash
git add backend/persistence/users.py backend/server.py backend/tests
git commit -m "feat(prefs): ui_level, font_scale, high_contrast per-user prefs"
```

---

### Task 3: Frontend prefs plumbing + Settings controls

**Files:**
- Modify: `frontend/src/types/ws.ts:386` (UserPrefs)
- Modify: `frontend/src/App.tsx` (state ~line 179, theme memo ~205, user_profile case ~436, handlers ~908, SettingsDialog props ~1248)
- Modify: `frontend/src/components/ConfigPanel/ConfigPanel.tsx`
- Modify: `frontend/src/components/SettingsDialog/SettingsDialog.tsx`
- Test: `frontend/src/components/ConfigPanel/__tests__/ConfigPanel.interface.test.tsx` (new)

**Interfaces:**
- Consumes: Task 1's `makeTheme(dark, { fontScale, highContrast })`; Task 2's pref keys.
- Produces: `ConfigPanel` new props: `uiLevel: 'simple' | 'operator'`, `fontScale: number`, `highContrast: boolean`, `onUiLevelChange: (v: 'simple' | 'operator') => void`, `onFontScaleChange: (v: number) => void`, `onToggleHighContrast: () => void`. `App.tsx` exposes state `uiLevel` used by Task 4.

- [ ] **Step 1: Extend UserPrefs type**

In `frontend/src/types/ws.ts` `UserPrefs`, after `aac_grid`:

```typescript
  ui_level?: 'simple' | 'operator';
  font_scale?: number;
  high_contrast?: boolean;
```

- [ ] **Step 2: Write failing ConfigPanel test**

Create `frontend/src/components/ConfigPanel/__tests__/ConfigPanel.interface.test.tsx`. Look at an existing ConfigPanel or SettingsDialog test for the standard prop scaffold; minimal version:

```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { axe } from 'jest-axe';
import { ConfigPanel } from '../ConfigPanel';

const noop = () => {};
const baseProps = {
  filterProfanity: true, aacMode: false, fuzzyCallsign: false, fuzzyCallsignRewrite: false,
  inputDevice: -1 as const, systemMonitorSink: '', inputDevices: [], monitorSinks: [],
  outputDevice: -1, outputDevices: [],
  spectroColormap: 'viridis' as const, spectroFreqRange: 'voice' as const, spectroTimeWindowS: 30,
  onToggleProfanity: noop, onToggleAacMode: noop, onToggleFuzzy: noop, onToggleFuzzyRewrite: noop,
  onInputDeviceChange: noop, onOutputDeviceChange: noop,
  onSpectroColormapChange: noop, onSpectroFreqRangeChange: noop, onSpectroTimeWindowChange: noop,
  uiLevel: 'simple' as const, fontScale: 1, highContrast: false,
  onUiLevelChange: noop, onFontScaleChange: noop, onToggleHighContrast: noop,
};

describe('ConfigPanel interface controls', () => {
  it('fires onUiLevelChange when Operator selected', () => {
    const onUiLevelChange = vi.fn();
    render(<ConfigPanel {...baseProps} onUiLevelChange={onUiLevelChange} />);
    fireEvent.click(screen.getByRole('button', { name: /operator interface/i }));
    expect(onUiLevelChange).toHaveBeenCalledWith('operator');
  });

  it('fires onFontScaleChange with 1.5 when 150% selected', () => {
    const onFontScaleChange = vi.fn();
    render(<ConfigPanel {...baseProps} onFontScaleChange={onFontScaleChange} />);
    fireEvent.click(screen.getByRole('button', { name: /150% text size/i }));
    expect(onFontScaleChange).toHaveBeenCalledWith(1.5);
  });

  it('fires onToggleHighContrast', () => {
    const onToggleHighContrast = vi.fn();
    render(<ConfigPanel {...baseProps} onToggleHighContrast={onToggleHighContrast} />);
    fireEvent.click(screen.getByLabelText(/high contrast/i));
    expect(onToggleHighContrast).toHaveBeenCalled();
  });

  it('has no axe violations', async () => {
    const { container } = render(<ConfigPanel {...baseProps} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
```

Run: `cd frontend && npx vitest run src/components/ConfigPanel/__tests__/ConfigPanel.interface.test.tsx`
Expected: FAIL — TypeScript/prop errors, controls not found.

- [ ] **Step 3: Add controls to ConfigPanel**

In `ConfigPanel.tsx`: add the six new props to `Props` and destructure. Insert a new "Interface" group at the TOP of `body` (before the profanity switch), so accessibility options lead:

```tsx
        {/* Interface tier + accessibility */}
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5, alignItems: 'center' }}>
          <Typography variant="caption" sx={{ fontWeight: 700, textTransform: 'uppercase', color: 'text.secondary' }}>
            Interface:
          </Typography>
          <ToggleButtonGroup
            size="small" exclusive value={uiLevel}
            onChange={(_, v) => v && onUiLevelChange(v)}
            aria-label="Interface level"
          >
            <ToggleButton value="simple" aria-label="Simple interface">Simple</ToggleButton>
            <ToggleButton value="operator" aria-label="Operator interface">Operator</ToggleButton>
          </ToggleButtonGroup>
          <ToggleButtonGroup
            size="small" exclusive value={fontScale}
            onChange={(_, v) => v != null && onFontScaleChange(v)}
            aria-label="Text size"
          >
            <ToggleButton value={1} aria-label="100% text size">A</ToggleButton>
            <ToggleButton value={1.25} aria-label="125% text size">A+</ToggleButton>
            <ToggleButton value={1.5} aria-label="150% text size">A++</ToggleButton>
            <ToggleButton value={2} aria-label="200% text size">A+++</ToggleButton>
          </ToggleButtonGroup>
          <FormControlLabel
            control={<Switch checked={highContrast} onChange={onToggleHighContrast} size="small" />}
            label="High Contrast"
          />
        </Box>

        <Divider orientation="vertical" flexItem />
```

Run the test again. Expected: PASS.

- [ ] **Step 4: Thread through SettingsDialog draft**

In `SettingsDialog.tsx`: add to `Props` (`uiLevel`, `fontScale`, `highContrast`, `onUiLevelChange`, `onFontScaleChange`, `onToggleHighContrast`), to `PrefsDraft` (`uiLevel: 'simple' | 'operator'; fontScale: number; highContrast: boolean;`), to `seedPrefs()`, to `applyPrefs()`:

```typescript
    if (draft.uiLevel !== prefsSeed.uiLevel) props.onUiLevelChange(draft.uiLevel);
    if (draft.fontScale !== prefsSeed.fontScale) props.onFontScaleChange(draft.fontScale);
    if (draft.highContrast !== prefsSeed.highContrast) props.onToggleHighContrast();
```

and pass to `ConfigPanel` in the tabpanel:

```tsx
            uiLevel={draft.uiLevel}
            fontScale={draft.fontScale}
            highContrast={draft.highContrast}
            onUiLevelChange={(v) => setDraft((d) => ({ ...d, uiLevel: v }))}
            onFontScaleChange={(v) => setDraft((d) => ({ ...d, fontScale: v }))}
            onToggleHighContrast={() => setDraft((d) => ({ ...d, highContrast: !d.highContrast }))}
```

- [ ] **Step 5: Wire App.tsx**

In `frontend/src/App.tsx`:

State (next to `darkMode` at ~line 179, copying its localStorage-seed pattern):

```typescript
  const [uiLevel, setUiLevel] = useState<'simple' | 'operator'>(
    (localStorage.getItem('radio_tty_ui_level') as 'simple' | 'operator') || 'simple',
  );
  const [fontScale, setFontScale] = useState(
    Number(localStorage.getItem('radio_tty_font_scale')) || 1,
  );
  const [highContrast, setHighContrast] = useState(
    localStorage.getItem('radio_tty_high_contrast') === 'true',
  );
```

Theme memo (line 205):

```typescript
  const baseTheme = useMemo(
    () => makeTheme(darkMode, { fontScale, highContrast }),
    [darkMode, fontScale, highContrast],
  );
```

`user_profile` case (after the `aac_grid` block at ~line 457):

```typescript
        if (prefs.ui_level) {
          setUiLevel(prefs.ui_level);
          localStorage.setItem('radio_tty_ui_level', prefs.ui_level);
        }
        if (prefs.font_scale) {
          setFontScale(prefs.font_scale);
          localStorage.setItem('radio_tty_font_scale', String(prefs.font_scale));
        }
        if (prefs.high_contrast !== undefined) {
          setHighContrast(prefs.high_contrast);
          localStorage.setItem('radio_tty_high_contrast', String(prefs.high_contrast));
        }
```

Handlers (next to `handleToggleDark` at ~line 908, same shape):

```typescript
  function handleUiLevelChange(next: 'simple' | 'operator') {
    setUiLevel(next);
    localStorage.setItem('radio_tty_ui_level', next);
    send({ type: 'save_user_prefs', prefs: { ui_level: next } });
  }
  function handleFontScaleChange(next: number) {
    setFontScale(next);
    localStorage.setItem('radio_tty_font_scale', String(next));
    send({ type: 'save_user_prefs', prefs: { font_scale: next } });
  }
  function handleToggleHighContrast() {
    const next = !highContrast;
    setHighContrast(next);
    localStorage.setItem('radio_tty_high_contrast', String(next));
    send({ type: 'save_user_prefs', prefs: { high_contrast: next } });
  }
```

SettingsDialog invocation (~line 1248): pass `uiLevel={uiLevel} fontScale={fontScale} highContrast={highContrast} onUiLevelChange={handleUiLevelChange} onFontScaleChange={handleFontScaleChange} onToggleHighContrast={handleToggleHighContrast}`.

- [ ] **Step 6: Full frontend suite + typecheck**

Run: `cd frontend && npx tsc --noEmit && npx vitest run`
Expected: PASS. (Other SettingsDialog tests may need the six new props added to their scaffolds — do that, mirroring `baseProps` above.)

- [ ] **Step 7: Commit**

```bash
git add frontend/src
git commit -m "feat(prefs): interface level, text size, high contrast settings"
```

---

### Task 4: HomeScreen shell + activity routing

**Files:**
- Create: `frontend/src/components/HomeScreen/HomeScreen.tsx`
- Create: `frontend/src/components/HomeScreen/ActivityCard.tsx`
- Test: `frontend/src/components/HomeScreen/__tests__/HomeScreen.test.tsx`
- Modify: `frontend/src/App.tsx` (shell routing ~line 1194-1245)
- Modify: `frontend/src/components/DesktopApp/DesktopApp.tsx` + `frontend/src/components/TopBar/TopBar.tsx` (Home button)

**Interfaces:**
- Consumes: `uiLevel` state from Task 3; existing `DesktopApp`, `isPluginEnabled(plugins, 'ncs')`.
- Produces:
  - `HomeScreen` props: `{ profile: UserProfile; connected: boolean; uiLevel: 'simple' | 'operator'; ncsEnabled: boolean; unreadCount: number; onOpenActivity: (a: 'station' | 'ncs') => void; onOpenSettings: () => void; onLogout: () => void; }`
  - `ActivityCard` props: `{ emoji: string; title: string; subtitle?: string; onClick: () => void; }` — renders a `ButtonBase` card ≥140px tall, emoji `aria-hidden`, accessible name = title.
  - `DesktopApp`/`TopBar` new optional prop `onGoHome?: () => void` — renders a Home icon button as the FIRST toolbar control when provided.

- [ ] **Step 1: Write failing HomeScreen test**

Create `frontend/src/components/HomeScreen/__tests__/HomeScreen.test.tsx`:

```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { axe } from 'jest-axe';
import { HomeScreen } from '../HomeScreen';
import type { UserProfile } from '../../../types/ws';

const profile = {
  id: 'u1', display_name: 'Ann', avatar_emoji: '🙂', operator_name: 'Ann',
  callsign: 'WABC123', location: 'Home', is_admin: false, prefs: {} as never,
} as UserProfile;

const base = {
  profile, connected: true, uiLevel: 'simple' as const, ncsEnabled: true,
  unreadCount: 0, onOpenActivity: vi.fn(), onOpenSettings: vi.fn(), onLogout: vi.fn(),
};

describe('HomeScreen', () => {
  it('simple tier shows Chat card but no Net Control card', () => {
    render(<HomeScreen {...base} />);
    expect(screen.getByRole('button', { name: /chat/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /net control/i })).toBeNull();
  });

  it('operator tier shows Net Control card when NCS enabled', () => {
    render(<HomeScreen {...base} uiLevel="operator" />);
    expect(screen.getByRole('button', { name: /net control/i })).toBeInTheDocument();
  });

  it('clicking Chat opens station activity', () => {
    const onOpenActivity = vi.fn();
    render(<HomeScreen {...base} onOpenActivity={onOpenActivity} />);
    fireEvent.click(screen.getByRole('button', { name: /chat/i }));
    expect(onOpenActivity).toHaveBeenCalledWith('station');
  });

  it('arrow keys move focus between cards (roving tabindex)', () => {
    render(<HomeScreen {...base} uiLevel="operator" />);
    const grid = screen.getByRole('list', { name: /activities/i });
    const cards = within(grid).getAllByRole('button');
    cards[0].focus();
    fireEvent.keyDown(cards[0], { key: 'ArrowRight' });
    expect(cards[1]).toHaveFocus();
    expect(cards[0]).toHaveAttribute('tabindex', '-1');
    expect(cards[1]).toHaveAttribute('tabindex', '0');
  });

  it('shows unread badge on Chat card', () => {
    render(<HomeScreen {...base} unreadCount={3} />);
    expect(screen.getByText(/3 new/i)).toBeInTheDocument();
  });

  it('has no axe violations', async () => {
    const { container } = render(<HomeScreen {...base} uiLevel="operator" />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
```

(Add `within` to the testing-library import.)

Run: `cd frontend && npx vitest run src/components/HomeScreen`
Expected: FAIL — module not found.

- [ ] **Step 2: Implement ActivityCard**

`frontend/src/components/HomeScreen/ActivityCard.tsx`:

```tsx
import { ButtonBase, Paper, Typography, Box } from '@mui/material';

interface Props {
  emoji: string;
  title: string;
  subtitle?: string;
  onClick: () => void;
}

/** Large tap-target card for the home activity grid (AAC-style sizing). */
export function ActivityCard({ emoji, title, subtitle, onClick }: Props) {
  return (
    <ButtonBase
      onClick={onClick}
      aria-label={title}
      sx={{ borderRadius: 2, width: '100%', textAlign: 'left' }}
    >
      <Paper
        sx={{
          p: 3, width: '100%', minHeight: 140, display: 'flex',
          flexDirection: 'column', gap: 1, justifyContent: 'center',
        }}
      >
        <Box component="span" aria-hidden sx={{ fontSize: '2.5rem', lineHeight: 1 }}>
          {emoji}
        </Box>
        <Typography variant="h6" sx={{ fontWeight: 700 }}>{title}</Typography>
        {subtitle && (
          <Typography variant="body2" color="text.secondary">{subtitle}</Typography>
        )}
      </Paper>
    </ButtonBase>
  );
}
```

- [ ] **Step 3: Implement HomeScreen with roving tabindex**

`frontend/src/components/HomeScreen/HomeScreen.tsx`:

```tsx
import { useRef, useState } from 'react';
import { Box, Typography, IconButton, Tooltip, Chip } from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import LogoutIcon from '@mui/icons-material/Logout';
import { Logo } from '../Logo/Logo';
import { ActivityCard } from './ActivityCard';
import type { UserProfile } from '../../types/ws';

interface Props {
  profile: UserProfile;
  connected: boolean;
  uiLevel: 'simple' | 'operator';
  ncsEnabled: boolean;
  unreadCount: number;
  onOpenActivity: (a: 'station' | 'ncs') => void;
  onOpenSettings: () => void;
  onLogout: () => void;
}

interface CardDef {
  key: string;
  emoji: string;
  title: string;
  subtitle?: string;
  onClick: () => void;
}

/** Home shell: glance header + activity card grid. Default landing screen. */
export function HomeScreen(props: Props) {
  const cards: CardDef[] = [
    {
      key: 'chat', emoji: '💬', title: 'Chat',
      subtitle: props.unreadCount > 0 ? `${props.unreadCount} new` : 'Talk on the radio',
      onClick: () => props.onOpenActivity('station'),
    },
  ];
  if (props.uiLevel === 'operator' && props.ncsEnabled) {
    cards.push({
      key: 'ncs', emoji: '🎙', title: 'Net Control',
      subtitle: 'Run a net', onClick: () => props.onOpenActivity('ncs'),
    });
  }

  // Roving tabindex: one card is tabbable; arrows move focus.
  const [focusIdx, setFocusIdx] = useState(0);
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  function handleKeyDown(e: React.KeyboardEvent, idx: number) {
    let next = idx;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next = (idx + 1) % cards.length;
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = (idx - 1 + cards.length) % cards.length;
    else return;
    e.preventDefault();
    setFocusIdx(next);
    refs.current[next]?.focus();
  }

  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', p: { xs: 2, md: 4 }, gap: 3 }}>
      <Box component="header" sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Logo />
        <Typography variant="h5" sx={{ fontWeight: 700, flexGrow: 1 }}>
          Hearthwave
        </Typography>
        <Chip
          size="small"
          color={props.connected ? 'success' : 'error'}
          label={props.connected ? 'Connected' : 'Disconnected'}
        />
        <Tooltip title="Settings">
          <IconButton aria-label="Settings" onClick={props.onOpenSettings}><SettingsIcon /></IconButton>
        </Tooltip>
        <Tooltip title="Log out">
          <IconButton aria-label="Log out" onClick={props.onLogout}><LogoutIcon /></IconButton>
        </Tooltip>
      </Box>

      <Typography variant="h6">
        Welcome, {props.profile.display_name} {props.profile.avatar_emoji}
      </Typography>

      <Box
        role="list"
        aria-label="Activities"
        sx={{
          display: 'grid', gap: 2,
          gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)' },
          alignContent: 'start', flexGrow: 1,
        }}
      >
        {cards.map((c, i) => (
          <Box role="listitem" key={c.key}>
            <ActivityCard
              emoji={c.emoji}
              title={c.title}
              subtitle={c.subtitle}
              onClick={c.onClick}
              buttonRef={(el) => { refs.current[i] = el; }}
              tabIndex={i === focusIdx ? 0 : -1}
              onKeyDown={(e) => handleKeyDown(e, i)}
              onFocus={() => setFocusIdx(i)}
            />
          </Box>
        ))}
      </Box>
    </Box>
  );
}
```

Extend `ActivityCard` props to support the roving pattern (`buttonRef`, `tabIndex`, `onKeyDown`, `onFocus` passed through to `ButtonBase`):

```tsx
interface Props {
  emoji: string;
  title: string;
  subtitle?: string;
  onClick: () => void;
  tabIndex?: number;
  onKeyDown?: (e: React.KeyboardEvent) => void;
  onFocus?: () => void;
  buttonRef?: (el: HTMLButtonElement | null) => void;
}
// ...
    <ButtonBase
      onClick={onClick}
      aria-label={title}
      tabIndex={tabIndex}
      onKeyDown={onKeyDown}
      onFocus={onFocus}
      ref={buttonRef}
      sx={{ borderRadius: 2, width: '100%', textAlign: 'left' }}
    >
```

Check `Logo` props (`frontend/src/components/Logo/Logo.tsx`) — if it requires a size prop, pass what TopBar passes.

- [ ] **Step 4: Run HomeScreen tests**

Run: `cd frontend && npx vitest run src/components/HomeScreen`
Expected: PASS.

- [ ] **Step 5: Route shell in App.tsx + Home button**

In `App.tsx`, add activity state near other UI state:

```typescript
  const [activity, setActivity] = useState<'home' | 'station'>('home');
```

Compute unread for the badge — simplest honest Phase 1 count: messages received while on home. Add alongside:

```typescript
  const homeSeenCountRef = useRef(0);
  // when opening home: remember length; unread = messages.length - ref
  function handleGoHome() {
    homeSeenCountRef.current = messages.length;
    setActivity('home');
  }
  function handleOpenActivity(a: 'station' | 'ncs') {
    if (a === 'ncs') setShowNcs(true);
    setActivity('station');
  }
  const unreadCount = Math.max(0, messages.length - homeSeenCountRef.current);
```

Replace the desktop branch of the shell JSX (line 1223-1245) — keep `AACApp` and `MobileApp` branches untouched:

```tsx
      ) : activity === 'home' ? (
        <HomeScreen
          profile={profile}
          connected={connected}
          uiLevel={uiLevel}
          ncsEnabled={isPluginEnabled(plugins, 'ncs')}
          unreadCount={unreadCount}
          onOpenActivity={handleOpenActivity}
          onOpenSettings={handleToggleSettings}
          onLogout={handleLogout}
        />
      ) : (
        <DesktopApp
          {...sharedProps}
          onGoHome={handleGoHome}
          ...
```

(keep all existing DesktopApp props; add `onGoHome`).

In `DesktopApp.tsx`: accept `onGoHome?: () => void` and forward to `TopBar`. In `TopBar.tsx`: add prop `onGoHome?: () => void`; render as first toolbar item:

```tsx
        {onGoHome && (
          <Tooltip title="Home screen">
            <IconButton aria-label="Home screen" onClick={onGoHome}>
              <HomeIcon />
            </IconButton>
          </Tooltip>
        )}
```

with `import HomeIcon from '@mui/icons-material/Home';`. Also add an Escape-to-home listener in `DesktopApp` (skip when a dialog is open — check `showSettings` etc. is not required; MUI dialogs stop propagation of Esc by closing themselves first, so a plain listener on `document` guarded by `event.defaultPrevented` suffices):

```tsx
  useEffect(() => {
    if (!onGoHome) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape' && !e.defaultPrevented) onGoHome!();
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onGoHome]);
```

- [ ] **Step 6: Simple-tier gating in TopBar**

Pass `uiLevel` through `sharedProps` in `App.tsx` and down `DesktopApp` → `TopBar`. In `TopBar`, wrap operator-only controls in `{uiLevel === 'operator' && (...)}`: waterfall toggle, level-meter toggle, journal toggle, attendance toggle, NCS toggle, clear-chat button, service-mode toggle, STT listening toggle. Keep visible for everyone: read-aloud, notifications, listen-only, dark mode, About, AccountMenu, VoicePTT, TX abort. `MobileApp` accepts `uiLevel` via sharedProps spread; ignore it there for Phase 1 (add the prop to its Props type or type sharedProps loosely as today).

- [ ] **Step 7: Typecheck + full suite**

Run: `cd frontend && npx tsc --noEmit && npx vitest run`
Expected: PASS. Existing DesktopApp/TopBar tests need the new optional props only if they assert toolbar contents — update scaffolds with `uiLevel: 'operator'` so current assertions still hold.

- [ ] **Step 8: Commit**

```bash
git add frontend/src
git commit -m "feat(home): home-screen activity shell with tiered cards and keyboard nav"
```

---

### Task 5: End-to-end verification + docs

**Files:**
- Modify: `USER_MANUAL.md` (new "Home screen & interface levels" + "Accessibility options" sections)

**Interfaces:**
- Consumes: everything above.
- Produces: verified feature + user docs. No version bumps (release flow later).

- [ ] **Step 1: Build + run the stack**

```bash
cd frontend && npm run build
cd .. && docker compose -p hearthwave up -d --build
```

(Local install runs as compose project `hearthwave` — never bare `docker compose up`.) Expected: containers healthy; `curl -s localhost/health` returns current version.

- [ ] **Step 2: Manual walkthrough**

- Log in → lands on Home screen, Chat card only (default simple tier).
- Settings → Interface: Operator → Save → Home now shows Net Control card (if NCS plugin enabled).
- Text size 200% → whole UI scales, no horizontal overflow on the home grid or chat.
- High Contrast + dark → pure black background, readable text, visible focus rings when tabbing.
- Keyboard only: Tab to grid, arrows move between cards, Enter opens Chat, Esc returns Home, Home button in TopBar works.
- Second browser session: prefs persist after reload (server-side prefs round-trip).
- AAC mode and phone layout unaffected (AACApp/MobileApp untouched branches).

- [ ] **Step 3: Full test suites**

```bash
cd backend && python -m pytest
cd ../frontend && npx vitest run && npx tsc --noEmit
```

Expected: all green.

- [ ] **Step 4: Document**

Add to `USER_MANUAL.md`: Home screen (cards, Esc/Home navigation), Interface level (Simple vs Operator — what Operator adds), Text size, High Contrast, keyboard navigation summary. Follow the manual's existing section style.

- [ ] **Step 5: Commit + push + PR**

```bash
git add USER_MANUAL.md
git commit -m "docs: home screen, interface levels, accessibility options"
git push -u origin feat/hearthwave-home-redesign
gh pr create --title "feat: Hearthwave Home shell, interface tiers, accessibility theme (redesign phase 1)" --body "Phase 1 of the Hearthwave Home redesign (spec: docs/superpowers/specs/2026-07-17-hearthwave-home-redesign-design.md). Home-screen activity shell, per-user ui_level (simple/operator), font scaling, high-contrast theme, keyboard navigation."
```

(No Claude co-author/footer per project rule.)
