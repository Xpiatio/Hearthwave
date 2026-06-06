# WCAG 2.2 Level AA Transition — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Achieve full WCAG 2.2 Level AA compliance in the Radio-TTY React/MUI frontend by fixing five gaps and adding axe-core regression tests.

**Architecture:** Fix-then-test, component by component. Task 0 (jest-axe setup) is the only prerequisite; Tasks 1–3 (DraggablePanel stream), Tasks 4–5 (Snackbar stream), and Tasks 6–7 (TokenPromptDialog stream) can run in parallel after Task 0. Tasks 8–12 (axe assertions on existing components) are all independent and can also run in parallel after Task 0.

**Tech Stack:** React 18, TypeScript, MUI v9, @dnd-kit/core + @dnd-kit/sortable, Vitest + @testing-library/react, jest-axe

**Design spec:** `docs/superpowers/specs/2026-06-06-wcag22-design.md`

---

## Parallelism Map

```
Task 0: jest-axe setup  ──────────────────────────────────────┐
                                                               ▼
Stream A:  Task 1 (DraggablePanel.tsx) → Task 2 (DesktopApp wiring)
Stream B:  Task 4 (DesktopApp Snackbars) → Task 5 (MobileApp Snackbars + test)
Stream C:  Task 6 (TokenPromptDialog component) → Task 7 (App.tsx wiring + tests)
Stream D:  Tasks 8–12 (axe assertions — all independent)
Stream E:  Task 13 (theme comment — trivial, do with any stream)
                                                               ▼
Task 14: Full test run + commit
```

Streams A, B, C, D, E all start after Task 0 completes. Within each stream, tasks are sequential.

---

## Task 0: jest-axe Setup

**Files:**
- Modify: `frontend/package.json` (via npm install)
- Modify: `frontend/src/test/setup.ts`
- Modify: `frontend/vitest.config.ts`

- [ ] **Step 1: Install jest-axe**

```bash
cd /mnt/storage/Repos/Radio-TTY/frontend
npm install --save-dev jest-axe
```

Expected: jest-axe appears in `package.json` devDependencies. jest-axe v8+ ships its own TypeScript types — no `@types/jest-axe` needed.

- [ ] **Step 2: Register the matcher in setup.ts**

Current content of `frontend/src/test/setup.ts`:
```ts
import '@testing-library/jest-dom'
```

New content:
```ts
import '@testing-library/jest-dom'
import { toHaveNoViolations } from 'jest-axe'
expect.extend(toHaveNoViolations)
```

- [ ] **Step 3: Increase test timeout in vitest.config.ts**

Current `frontend/vitest.config.ts`:
```ts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/main.tsx', 'src/**/*.d.ts'],
    },
  },
})
```

New content (add `testTimeout`):
```ts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    testTimeout: 10000,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/main.tsx', 'src/**/*.d.ts'],
    },
  },
})
```

- [ ] **Step 4: Verify setup compiles**

```bash
cd /mnt/storage/Repos/Radio-TTY/frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/test/setup.ts frontend/vitest.config.ts
git commit -m "test: install jest-axe and register toHaveNoViolations matcher"
```

---

## Task 1: DraggablePanel — Add ▲/▼ Buttons + ARIA (Stream A)

**Files:**
- Modify: `frontend/src/components/DraggablePanel/DraggablePanel.tsx`

- [ ] **Step 1: Replace DraggablePanel.tsx**

Full new content of `frontend/src/components/DraggablePanel/DraggablePanel.tsx`:

```tsx
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Box, IconButton } from '@mui/material';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';

interface Props {
  id: string;
  children: React.ReactNode;
  onMoveUp?: () => void;
  onMoveDown?: () => void;
}

export function DraggablePanel({ id, children, onMoveUp, onMoveDown }: Props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const showButtons = onMoveUp !== undefined || onMoveDown !== undefined;

  return (
    <Box
      ref={setNodeRef}
      sx={{
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
        zIndex: isDragging ? 1000 : 'auto',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          py: 0.25,
          bgcolor: 'action.hover',
          borderBottom: 1,
          borderColor: 'divider',
          color: 'text.secondary',
          '&:hover': { bgcolor: 'action.selected' },
        }}
      >
        <Box
          {...attributes}
          {...listeners}
          role="button"
          aria-label={`Drag to reorder ${id} panel`}
          sx={{
            flex: 1,
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            py: 0.25,
            cursor: 'grab',
            '&:active': { cursor: 'grabbing' },
            touchAction: 'none',
            userSelect: 'none',
          }}
        >
          <DragIndicatorIcon fontSize="small" sx={{ transform: 'rotate(90deg)' }} />
        </Box>
        {showButtons && (
          <Box sx={{ display: 'flex', gap: 0.25, pr: 0.5 }}>
            <IconButton
              size="small"
              onClick={onMoveUp}
              disabled={onMoveUp === undefined}
              aria-label={`Move ${id} panel up`}
            >
              <KeyboardArrowUpIcon fontSize="small" />
            </IconButton>
            <IconButton
              size="small"
              onClick={onMoveDown}
              disabled={onMoveDown === undefined}
              aria-label={`Move ${id} panel down`}
            >
              <KeyboardArrowDownIcon fontSize="small" />
            </IconButton>
          </Box>
        )}
      </Box>
      {children}
    </Box>
  );
}
```

- [ ] **Step 2: Run existing DraggablePanel tests**

```bash
cd /mnt/storage/Repos/Radio-TTY/frontend
npx vitest run src/components/DraggablePanel
```

Expected: all existing tests pass (no regressions).

- [ ] **Step 3: Add axe assertion to DraggablePanel.test.tsx**

Open `frontend/src/components/DraggablePanel/__tests__/DraggablePanel.test.tsx`.

Add these imports at the top (after existing imports):
```ts
import { axe } from 'jest-axe'
```

Add these tests inside the existing `describe('DraggablePanel', () => {` block, after the last existing test:

```ts
  describe('accessibility', () => {
    it('has no violations when used standalone (no buttons)', async () => {
      const { container } = render(
        <DraggablePanel id="test">
          <div>content</div>
        </DraggablePanel>
      )
      expect(await axe(container)).toHaveNoViolations()
    })

    it('has no violations mid-list (both buttons enabled)', async () => {
      const { container } = render(
        <DraggablePanel id="config" onMoveUp={vi.fn()} onMoveDown={vi.fn()}>
          <div>content</div>
        </DraggablePanel>
      )
      expect(await axe(container)).toHaveNoViolations()
    })

    it('has no violations at top of list (up button disabled)', async () => {
      const { container } = render(
        <DraggablePanel id="config" onMoveDown={vi.fn()}>
          <div>content</div>
        </DraggablePanel>
      )
      expect(await axe(container)).toHaveNoViolations()
    })

    it('has no violations at bottom of list (down button disabled)', async () => {
      const { container } = render(
        <DraggablePanel id="config" onMoveUp={vi.fn()}>
          <div>content</div>
        </DraggablePanel>
      )
      expect(await axe(container)).toHaveNoViolations()
    })
  })
```

- [ ] **Step 4: Run DraggablePanel tests (including new axe tests)**

```bash
cd /mnt/storage/Repos/Radio-TTY/frontend
npx vitest run src/components/DraggablePanel
```

Expected: all tests pass including the four new axe assertions.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/DraggablePanel/DraggablePanel.tsx \
        frontend/src/components/DraggablePanel/__tests__/DraggablePanel.test.tsx
git commit -m "feat(a11y): add keyboard reorder buttons and ARIA to DraggablePanel (WCAG 2.5.7)"
```

---

## Task 2: DesktopApp — KeyboardSensor + handlePanelMove Wiring (Stream A)

**Files:**
- Modify: `frontend/src/components/DesktopApp/DesktopApp.tsx`
- Modify: `frontend/src/App.tsx`

### DesktopApp.tsx changes

- [ ] **Step 1: Update @dnd-kit imports in DesktopApp.tsx**

Current line 2–3 in `DesktopApp.tsx`:
```ts
import { DndContext } from '@dnd-kit/core';
import type { DragEndEvent } from '@dnd-kit/core';
```

Replace with:
```ts
import { DndContext, useSensors, useSensor, PointerSensor, KeyboardSensor } from '@dnd-kit/core';
import type { DragEndEvent } from '@dnd-kit/core';
```

Current line 4:
```ts
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
```

Replace with:
```ts
import { SortableContext, verticalListSortingStrategy, sortableKeyboardCoordinates } from '@dnd-kit/sortable';
```

- [ ] **Step 2: Add onPanelMove to DesktopAppProps**

In `DesktopApp.tsx`, find the `DesktopAppProps` interface. It currently has:
```ts
  onPanelDragEnd: (event: DragEndEvent) => void;
```

Add `onPanelMove` right after it:
```ts
  onPanelDragEnd: (event: DragEndEvent) => void;
  onPanelMove: (fromIndex: number, toIndex: number) => void;
```

- [ ] **Step 3: Destructure onPanelMove in the component function**

Find the destructuring of `onPanelDragEnd` in the component function parameters (around line 290). Add `onPanelMove` next to it:
```ts
  onPanelDragEnd,
  onPanelMove,
```

- [ ] **Step 4: Add sensors inside the DesktopApp component**

The component body currently starts with `const messageInputRef = useRef<...>`. Add the sensors setup immediately after it:

```ts
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
```

- [ ] **Step 5: Wire sensors to DndContext**

Find:
```tsx
      <DndContext onDragEnd={onPanelDragEnd}>
```

Replace with:
```tsx
      <DndContext sensors={sensors} onDragEnd={onPanelDragEnd}>
```

- [ ] **Step 6: Add index to panelOrder.map and wire onMoveUp/onMoveDown**

Find:
```tsx
          {panelOrder.map((id) => {
```

Replace with:
```tsx
          {panelOrder.map((id, index) => {
```

Then find every `<DraggablePanel key="config" id="config">` (and attendance, journal, ncs). Replace all four with the pattern below. Each one gets `onMoveUp` and `onMoveDown`:

```tsx
            if (id === 'config' && showConfig) {
              return (
                <DraggablePanel
                  key="config"
                  id="config"
                  onMoveUp={index > 0 ? () => onPanelMove(index, index - 1) : undefined}
                  onMoveDown={index < panelOrder.length - 1 ? () => onPanelMove(index, index + 1) : undefined}
                >
                  <ConfigPanel
                    filterProfanity={filterProfanity}
                    fuzzyCallsign={fuzzyCallsign}
                    inputDevice={inputDevice}
                    systemMonitorSink={systemMonitorSink}
                    inputDevices={inputDevices}
                    monitorSinks={monitorSinks}
                    spectroColormap={spectroColormap}
                    spectroFreqRange={spectroFreqRange}
                    spectroTimeWindowS={spectroTimeWindowS}
                    onToggleProfanity={onToggleProfanity}
                    onToggleFuzzy={onToggleFuzzy}
                    onInputDeviceChange={onInputDeviceChange}
                    onSpectroColormapChange={onSpectroColormapChange}
                    onSpectroFreqRangeChange={onSpectroFreqRangeChange}
                    onSpectroTimeWindowChange={onSpectroTimeWindowChange}
                  />
                </DraggablePanel>
              );
            }
            if (id === 'attendance' && showAttendance) {
              return (
                <DraggablePanel
                  key="attendance"
                  id="attendance"
                  onMoveUp={index > 0 ? () => onPanelMove(index, index - 1) : undefined}
                  onMoveDown={index < panelOrder.length - 1 ? () => onPanelMove(index, index + 1) : undefined}
                >
                  <AttendancePanel
                    stations={attendanceStations}
                    onClear={onClearAttendance}
                  />
                </DraggablePanel>
              );
            }
            if (id === 'journal' && showJournal) {
              return (
                <DraggablePanel
                  key="journal"
                  id="journal"
                  onMoveUp={index > 0 ? () => onPanelMove(index, index - 1) : undefined}
                  onMoveDown={index < panelOrder.length - 1 ? () => onPanelMove(index, index + 1) : undefined}
                >
                  <JournalPanel
                    journals={journals}
                    pendingResult={journalResult}
                    generating={journalGenerating}
                    journalError={journalError}
                    rxTexts={rxTexts}
                    rxCallsigns={rxCallsigns}
                    onListJournals={onListJournals}
                    onGenerate={onGenerate}
                    onSave={onSaveJournal}
                    onDelete={onDeleteJournal}
                    onPublish={onPublishJournal}
                    onUnpublish={onUnpublishJournal}
                    onDismissResult={onDismissJournalResult}
                  />
                </DraggablePanel>
              );
            }
            if (id === 'ncs' && showNcs) {
              return (
                <DraggablePanel
                  key="ncs"
                  id="ncs"
                  onMoveUp={index > 0 ? () => onPanelMove(index, index - 1) : undefined}
                  onMoveDown={index < panelOrder.length - 1 ? () => onPanelMove(index, index + 1) : undefined}
                >
                  <NCSPanel
                    send={send}
                    lastMessage={lastMessage}
                    contacts={contacts}
                    channelClear={channelClear}
                    transmitting={transmitting}
                  />
                </DraggablePanel>
              );
            }
```

### App.tsx changes

- [ ] **Step 7: Add handlePanelMove to App.tsx**

In `App.tsx`, find `handlePanelDragEnd`:
```ts
  function handlePanelDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      setPanelOrder((prev) => {
        const oldIndex = prev.indexOf(String(active.id));
        const newIndex = prev.indexOf(String(over.id));
        const next = arrayMove(prev, oldIndex, newIndex);
        localStorage.setItem('radio_tty_panel_order', JSON.stringify(next));
        send({ type: 'save_user_prefs', prefs: { panel_order: next } });
        return next;
      });
    }
  }
```

Add `handlePanelMove` immediately after it:
```ts
  function handlePanelMove(fromIndex: number, toIndex: number) {
    setPanelOrder((prev) => {
      const next = arrayMove(prev, fromIndex, toIndex);
      localStorage.setItem('radio_tty_panel_order', JSON.stringify(next));
      send({ type: 'save_user_prefs', prefs: { panel_order: next } });
      return next;
    });
  }
```

- [ ] **Step 8: Pass onPanelMove to DesktopApp in App.tsx**

Find the `<DesktopApp` render call near the bottom of App.tsx. It already has `onPanelDragEnd={handlePanelDragEnd}`. Add `onPanelMove` next to it:
```tsx
          onPanelDragEnd={handlePanelDragEnd}
          onPanelMove={handlePanelMove}
```

- [ ] **Step 9: Type-check**

```bash
cd /mnt/storage/Repos/Radio-TTY/frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/components/DesktopApp/DesktopApp.tsx frontend/src/App.tsx
git commit -m "feat(a11y): wire KeyboardSensor and panel move buttons in DesktopApp"
```

---

## Task 4: DesktopApp Snackbars — aria-live (Stream B)

**Files:**
- Modify: `frontend/src/components/DesktopApp/DesktopApp.tsx`

- [ ] **Step 1: Add aria-live to DesktopApp Snackbar Alerts**

In `frontend/src/components/DesktopApp/DesktopApp.tsx`, find the two Snackbar blocks near the bottom. They currently look like:

```tsx
      <Snackbar
        open={publishSnack !== null}
        autoHideDuration={5000}
        onClose={onClosePublishSnack}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={onClosePublishSnack} severity="success" sx={{ width: '100%' }}>
          {publishSnack}
        </Alert>
      </Snackbar>

      <Snackbar
        open={errorSnack !== null}
        autoHideDuration={7000}
        onClose={onCloseErrorSnack}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={onCloseErrorSnack} severity="error" sx={{ width: '100%' }}>
          {errorSnack}
        </Alert>
      </Snackbar>
```

Replace with:

```tsx
      <Snackbar
        open={publishSnack !== null}
        autoHideDuration={5000}
        onClose={onClosePublishSnack}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          onClose={onClosePublishSnack}
          severity="success"
          aria-live="polite"
          aria-atomic="true"
          sx={{ width: '100%' }}
        >
          {publishSnack}
        </Alert>
      </Snackbar>

      <Snackbar
        open={errorSnack !== null}
        autoHideDuration={7000}
        onClose={onCloseErrorSnack}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          onClose={onCloseErrorSnack}
          severity="error"
          aria-live="assertive"
          aria-atomic="true"
          sx={{ width: '100%' }}
        >
          {errorSnack}
        </Alert>
      </Snackbar>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/DesktopApp/DesktopApp.tsx
git commit -m "fix(a11y): add aria-live to DesktopApp Snackbar Alerts (WCAG 4.1.3)"
```

---

## Task 5: MobileApp Snackbars + Snackbar a11y Test (Stream B)

**Files:**
- Modify: `frontend/src/components/MobileApp/MobileApp.tsx`
- Create: `frontend/src/components/DesktopApp/__tests__/Snackbar.a11y.test.tsx`

### MobileApp.tsx

- [ ] **Step 1: Find the Snackbar blocks in MobileApp.tsx**

```bash
grep -n "Snackbar\|Alert" /mnt/storage/Repos/Radio-TTY/frontend/src/components/MobileApp/MobileApp.tsx
```

Read the lines identified and confirm the same two-Snackbar pattern (success publish, error). They will be near lines 406–426 by analogy with DesktopApp.

- [ ] **Step 2: Add the same aria-live attributes to MobileApp Snackbar Alerts**

Apply the identical change as Task 4 Step 1:
- Success Alert: add `aria-live="polite"` `aria-atomic="true"`
- Error Alert: add `aria-live="assertive"` `aria-atomic="true"`

- [ ] **Step 3: Create Snackbar a11y test**

Create `frontend/src/components/DesktopApp/__tests__/Snackbar.a11y.test.tsx`:

```tsx
import { render as rtlRender } from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { Snackbar, Alert } from '@mui/material'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi } from 'vitest'
import { axe } from 'jest-axe'

function render(ui: React.ReactElement) {
  return rtlRender(
    <ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>
  )
}

describe('Snackbar accessibility', () => {
  it('success Snackbar has no violations', async () => {
    const { container } = render(
      <Snackbar open anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
        <Alert
          onClose={vi.fn()}
          severity="success"
          aria-live="polite"
          aria-atomic="true"
          sx={{ width: '100%' }}
        >
          Journal published
        </Alert>
      </Snackbar>
    )
    expect(await axe(container)).toHaveNoViolations()
  })

  it('error Snackbar has no violations', async () => {
    const { container } = render(
      <Snackbar open anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
        <Alert
          onClose={vi.fn()}
          severity="error"
          aria-live="assertive"
          aria-atomic="true"
          sx={{ width: '100%' }}
        >
          Something went wrong
        </Alert>
      </Snackbar>
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
```

- [ ] **Step 4: Run the new Snackbar test**

```bash
cd /mnt/storage/Repos/Radio-TTY/frontend
npx vitest run src/components/DesktopApp/__tests__/Snackbar.a11y.test.tsx
```

Expected: both tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/MobileApp/MobileApp.tsx \
        frontend/src/components/DesktopApp/__tests__/Snackbar.a11y.test.tsx
git commit -m "fix(a11y): add aria-live to MobileApp Snackbars and add Snackbar a11y tests (WCAG 4.1.3)"
```

---

## Task 6: TokenPromptDialog Component (Stream C)

**Files:**
- Create: `frontend/src/components/TokenPromptDialog/TokenPromptDialog.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/TokenPromptDialog/TokenPromptDialog.tsx`:

```tsx
import { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Box,
} from '@mui/material';

interface Props {
  open: boolean;
  tokens: string[];
  originalText: string;
  onSubmit: (resolvedText: string) => void;
  onCancel: () => void;
}

export function TokenPromptDialog({ open, tokens, originalText, onSubmit, onCancel }: Props) {
  const [values, setValues] = useState<Record<string, string>>({});

  const allFilled = tokens.every((t) => (values[t] ?? '').trim().length > 0);

  function handleSubmit() {
    if (!allFilled) return;
    let resolved = originalText;
    for (const token of tokens) {
      resolved = resolved.replaceAll(`{${token}}`, values[token] ?? '');
    }
    onSubmit(resolved);
    setValues({});
  }

  function handleKeyDown(e: React.KeyboardEvent, isLast: boolean) {
    if (isLast && e.key === 'Enter' && allFilled) {
      e.preventDefault();
      handleSubmit();
    }
  }

  function handleCancel() {
    setValues({});
    onCancel();
  }

  return (
    <Dialog open={open} onClose={handleCancel} aria-labelledby="token-prompt-title" maxWidth="xs" fullWidth>
      <DialogTitle id="token-prompt-title">Fill in message placeholders</DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          {tokens.map((token, i) => (
            <TextField
              key={token}
              label={`Value for {${token}}`}
              value={values[token] ?? ''}
              onChange={(e) => setValues((prev) => ({ ...prev, [token]: e.target.value }))}
              onKeyDown={(e) => handleKeyDown(e, i === tokens.length - 1)}
              autoFocus={i === 0}
              fullWidth
            />
          ))}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleCancel}>Cancel</Button>
        <Button variant="contained" onClick={handleSubmit} disabled={!allFilled}>
          Send
        </Button>
      </DialogActions>
    </Dialog>
  );
}
```

- [ ] **Step 2: Type-check**

```bash
cd /mnt/storage/Repos/Radio-TTY/frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/TokenPromptDialog/TokenPromptDialog.tsx
git commit -m "feat(a11y): add TokenPromptDialog to replace window.prompt() (WCAG 4.1.3)"
```

---

## Task 7: App.tsx Wiring + TokenPromptDialog Tests (Stream C)

**Files:**
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/components/TokenPromptDialog/__tests__/TokenPromptDialog.test.tsx`

### App.tsx wiring

- [ ] **Step 1: Add PromptState type to appTypes.ts**

Open `frontend/src/types/appTypes.ts`. Add to the bottom:

```ts
export interface PromptState {
  tokens: string[];
  originalText: string;
  operator: string;
  callsign: string;
  targetCall: string;
  targetName: string;
}
```

- [ ] **Step 2: Import TokenPromptDialog and PromptState in App.tsx**

At the top of `App.tsx`, add imports:

```ts
import { TokenPromptDialog } from './components/TokenPromptDialog/TokenPromptDialog';
import type { PromptState } from './types/appTypes';
```

(The existing `import type { JournalResultDraft, PendingStation } from './types/appTypes'` line should be updated to include `PromptState`.)

- [ ] **Step 3: Add promptState to App state**

In App.tsx, find where other dialog state is declared (e.g. `fccLookupResult`, `verifyAllComplete`). Add:

```ts
  const [promptState, setPromptState] = useState<PromptState | null>(null);
```

- [ ] **Step 4: Replace the prompt_token case**

Find this block in the `handleWsMessage` switch (around line 396–416):

```ts
      case 'prompt_token': {
        const tokens = msg.tokens;
        let resolvedText = msg.original_text;
        let cancelled = false;
        for (const token of tokens) {
          const val = window.prompt(`Enter value for {${token}}:`);
          if (val === null) { cancelled = true; break; }
          resolvedText = resolvedText.replaceAll(`{${token}}`, val);
        }
        if (!cancelled) {
          sendRef.current({
            type: 'tx_message',
            text: resolvedText,
            operator: msg.operator,
            callsign: msg.callsign,
            target_call: msg.target_call,
            target_name: msg.target_name,
          });
        }
        break;
      }
```

Replace with:

```ts
      case 'prompt_token':
        setPromptState({
          tokens: msg.tokens,
          originalText: msg.original_text,
          operator: msg.operator,
          callsign: msg.callsign,
          targetCall: msg.target_call,
          targetName: msg.target_name,
        });
        break;
```

- [ ] **Step 5: Add handleTokenSubmit and handleTokenCancel**

Near the other handler functions in App.tsx (e.g. after `handleVerifyAllDismiss`), add:

```ts
  function handleTokenSubmit(resolvedText: string) {
    if (!promptState) return;
    send({
      type: 'tx_message',
      text: resolvedText,
      operator: promptState.operator,
      callsign: promptState.callsign,
      target_call: promptState.targetCall,
      target_name: promptState.targetName,
    });
    setPromptState(null);
  }

  function handleTokenCancel() {
    setPromptState(null);
  }
```

- [ ] **Step 6: Render TokenPromptDialog in the JSX**

In the `return (...)` of App.tsx, inside the `<ThemeProvider>` after `<CssBaseline />` and before `{isMobile ? ...}`, add:

```tsx
      <TokenPromptDialog
        open={promptState !== null}
        tokens={promptState?.tokens ?? []}
        originalText={promptState?.originalText ?? ''}
        onSubmit={handleTokenSubmit}
        onCancel={handleTokenCancel}
      />
```

- [ ] **Step 7: Type-check**

```bash
cd /mnt/storage/Repos/Radio-TTY/frontend
npx tsc --noEmit
```

Expected: no errors.

### TokenPromptDialog tests

- [ ] **Step 8: Create the test file**

Create `frontend/src/components/TokenPromptDialog/__tests__/TokenPromptDialog.test.tsx`:

```tsx
import { render as rtlRender, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi } from 'vitest'
import { axe } from 'jest-axe'
import { TokenPromptDialog } from '../TokenPromptDialog'

function render(ui: React.ReactElement) {
  return rtlRender(
    <ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>
  )
}

describe('TokenPromptDialog', () => {
  describe('accessibility', () => {
    it('has no violations when open with two tokens', async () => {
      const { container } = render(
        <TokenPromptDialog
          open
          tokens={['name', 'location']}
          originalText="Hello {name} from {location}"
          onSubmit={vi.fn()}
          onCancel={vi.fn()}
        />
      )
      expect(await axe(container)).toHaveNoViolations()
    })
  })

  describe('rendering', () => {
    it('renders a field per token', () => {
      render(
        <TokenPromptDialog
          open
          tokens={['name', 'city']}
          originalText="{name} in {city}"
          onSubmit={vi.fn()}
          onCancel={vi.fn()}
        />
      )
      expect(screen.getByLabelText(/value for \{name\}/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/value for \{city\}/i)).toBeInTheDocument()
    })

    it('Send button is disabled when fields are empty', () => {
      render(
        <TokenPromptDialog
          open
          tokens={['name']}
          originalText="{name}"
          onSubmit={vi.fn()}
          onCancel={vi.fn()}
        />
      )
      expect(screen.getByRole('button', { name: /send/i })).toBeDisabled()
    })

    it('Send button is enabled when all fields are filled', async () => {
      render(
        <TokenPromptDialog
          open
          tokens={['name']}
          originalText="{name}"
          onSubmit={vi.fn()}
          onCancel={vi.fn()}
        />
      )
      await userEvent.type(screen.getByLabelText(/value for \{name\}/i), 'Alice')
      expect(screen.getByRole('button', { name: /send/i })).not.toBeDisabled()
    })
  })

  describe('submission', () => {
    it('calls onSubmit with resolved text when Send is clicked', async () => {
      const onSubmit = vi.fn()
      render(
        <TokenPromptDialog
          open
          tokens={['name', 'location']}
          originalText="Hello {name} from {location}"
          onSubmit={onSubmit}
          onCancel={vi.fn()}
        />
      )
      await userEvent.type(screen.getByLabelText(/value for \{name\}/i), 'Alice')
      await userEvent.type(screen.getByLabelText(/value for \{location\}/i), 'Grand Rapids')
      await userEvent.click(screen.getByRole('button', { name: /send/i }))
      await waitFor(() =>
        expect(onSubmit).toHaveBeenCalledWith('Hello Alice from Grand Rapids')
      )
    })

    it('calls onCancel when Cancel is clicked', async () => {
      const onCancel = vi.fn()
      render(
        <TokenPromptDialog
          open
          tokens={['x']}
          originalText="{x}"
          onSubmit={vi.fn()}
          onCancel={onCancel}
        />
      )
      await userEvent.click(screen.getByRole('button', { name: /cancel/i }))
      expect(onCancel).toHaveBeenCalled()
    })
  })
})
```

- [ ] **Step 9: Run the tests**

```bash
cd /mnt/storage/Repos/Radio-TTY/frontend
npx vitest run src/components/TokenPromptDialog
```

Expected: all tests pass.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/App.tsx \
        frontend/src/types/appTypes.ts \
        frontend/src/components/TokenPromptDialog/__tests__/TokenPromptDialog.test.tsx
git commit -m "feat(a11y): wire TokenPromptDialog in App.tsx, replacing window.prompt()"
```

---

## Task 8: Axe Assertion — LoginScreen (Stream D)

**Files:**
- Modify: `frontend/src/components/LoginScreen/__tests__/LoginScreen.test.tsx`

- [ ] **Step 1: Add jest-axe import**

At the top of `LoginScreen.test.tsx`, add:
```ts
import { axe } from 'jest-axe'
```

- [ ] **Step 2: Add axe test**

Inside the `describe('LoginScreen', () => {` block, after all existing describes, add:

```ts
  describe('accessibility', () => {
    it('has no violations in idle state', async () => {
      const { container } = render(<LoginScreen onLogin={vi.fn()} />)
      expect(await axe(container)).toHaveNoViolations()
    })
  })
```

- [ ] **Step 3: Run**

```bash
cd /mnt/storage/Repos/Radio-TTY/frontend
npx vitest run src/components/LoginScreen
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/LoginScreen/__tests__/LoginScreen.test.tsx
git commit -m "test(a11y): add axe assertion to LoginScreen tests"
```

---

## Task 9: Axe Assertion — SetupScreen (Stream D)

**Files:**
- Modify: `frontend/src/components/SetupScreen/__tests__/SetupScreen.test.tsx`

- [ ] **Step 1: Add jest-axe import**

```ts
import { axe } from 'jest-axe'
```

- [ ] **Step 2: Add axe test**

Inside the existing `describe('SetupScreen', () => {` block, add:

```ts
  describe('accessibility', () => {
    it('has no violations in idle state', async () => {
      const { container } = render(<SetupScreen onSetup={vi.fn()} />)
      expect(await axe(container)).toHaveNoViolations()
    })
  })
```

- [ ] **Step 3: Run**

```bash
cd /mnt/storage/Repos/Radio-TTY/frontend
npx vitest run src/components/SetupScreen
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/SetupScreen/__tests__/SetupScreen.test.tsx
git commit -m "test(a11y): add axe assertion to SetupScreen tests"
```

---

## Task 10: Axe Assertion — MessageInput (Stream D)

**Files:**
- Modify: `frontend/src/components/MessageInput/__tests__/MessageInput.test.tsx`

- [ ] **Step 1: Add jest-axe import**

```ts
import { axe } from 'jest-axe'
```

- [ ] **Step 2: Add axe test**

The test already has a `CONTACTS` array defined. Add to the existing `describe('MessageInput', () => {` block:

```ts
  describe('accessibility', () => {
    it('has no violations with contacts list', async () => {
      const { container } = render(
        <MessageInput
          transmitting={false}
          contacts={CONTACTS}
          onSend={vi.fn()}
        />
      )
      expect(await axe(container)).toHaveNoViolations()
    })
  })
```

- [ ] **Step 3: Run**

```bash
cd /mnt/storage/Repos/Radio-TTY/frontend
npx vitest run src/components/MessageInput
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/MessageInput/__tests__/MessageInput.test.tsx
git commit -m "test(a11y): add axe assertion to MessageInput tests"
```

---

## Task 11: Axe Assertion — TopBar (Stream D)

**Files:**
- Modify: `frontend/src/components/TopBar/__tests__/TopBar.test.tsx`

- [ ] **Step 1: Add jest-axe import**

```ts
import { axe } from 'jest-axe'
```

- [ ] **Step 2: Add axe test**

The test already has `makeProps()`. Add after the existing describes:

```ts
  describe('accessibility', () => {
    it('has no violations in connected state', async () => {
      const { container } = render(<TopBar {...makeProps()} />)
      expect(await axe(container)).toHaveNoViolations()
    })
  })
```

- [ ] **Step 3: Run**

```bash
cd /mnt/storage/Repos/Radio-TTY/frontend
npx vitest run src/components/TopBar
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/TopBar/__tests__/TopBar.test.tsx
git commit -m "test(a11y): add axe assertion to TopBar tests"
```

---

## Task 12: Axe Assertion — ChatDisplay (Stream D)

**Files:**
- Modify: `frontend/src/components/ChatDisplay/__tests__/ChatDisplay.test.tsx`

- [ ] **Step 1: Add jest-axe import**

```ts
import { axe } from 'jest-axe'
```

- [ ] **Step 2: Add axe test**

The test already has `makeEntry()` and `NO_CONTACTS`. Add a new describe block:

```ts
describe('ChatDisplay — accessibility', () => {
  it('has no violations with mixed message types', async () => {
    const entries: ChatEntry[] = [
      makeEntry({ id: 'a1', kind: 'rx', text: 'Received message', sender: 'W1AAA' }),
      makeEntry({ id: 'a2', kind: 'tx', text: 'Sent message', sender: 'W2BBB' }),
      makeEntry({ id: 'a3', kind: 'system', text: 'System notification' }),
    ]
    const { container } = render(
      <ChatDisplay entries={entries} contacts={NO_CONTACTS} showCallsignChips={false} />
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
```

- [ ] **Step 3: Run**

```bash
cd /mnt/storage/Repos/Radio-TTY/frontend
npx vitest run src/components/ChatDisplay
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ChatDisplay/__tests__/ChatDisplay.test.tsx
git commit -m "test(a11y): add axe assertion to ChatDisplay tests"
```

---

## Task 13: Theme Comment + Full Test Run

**Files:**
- Modify: `frontend/src/theme.ts`

- [ ] **Step 1: Update the WCAG version comment in theme.ts**

In `frontend/src/theme.ts`, line 3 currently reads:
```ts
// WCAG 2.1 AA color palettes from GMRS-TTY constants
```

Change to:
```ts
// WCAG 2.2 AA color palettes from GMRS-TTY constants
```

- [ ] **Step 2: Run the full test suite**

```bash
cd /mnt/storage/Repos/Radio-TTY/frontend
npx vitest run
```

Expected: all tests pass. No regressions.

- [ ] **Step 3: Type-check the full project**

```bash
cd /mnt/storage/Repos/Radio-TTY/frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Final commit**

```bash
git add frontend/src/theme.ts
git commit -m "chore(a11y): update theme comment to reflect WCAG 2.2 AA compliance"
```

---

## Self-Review Checklist

- [x] **2.5.7 Dragging** — Task 1 adds ▲/▼ buttons; Task 2 adds KeyboardSensor
- [x] **4.1.3 Snackbars** — Tasks 4+5 add aria-live/aria-atomic to both DesktopApp and MobileApp
- [x] **window.prompt()** — Task 6+7 replaces with TokenPromptDialog
- [x] **jest-axe setup** — Task 0 installs and configures
- [x] **Axe assertions** — Tasks 1 (DraggablePanel), 5 (Snackbars), 7 (TokenPromptDialog), 8–12 (existing components)
- [x] **Theme comment** — Task 13
- [x] **Type names consistent** — `PromptState` defined in appTypes.ts (Task 7 Step 1), imported in App.tsx (Task 7 Step 2), matches fields used in handler (Task 7 Steps 4–5)
- [x] **handlePanelMove** defined in App.tsx (Task 2 Step 7), passed as `onPanelMove` to DesktopApp (Task 2 Step 8), destructured in DesktopApp (Task 2 Step 3)
