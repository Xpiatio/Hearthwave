# Website Look & Feel — App Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the website's navy/blue visual identity to both app modes, add gradient panel headers, run a full test suite pass, audit all 26 components, and expand all documentation.

**Architecture:** Theme-first — update `theme.ts` once with the new palette and five global MUI overrides; add a stateless `PanelHeader` component for typed gradient headers; apply it to panels with simple text headers and apply the gradient directly to complex existing header Boxes. Code audit follows with inline fixes. Docs expand last.

**Tech Stack:** React 18, MUI 9, TypeScript, Vitest + Testing Library (jest-axe)

---

## File Map

**Created:**
- `frontend/src/components/PanelHeader/PanelHeader.tsx`
- `frontend/src/components/PanelHeader/__tests__/PanelHeader.test.tsx`

**Modified:**
- `frontend/src/theme.ts`
- `frontend/src/components/NCSPanel/NCSPanel.tsx`
- `frontend/src/components/ConfigPanel/ConfigPanel.tsx`
- `frontend/src/components/JournalPanel/JournalPanel.tsx`
- `frontend/src/components/AttendancePanel/AttendancePanel.tsx`
- All 26 component files (code audit fixes)
- `README.md`
- `USER_MANUAL.md`
- `docs/index.html`

---

## Task 1: Verify Test Baseline

**Files:** none (read-only verification)

- [ ] **Step 1: Run full test suite**

```bash
cd frontend && npm run test
```

Expected: `568 passed` with no failures. If any fail, fix them before proceeding — they are pre-existing regressions unrelated to this work.

- [ ] **Step 2: Record baseline**

Note the exact pass count. All tests must still pass after each subsequent task.

---

## Task 2: Update theme.ts — Navy/Blue Palette + Global Overrides

**Files:**
- Modify: `frontend/src/theme.ts`

- [ ] **Step 1: Replace theme.ts entirely**

```typescript
import { createTheme } from '@mui/material/styles';

export function makeTheme(dark: boolean) {
  return createTheme({
    palette: {
      mode: dark ? 'dark' : 'light',
      primary: {
        main: dark ? '#60A5FA' : '#2563EB',
        dark: dark ? '#2563EB' : '#1D4ED8',
      },
      info: {
        main: dark ? '#93C5FD' : '#1E4976',
      },
      warning: {
        main: dark ? '#FBBF24' : '#7a4a00',
      },
      error: {
        main: dark ? '#F87171' : '#B91C1C',
      },
      success: {
        main: dark ? '#4ADE80' : '#15803D',
      },
      background: {
        default: dark ? '#0F2540' : '#E8EEF7',
        paper: dark ? '#1A3A5C' : '#C8D8EC',
      },
      text: {
        primary: dark ? '#F9FAFB' : '#0F2540',
      },
      divider: dark ? 'rgba(37,99,235,0.3)' : 'rgba(30,73,118,0.25)',
    },
    typography: {
      htmlFontSize: 16,
      fontFamily:
        "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      body1: { fontSize: '1.125rem' },
      body2: { fontSize: '1rem' },
    },
    components: {
      MuiButton: {
        styleOverrides: {
          root: {
            minHeight: 48,
            fontWeight: 700,
            letterSpacing: '0.04em',
          },
          sizeLarge: {
            minHeight: 56,
            fontSize: '1rem',
          },
        },
      },
      MuiIconButton: {
        styleOverrides: {
          root: {
            minHeight: 44,
            minWidth: 44,
          },
        },
      },
      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            fontSize: '1.125rem',
          },
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: ({ theme }) => ({
            border: `1px solid ${theme.palette.divider}`,
          }),
          rounded: {
            borderRadius: 8,
          },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: {
            overflow: 'hidden',
          },
        },
      },
      MuiAppBar: {
        styleOverrides: {
          root: ({ theme }) => ({
            backgroundColor:
              theme.palette.mode === 'dark' ? '#0F2540' : '#1A3A5C',
            border: 'none',
            borderRadius: 0,
            color: '#F9FAFB',
          }),
        },
      },
      MuiDialogTitle: {
        styleOverrides: {
          root: ({ theme }) => ({
            background:
              theme.palette.mode === 'dark'
                ? 'linear-gradient(135deg, #0F2540 0%, #1E4976 100%)'
                : 'linear-gradient(135deg, #1A3A5C 0%, #1E4976 100%)',
            color: '#F9FAFB',
            fontWeight: 700,
          }),
        },
      },
    },
  });
}
```

- [ ] **Step 2: Run tests**

```bash
cd frontend && npm run test
```

Expected: all 568 tests pass. If tests fail due to colour-dependent assertions, fix the assertion to match the new value (the colour changed deliberately).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/theme.ts
git commit -m "feat(theme): navy/blue palette + panel border/gradient overrides"
```

---

## Task 3: Create PanelHeader Component (TDD)

**Files:**
- Create: `frontend/src/components/PanelHeader/__tests__/PanelHeader.test.tsx`
- Create: `frontend/src/components/PanelHeader/PanelHeader.tsx`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/PanelHeader/__tests__/PanelHeader.test.tsx`:

```typescript
import React from 'react'
import { render as rtlRender, screen } from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect } from 'vitest'
import { PanelHeader } from '../PanelHeader'

const NAVY_GRADIENT = 'linear-gradient(135deg, #1A3A5C 0%, #1E4976 100%)'
const BLUE_GRADIENT = 'linear-gradient(135deg, #1E4976 0%, #2563EB 100%)'

function render(ui: React.ReactElement) {
  return rtlRender(
    <ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>
  )
}

describe('PanelHeader', () => {
  it('renders the title text', () => {
    render(<PanelHeader title="NET CONTROL STATION" gradient={BLUE_GRADIENT} />)
    expect(screen.getByText('NET CONTROL STATION')).toBeInTheDocument()
  })

  it('renders title in an element with role region via parent panel — title is visible text', () => {
    render(<PanelHeader title="JOURNALS" gradient={NAVY_GRADIENT} />)
    expect(screen.getByText('JOURNALS')).toBeVisible()
  })

  it('renders an icon when provided', () => {
    render(
      <PanelHeader
        title="CONFIGURATION"
        gradient={NAVY_GRADIENT}
        icon={<span data-testid="ph-icon" aria-hidden="true" />}
      />
    )
    expect(screen.getByTestId('ph-icon')).toBeInTheDocument()
  })

  it('renders without icon prop', () => {
    render(<PanelHeader title="ATTENDANCE" gradient={NAVY_GRADIENT} />)
    expect(screen.getByText('ATTENDANCE')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd frontend && npm run test -- PanelHeader
```

Expected: FAIL with `Cannot find module '../PanelHeader'`

- [ ] **Step 3: Implement PanelHeader**

Create `frontend/src/components/PanelHeader/PanelHeader.tsx`:

```typescript
import { Box, Typography } from '@mui/material';

interface PanelHeaderProps {
  title: string;
  gradient: string;
  icon?: React.ReactNode;
}

export function PanelHeader({ title, gradient, icon }: PanelHeaderProps) {
  return (
    <Box
      sx={{
        background: gradient,
        px: 2,
        py: 1,
        display: 'flex',
        alignItems: 'center',
        gap: 1,
      }}
    >
      {icon}
      <Typography
        variant="subtitle2"
        sx={{ fontWeight: 700, textTransform: 'uppercase', color: '#F9FAFB' }}
      >
        {title}
      </Typography>
    </Box>
  );
}
```

- [ ] **Step 4: Run tests — expect pass**

```bash
cd frontend && npm run test -- PanelHeader
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/PanelHeader/
git commit -m "feat(ui): add PanelHeader component for typed gradient panel headers"
```

---

## Task 4: Apply Panel Gradients

Four panels get visual treatment. AdminPanel and ServerConfigPanel are Dialogs and already get gradient headers from the `MuiDialogTitle` theme override — no code changes needed there.

**Files:**
- Modify: `frontend/src/components/ConfigPanel/ConfigPanel.tsx`
- Modify: `frontend/src/components/AttendancePanel/AttendancePanel.tsx`
- Modify: `frontend/src/components/JournalPanel/JournalPanel.tsx`
- Modify: `frontend/src/components/NCSPanel/NCSPanel.tsx`

### 4a — ConfigPanel

The root Paper has `px: 2, py: 1.5` applied globally. Remove those from Paper and move them to the content Box so PanelHeader can bleed edge-to-edge.

- [ ] **Step 1: Update ConfigPanel**

In `frontend/src/components/ConfigPanel/ConfigPanel.tsx`:

Add import at top:
```typescript
import { PanelHeader } from '../PanelHeader/PanelHeader';
```

Change the `return` block. Replace:
```typescript
  return (
    <Paper
      elevation={0}
      square
      sx={{ px: 2, py: 1.5, borderBottom: 1, borderColor: 'divider' }}
      role="region"
      aria-label="Configuration"
    >
      <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 700, textTransform: 'uppercase' }}>
        Configuration
      </Typography>

      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
```

With:
```typescript
  return (
    <Paper
      elevation={0}
      square
      sx={{ borderBottom: 1, borderColor: 'divider', overflow: 'hidden' }}
      role="region"
      aria-label="Configuration"
    >
      <PanelHeader
        title="Configuration"
        gradient="linear-gradient(135deg, #1A3A5C 0%, #1E4976 100%)"
      />
      <Box sx={{ px: 2, py: 1.5, display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
```

Also remove the `Typography` import if it's no longer used elsewhere in the file (check first with grep).

- [ ] **Step 2: Run ConfigPanel tests**

```bash
cd frontend && npm run test -- ConfigPanel
```

Expected: all ConfigPanel tests pass.

### 4b — AttendancePanel

The root Paper has `px: 2, py: 1`. The header Box is the first child. Add the gradient directly to the header Box and restructure padding.

- [ ] **Step 3: Update AttendancePanel**

In `frontend/src/components/AttendancePanel/AttendancePanel.tsx`:

Replace the full `return` block:
```typescript
  return (
    <Paper square elevation={0} sx={{ borderBottom: 1, borderColor: 'divider', overflow: 'hidden' }}>
      <Box
        sx={{
          background: 'linear-gradient(135deg, #1A3A5C 0%, #1E4976 100%)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          px: 2,
          py: 1,
        }}
      >
        <Typography variant="h6" sx={{ fontWeight: 700, color: '#F9FAFB' }}>
          STATIONS HEARD THIS SESSION
        </Typography>
        <Button
          size="small"
          variant="outlined"
          onClick={onClear}
          disabled={stations.length === 0}
          sx={{ color: '#F9FAFB', borderColor: 'rgba(255,255,255,0.4)' }}
        >
          CLEAR
        </Button>
      </Box>

      <Box sx={{ px: 2, py: 1 }}>
        {stations.length === 0 ? (
          <Typography variant="body2" sx={{ color: 'text.secondary', fontStyle: 'italic' }}>
            No stations heard yet.
          </Typography>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 700 }}>Callsign</TableCell>
                  <TableCell>Name</TableCell>
                  <TableCell>Location</TableCell>
                  <TableCell>GMRS</TableCell>
                  <TableCell>HAM</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {stations.map((s) => (
                  <TableRow key={s.callsign} hover>
                    <TableCell sx={{ fontWeight: 700 }}>{s.callsign}</TableCell>
                    <TableCell>{s.name}</TableCell>
                    <TableCell>{s.location}</TableCell>
                    <TableCell>{s.gmrs}</TableCell>
                    <TableCell>{s.ham}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Box>
    </Paper>
  );
```

- [ ] **Step 4: Run AttendancePanel tests**

```bash
cd frontend && npm run test -- AttendancePanel
```

Expected: all AttendancePanel tests pass. The test looks for `'STATIONS HEARD THIS SESSION'` which is still present.

### 4c — JournalPanel

The JOURNALS header is inside the left-column Box (a nested `<Box sx={{ px: 1.5, py: 1, ... }}>`). Add gradient directly to that Box.

- [ ] **Step 5: Update JournalPanel**

In `frontend/src/components/JournalPanel/JournalPanel.tsx`, find:
```typescript
        <Box sx={{ px: 1.5, py: 1, borderBottom: 1, borderColor: 'divider' }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>JOURNALS</Typography>
        </Box>
```

Replace with:
```typescript
        <Box
          sx={{
            background: 'linear-gradient(135deg, #1A3A5C 0%, #1E4976 100%)',
            px: 1.5,
            py: 1,
            borderBottom: 1,
            borderColor: 'divider',
          }}
        >
          <Typography variant="subtitle1" sx={{ fontWeight: 700, color: '#F9FAFB' }}>
            JOURNALS
          </Typography>
        </Box>
```

- [ ] **Step 6: Run JournalPanel tests**

```bash
cd frontend && npm run test -- JournalPanel
```

Expected: all JournalPanel tests pass.

### 4d — NCSPanel

The header Box (line ~147) is complex — icon, title, Chip, buttons. Add the gradient to the existing Box `sx`. Chip and Button styles may need `sx` color overrides to remain legible on the blue gradient.

- [ ] **Step 7: Update NCSPanel header Box**

In `frontend/src/components/NCSPanel/NCSPanel.tsx`, find:
```typescript
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 2, py: 1, borderBottom: 1, borderColor: 'divider' }}>
```

Replace with:
```typescript
      <Box
        sx={{
          background: 'linear-gradient(135deg, #1E4976 0%, #2563EB 100%)',
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          px: 2,
          py: 1,
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
```

Find the Typography inside that Box:
```typescript
        <Typography variant="subtitle2" sx={{ fontWeight: 700, flex: 1 }}>
          NET CONTROL STATION
        </Typography>
```

Replace with:
```typescript
        <Typography variant="subtitle2" sx={{ fontWeight: 700, flex: 1, color: '#F9FAFB' }}>
          NET CONTROL STATION
        </Typography>
```

- [ ] **Step 8: Run NCSPanel tests**

```bash
cd frontend && npm run test -- NCSPanel
```

Expected: all NCSPanel tests pass.

- [ ] **Step 9: Commit all panel changes**

```bash
git add frontend/src/components/ConfigPanel/ \
        frontend/src/components/AttendancePanel/ \
        frontend/src/components/JournalPanel/ \
        frontend/src/components/NCSPanel/
git commit -m "feat(ui): apply gradient panel headers to ConfigPanel, AttendancePanel, JournalPanel, NCSPanel"
```

---

## Task 5: Full Test Suite Pass

- [ ] **Step 1: Run all tests**

```bash
cd frontend && npm run test
```

Expected: all 568+ tests pass (568 baseline + 4 new PanelHeader tests = 572 minimum).

- [ ] **Step 2: Fix any failures**

Priority order:
1. **Assertion value mismatches** — a test checking for the old green `#4ADE80` as primary — update the assertion to `#60A5FA` (dark) or `#2563EB` (light).
2. **Missing text** — a test looking for header text that moved — verify the text is still rendered in PanelHeader and adjust selector if needed.
3. **Snapshot failures** — if any snapshot tests exist, update snapshots: `npm run test -- --update-snapshots`.

- [ ] **Step 3: Commit fixes**

```bash
git add -p   # stage only test fixes
git commit -m "test: update assertions for navy/blue theme and panel header changes"
```

---

## Task 6: Code Audit — Components A–M

Audit each component file listed. For each: open the file, run the relevant grep, apply fixes, re-run the component's tests.

**Components:** AccountMenu, AdminPanel, AttendancePanel, ChatDisplay, ConfigPanel, ContactsDialog, DesktopApp (+ Snackbar.a11y), DraggablePanel, JournalPanel, LoginScreen, MessageInput

**Audit checklist per component:**

### Check 1: Hardcoded colors bypassing theme

```bash
grep -n "#[0-9a-fA-F]\{3,6\}\b" frontend/src/components/<Name>/<Name>.tsx
```

- `#000` or `#000000` on spectrogram canvas: acceptable (spectrogram background is intentionally black).
- Any other hardcoded color: replace with the appropriate theme token via `sx={{ color: 'text.primary' }}` or `bgcolor: 'background.paper'` etc.
- Exception: the gradient strings added in Task 4 are intentional — leave them.

### Check 2: WCAG 2.2 AA — ARIA

```bash
grep -n "onClick\|onChange\|onKeyDown" frontend/src/components/<Name>/<Name>.tsx
```

Every interactive element that is NOT a native `<button>`, `<input>`, `<select>`, or `<a>` must have:
- `role="button"` (or appropriate role)
- `tabIndex={0}`
- `onKeyDown` handler that fires on Enter/Space

Every icon-only button must have `aria-label`.

### Check 3: TypeScript — unused imports

```bash
npx tsc --noEmit -p frontend/tsconfig.json 2>&1 | grep "<Name>"
```

Remove any import reported as unused.

### Check 4: Dead code

Look for: state variables set but never read, `useEffect` with empty body, commented-out JSX blocks.

### Check 5: Console statements left in production code

```bash
grep -n "console\." frontend/src/components/<Name>/<Name>.tsx
```

- `console.error` in catch blocks: keep (legitimate error reporting).
- `console.log` / `console.warn` for debugging: remove.

---

**Per-component specifics:**

### AccountMenu (`AccountMenu.tsx`)

- `Avatar sx={{ bgcolor: 'primary.main' }}` — primary is now blue. This is correct (UI action color on Avatar). No change needed.
- `borderColor: avatarEmoji === e ? 'primary.main' : 'transparent'` — correct, leave as-is.
- Verify all Dialog/Menu items have accessible labels.

### AdminPanel (`AdminPanel.tsx`)

- Is a Dialog — MuiDialogTitle override applies automatically.
- Check all TextField inputs have `label` prop (not just placeholder).
- Check Slider has `aria-label` or `aria-labelledby`.

### AttendancePanel (`AttendancePanel.tsx`)

- Already updated in Task 4.
- Verify `<Table>` has `aria-label` prop: `<Table size="small" aria-label="Stations heard this session">`.
- Add if missing.

### ChatDisplay (`ChatDisplay.tsx`)

- Line 32: `rx: 'success.main'` — green for incoming radio messages. Correct per spec. Leave.
- Line 134: `color: 'success.main'` — radio status. Correct. Leave.
- Check the chat list container has `role="log"` and `aria-live="polite"` for screen reader announcements.
- Add if missing: `<Box role="log" aria-live="polite" aria-label="Radio chat messages">`.

### ConfigPanel (`ConfigPanel.tsx`)

- Already updated in Task 4.
- All Switch controls must have `inputProps={{ 'aria-label': '...' }}` if no visible label is associated.
- The `FormControlLabel` wrapping each Switch handles labelling — verify `control` and `label` props are both present.

### ContactsDialog (`ContactsDialog.tsx`)

- Is a Dialog — gradient header applies automatically.
- Check all TableCell headers have `scope="col"` if inside `<TableHead>`.
- Add `scope="col"` to any `<TableCell>` in a header row.

### DesktopApp (`DesktopApp.tsx`)

- Check Snackbar messages have `role="status"` or are inside an `aria-live` region.
- The existing `Snackbar.a11y.test.tsx` covers this — verify it passes.

### DraggablePanel (`DraggablePanel.tsx`)

- Verify drag handle has `aria-label="Drag to reorder panel"` or similar.
- Verify keyboard move buttons (if present) have accessible labels.

### JournalPanel (`JournalPanel.tsx`)

- Already updated in Task 4.
- Check `<List>` has `aria-label="Journal entries"`.
- Check action buttons (delete, select) have `aria-label`.

### LoginScreen (`LoginScreen.tsx`)

- All input fields must have `label` (not just `placeholder`).
- Submit button must be `type="submit"` or in a `<form onSubmit>`.
- Password field must have `type="password"`.

### MessageInput (`MessageInput.tsx`)

- TextField for message input: verify `label` or `aria-label` prop.
- Send button: verify `aria-label="Send message"` or visible text label.

- [ ] **Step 1: Audit each component, apply all fixes found above**

Open each file, run checks, apply fixes. After each file, run its test:
```bash
cd frontend && npm run test -- <ComponentName>
```

- [ ] **Step 2: Commit audit batch A–M**

```bash
git add frontend/src/components/AccountMenu/ \
        frontend/src/components/AdminPanel/ \
        frontend/src/components/AttendancePanel/ \
        frontend/src/components/ChatDisplay/ \
        frontend/src/components/ConfigPanel/ \
        frontend/src/components/ContactsDialog/ \
        frontend/src/components/DesktopApp/ \
        frontend/src/components/DraggablePanel/ \
        frontend/src/components/JournalPanel/ \
        frontend/src/components/LoginScreen/ \
        frontend/src/components/MessageInput/
git commit -m "fix(audit): a11y, dead code, and type fixes — components A–M"
```

---

## Task 7: Code Audit — Components N–Z + Hooks

**Components:** MobileApp, MobileTopBar, NCSPanel, PendingStationsBar, PluginSlot, QuickMessages, ServerConfigPanel, SetupScreen, Spectrogram, StatusRow, TokenPromptDialog, TopBar, UsersPanel, VoicePTT
**Hooks:** useAuth, useMobileDetect, useWebSocket

Apply the same five-check audit checklist from Task 6.

**Per-component specifics:**

### MobileApp / MobileTopBar

- `success.main` for connected dot — correct radio status green. Leave.
- SwipeableDrawer: verify `aria-label` on the drawer (`aria-label="Settings menu"`).
- All Switch items in drawer: have visible labels via `ListItemText` — correct.
- ABORT TX button: already has `aria-label="Abort transmission"` — verify.
- VoicePTT keyboard trigger: verify `onKeyDown` fires on Space/Enter.

### NCSPanel (`NCSPanel.tsx`)

- Already updated in Task 4.
- `console.error` in `playPcmAudio` catch block: keep — this is legitimate error logging.
- `success.dark` on the active NCS banner: correct radio status green. Leave.
- Verify all icon buttons in the roster table have `aria-label`.
- Verify `<Table>` has `aria-label="NCS roster"` or equivalent.

### PendingStationsBar

- Check each pending-station item is keyboard accessible.
- If items have click handlers on a `<Box>`, add `role="button"`, `tabIndex={0}`, `onKeyDown`.

### PluginSlot

- Thin wrapper — likely no issues. Verify import is not unused.

### QuickMessages

- All quick-message buttons: verify `aria-label` includes the message text (for screen readers).
- `aria-label={`Send quick message: ${msg}`}` pattern.

### ServerConfigPanel (`ServerConfigPanel.tsx`)

- Is a Dialog — gradient header applies automatically.
- All TextField inputs: verify `label` prop present.
- Check number inputs have `type="number"` with appropriate `inputProps={{ min, max }}`.

### SetupScreen (`SetupScreen.tsx`)

- Form inputs: verify `label` present on all fields.
- Password field: `type="password"`.
- Submit: `type="submit"` or form `onSubmit`.

### Spectrogram (`Spectrogram.tsx`)

- `bgcolor: '#000'` on spectrogram canvas container: acceptable. Black is the correct background for a spectrogram display. Add a comment: `// canvas background is intentionally black for spectrogram contrast`.
- Canvas must have `aria-label="Audio spectrogram display"` and `role="img"`.

### StatusRow (`StatusRow.tsx`)

- `ok: 'success.main'` — green for radio status. Correct. Leave.
- Verify the status row container has `role="status"` or `aria-live="polite"` so screen readers announce state changes.

### TokenPromptDialog (`TokenPromptDialog.tsx`)

- Is a Dialog — gradient header applies automatically.
- Verify password/token input has `type="password"` and `autoComplete="current-password"`.

### TopBar (`TopBar.tsx`)

- `color: connected ? 'primary.main' : 'warning.main'` — READY text in primary (now blue). Acceptable — this is a UI indicator, not a radio status.
- `bgcolor: isOnline ? 'success.main' : 'text.disabled'` — online dot in green. Correct radio status. Leave.
- Verify `aria-label` on the online status dot (it uses `aria-label` already per recent a11y work — confirm it's still present).

### UsersPanel (`UsersPanel.tsx`)

- `borderColor: avatarEmoji === e ? 'primary.main' : 'transparent'` — blue selection border. Correct.
- Verify avatar emoji picker grid has keyboard navigation (tabIndex, onKeyDown).

### VoicePTT (`VoicePTT.tsx`)

- PTT button must have `aria-pressed={recording}` to announce recording state to screen readers.
- Verify `onKeyDown` fires on Space to start recording (keyboard PTT).
- Check if `aria-pressed` is already present; add if missing.

### Hooks

```bash
npx tsc --noEmit -p frontend/tsconfig.json 2>&1 | grep "hooks/"
```

Fix any type errors reported. No ARIA concerns in hooks.

- [ ] **Step 1: Audit each component and hook, apply all fixes**

After each file:
```bash
cd frontend && npm run test -- <ComponentName>
```

- [ ] **Step 2: Commit audit batch N–Z + hooks**

```bash
git add frontend/src/components/MobileApp/ \
        frontend/src/components/NCSPanel/ \
        frontend/src/components/PendingStationsBar/ \
        frontend/src/components/PluginSlot/ \
        frontend/src/components/QuickMessages/ \
        frontend/src/components/ServerConfigPanel/ \
        frontend/src/components/SetupScreen/ \
        frontend/src/components/Spectrogram/ \
        frontend/src/components/StatusRow/ \
        frontend/src/components/TokenPromptDialog/ \
        frontend/src/components/TopBar/ \
        frontend/src/components/UsersPanel/ \
        frontend/src/components/VoicePTT/ \
        frontend/src/hooks/
git commit -m "fix(audit): a11y, dead code, and type fixes — components N–Z + hooks"
```

---

## Task 8: Full Test Suite After Audit

- [ ] **Step 1: Run all tests**

```bash
cd frontend && npm run test
```

Expected: all tests pass (572+). Zero failures.

- [ ] **Step 2: Fix any new failures from audit changes**

If an audit fix broke a test (e.g., adding `aria-label` changed a selector), update the test to match:
```typescript
// before
screen.getByRole('button')
// after (if button now has aria-label)
screen.getByRole('button', { name: /send message/i })
```

- [ ] **Step 3: Commit test fixes if any**

```bash
git add frontend/src/
git commit -m "test: update selectors for audit a11y additions"
```

---

## Task 9: Update README.md

**File:** `README.md`

- [ ] **Step 1: Rewrite README.md**

Replace the full file with this expanded version:

```markdown
# Radio-TTY

A GMRS family hub that turns a home server or x86 mini PC into a shared radio
operating station for every member of your household. Incoming transmissions are
transcribed by speech-to-text and streamed to all connected devices; outgoing
messages are synthesized to speech, automatically wrapped with the FCC station
callsign (§95.1751), and transmitted over the air. Each family member signs in
from their own phone, tablet, or laptop — no app install required.

Built-in plugins add Net Control Station (NCS) mode with a live check-in roster
and six traffic priority levels, SKYWARN weather alerts sourced directly from the
National Weather Service, and an instant audio replay buffer. The plugin
architecture is open — additional capabilities wire into the radio pipeline
without touching core server logic.

Radio-TTY is a fork of GMRS-TTY that replaces the desktop PySide6 UI with a
browser-based React frontend communicating over WebSocket.

## Features

- **Live transcription** — Whisper STT converts every received transmission to
  text in real time and broadcasts it to all connected users
- **Multi-user auth** — PBKDF2 password hashing, per-user session tokens, and
  per-user preferences stored server-side
- **Voice PTT** — browser microphone button (or Space bar) captures and transmits
  audio; pre-roll buffer captures the first syllable even before PTT is pressed
- **Priority audio mixer** — six traffic priority levels (Routine → Emergency)
  with an AGC+LPF audio pipeline
- **CW decode** — Morse code receive mode alongside voice
- **NCS mode** — Net Control Station plugin with roster management, six priority
  levels, and one-click callsign check-in/out
- **SKYWARN alerts** — live National Weather Service alerts pushed to all users
  with browser notification support
- **Journals** — AI-assisted session summaries with full transcript export
- **Contacts** — per-user contact book with FCC license lookup
- **Spectrogram** — real-time frequency display (voice or full range, viridis or
  grayscale colormaps)
- **Attendance panel** — automatic log of every station heard this session
- **Draggable panels** — desktop layout fully customisable with drag-and-drop
- **WCAG 2.2 AA** — full keyboard navigation, screen reader support, and ARIA
  labelling throughout the interface
- **Docker install** — single `docker compose up -d` gets you running

## UI Overview

The interface uses a navy/blue design language that matches the
[Radio-TTY website](https://xpiatio.github.io/Radio-TTY/):

- **Dark mode** — deep navy backgrounds (`#0F2540` page, `#1A3A5C` panels) with
  blue primary actions (`#60A5FA`) and white text
- **Light mode** — navy-tinted backgrounds (`#E8EEF7` page, `#C8D8EC` panels)
  with blue primary actions (`#2563EB`) and dark navy text
- **Green** is reserved exclusively for radio status indicators: connected dot,
  transmitting state, PTT active, and received-message labels
- **Gradient panel headers** — each panel type has a typed gradient (NCS and
  Admin use a deeper blue; Config, Journals, and Attendance use base navy)
- **WCAG 2.2 AA compliant** — all colour pairs meet 4.5:1 contrast for normal
  text and 3:1 for large text and UI components

### Desktop layout

```
┌──────────────────────────── TopBar ─────────────────────────────┐
│ Callsign · Status · PTT · ABORT TX · Spectrogram · Account      │
├─────────────────────────────────────────────────────────────────┤
│              │                        │                          │
│  Panels      │    Chat Display        │   Side Panels            │
│  (draggable) │    (scrollable log)    │   (NCS / Journals /      │
│              │                        │    Attendance)           │
│              │                        │                          │
├──────────────┴────────────────────────┴──────────────────────────┤
│ StatusRow · ConfigPanel · PendingStationsBar · QuickMessages      │
└──────────────────────────────────────────────────────────────────┘
```

### Mobile layout

Sticky TopBar with hamburger menu → SwipeableDrawer for settings and account.
PTT and ABORT TX in the top bar. Chat display fills the viewport.
Bottom navigation bar for panel switching.

## How it works

```
Browser (any device)
      │  WebSocket :8765 (?token=…)
      ▼
FastAPI Backend  ──►  PulseAudio / sounddevice
      │                     │
   Piper TTS            Whisper STT / CW Decoder
      │                     │
   Serial PTT          Silero VAD
      ▼                     ▼
    Radio               Spectrogram
```

- **RX pipeline**: audio capture → VAD → squelch → segmentation → Whisper STT
  (or CW decoder) → callsign span detection → text broadcast to all clients
- **TX pipeline**: text input → abbreviation expansion → profanity filter →
  FCC ID wrapper → Piper TTS → PTT → audio output → `tx_echo` broadcast
- **Auth**: PBKDF2-hashed passwords, session tokens validated on WebSocket
  connect; unauthenticated connections are rejected

## FCC compliance

Radio-TTY is designed as a **remote control point** for a single local station,
not an internet repeater gateway or RoIP bridge. All transmissions originate
from the licensed station's transceiver under direct operator control. The system
automatically prepends and appends the station callsign per §95.1751.

Remote access over the internet is the operator's responsibility. Radio-TTY
provides no port-forwarding, relay, or TURN/STUN infrastructure — use a VPN or
private tunnel.

## Hardware requirements

| Component | Requirement |
|---|---|
| Server | x86 mini PC or NUC (e.g. Intel N100, N305); ARM not supported |
| RAM | 4 GB minimum, 8 GB recommended (Whisper STT is memory-intensive) |
| Audio | USB audio interface with radio speaker/mic connections |
| PTT | USB serial dongle (RTS or DTR pin) or VOX |
| OS | Ubuntu 22.04+ or Debian 12+ recommended; Docker required |
| Radio | Any GMRS transceiver with an external speaker/mic port |

## Quick start

```bash
# 1. Clone the repo
git clone https://github.com/Xpiatio/Radio-TTY
cd Radio-TTY

# 2. Run setup (creates .env and configures audio)
./setup.sh

# 3. Start the stack
docker compose up -d

# 4. Open in your browser
http://your-server-ip
```

On first launch the Setup screen appears — create the admin account and configure
your callsign, audio devices, and PTT interface.

## Development

```bash
# Backend (requires Python 3.11+)
pip install -r requirements.txt
uvicorn backend.main:app --reload

# Frontend
cd frontend
npm install
npm run dev        # dev server on :5173
npm run test       # run test suite
npm run build      # production build
```

## Plugin system

Plugins are React components that receive `PluginProps` (send, lastMessage,
contacts, channelClear, transmitting) and register themselves at module init:

```typescript
import { registerPlugin } from '../plugins';

registerPlugin({
  id: 'my-plugin',
  label: 'My Plugin',
  component: MyPluginComponent,
});
```

The app shell mounts registered plugins in the draggable panel area via
`PluginSlot`. Backend plugins extend `BasePlugin` and hook into the RX/TX
pipeline via `on_rx`, `on_tx`, and `on_ws_message`.

## License

MIT
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: expand README with UI overview, feature list, hardware table, dev guide"
```

---

## Task 10: Update USER_MANUAL.md

**File:** `USER_MANUAL.md`

- [ ] **Step 1: Read the current USER_MANUAL.md in full**

```bash
cat USER_MANUAL.md
```

Note the 23 existing sections. The update must:
- Keep all 23 sections and their numbering
- Update all interface descriptions to reflect the navy/blue UI
- Expand sections 2 and 2a with current layout detail
- Add new feature descriptions for: TokenPromptDialog, keyboard PTT (Space bar), audio pre-roll, priority mixer, dark/light mode toggle

- [ ] **Step 2: Update section 0 — Quick start**

Keep content. Add a note about the UI:

```markdown
> **UI note:** The interface uses a navy/blue design. Dark mode is enabled by
> default. Toggle between dark and light mode from Settings (hamburger menu on
> mobile, or the top-right account menu on desktop).
```

- [ ] **Step 3: Update section 2 — The interface**

Replace with:

```markdown
## 2. The interface

The Radio-TTY interface adapts to your screen size — desktop and mobile use
different layouts but share the same feature set.

### Desktop layout

The desktop shows all panels simultaneously:

```
┌──────────────────────────── TopBar ─────────────────────────────┐
│ [≡ panels]  Callsign ●  [PTT]  [ABORT TX]  [Spectrogram]  [👤] │
├───────────────┬──────────────────────────┬───────────────────────┤
│ Draggable     │  Chat Display            │  Side panels          │
│ panels        │  (scrollable RX/TX log)  │  NCS / Journals /     │
│               │                          │  Attendance           │
├───────────────┴──────────────────────────┴───────────────────────┤
│ Status · Config · Pending Stations · Quick Messages              │
└──────────────────────────────────────────────────────────────────┘
```

- **TopBar** — navy gradient bar. Shows your callsign, a green dot when
  connected, the PTT button, the ABORT TX button, the spectrogram toggle, and
  your account chip.
- **Chat Display** — scrollable log of all RX (received) and TX (sent)
  messages. Received messages appear with a green `[RX]` label; sent messages
  with a blue `[TX]` label.
- **Draggable panels** — NCS, Journals, Attendance, and any installed plugins.
  Drag the panel handle to reorder. Each panel has a coloured gradient header:
  NCS and Admin use a blue gradient; Config, Journals, and Attendance use a
  darker navy gradient.
- **StatusRow** — bottom bar showing radio status (READY / OFFLINE /
  TRANSMITTING), audio device, and connection count.

### Colour language

| Colour | Meaning |
|---|---|
| Green dot / indicator | Radio connected and ready |
| Green `[RX]` label | Incoming transmission |
| Blue button / highlight | Primary action (send, save, confirm) |
| Amber / warning | Degraded state (connection issues) |
| Red / error | Error or emergency state |
```

- [ ] **Step 4: Update section 2a — Mobile interface**

Replace with:

```markdown
## 2a. Mobile interface

On phones and narrow tablets Radio-TTY shows a single-column view:

```
┌────────────────── TopBar (sticky) ──────────────────┐
│ [≡]  Callsign ●        [PTT]  [ABORT TX]            │
└──────────────────────────────────────────────────────┘
│                                                      │
│              Chat Display (scrollable)               │
│                                                      │
└──────────────────────────────────────────────────────┘
┌────────── Bottom Navigation ─────────────────────────┐
│ Chat  │  NCS  │  Journals  │  Status  │  Settings    │
└──────────────────────────────────────────────────────┘
```

- Tap **[≡]** (top-left) to open the settings drawer: dark mode, listen-only,
  STT, read-aloud, notifications.
- The **PTT** button and **ABORT TX** button are always visible in the top bar.
- Bottom navigation switches between Chat, NCS, Journals, Status, and Settings
  views.
- The account menu is accessible from the settings drawer.
```

- [ ] **Step 5: Update section 19 — Voice PTT**

Replace with:

```markdown
## 19. Voice PTT (browser microphone)

The PTT button captures audio from your browser microphone and transmits it
over the radio using Piper TTS speech synthesis.

**To use Voice PTT:**

1. Click and hold the **PTT** button (top bar) — or press and hold the **Space
   bar** anywhere on the page.
2. Speak your message. A pre-roll buffer captures the first ~200 ms before you
   press, so the first syllable is never clipped.
3. Release the button or Space bar. The audio is sent to the server, synthesised
   to speech, and transmitted.

**Keyboard PTT:** The Space bar triggers PTT when focus is not inside a text
field. This lets you keep your hands on a keyboard during a net.

**Notes:**
- The PTT button shows **PTT●** (with a dot) while recording.
- The browser will ask for microphone permission on first use.
- If the channel is busy (another user is transmitting), PTT is disabled until
  the channel clears.
- Listen-only mode disables PTT entirely.
```

- [ ] **Step 6: Update section 13 — Settings**

Find the Settings section and add a dark/light mode entry:

```markdown
### Dark / Light mode

Toggle between dark mode (navy backgrounds, light text) and light mode
(navy-tinted light backgrounds, dark text) from:

- **Mobile:** Settings drawer (hamburger menu → Dark mode switch)
- **Desktop:** Account menu → dark mode toggle

The preference is saved per-user on the server and restored on next login.
```

- [ ] **Step 7: Update all remaining sections for accuracy**

Read through sections 3–18 and 20–23. For each section, check:
- Is the feature description still accurate?
- Does it reference any UI elements that have been renamed or moved?
- Does it mention any old colours (green for buttons — now blue for buttons)?

Update any outdated references. Common corrections:
- "green button" → "blue button" for primary actions
- "click the green ●" → use the current status indicator description
- Add any features that are present in code but missing from the manual
  (e.g., instant replay in NCS, audio pre-roll, priority mixer levels)

- [ ] **Step 8: Commit**

```bash
git add USER_MANUAL.md
git commit -m "docs: expand USER_MANUAL — navy/blue UI, keyboard PTT, audio pre-roll, dark mode"
```

---

## Task 11: Update docs/index.html

**File:** `docs/index.html`

- [ ] **Step 1: Read the current index.html**

```bash
wc -l docs/index.html && head -60 docs/index.html
```

Note the existing feature grid items, hero content, and install section.

- [ ] **Step 2: Update hero decorative chat preview colours**

Find the decorative chat preview inside the hero section. It uses inline styles or Tailwind classes for bubble colours. Update any green-primary bubbles to blue (`#2563eb` or `bg-blue-600`). The received-message bubble (`[RX]`) stays green — that is radio status.

- [ ] **Step 3: Update feature grid — add missing features**

The feature grid currently has 8 cards. Add cards for:

```html
<!-- Voice PTT keyboard support -->
<div class="feature-card">
  <div class="feature-icon" aria-hidden="true">⌨️</div>
  <h3>Keyboard PTT</h3>
  <p>Hold Space to transmit from any keyboard. Pre-roll buffer captures the
  first syllable before you press — never lose the start of your message.</p>
</div>

<!-- WCAG 2.2 AA badge -->
<div class="feature-card">
  <div class="feature-icon" aria-hidden="true">♿</div>
  <h3>WCAG 2.2 AA</h3>
  <p>Full keyboard navigation, screen reader support, and ARIA labelling
  throughout. Every interactive element meets WCAG 2.2 Level AA requirements.</p>
</div>

<!-- Audio pipeline -->
<div class="feature-card">
  <div class="feature-icon" aria-hidden="true">🎛️</div>
  <h3>Priority Audio Mixer</h3>
  <p>Six traffic priority levels — Routine through Emergency — with AGC and
  low-pass filtering. Higher-priority transmissions pre-empt lower ones.</p>
</div>
```

- [ ] **Step 4: Update install section hardware list**

Find the hardware requirements list. Ensure it matches README.md:
- x86 mini PC or NUC (Intel N100 / N305 recommended)
- 4 GB RAM minimum, 8 GB recommended
- USB audio interface
- USB serial PTT dongle (or VOX)
- Remove any Raspberry Pi references

- [ ] **Step 5: Cross-check all copy against README.md**

Read both files side by side. Ensure:
- Feature names match exactly (e.g., "Net Control Station" not "Network Control")
- Version-specific claims are consistent
- The install command block is identical

- [ ] **Step 6: Verify WCAG 2.2 AA compliance of changes**

For any new HTML added:
- All `<img>` have `alt` text (or `alt=""` if decorative)
- All interactive elements are keyboard reachable
- Colour contrast: white text on `#2563eb` (blue-600) is ~4.5:1 — passes AA
- New feature cards: verify they follow the same heading + paragraph pattern
  as existing cards

- [ ] **Step 7: Commit**

```bash
git add docs/index.html
git commit -m "docs(site): add keyboard PTT, WCAG badge, priority mixer cards; update hero and hardware list"
```

---

## Final Verification

- [ ] **Run full test suite one last time**

```bash
cd frontend && npm run test
```

Expected: all tests pass.

- [ ] **TypeScript check**

```bash
cd frontend && npx tsc --noEmit -p tsconfig.json
```

Expected: zero errors.

- [ ] **Final commit if any loose files**

```bash
git status
# If clean, done. If any unstaged changes, stage and commit.
```
