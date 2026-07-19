# Hearthwave Phase 5 — Switch Scanning + A11y Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Single-switch auto-scanning for the home card grid and AAC grid, visual twins (screen-edge flash + vibration) for audio cues, a keyboard-shortcut overlay, the AAC huge-yes/no confirm pattern generalized to all destructive actions, and the deferred kid+AAC send path.

**Architecture:** A reusable `useSwitchScan` hook moves real DOM focus through `[data-scan="true"]` elements on a timer (activation is native Enter/Space, so no click plumbing). Three new per-user prefs (`switch_scan`, `switch_scan_interval_s`, `visual_alerts`) flow through the existing prefs pipeline (users.py defaults → server.py allowlist/validation → `UserPrefs` → App state/localStorage → SettingsDialog draft → ConfigPanel controls). Kid AAC sends carry an `aac_chunks` array that the server validates against the kid's stored `aac_grid` and rebuilds server-side, mirroring the frontend's `resolveTokens`.

**Tech Stack:** React 18 + MUI v9 + vitest + jest-axe (frontend); FastAPI WS + pytest (backend).

## Global Constraints

- Branch: `feat/hearthwave-a11y-phase5` off `master`. One PR at the end.
- NO version bumps anywhere — release is a separate `/release` cut later.
- Commits: NO `Co-Authored-By` trailers, no Claude footers (user rule).
- Frontend tests: `cd frontend && npx vitest run <path>`; full suite `npx vitest run`. Backend: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/... -v`.
- Every new component gets a jest-axe test (`expect(await axe(container)).toHaveNoViolations()` — see `frontend/src/components/HomeScreen/__tests__/HomeScreen.test.tsx` imports: `render, screen, fireEvent` from `@testing-library/react`; `describe, it, expect, vi` from `vitest`; `axe` from `jest-axe`).
- New pref values (exact): `switch_scan` bool default `False`; `switch_scan_interval_s` number default `1.5`, allowed `(1, 1.5, 2, 3)`; `visual_alerts` bool default `False`. All three kid-self-serviceable.
- localStorage keys: `radio_tty_switch_scan`, `radio_tty_switch_scan_interval_s`, `radio_tty_visual_alerts` (project convention keeps the `radio_tty_` prefix).

---

### Task 1: Backend prefs — switch_scan, switch_scan_interval_s, visual_alerts

**Files:**
- Modify: `backend/persistence/users.py:37-52` (DEFAULT_PREFS)
- Modify: `backend/server.py:2342` (KID_ALLOWED_PREF_KEYS), `backend/server.py:3253-3271` (allowlist + validation)
- Test: `backend/tests/integration/test_server_ws.py` (extend `TestSaveUserPrefsUiLevelAndA11y`, line ~360)

**Interfaces:**
- Produces: prefs `switch_scan: bool`, `switch_scan_interval_s: float`, `visual_alerts: bool` present in every `user_profile.prefs` payload (defaults merged by `effective_prefs`). Later frontend tasks rely on these exact key names.

- [ ] **Step 1: Write failing tests** — add to class `TestSaveUserPrefsUiLevelAndA11y` in `backend/tests/integration/test_server_ws.py` (clone the structure of `test_valid_values_saved_and_reflected` at line 361 — same `_minimal_cfg`/`_make_mocks`/`_make_auth_mocks`/patch block):

```python
    def test_switch_scan_and_visual_alerts_saved(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()
        mock_users.update_prefs.return_value = {
            "id": "test-user",
            "display_name": "Test Operator",
            "is_admin": True,
            "prefs": {"switch_scan": True, "switch_scan_interval_s": 2, "visual_alerts": True},
        }
        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    ws.send_json({"type": "save_user_prefs",
                                  "prefs": {"switch_scan": True, "switch_scan_interval_s": 2, "visual_alerts": True}})
                    msg = _next_of_type(ws, "user_profile")
        assert msg is not None
        mock_users.update_prefs.assert_called_once_with(
            "test-user",
            {"switch_scan": True, "switch_scan_interval_s": 2, "visual_alerts": True},
        )

    def test_switch_scan_rejects_bad_values(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()
        mock_users.update_prefs.return_value = {
            "id": "test-user", "display_name": "Test Operator", "is_admin": True,
            "prefs": {"dark_mode": True},
        }
        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    # invalid interval, non-bool toggles → all dropped; dark_mode survives
                    ws.send_json({"type": "save_user_prefs",
                                  "prefs": {"switch_scan": "yes", "switch_scan_interval_s": 0.1,
                                            "visual_alerts": 1, "dark_mode": True}})
                    msg = _next_of_type(ws, "user_profile")
        assert msg is not None
        mock_users.update_prefs.assert_called_once_with("test-user", {"dark_mode": True})

    def test_kid_can_save_switch_scan_prefs_but_not_listen_only(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks(is_admin=False, role="kid")
        mock_users.update_prefs.return_value = {
            "id": "test-user", "display_name": "Test Operator", "is_admin": False,
            "role": "kid", "prefs": {"switch_scan": True, "visual_alerts": True},
        }
        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    ws.send_json({"type": "save_user_prefs",
                                  "prefs": {"switch_scan": True, "visual_alerts": True, "listen_only": True}})
                    msg = _next_of_type(ws, "user_profile")
        assert msg is not None
        # listen_only is NOT kid-allowed and must be filtered out
        mock_users.update_prefs.assert_called_once_with(
            "test-user", {"switch_scan": True, "visual_alerts": True},
        )
```

(Mirror the mock shapes of the existing kid tests — `test_kid_prefs_locked` at line 1937 and `test_kid_tx_with_no_presets_rejects_everything` at line 2854 — if `_make_auth_mocks(role="kid")` needs extra return-value shaping.)

- [ ] **Step 2: Run tests, verify they fail**

Run: `python -m pytest backend/tests/integration/test_server_ws.py -k "switch_scan or visual_alerts" -v`
Expected: FAIL (prefs filtered out by allowlist → `update_prefs` called without the new keys, or no `user_profile` reply).

- [ ] **Step 3: Implement.** In `backend/persistence/users.py`, extend `DEFAULT_PREFS` (after `"high_contrast": False,`):

```python
    "switch_scan": False,           # single-switch auto-scan (home cards + AAC grid)
    "switch_scan_interval_s": 1.5,  # 1 | 1.5 | 2 | 3
    "visual_alerts": False,         # screen-edge flash + vibration twin for audio cues
```

In `backend/server.py:2342` replace KID_ALLOWED_PREF_KEYS:

```python
KID_ALLOWED_PREF_KEYS = {"dark_mode", "font_scale", "high_contrast", "aac_mode", "aac_grid",
                         "switch_scan", "switch_scan_interval_s", "visual_alerts"}
```

In the `save_user_prefs` handler add the three keys to `allowed` (line 3253-3256):

```python
                allowed = {"dark_mode", "filter_profanity", "listen_only",
                           "read_aloud", "notifications_enabled", "spectro_colormap", "spectro_time_window_s",
                           "tts_voice", "tts_length_scale", "aac_mode", "aac_grid",
                           "ui_level", "font_scale", "high_contrast", "quick_messages",
                           "switch_scan", "switch_scan_interval_s", "visual_alerts"}
```

and after the `high_contrast` validation (line 3270-3271) add:

```python
                if "switch_scan" in updates and not isinstance(updates["switch_scan"], bool):
                    updates.pop("switch_scan")
                if "switch_scan_interval_s" in updates and updates["switch_scan_interval_s"] not in (1, 1.5, 2, 3):
                    updates.pop("switch_scan_interval_s")
                if "visual_alerts" in updates and not isinstance(updates["visual_alerts"], bool):
                    updates.pop("visual_alerts")
```

Note Python quirk: `True not in (1, 1.5, 2, 3)` is False (`True == 1`), so `switch_scan_interval_s: True` would slip through the tuple check — add `or isinstance(updates["switch_scan_interval_s"], bool)` to the pop condition:

```python
                if "switch_scan_interval_s" in updates and (
                    isinstance(updates["switch_scan_interval_s"], bool)
                    or updates["switch_scan_interval_s"] not in (1, 1.5, 2, 3)
                ):
                    updates.pop("switch_scan_interval_s")
```

- [ ] **Step 4: Run tests, verify pass**

Run: `python -m pytest backend/tests/integration/test_server_ws.py -v` (full file — guard against regressions)
Expected: PASS

- [ ] **Step 5: Commit** — `feat(prefs): switch_scan, switch_scan_interval_s, visual_alerts user prefs`

---

### Task 2: Frontend prefs plumbing (types, App state, Settings UI)

**Files:**
- Modify: `frontend/src/types/ws.ts:388-405` (UserPrefs)
- Modify: `frontend/src/App.tsx` — state near line 242, ref near 309, `user_profile` handler near 509-536, handlers near 1195-1207, SettingsDialog props near 1665, HomeScreen/AACApp prop threading (lines 1569, 1588 — consumed by Tasks 4/5)
- Modify: `frontend/src/components/SettingsDialog/SettingsDialog.tsx` (Props 31-33, PrefsDraft 83, seed 116, applyPrefs 149-151, ConfigPanel pass-through 199-212)
- Modify: `frontend/src/components/ConfigPanel/ConfigPanel.tsx` (Props 22-36, Interface row 89-116)
- Test: `frontend/src/components/SettingsDialog/__tests__/SettingsDialog.test.tsx`

**Interfaces:**
- Consumes: pref keys from Task 1.
- Produces: App state `switchScan: boolean`, `switchScanIntervalS: number`, `visualAlerts: boolean`, `visualAlertsRef` (React ref, current boolean); handlers `handleToggleSwitchScan()`, `handleSwitchScanIntervalChange(v: number)`, `handleToggleVisualAlerts()`. ConfigPanel props `switchScan/switchScanIntervalS/visualAlerts` + `onToggleSwitchScan/onSwitchScanIntervalChange/onToggleVisualAlerts`. Tasks 4, 5, 8 consume the App state.

- [ ] **Step 1: Write failing test** — in `SettingsDialog.test.tsx`, following that file's existing render pattern (reuse its base-props helper, adding the new required props):

```tsx
  it('renders switch scanning and visual alerts controls and applies them on Save', () => {
    const onToggleSwitchScan = vi.fn();
    const onSwitchScanIntervalChange = vi.fn();
    const onToggleVisualAlerts = vi.fn();
    render(<SettingsDialog {...baseProps}
      switchScan={false} switchScanIntervalS={1.5} visualAlerts={false}
      onToggleSwitchScan={onToggleSwitchScan}
      onSwitchScanIntervalChange={onSwitchScanIntervalChange}
      onToggleVisualAlerts={onToggleVisualAlerts}
    />);
    fireEvent.click(screen.getByLabelText('Switch Scanning'));
    fireEvent.click(screen.getByLabelText('Visual Alerts (flash + vibrate)'));
    fireEvent.click(screen.getByRole('button', { name: /save/i }));
    expect(onToggleSwitchScan).toHaveBeenCalledTimes(1);
    expect(onToggleVisualAlerts).toHaveBeenCalledTimes(1);
    expect(onSwitchScanIntervalChange).not.toHaveBeenCalled();
  });

  it('interval toggles only visible when switch scanning enabled in draft', () => {
    render(<SettingsDialog {...baseProps}
      switchScan={true} switchScanIntervalS={1.5} visualAlerts={false}
      onToggleSwitchScan={vi.fn()} onSwitchScanIntervalChange={vi.fn()} onToggleVisualAlerts={vi.fn()}
    />);
    expect(screen.getByRole('button', { name: 'Scan every 2 seconds' })).toBeInTheDocument();
  });
```

(Adjust `baseProps` naming to whatever the file's existing helper is called; add the three new props to it so other tests compile.)

- [ ] **Step 2: Run to verify fail** — `cd frontend && npx vitest run src/components/SettingsDialog` — expect TS errors/missing controls.

- [ ] **Step 3: Implement.**

`ws.ts` — inside `UserPrefs` after `high_contrast?: boolean;`:

```ts
  switch_scan?: boolean;
  switch_scan_interval_s?: number; // 1 | 1.5 | 2 | 3
  visual_alerts?: boolean;
```

`App.tsx` — state (next to the `aacMode` initializer at line 242, mirroring its localStorage pattern):

```ts
  const [switchScan, setSwitchScan] = useState(localStorage.getItem('radio_tty_switch_scan') === 'true');
  const [switchScanIntervalS, setSwitchScanIntervalS] = useState(() => {
    const v = Number(localStorage.getItem('radio_tty_switch_scan_interval_s'));
    return [1, 1.5, 2, 3].includes(v) ? v : 1.5;
  });
  const [visualAlerts, setVisualAlerts] = useState(localStorage.getItem('radio_tty_visual_alerts') === 'true');
```

Ref (next to `notificationsEnabledRef` at 309-310, same pattern — Task 8 consumes it):

```ts
  const visualAlertsRef = useRef(false);
  visualAlertsRef.current = visualAlerts;
```

`user_profile` handler (after the `high_contrast` block near line 534):

```ts
          if (prefs.switch_scan !== undefined) {
            setSwitchScan(prefs.switch_scan);
            localStorage.setItem('radio_tty_switch_scan', String(prefs.switch_scan));
          }
          if (prefs.switch_scan_interval_s !== undefined) {
            setSwitchScanIntervalS(prefs.switch_scan_interval_s);
            localStorage.setItem('radio_tty_switch_scan_interval_s', String(prefs.switch_scan_interval_s));
          }
          if (prefs.visual_alerts !== undefined) {
            setVisualAlerts(prefs.visual_alerts);
            localStorage.setItem('radio_tty_visual_alerts', String(prefs.visual_alerts));
          }
```

Handlers (next to `handleToggleHighContrast` at 1195):

```ts
  function handleToggleSwitchScan() {
    const next = !switchScan;
    setSwitchScan(next);
    localStorage.setItem('radio_tty_switch_scan', String(next));
    send({ type: 'save_user_prefs', prefs: { switch_scan: next } });
  }

  function handleSwitchScanIntervalChange(next: number) {
    setSwitchScanIntervalS(next);
    localStorage.setItem('radio_tty_switch_scan_interval_s', String(next));
    send({ type: 'save_user_prefs', prefs: { switch_scan_interval_s: next } });
  }

  function handleToggleVisualAlerts() {
    const next = !visualAlerts;
    setVisualAlerts(next);
    localStorage.setItem('radio_tty_visual_alerts', String(next));
    send({ type: 'save_user_prefs', prefs: { visual_alerts: next } });
  }
```

SettingsDialog invocation (line 1665) gains:

```tsx
        switchScan={switchScan}
        switchScanIntervalS={switchScanIntervalS}
        visualAlerts={visualAlerts}
        onToggleSwitchScan={handleToggleSwitchScan}
        onSwitchScanIntervalChange={handleSwitchScanIntervalChange}
        onToggleVisualAlerts={handleToggleVisualAlerts}
```

`SettingsDialog.tsx` — Props after `highContrast: boolean;`:

```ts
  switchScan: boolean;
  switchScanIntervalS: number;
  visualAlerts: boolean;
```
and after `onToggleHighContrast: () => void;`:
```ts
  onToggleSwitchScan: () => void;
  onSwitchScanIntervalChange: (v: number) => void;
  onToggleVisualAlerts: () => void;
```
`PrefsDraft` (line 83) append `switchScan: boolean; switchScanIntervalS: number; visualAlerts: boolean;`; seed (line 116) append `switchScan: props.switchScan, switchScanIntervalS: props.switchScanIntervalS, visualAlerts: props.visualAlerts,`; `applyPrefs` (after line 151):

```ts
    if (draft.switchScan !== prefsSeed.switchScan) props.onToggleSwitchScan();
    if (draft.switchScanIntervalS !== prefsSeed.switchScanIntervalS) props.onSwitchScanIntervalChange(draft.switchScanIntervalS);
    if (draft.visualAlerts !== prefsSeed.visualAlerts) props.onToggleVisualAlerts();
```
ConfigPanel pass-through (near line 199-212):

```tsx
            switchScan={draft.switchScan}
            switchScanIntervalS={draft.switchScanIntervalS}
            visualAlerts={draft.visualAlerts}
            onToggleSwitchScan={() => setDraft((d) => ({ ...d, switchScan: !d.switchScan }))}
            onSwitchScanIntervalChange={(v) => setDraft((d) => ({ ...d, switchScanIntervalS: v }))}
            onToggleVisualAlerts={() => setDraft((d) => ({ ...d, visualAlerts: !d.visualAlerts }))}
```

`ConfigPanel.tsx` — Props + destructure additions matching the above; UI in the "Interface tier + accessibility" Box after the High Contrast `FormControlLabel` (line 112-115):

```tsx
          <FormControlLabel
            control={<Switch checked={switchScan} onChange={onToggleSwitchScan} size="small" />}
            label="Switch Scanning"
          />
          {switchScan && (
            <ToggleButtonGroup
              size="small" exclusive value={switchScanIntervalS}
              onChange={(_, v) => v != null && onSwitchScanIntervalChange(v)}
              aria-label="Scan speed"
            >
              <ToggleButton value={1} aria-label="Scan every 1 second">1s</ToggleButton>
              <ToggleButton value={1.5} aria-label="Scan every 1.5 seconds">1.5s</ToggleButton>
              <ToggleButton value={2} aria-label="Scan every 2 seconds">2s</ToggleButton>
              <ToggleButton value={3} aria-label="Scan every 3 seconds">3s</ToggleButton>
            </ToggleButtonGroup>
          )}
          <FormControlLabel
            control={<Switch checked={visualAlerts} onChange={onToggleVisualAlerts} size="small" />}
            label="Visual Alerts (flash + vibrate)"
          />
```

- [ ] **Step 4: Run** — `npx vitest run src/components/SettingsDialog && npx tsc -p tsconfig.build.json` (from `frontend/`). Expected: PASS, no TS errors. Fix any other SettingsDialog call sites the compiler flags (MobileApp does not render its own SettingsDialog — App-level only — but let tsc confirm).

- [ ] **Step 5: Commit** — `feat(settings): switch scanning + visual alerts preference controls`

---

### Task 3: useSwitchScan hook

**Files:**
- Create: `frontend/src/hooks/useSwitchScan.ts`
- Test: `frontend/src/hooks/__tests__/useSwitchScan.test.tsx`

**Interfaces:**
- Produces: `useSwitchScan(enabled: boolean, intervalMs: number, containerRef: React.RefObject<HTMLElement | null>): void`. Scans elements matching `[data-scan="true"]` inside the container, skipping `disabled`/`aria-disabled="true"`, moving real DOM focus in DOM order, wrapping. Consumed by Tasks 4, 5, 6.

- [ ] **Step 1: Write failing test** `frontend/src/hooks/__tests__/useSwitchScan.test.tsx`:

```tsx
import { render, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useRef } from 'react';
import { useSwitchScan } from '../useSwitchScan';

function Harness({ enabled, interval = 1000 }: { enabled: boolean; interval?: number }) {
  const ref = useRef<HTMLDivElement | null>(null);
  useSwitchScan(enabled, interval, ref);
  return (
    <div ref={ref}>
      <button data-scan="true">one</button>
      <button data-scan="true" disabled>skipped</button>
      <button data-scan="true">two</button>
      <button>not scanned</button>
    </div>
  );
}

describe('useSwitchScan', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('moves focus through enabled [data-scan] elements in order, wrapping', () => {
    const { getAllByRole } = render(<Harness enabled />);
    const [one, , two] = getAllByRole('button');
    act(() => { vi.advanceTimersByTime(1000); });
    expect(one).toHaveFocus();
    act(() => { vi.advanceTimersByTime(1000); });
    expect(two).toHaveFocus();
    act(() => { vi.advanceTimersByTime(1000); });
    expect(one).toHaveFocus(); // wrapped, disabled button skipped
  });

  it('does nothing when disabled', () => {
    const { getAllByRole } = render(<Harness enabled={false} />);
    act(() => { vi.advanceTimersByTime(3000); });
    expect(getAllByRole('button')[0]).not.toHaveFocus();
  });

  it('stops scanning when enabled flips off', () => {
    const { rerender, getAllByRole } = render(<Harness enabled />);
    act(() => { vi.advanceTimersByTime(1000); });
    expect(getAllByRole('button')[0]).toHaveFocus();
    rerender(<Harness enabled={false} />);
    act(() => { vi.advanceTimersByTime(5000); });
    expect(getAllByRole('button')[1]).not.toHaveFocus();
  });
});
```

- [ ] **Step 2: Run to verify fail** — `npx vitest run src/hooks/__tests__/useSwitchScan.test.tsx` — module not found.

- [ ] **Step 3: Implement** `frontend/src/hooks/useSwitchScan.ts`:

```ts
import { useEffect, type RefObject } from 'react';

/**
 * Single-switch auto-scan: while enabled, moves real DOM focus through the
 * container's `[data-scan="true"]` elements on a timer, in DOM order,
 * wrapping at the end. The user's switch activates the focused element
 * natively (Enter/Space on a button), so no click plumbing is needed and
 * the highlight is the theme's global focus-visible ring. Disabled elements
 * are skipped. The element list is re-queried every tick so dynamic grids
 * (AAC categories, operator-tier cards) stay correct.
 */
export function useSwitchScan(
  enabled: boolean,
  intervalMs: number,
  containerRef: RefObject<HTMLElement | null>,
) {
  useEffect(() => {
    if (!enabled) return;
    let idx = -1;
    const timer = setInterval(() => {
      const root = containerRef.current;
      if (!root) return;
      const els = Array.from(root.querySelectorAll<HTMLElement>('[data-scan="true"]')).filter(
        (el) => !el.hasAttribute('disabled') && el.getAttribute('aria-disabled') !== 'true',
      );
      if (els.length === 0) return;
      idx = (idx + 1) % els.length;
      els[idx].focus();
    }, intervalMs);
    return () => clearInterval(timer);
  }, [enabled, intervalMs, containerRef]);
}
```

- [ ] **Step 4: Run to verify pass** — same command. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(a11y): useSwitchScan single-switch auto-scan hook`

---

### Task 4: Home grid switch scanning

**Files:**
- Modify: `frontend/src/components/HomeScreen/HomeScreen.tsx` (Props line 11-26, grid Box line 140, hook wiring near line 97)
- Modify: `frontend/src/components/HomeScreen/ActivityCard.tsx` (`ButtonBase`, line 35)
- Modify: `frontend/src/App.tsx:1588` (HomeScreen invocation)
- Test: `frontend/src/components/HomeScreen/__tests__/HomeScreen.test.tsx`

**Interfaces:**
- Consumes: `useSwitchScan` (Task 3); App state `switchScan`, `switchScanIntervalS`, `showSettings` (Task 2).
- Produces: HomeScreen props `switchScan: boolean; switchScanIntervalS: number;`.

- [ ] **Step 1: Write failing test** — add to `HomeScreen.test.tsx` (reuse its existing base props):

```tsx
  it('switch scanning cycles focus through activity cards', () => {
    vi.useFakeTimers();
    render(<HomeScreen {...base} uiLevel="simple" switchScan switchScanIntervalS={1.5} />);
    const cards = screen.getAllByRole('listitem').map((li) => within(li).getByRole('button'));
    act(() => { vi.advanceTimersByTime(1500); });
    expect(cards[0]).toHaveFocus();
    act(() => { vi.advanceTimersByTime(1500); });
    expect(cards[1]).toHaveFocus();
    vi.useRealTimers();
  });
```

(Import `act` from `@testing-library/react`; add `switchScan={false} switchScanIntervalS={1.5}` to the file's base props so existing tests compile.)

- [ ] **Step 2: Run to verify fail** — `npx vitest run src/components/HomeScreen`.

- [ ] **Step 3: Implement.**
  - `ActivityCard.tsx`: add `data-scan="true"` to the `ButtonBase` (harmless when scanning is off):

```tsx
    <ButtonBase
      onClick={onClick}
      aria-label={accessibleName}
      data-scan="true"
      ...
```

  - `HomeScreen.tsx`: Props add `switchScan: boolean; switchScanIntervalS: number;`. Imports add `useSwitchScan`. After the roving-tabindex block (near line 99):

```ts
  const gridRef = useRef<HTMLDivElement | null>(null);
  useSwitchScan(props.switchScan, props.switchScanIntervalS * 1000, gridRef);
```

  and put `ref={gridRef}` on the `role="list"` grid Box (line 140).
  - `App.tsx:1588`: pass `switchScan={switchScan && !showSettings}` (pause while the Settings dialog overlays home) and `switchScanIntervalS={switchScanIntervalS}`.

- [ ] **Step 4: Run** — `npx vitest run src/components/HomeScreen && npx tsc -p tsconfig.build.json`. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(home): switch scanning over activity cards`

---

### Task 5: AAC grid switch scanning + roving keyboard nav

**Files:**
- Modify: `frontend/src/components/AACApp/AACApp.tsx` (root Box line 156, Tabs line 209-221, send bar 256-288, hook wiring near line 60)
- Modify: `frontend/src/components/AACApp/ButtonGrid.tsx` (roving tabindex over word buttons)
- Modify: `frontend/src/components/AACApp/AACGridButton.tsx` (Button, line 12 — data-scan + roving props)
- Modify: `frontend/src/App.tsx:1569` (AACApp invocation)
- Test: `frontend/src/components/AACApp/__tests__/AACApp.test.tsx`

**Interfaces:**
- Consumes: `useSwitchScan` (Task 3); App state (Task 2).
- Produces: `AACAppProps` gains `switchScan: boolean; switchScanIntervalS: number;`. `AACGridButton` Props gain `tabIndex?: number; onKeyDown?: (e: React.KeyboardEvent) => void; onFocus?: () => void; buttonRef?: (el: HTMLButtonElement | null) => void;` (same shape as `ActivityCard.tsx:19-22`).

Two additions: (a) roving tabindex over the word grid — the spec's "roving tabindex (home grid + AAC grid)"; home shipped in Phase 1, AAC grid is still all-tabbable; (b) switch scanning. Scan order (DOM order): category tabs → active category's word buttons → SEND (or ABORT while transmitting). Scanning pauses whenever edit mode or any AAC dialog is open (`editMode || editorOpen || catEditorOpen || exitConfirmOpen` — the exit confirm gets its own in-dialog scan in Task 6).

- [ ] **Step 1: Write failing tests** — add to `AACApp.test.tsx` (reuse its base props/grid fixture):

```tsx
  it('arrow keys move focus between word buttons (roving tabindex)', () => {
    render(<AACApp {...base} />);
    const words = within(screen.getByRole('group')).getAllByRole('button');
    words[0].focus();
    fireEvent.keyDown(words[0], { key: 'ArrowRight' });
    expect(words[1]).toHaveFocus();
    expect(words[0]).toHaveAttribute('tabindex', '-1');
    expect(words[1]).toHaveAttribute('tabindex', '0');
    fireEvent.keyDown(words[1], { key: 'ArrowLeft' });
    expect(words[0]).toHaveFocus();
  });

  it('switch scanning cycles tabs, word buttons, then SEND', () => {
    vi.useFakeTimers();
    render(<AACApp {...base} switchScan switchScanIntervalS={1} />);
    act(() => { vi.advanceTimersByTime(1000); });
    expect(screen.getAllByRole('tab')[0]).toHaveFocus();
    // advance past all tabs and all word buttons of the active category
    const tabs = screen.getAllByRole('tab').length;
    const words = within(screen.getByRole('group')).getAllByRole('button').length;
    act(() => { vi.advanceTimersByTime(1000 * (tabs + words)); });
    expect(screen.getByRole('button', { name: 'Send message over radio' })).toHaveFocus();
    vi.useRealTimers();
  });

  it('switch scanning pauses in edit mode', () => {
    vi.useFakeTimers();
    render(<AACApp {...base} switchScan switchScanIntervalS={1} />);
    fireEvent.click(screen.getByRole('button', { name: 'Edit buttons' }));
    act(() => { vi.advanceTimersByTime(3000); });
    expect(screen.getAllByRole('tab')[0]).not.toHaveFocus();
    vi.useRealTimers();
  });
```

Note: SEND is `disabled` until a chunk is queued, and the hook skips disabled elements — for the first test, press a word button once before advancing timers (`fireEvent.click(within(screen.getByRole('group')).getAllByRole('button')[0])`) so SEND is scannable, and account for focus order accordingly.

- [ ] **Step 2: Run to verify fail** — `npx vitest run src/components/AACApp/__tests__/AACApp.test.tsx`.

- [ ] **Step 3: Implement.**
  - `AACGridButton.tsx`: on the `Button`, add `data-scan={editMode ? undefined : 'true'}` (edit mode buttons open editors — not part of a switch user's flow), plus the roving pass-through props (mirroring `ActivityCard.tsx:35-41`):

```tsx
interface Props {
  button: AACButton;
  editMode: boolean;
  onPress: (button: AACButton) => void;
  tabIndex?: number;
  onKeyDown?: (e: React.KeyboardEvent) => void;
  onFocus?: () => void;
  buttonRef?: (el: HTMLButtonElement | null) => void;
}

export function AACGridButton({ button, editMode, onPress, tabIndex, onKeyDown, onFocus, buttonRef }: Props) {
  return (
    <Button
      variant="outlined"
      onClick={() => onPress(button)}
      aria-label={editMode ? `Edit button: ${button.label}` : button.label}
      data-scan={editMode ? undefined : 'true'}
      tabIndex={tabIndex}
      onKeyDown={onKeyDown}
      onFocus={onFocus}
      ref={buttonRef}
      sx={{ /* unchanged */ }}
    >
```
(keep the existing `sx` block and children verbatim).
  - `ButtonGrid.tsx`: roving tabindex over the word buttons, same pattern as `HomeScreen.tsx:97-112`:

```tsx
import { useRef, useState } from 'react';

export function ButtonGrid({ category, editMode, onPress, onAdd }: Props) {
  // Roving tabindex: one word button is tabbable; arrows move focus.
  const [focusIdx, setFocusIdx] = useState(0);
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const count = category.buttons.length;
  const effectiveFocusIdx = Math.min(focusIdx, Math.max(0, count - 1));
  function handleKeyDown(e: React.KeyboardEvent, idx: number) {
    let next = idx;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next = (idx + 1) % count;
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = (idx - 1 + count) % count;
    else return;
    e.preventDefault();
    setFocusIdx(next);
    refs.current[next]?.focus();
  }
  return (
    <Box role="group" aria-label={`${category.name} buttons`} sx={{ /* unchanged */ }}>
      {category.buttons.map((b, i) => (
        <AACGridButton
          key={b.id}
          button={b}
          editMode={editMode}
          onPress={onPress}
          buttonRef={(el) => { refs.current[i] = el; }}
          tabIndex={i === effectiveFocusIdx ? 0 : -1}
          onKeyDown={(e) => handleKeyDown(e, i)}
          onFocus={() => setFocusIdx(i)}
        />
      ))}
      {/* editMode Add button unchanged — stays outside the roving set */}
```
(The switch-scan hook focuses `tabIndex={-1}` elements fine — `focus()` ignores tabindex.)
  - `AACApp.tsx`:
    - Props add `switchScan: boolean; switchScanIntervalS: number;` (both destructured).
    - Imports add `useRef` and `useSwitchScan`.
    - Wiring after state declarations (line ~70):

```ts
  const rootRef = useRef<HTMLDivElement | null>(null);
  const scanActive =
    switchScan && !editMode && !editorOpen && !catEditorOpen && !exitConfirmOpen;
  useSwitchScan(scanActive, switchScanIntervalS * 1000, rootRef);
```

    - `ref={rootRef}` on the root Box (line 156).
    - Each `Tab` (line 210) gains `data-scan="true"` (MUI Tab forwards unknown props to its root button).
    - SEND button (line 275) and ABORT button (line 263) gain `data-scan="true"`.
  - `App.tsx:1569`: pass `switchScan={switchScan}` and `switchScanIntervalS={switchScanIntervalS}` to `<AACApp>`.

- [ ] **Step 4: Run** — `npx vitest run src/components/AACApp && npx tsc -p tsconfig.build.json`. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(aac): roving tabindex + switch scanning over tabs, word grid, and send`

---

### Task 6: ConfirmDialog component (generalized huge yes/no) + AAC exit refactor

**Files:**
- Create: `frontend/src/components/ConfirmDialog/ConfirmDialog.tsx`
- Modify: `frontend/src/components/AACApp/AACApp.tsx` (replace inline exit Dialog, lines 332-359)
- Test: `frontend/src/components/ConfirmDialog/__tests__/ConfirmDialog.test.tsx`

**Interfaces:**
- Consumes: `useSwitchScan` (Task 3).
- Produces:

```ts
export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  body?: string;
  confirmLabel: string;      // rendered as "✅ {confirmLabel}"
  cancelLabel?: string;      // default 'No, go back', rendered as "↩️ {cancelLabel}"
  destructive?: boolean;     // confirm button color="error"
  switchScan?: boolean;      // scan the two buttons while open
  switchScanIntervalS?: number;
  onConfirm: () => void;
  onClose: () => void;
}
export function ConfirmDialog(props: ConfirmDialogProps): JSX.Element
```
Tasks 7 and later consume this exact signature.

- [ ] **Step 1: Write failing test** `ConfirmDialog.test.tsx`:

```tsx
import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { axe } from 'jest-axe';
import { ConfirmDialog } from '../ConfirmDialog';

describe('ConfirmDialog', () => {
  it('fires onConfirm then closes; cancel only closes', () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();
    render(<ConfirmDialog open title="Delete it?" confirmLabel="Yes, delete"
      destructive onConfirm={onConfirm} onClose={onClose} />);
    fireEvent.click(screen.getByRole('button', { name: /yes, delete/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: /no, go back/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it('switch scanning cycles the two buttons while open', () => {
    vi.useFakeTimers();
    render(<ConfirmDialog open title="Sure?" confirmLabel="Yes, do it"
      switchScan switchScanIntervalS={1} onConfirm={vi.fn()} onClose={vi.fn()} />);
    act(() => { vi.advanceTimersByTime(1000); });
    expect(screen.getByRole('button', { name: /yes, do it/i })).toHaveFocus();
    act(() => { vi.advanceTimersByTime(1000); });
    expect(screen.getByRole('button', { name: /no, go back/i })).toHaveFocus();
    vi.useRealTimers();
  });

  it('has no axe violations', async () => {
    const { baseElement } = render(<ConfirmDialog open title="Exit?" body="This switches back."
      confirmLabel="Yes, exit" onConfirm={vi.fn()} onClose={vi.fn()} />);
    expect(await axe(baseElement)).toHaveNoViolations();
  });
});
```

- [ ] **Step 2: Run to verify fail** — `npx vitest run src/components/ConfirmDialog`.

- [ ] **Step 3: Implement** `ConfirmDialog.tsx`:

```tsx
import { useRef } from 'react';
import { Button, Dialog, DialogActions, DialogContent, DialogTitle, Typography } from '@mui/material';
import { useSwitchScan } from '../../hooks/useSwitchScan';

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  body?: string;
  confirmLabel: string;
  cancelLabel?: string;
  destructive?: boolean;
  switchScan?: boolean;
  switchScanIntervalS?: number;
  onConfirm: () => void;
  onClose: () => void;
}

/**
 * Large stacked yes/no confirmation — the AAC exit-confirm pattern
 * generalized to all destructive actions (WCAG-friendly big targets,
 * explicit verb labels instead of OK/Cancel, optional switch scanning).
 */
export function ConfirmDialog({
  open, title, body, confirmLabel, cancelLabel, destructive,
  switchScan, switchScanIntervalS, onConfirm, onClose,
}: ConfirmDialogProps) {
  const actionsRef = useRef<HTMLDivElement | null>(null);
  useSwitchScan(!!switchScan && open, (switchScanIntervalS ?? 1.5) * 1000, actionsRef);
  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>{title}</DialogTitle>
      {body && (
        <DialogContent>
          <Typography>{body}</Typography>
        </DialogContent>
      )}
      <DialogActions ref={actionsRef} sx={{ flexDirection: 'column', gap: 1, p: 2 }}>
        <Button
          fullWidth
          variant="contained"
          color={destructive ? 'error' : 'primary'}
          data-scan="true"
          onClick={() => { onClose(); onConfirm(); }}
          sx={{ minHeight: 64, fontSize: '1.2rem' }}
        >
          ✅ {confirmLabel}
        </Button>
        <Button
          fullWidth
          variant="outlined"
          data-scan="true"
          onClick={onClose}
          sx={{ minHeight: 64, fontSize: '1.2rem' }}
        >
          ↩️ {cancelLabel ?? 'No, go back'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
```

Then in `AACApp.tsx` replace the inline exit Dialog (lines 332-359) with:

```tsx
      {/* Exit confirmation — the only path back to the normal UI */}
      <ConfirmDialog
        open={exitConfirmOpen}
        title="Exit AAC mode?"
        body="This switches back to the standard Hearthwave screen."
        confirmLabel="Yes, exit"
        cancelLabel="No, stay here"
        switchScan={switchScan}
        switchScanIntervalS={switchScanIntervalS}
        onConfirm={onExitAac}
        onClose={() => setExitConfirmOpen(false)}
      />
```

(import `ConfirmDialog`; drop now-unused `Dialog/DialogActions/DialogContent/DialogTitle` imports if nothing else in the file uses them — the category editor still uses them, so keep.)

- [ ] **Step 4: Run** — `npx vitest run src/components/ConfirmDialog src/components/AACApp && npx tsc -p tsconfig.build.json`. Existing AACApp exit-confirm tests must still pass (button labels unchanged: "✅ Yes, exit" / "↩️ No, stay here").
- [ ] **Step 5: Commit** — `feat(a11y): ConfirmDialog big yes/no component; AAC exit uses it`

---

### Task 7: Replace window.confirm sites + add missing confirms

**Files:**
- Modify: `frontend/src/components/AACApp/AACApp.tsx:147-153` (category delete)
- Modify: `frontend/src/components/AACApp/ButtonEditorDialog.tsx:83-96` (button delete)
- Modify: `frontend/src/components/SettingsDialog/SettingsDialog.tsx:163` (discard unsaved)
- Modify: `frontend/src/App.tsx:1079-1087` (plugin uninstall)
- Modify: `frontend/src/components/NeighborhoodPanel/NeighborhoodPanel.tsx:113-119` (street alert)
- Modify: `frontend/src/components/AdminPanel/AdminPanel.tsx:482-489` (device token revoke — currently NO confirm)
- Modify: `frontend/src/components/AttendancePanel/AttendancePanel.tsx:48-56` (roster clear — currently NO confirm)
- Test: existing test files for each component (grep each `__tests__` dir; `SettingsDialog.test.tsx` and `ButtonEditorDialog.test.tsx` stub `window.confirm` today and must be rewritten to click dialog buttons)

**Interfaces:**
- Consumes: `ConfirmDialog` (Task 6 signature).

Pattern for every site — replace the `window.confirm(...)` guard with a piece of pending-state + a `ConfirmDialog`. Concretely:

- **AACApp category delete** — add state `const [catDeleteConfirmOpen, setCatDeleteConfirmOpen] = useState(false);`. `handleDeleteCategory` becomes two functions:

```ts
  function requestDeleteCategory() {
    if (!catEditorTarget || grid.categories.length <= 1) return;
    setCatDeleteConfirmOpen(true);
  }

  function handleDeleteCategory() {
    if (!catEditorTarget) return;
    mutateCategory(catEditorTarget.id, () => null);
    setCatEditorOpen(false);
  }
```
DELETE button (line 320) calls `requestDeleteCategory`; render beside the exit ConfirmDialog:

```tsx
      <ConfirmDialog
        open={catDeleteConfirmOpen}
        title="Delete this category?"
        body={catEditorTarget ? `"${catEditorTarget.name}" and all its buttons will be removed.` : ''}
        confirmLabel="Yes, delete it"
        destructive
        switchScan={switchScan}
        switchScanIntervalS={switchScanIntervalS}
        onConfirm={handleDeleteCategory}
        onClose={() => setCatDeleteConfirmOpen(false)}
      />
```
(Also add `catDeleteConfirmOpen` to the Task 5 `scanActive` pause condition.)

- **ButtonEditorDialog** — add `const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);`; DELETE button onClick becomes `() => setDeleteConfirmOpen(true)`; render inside the component (after the main Dialog):

```tsx
      <ConfirmDialog
        open={deleteConfirmOpen}
        title="Delete this button?"
        body={button ? `"${button.label}" will be removed.` : ''}
        confirmLabel="Yes, delete it"
        destructive
        onConfirm={() => { if (button) { onDelete(button.id); onClose(); } }}
        onClose={() => setDeleteConfirmOpen(false)}
      />
```
(Component must return a fragment wrapping both dialogs.)

- **SettingsDialog discard** — replace line 163's `window.confirm` in its close handler with state `const [discardConfirmOpen, setDiscardConfirmOpen] = useState(false);`:

```ts
  function handleClose() {
    if (dirty) { setDiscardConfirmOpen(true); return; }
    onClose();
  }
```
plus, rendered inside the root Dialog:

```tsx
      <ConfirmDialog
        open={discardConfirmOpen}
        title="Discard unsaved changes?"
        confirmLabel="Yes, discard"
        cancelLabel="No, keep editing"
        destructive
        onConfirm={() => { setDiscardConfirmOpen(false); onClose(); }}
        onClose={() => setDiscardConfirmOpen(false)}
      />
```
(Keep the rest of the original close flow — whatever line 163's function did after the confirm, `onConfirm` must do. Read the surrounding function first and preserve draft-reset behavior.)

- **App.tsx plugin uninstall** — state `const [pluginToUninstall, setPluginToUninstall] = useState<string | null>(null);`. `handleUninstallPlugin(id)` becomes `setPluginToUninstall(id)`; the actual fetch moves to `confirmUninstallPlugin`:

```ts
  async function confirmUninstallPlugin() {
    const id = pluginToUninstall;
    if (!id) return;
    setPluginBusy(true);
    try {
      await fetch(`/plugins/${encodeURIComponent(id)}`, { method: 'DELETE', headers: authHeaders() });
    } finally {
      setPluginBusy(false);
    }
  }
```
Render next to `TokenPromptDialog` (line 1561):

```tsx
      <ConfirmDialog
        open={pluginToUninstall !== null}
        title="Uninstall plugin?"
        body={pluginToUninstall ? `"${pluginToUninstall}" and its files will be removed.` : ''}
        confirmLabel="Yes, uninstall"
        destructive
        switchScan={switchScan}
        switchScanIntervalS={switchScanIntervalS}
        onConfirm={confirmUninstallPlugin}
        onClose={() => setPluginToUninstall(null)}
      />
```

- **NeighborhoodPanel street alert** — state `const [alertConfirmOpen, setAlertConfirmOpen] = useState(false);`; `handleSendStreetAlert` splits into request (validates non-empty, opens dialog) and confirm (calls `props.onStreetAlert(message); setStreetAlert('');`). Dialog: title `"Send this alert to everyone?"`, body = the alert text, confirmLabel `"Yes, send the alert"`, `destructive`.

- **AdminPanel token revoke** — state `const [tokenToRevoke, setTokenToRevoke] = useState<DeviceTokenRecord | null>(null);`; Revoke button (line 486) onClick `() => setTokenToRevoke(t)`; dialog: title `"Revoke this display?"`, body `` `"${tokenToRevoke?.label}" will stop working immediately.` ``, confirmLabel `"Yes, revoke it"`, `destructive`, onConfirm `() => { if (tokenToRevoke) onRevokeDeviceToken(tokenToRevoke.id); }`.

- **AttendancePanel clear** — state `const [clearConfirmOpen, setClearConfirmOpen] = useState(false);`; CLEAR button onClick `() => setClearConfirmOpen(true)`; dialog: title `"Clear stations heard?"`, confirmLabel `"Yes, clear the list"`, `destructive`, onConfirm `onClear`.

Steps:

- [ ] **Step 1: Update/write tests first.** `grep -rn "window.confirm" frontend/src` and rewrite the two test files stubbing it (`SettingsDialog.test.tsx`, `ButtonEditorDialog.test.tsx`) to click the dialog's "✅ Yes…" / "↩️ No…" buttons instead. Add one new test per newly-confirmed action (AdminPanel revoke, AttendancePanel clear), e.g.:

```tsx
  it('revoking a device token asks for confirmation first', () => {
    const onRevokeDeviceToken = vi.fn();
    render(<AdminPanel {...base} deviceTokens={[{ id: 't1', label: 'Kitchen', created_at: 'x', last_seen: null }]}
      onRevokeDeviceToken={onRevokeDeviceToken} />);
    fireEvent.click(screen.getByRole('button', { name: 'Revoke Kitchen' }));
    expect(onRevokeDeviceToken).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: /yes, revoke it/i }));
    expect(onRevokeDeviceToken).toHaveBeenCalledWith('t1');
  });
```
(Adapt fixture/base-prop names per file.)

- [ ] **Step 2: Run to verify new/updated tests fail** — `npx vitest run` (touched dirs).
- [ ] **Step 3: Implement all seven sites** per the pattern blocks above. After this task `grep -rn "window.confirm" frontend/src --include=*.tsx | grep -v __tests__` must return nothing.
- [ ] **Step 4: Run full frontend suite** — `npx vitest run && npx tsc -p tsconfig.build.json`. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(a11y): replace window.confirm with big-button ConfirmDialog everywhere; confirm token revoke + roster clear`

---

### Task 8: ScreenFlash visual twin + vibration

**Files:**
- Create: `frontend/src/components/ScreenFlash/ScreenFlash.tsx`
- Modify: `frontend/src/App.tsx` — flash state near line 288, trigger calls in `rx_message` final branch (~line 422), `ncs_alert` (~753), `family_presence` (~767), `neighborhood_alert` (~808), render after `<CssBaseline />` (line 1560)
- Test: `frontend/src/components/ScreenFlash/__tests__/ScreenFlash.test.tsx`

**Interfaces:**
- Consumes: `visualAlertsRef` (Task 2).
- Produces:

```ts
export type FlashKind = 'rx' | 'weather' | 'street' | 'family';
export function ScreenFlash({ flash }: { flash: { kind: FlashKind; seq: number } | null }): JSX.Element | null
export const VIBRATE_PATTERNS: Record<FlashKind, number[]>
```

- [ ] **Step 1: Write failing test** `ScreenFlash.test.tsx`:

```tsx
import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { axe } from 'jest-axe';
import { ScreenFlash } from '../ScreenFlash';

describe('ScreenFlash', () => {
  it('renders nothing when no flash', () => {
    const { container } = render(<ScreenFlash flash={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders an aria-hidden non-interactive overlay keyed by seq', () => {
    const { container, rerender } = render(<ScreenFlash flash={{ kind: 'street', seq: 1 }} />);
    const el = container.firstElementChild as HTMLElement;
    expect(el.getAttribute('aria-hidden')).toBe('true');
    expect(el.style.pointerEvents).toBe('none');
    rerender(<ScreenFlash flash={{ kind: 'street', seq: 2 }} />);
    expect(container.firstElementChild).not.toBe(el); // key change restarts the animation
  });

  it('has no axe violations', async () => {
    const { container } = render(<ScreenFlash flash={{ kind: 'rx', seq: 1 }} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
```

- [ ] **Step 2: Run to verify fail.**
- [ ] **Step 3: Implement** `ScreenFlash.tsx`:

```tsx
import { Box } from '@mui/material';
import { keyframes } from '@mui/system';

export type FlashKind = 'rx' | 'weather' | 'street' | 'family';

// Visual twin colors: RX = info blue, weather/family = amber, street = red.
const COLORS: Record<FlashKind, string> = {
  rx: '#00B0FF',
  weather: '#FFA000',
  street: '#D32F2F',
  family: '#FFA000',
};

export const VIBRATE_PATTERNS: Record<FlashKind, number[]> = {
  rx: [100],
  weather: [200, 100, 200],
  street: [300, 100, 300, 100, 300],
  family: [200, 100, 200],
};

const pulse = (color: string) => keyframes`
  0%   { box-shadow: inset 0 0 0 0 transparent; }
  15%  { box-shadow: inset 0 0 60px 12px ${color}; }
  40%  { box-shadow: inset 0 0 0 0 transparent; }
  55%  { box-shadow: inset 0 0 60px 12px ${color}; }
  100% { box-shadow: inset 0 0 0 0 transparent; }
`;

/** Screen-edge flash: the hearing-accessible twin of an audio cue.
 *  Purely decorative for AT (the cue's real content is the chat entry /
 *  banner / notification), hence aria-hidden + pointer-events none. */
export function ScreenFlash({ flash }: { flash: { kind: FlashKind; seq: number } | null }) {
  if (!flash) return null;
  const color = COLORS[flash.kind];
  return (
    <Box
      key={flash.seq}
      aria-hidden="true"
      style={{ pointerEvents: 'none' }}
      sx={{
        position: 'fixed',
        inset: 0,
        zIndex: (theme) => theme.zIndex.tooltip + 1,
        animation: `${pulse(color)} 1.4s ease-out 1`,
      }}
    />
  );
}
```

`App.tsx`:
- Import `ScreenFlash`, `VIBRATE_PATTERNS`, `type FlashKind` from `./components/ScreenFlash/ScreenFlash`.
- State near line 288: `const [flash, setFlash] = useState<{ kind: FlashKind; seq: number } | null>(null);`
- Helper near the other handlers (uses `visualAlertsRef` from Task 2 so it's safe inside the stable WS callback):

```ts
  function triggerVisualAlert(kind: FlashKind) {
    if (!visualAlertsRef.current) return;
    setFlash((prev) => ({ kind, seq: (prev?.seq ?? 0) + 1 }));
    if (typeof navigator !== 'undefined' && 'vibrate' in navigator) {
      navigator.vibrate(VIBRATE_PATTERNS[kind]);
    }
  }
```
- Trigger calls (each one line, placed immediately after the existing Notification block in that case):
  - `rx_message` final branch (after line 433): `triggerVisualAlert('rx');`
  - `ncs_alert` (after line 764): `triggerVisualAlert('weather');`
  - `family_presence` — inside the `newlyMissed` loop's guard is wrong (it's gated on notifications); instead, after the Notification `if` block but still inside `setFamilyPresence` updater where `newlyMissed(prev, entries)` is available: `if (newlyMissed(prev, entries).length > 0) triggerVisualAlert('family');`
  - `neighborhood_alert` (in its case, after the notification logic): `triggerVisualAlert('street');`
- Render `<ScreenFlash flash={flash} />` immediately after `<CssBaseline />` (line 1560) so it covers every shell including AAC and activities.

- [ ] **Step 4: Run** — `npx vitest run src/components/ScreenFlash && npx tsc -p tsconfig.build.json`. Also run the App-level WS handler tests if any exist (`npx vitest run src/__tests__`). Expected: PASS.
- [ ] **Step 5: Commit** — `feat(a11y): screen-edge flash + vibration visual twins for RX and alerts`

---

### Task 9: Keyboard shortcut overlay

**Files:**
- Create: `frontend/src/components/ShortcutOverlay/ShortcutOverlay.tsx`
- Modify: `frontend/src/App.tsx` (state + `?` keydown effect + render next to TokenPromptDialog line 1561)
- Test: `frontend/src/components/ShortcutOverlay/__tests__/ShortcutOverlay.test.tsx`

**Interfaces:**
- Produces: `ShortcutOverlay({ open, onClose }: { open: boolean; onClose: () => void })`.

- [ ] **Step 1: Write failing test:**

```tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { axe } from 'jest-axe';
import { ShortcutOverlay } from '../ShortcutOverlay';

describe('ShortcutOverlay', () => {
  it('lists the global shortcuts', () => {
    render(<ShortcutOverlay open onClose={vi.fn()} />);
    expect(screen.getByRole('dialog', { name: /keyboard shortcuts/i })).toBeInTheDocument();
    expect(screen.getByText('Esc')).toBeInTheDocument();
    expect(screen.getByText(/back to home/i)).toBeInTheDocument();
  });

  it('has no axe violations', async () => {
    const { baseElement } = render(<ShortcutOverlay open onClose={vi.fn()} />);
    expect(await axe(baseElement)).toHaveNoViolations();
  });
});
```

- [ ] **Step 2: Run to verify fail.**
- [ ] **Step 3: Implement** `ShortcutOverlay.tsx`:

```tsx
import {
  Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, Typography,
} from '@mui/material';

const SHORTCUTS: Array<[string, string]> = [
  ['?', 'Show or hide this shortcut list'],
  ['Esc', 'Back to home (closes the current activity)'],
  ['← ↑ → ↓', 'Move between cards on the home screen and AAC buttons'],
  ['Enter / Space', 'Open or press the focused card or button'],
  ['Tab', 'Move between controls'],
  ['Hold Space', 'Push-to-talk while the voice button is focused'],
];

export function ShortcutOverlay({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="xs" aria-labelledby="shortcut-overlay-title">
      <DialogTitle id="shortcut-overlay-title">Keyboard shortcuts</DialogTitle>
      <DialogContent>
        <Box component="dl" sx={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: 1.5, m: 0 }}>
          {SHORTCUTS.map(([key, desc]) => (
            <Box key={key} sx={{ display: 'contents' }}>
              <Typography component="dt" sx={{ fontFamily: 'monospace', fontWeight: 700, whiteSpace: 'nowrap' }}>
                {key}
              </Typography>
              <Typography component="dd" sx={{ m: 0 }}>{desc}</Typography>
            </Box>
          ))}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>CLOSE</Button>
      </DialogActions>
    </Dialog>
  );
}
```

`App.tsx`: state `const [shortcutsOpen, setShortcutsOpen] = useState(false);`; effect (near the other document-level effects):

```ts
  // "?" opens the shortcut overlay anywhere except while typing.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key !== '?' || e.defaultPrevented) return;
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
      setShortcutsOpen((v) => !v);
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);
```
Render next to `TokenPromptDialog`: `<ShortcutOverlay open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />`.

- [ ] **Step 4: Run** — `npx vitest run src/components/ShortcutOverlay && npx tsc -p tsconfig.build.json`. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(a11y): "?" keyboard shortcut overlay`

---

### Task 10: Kid+AAC send path — backend

**Files:**
- Modify: `backend/text/placeholders.py` (add `resolve_aac_placeholders`)
- Modify: `backend/server.py:2561-2565` (kid TX gate) + helper near `_is_kid` (line 2345)
- Test: `backend/tests/unit/` (placeholders unit test — put beside existing placeholders tests; `ls backend/tests/unit` and match the dir layout), `backend/tests/integration/test_server_ws.py` (extend `TestKidTxGate`, line 2825)

**Interfaces:**
- Consumes: `state.prefs["aac_grid"]` (live-synced prefs), `find_placeholders` flow.
- Produces: `tx_message` accepts optional `aac_chunks: list[str]`. For kids with valid chunks, server rebuilds `data["text"]` from the chunks (client text ignored). `resolve_aac_placeholders(text: str, operator_name: str, callsign: str) -> str` in `backend/text/placeholders.py`. Task 11 (frontend) relies on: kid + `aac_chunks` all from stored grid → transmits; anything else → `{"type": "error", "detail": "TX not allowed for this account"}`.

- [ ] **Step 1: Write failing unit test** for the resolver (mirror of frontend `resolveTokens` in `defaultGrid.ts:127-135` — {Name}/{callsign} case-insensitive, other {…} stripped, whitespace collapsed):

```python
from backend.text.placeholders import resolve_aac_placeholders


class TestResolveAacPlaceholders:
    def test_fills_name_and_callsign_case_insensitive(self):
        out = resolve_aac_placeholders("this is {callsign} checking in, {Name}", "Sam", "WRXB123")
        assert out == "this is WRXB123 checking in, Sam"

    def test_strips_unknown_tokens_and_collapses_whitespace(self):
        assert resolve_aac_placeholders("hello {weird token} world", "Sam", "W1AW") == "hello world"

    def test_fallbacks_match_frontend(self):
        assert resolve_aac_placeholders("{Name} {callsign}", "", "") == "Operator my callsign"
```

- [ ] **Step 2: Write failing integration tests** in `TestKidTxGate` (`kid_client`'s mock exposes prefs via `mock_users.get.return_value["prefs"]` — build standalone fixtures like `test_kid_tx_with_no_presets_rejects_everything` so you control the grid):

```python
    def _kid_client_with_grid(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks(is_admin=False, role="kid")
        mock_users.get.return_value["prefs"] = {"aac_grid": {
            "version": 1,
            "categories": [{"id": "c1", "name": "Core", "emoji": "⭐", "buttons": [
                {"id": "b1", "emoji": "👍", "label": "Yes", "text": "Yes"},
                {"id": "b2", "emoji": "📻", "label": "Check in", "text": "This is {callsign} checking in"},
            ]}],
        }}
        return cfg, mock_stt, mock_tts, mock_users, mock_tokens

    def test_kid_aac_chunks_from_grid_transmit(self, tmp_path):
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = self._kid_client_with_grid(tmp_path)
        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    ws.send_json({"type": "tx_message", "callsign": "WRXB123",
                                  "text": "ignored by server",
                                  "aac_chunks": ["Yes", "This is {callsign} checking in"]})
                    frames = _drain_until_idle(ws)
        assert frames[0] == {"type": "tx_status", "status": "transmitting"}
        # no prompt_token frame — placeholders resolved server-side
        assert all(f["type"] != "prompt_token" for f in frames)

    def test_kid_aac_chunk_not_in_grid_rejected(self, tmp_path):
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = self._kid_client_with_grid(tmp_path)
        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    ws.send_json({"type": "tx_message", "callsign": "WRXB123",
                                  "text": "x", "aac_chunks": ["Yes", "free text injection"]})
                    msg = _next_of_type(ws, "error")
        assert msg is not None
        assert "not allowed" in msg["detail"].lower()

    def test_kid_aac_chunks_without_stored_grid_rejected(self, kid_client):
        """kid_client has quick_messages but no aac_grid — chunk sends must fail."""
        with kid_client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "tx_message", "callsign": "WRXB123",
                          "text": "x", "aac_chunks": ["Yes"]})
            msg = _next_of_type(ws, "error")
        assert msg is not None

    def test_adult_tx_ignores_aac_chunks(self, client):
        """Non-kid sends are validated as before; chunks are inert metadata."""
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            ws.send_json({"type": "tx_message", "callsign": "W5TST", "text": "hello",
                          "aac_chunks": ["whatever"]})
            frames = _drain_until_idle(ws)
        assert frames[0] == {"type": "tx_status", "status": "transmitting"}
```

- [ ] **Step 3: Run to verify fail** — `python -m pytest backend/tests/integration/test_server_ws.py::TestKidTxGate -v` and the new unit file.

- [ ] **Step 4: Implement.**

`backend/text/placeholders.py` (below `find_placeholders`):

```python
_AAC_NAME_RE = re.compile(r"\{name\}", re.IGNORECASE)
_AAC_CALLSIGN_RE = re.compile(r"\{callsign\}", re.IGNORECASE)
_AAC_OTHER_RE = re.compile(r"\{[^}]*\}")
_WS_RE = re.compile(r"\s{2,}")


def resolve_aac_placeholders(text: str, operator_name: str, callsign: str) -> str:
    """Mirror of the frontend resolveTokens (AACApp defaultGrid.ts): fill
    {Name}/{callsign} case-insensitively, strip any other {...} token, and
    collapse whitespace — so a kid AAC send never reaches the prompt_token
    typing dialog, which a non-typing AAC user can't answer."""
    text = _AAC_NAME_RE.sub(operator_name or "Operator", text)
    text = _AAC_CALLSIGN_RE.sub(callsign or "my callsign", text)
    text = _AAC_OTHER_RE.sub("", text)
    return _WS_RE.sub(" ", text).strip()
```
(`import re` already present in that module; add if not.)

`backend/server.py` — helper below `_is_kid` (line 2346):

```python
def _aac_grid_texts(grid) -> set[str]:
    """All button texts in a stored aac_grid pref (empty set if absent/malformed)."""
    texts: set[str] = set()
    if not isinstance(grid, dict):
        return texts
    for cat in grid.get("categories") or []:
        if not isinstance(cat, dict):
            continue
        for b in cat.get("buttons") or []:
            if isinstance(b, dict) and isinstance(b.get("text"), str) and b["text"].strip():
                texts.add(b["text"])
    return texts
```
Import `resolve_aac_placeholders` next to the existing `find_placeholders` import.

Replace the kid gate (lines 2561-2565) with:

```python
                if _is_kid(state):
                    chunks = data.get("aac_chunks")
                    if isinstance(chunks, list) and chunks and all(isinstance(c, str) for c in chunks):
                        # AAC path: every chunk must be a button text in the kid's
                        # *stored* grid; the client-sent text is ignored and the
                        # transmission is rebuilt server-side so button presses are
                        # the only vocabulary a kid can put on the air.
                        allowed_texts = _aac_grid_texts(state.prefs.get("aac_grid"))
                        if not allowed_texts or any(c not in allowed_texts for c in chunks):
                            await _manager.send_to(ws, {"type": "error", "detail": "TX not allowed for this account"})
                            continue
                        profile_pub = (_users_store.get_public_one(state.user_id) or {}) if _users_store else {}
                        data["text"] = resolve_aac_placeholders(
                            " ".join(c.strip() for c in chunks),
                            (profile_pub.get("operator_name") or "").strip(),
                            (profile_pub.get("callsign") or "").strip() or callsign,
                        )
                        if not data["text"]:
                            await _manager.send_to(ws, {"type": "error", "detail": "TX not allowed for this account"})
                            continue
                    else:
                        presets = state.prefs.get("quick_messages") or []
                        if (data.get("text") or "").strip() not in presets:
                            await _manager.send_to(ws, {"type": "error", "detail": "TX not allowed for this account"})
                            continue
```

- [ ] **Step 5: Run** — `python -m pytest backend/tests/ -v` (full backend). Expected: PASS.
- [ ] **Step 6: Commit** — `feat(kid): AAC sends validated against stored grid, rebuilt server-side`

---

### Task 11: Kid+AAC send path — frontend + manual note

**Files:**
- Modify: `frontend/src/types/ws.ts:726-737` (TxMessagePayload)
- Modify: `frontend/src/components/AACApp/AACApp.tsx` (onSend signature line 41, handleSendClick line 90-96, error snackbar)
- Modify: `frontend/src/App.tsx` (handleSend line 884-898, AACApp invocation line 1569, kid default-grid persist effect)
- Modify: `USER_MANUAL.md:546` (remove/replace "AAC Interface … is not yet supported for Kid accounts.")
- Test: `frontend/src/components/AACApp/__tests__/AACApp.test.tsx`

**Interfaces:**
- Consumes: backend `aac_chunks` contract (Task 10); `errorSnack`/`handleCloseErrorSnack` App state; `defaultAacGrid` memo (App.tsx:247); `makeDefaultGrid`.
- Produces: `AACAppProps.onSend: (text: string, targetCall: string, targetName: string, aacChunks?: string[]) => void`; new AACApp props `errorSnack: string | null; onCloseErrorSnack: () => void;`.

- [ ] **Step 1: Write failing tests** in `AACApp.test.tsx`:

```tsx
  it('SEND passes the raw button chunks alongside the resolved text', () => {
    const onSend = vi.fn();
    render(<AACApp {...base} onSend={onSend} />);
    fireEvent.click(within(screen.getByRole('group')).getByRole('button', { name: 'Yes' }));
    fireEvent.click(screen.getByRole('button', { name: 'Send message over radio' }));
    expect(onSend).toHaveBeenCalledWith('Yes', '', '', ['Yes']);
  });

  it('shows server errors in a snackbar', () => {
    render(<AACApp {...base} errorSnack="TX not allowed for this account" onCloseErrorSnack={vi.fn()} />);
    expect(screen.getByRole('alert')).toHaveTextContent('TX not allowed for this account');
  });
```
(Add `errorSnack={null} onCloseErrorSnack={vi.fn()}` to the file's base props.)

- [ ] **Step 2: Run to verify fail.**
- [ ] **Step 3: Implement.**

`ws.ts` — `TxMessagePayload` gains:

```ts
  // Raw AAC button texts this message was composed from. For kid accounts the
  // server validates these against the stored aac_grid and rebuilds the text
  // itself; for adults they're inert.
  aac_chunks?: string[];
```

`AACApp.tsx`:
- `AACAppProps.onSend: (text: string, targetCall: string, targetName: string, aacChunks?: string[]) => void;` plus new props `errorSnack: string | null;` and `onCloseErrorSnack: () => void;` (destructure both).
- `handleSendClick` sends the chunks:

```ts
  function handleSendClick() {
    if (!canSend) return;
    const text = resolveTokens(chunks.join(' '), profile.operator_name, effectiveCallsign);
    if (!text) return;
    onSend(text, '', '', chunks);
    setChunks([]);
  }
```
- Error surface before the closing `</Box>` (imports: `Snackbar` from @mui/material; `Alert` already imported):

```tsx
      <Snackbar open={!!errorSnack} autoHideDuration={6000} onClose={onCloseErrorSnack}>
        <Alert severity="error" onClose={onCloseErrorSnack} sx={{ fontSize: '1.1rem' }}>
          {errorSnack}
        </Alert>
      </Snackbar>
```

`App.tsx`:
- `handleSend` gains the pass-through param:

```ts
  function handleSend(text: string, targetCall: string, targetName: string, aacChunks?: string[]) {
    if (!profile) return;
    const payload: TxMessagePayload = {
      type: 'tx_message',
      text,
      operator: profile.operator_name,
      callsign: effectiveCallsign,
      target_call: targetCall,
      target_name: targetName,
      // Transmit in this operator's profile voice/speed (the [tx] [name]
      // convention); the backend resolves it by display name.
      voice_as: profile.display_name,
      ...(aacChunks && aacChunks.length > 0 ? { aac_chunks: aacChunks } : {}),
    };
    send(payload);
  }
```
(Existing call sites pass 3 args — unchanged.)
- AACApp invocation (line 1569) gains `errorSnack={errorSnack}` and `onCloseErrorSnack={handleCloseErrorSnack}`.
- Kid default-grid persist effect (near the other effects; `defaultAacGrid` is the memo at line 247 — persisting that exact object keeps IDs identical to what's rendered):

```ts
  // A kid's AAC sends are validated server-side against their *stored* grid;
  // the client-only built-in default grid is invisible to the server. Persist
  // it once so a kid can use AAC before an adult customizes anything.
  useEffect(() => {
    if (aacMode && isKid && profile && aacGrid == null) {
      handleSaveAacGrid(defaultAacGrid);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aacMode, isKid, profile, aacGrid]);
```

`USER_MANUAL.md:546` — replace the "not yet supported" line with:

```markdown
Kid accounts can use the AAC Interface (section 27): sends are limited to the words on their buttons — the server checks every send against the buttons a parent configured (or the built-in starter grid) and rejects anything else.
```

- [ ] **Step 4: Run** — `npx vitest run && npx tsc -p tsconfig.build.json` (full frontend). Expected: PASS.
- [ ] **Step 5: Commit** — `feat(kid): AAC send path — chunks payload, error snackbar, manual note`

---

### Task 12: Docs — USER_MANUAL accessibility section

**Files:**
- Modify: `USER_MANUAL.md` (new section 33 after the section-32 kiosk content; update table of contents if the manual has one — check the top of the file)

- [ ] **Step 1: Write section 33** covering, in the manual's existing plain-language style:
  - **Switch scanning** — what it is (one-switch use), where to turn it on (Settings → Preferences → Switch Scanning), scan speeds (1s/1.5s/2s/3s), what gets scanned (home cards; AAC tabs, words, SEND; confirmation dialogs), how to select (press your switch — Enter or Space — when the highlight lands).
  - **Visual alerts** — Settings → Preferences → "Visual Alerts (flash + vibrate)": screen edges flash (blue = incoming radio message, amber = weather/family, red = street alert) and phones/tablets vibrate.
  - **Keyboard shortcuts** — press `?` anywhere for the shortcut list; recap the shortcuts from Task 9's table.
  - **Confirmation dialogs** — destructive actions now ask with two large buttons.
- [ ] **Step 2: Verify** — `grep -n "not yet supported" USER_MANUAL.md` returns nothing (Task 11 removed it); section numbering is contiguous.
- [ ] **Step 3: Commit** — `docs: USER_MANUAL section 33 — switch scanning, visual alerts, shortcuts`

---

## Final verification (whole phase)

- [ ] `cd frontend && npx vitest run && npx tsc -p tsconfig.build.json` — all green.
- [ ] `python -m pytest backend/tests/ -q` — all green.
- [ ] `grep -rn "window.confirm" frontend/src --include=*.tsx | grep -v __tests__` — empty.
- [ ] Manual smoke (docker compose `-p hearthwave`, or `npm run dev`): enable Switch Scanning in Settings → watch home cards cycle focus; enable Visual Alerts → send a street alert from a coordinator account → edges flash red; press `?` → overlay; kid account in AAC mode → compose from buttons → SEND transmits, free text impossible.
- [ ] Open PR `feat/hearthwave-a11y-phase5` → master. NO release tag (release is a separate `/release` invocation).

## Explicitly out of scope (follow-up tickets, not this phase)

- Server-side-only audio cues with no WS frame (VOX primer tone, tail-ID, monitoring beacon) get no visual twin — no frontend signal exists to hook.
- Phase-4 follow-ups from PR #119/#120: NCS plugin dispatch identity, `_pre_formatted` profanity bypass, CI typecheck of frontend test files, `tx_status` during server-initiated TTS, diverging quick-message lists.
- Client-supplied `callsign` field on `tx_message` is trusted for kids (pre-existing behavior, both preset and AAC paths).
