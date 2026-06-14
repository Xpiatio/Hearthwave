# Hearthwave Logo, About Page & Version Display — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Hearthwave logo to the login and in-app UI, an About dialog reachable from three entry points, and a single-sourced version number surfaced via the backend `/health` endpoint.

**Architecture:** A single inline-SVG `Logo` React component is the source of truth for the mark (theme-aware strokes, fixed amber hearth glow). The backend exposes `__version__` through `/health`; a small `useVersion()` hook reads it. A reusable `AboutDialog` (using `Logo` + `useVersion`) is mounted self-contained at each of the three entry points (login screen, account menu, topbar logo), each owning its own open/close state — no prop threading through the large `App.tsx` props object.

**Tech Stack:** React + TypeScript + MUI (frontend, Vite, Vitest + Testing Library); Python + Starlette/FastAPI (backend, pytest + Starlette TestClient).

---

## File Structure

**Backend**
- Modify: `backend/__init__.py` — add `__version__`.
- Modify: `backend/server.py:1354-1356` — `/health` returns the version.
- Test: `backend/tests/integration/test_server_ws.py` — add `/health` version assertion (reuses existing `client` fixture).

**Frontend**
- Create: `frontend/src/components/Logo/Logo.tsx` — the SVG mark + optional wordmark.
- Test: `frontend/src/components/Logo/__tests__/Logo.test.tsx`
- Create: `frontend/src/hooks/useVersion.ts` — fetches `/health`, returns version string.
- Test: `frontend/src/hooks/__tests__/useVersion.test.ts`
- Create: `frontend/src/components/AboutDialog/AboutDialog.tsx` — the About dialog.
- Test: `frontend/src/components/AboutDialog/__tests__/AboutDialog.test.tsx`
- Modify: `frontend/src/components/LoginScreen/LoginScreen.tsx` — logo lockup + About/version footer.
- Test: `frontend/src/components/LoginScreen/__tests__/LoginScreen.test.tsx` (new)
- Modify: `frontend/src/components/AccountMenu/AccountMenu.tsx` — "About Hearthwave" menu item.
- Test: `frontend/src/components/AccountMenu/__tests__/AccountMenu.test.tsx` (new)
- Modify: `frontend/src/components/TopBar/TopBar.tsx` — clickable logo opens About.
- Create: `frontend/public/favicon.svg`
- Modify: `frontend/index.html` — favicon link.
- Modify: `frontend/Dockerfile` — copy `public/` before build.

**Repo housekeeping**
- Modify: `.gitignore` — ignore `.superpowers/`.

---

## Task 1: Backend version constant + `/health` exposes it

**Files:**
- Modify: `backend/__init__.py`
- Modify: `backend/server.py:1354-1356`
- Test: `backend/tests/integration/test_server_ws.py`

- [ ] **Step 1: Write the failing test**

Add this test function to `backend/tests/integration/test_server_ws.py` (anywhere after the `client` fixture, e.g. near the end of the file):

```python
def test_health_reports_version(client):
    """/health returns ok plus the backend package version."""
    import backend

    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["version"] == backend.__version__
    assert isinstance(backend.__version__, str) and body["version"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/integration/test_server_ws.py::test_health_reports_version -v`
Expected: FAIL — `AttributeError: module 'backend' has no attribute '__version__'` (and/or KeyError on `version`).

- [ ] **Step 3: Add the version constant**

Set the entire contents of `backend/__init__.py` to:

```python
"""Hearthwave backend package."""

__version__ = "2.5.2"
```

- [ ] **Step 4: Surface it from `/health`**

In `backend/server.py`, replace the health handler at lines 1354-1356:

```python
@app.get("/health")
async def health() -> dict:
    return {"ok": True}
```

with:

```python
@app.get("/health")
async def health() -> dict:
    from backend import __version__
    return {"ok": True, "version": __version__}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/integration/test_server_ws.py::test_health_reports_version -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/__init__.py backend/server.py backend/tests/integration/test_server_ws.py
git commit -m "feat(backend): expose package version via /health"
```

---

## Task 2: `Logo` component

**Files:**
- Create: `frontend/src/components/Logo/Logo.tsx`
- Test: `frontend/src/components/Logo/__tests__/Logo.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/Logo/__tests__/Logo.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { describe, it, expect } from 'vitest'
import { makeTheme } from '../../../theme'
import { Logo } from '../Logo'

function renderLogo(ui: React.ReactElement) {
  return render(<ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>)
}

describe('Logo', () => {
  it('renders the mark with an accessible label', () => {
    renderLogo(<Logo />)
    expect(screen.getByRole('img', { name: /hearthwave logo/i })).toBeInTheDocument()
  })

  it('shows the wordmark when withWordmark is set', () => {
    renderLogo(<Logo withWordmark />)
    expect(screen.getByText('Hearthwave')).toBeInTheDocument()
  })

  it('omits the wordmark by default', () => {
    renderLogo(<Logo />)
    expect(screen.queryByText('Hearthwave')).not.toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /mnt/storage/Repos/Radio-TTY/frontend && npx vitest run src/components/Logo`
Expected: FAIL — cannot resolve `../Logo`.

- [ ] **Step 3: Implement the component**

Create `frontend/src/components/Logo/Logo.tsx`:

```tsx
import { Box } from '@mui/material';
import { useTheme } from '@mui/material/styles';

interface LogoProps {
  /** Pixel size of the square mark. Default 32. */
  size?: number;
  /** When true, renders the "Hearthwave" wordmark beside the mark. */
  withWordmark?: boolean;
}

/**
 * Hearthwave logo — a radio wave cresting into a rooftop over a glowing
 * hearth doorway. Wave/roof strokes follow the active theme; the doorway
 * glow is a fixed warm amber so the "hearth" reads in both color modes.
 */
export function Logo({ size = 32, withWordmark = false }: LogoProps) {
  const theme = useTheme();
  const wave = theme.palette.primary.main;
  const roof = theme.palette.mode === 'dark' ? '#93C5FD' : theme.palette.info.main;

  const mark = (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      role="img"
      aria-label="Hearthwave logo"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M12 50 Q31 24 50 37 Q69 50 88 30" fill="none" stroke={wave} strokeWidth={5.5} strokeLinecap="round" />
      <path d="M22 54 L22 82 L78 82 L78 44" fill="none" stroke={roof} strokeWidth={4.5} strokeLinejoin="round" />
      <path d="M44 82 L44 64 Q44 57 51 57 L57 57 Q64 57 64 64 L64 82 Z" fill="#FBBF24" />
    </svg>
  );

  if (!withWordmark) return mark;

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      {mark}
      <Box
        component="span"
        sx={{ fontWeight: 800, fontSize: size * 0.6, letterSpacing: '0.5px', color: 'text.primary' }}
      >
        Hearthwave
      </Box>
    </Box>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /mnt/storage/Repos/Radio-TTY/frontend && npx vitest run src/components/Logo`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/Logo/
git commit -m "feat(frontend): add Hearthwave Logo component"
```

---

## Task 3: `useVersion` hook

**Files:**
- Create: `frontend/src/hooks/useVersion.ts`
- Test: `frontend/src/hooks/__tests__/useVersion.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/hooks/__tests__/useVersion.test.ts`:

```ts
import { renderHook, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, afterEach } from 'vitest'
import { useVersion } from '../useVersion'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useVersion', () => {
  it('returns the version from /health', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true, version: '2.5.2' }),
    } as Response)

    const { result } = renderHook(() => useVersion())
    await waitFor(() => expect(result.current).toBe('2.5.2'))
    expect(global.fetch).toHaveBeenCalledWith('/health')
  })

  it('stays null when the request fails', async () => {
    vi.spyOn(global, 'fetch').mockRejectedValue(new Error('network'))
    const { result } = renderHook(() => useVersion())
    // Give the rejected promise a tick to settle.
    await new Promise((r) => setTimeout(r, 0))
    expect(result.current).toBeNull()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /mnt/storage/Repos/Radio-TTY/frontend && npx vitest run src/hooks/__tests__/useVersion.test.ts`
Expected: FAIL — cannot resolve `../useVersion`.

- [ ] **Step 3: Implement the hook**

Create `frontend/src/hooks/useVersion.ts`:

```ts
import { useEffect, useState } from 'react';

/**
 * Fetches the running backend version from the unauthenticated /health
 * endpoint once on mount. Returns null until it resolves (or on failure).
 */
export function useVersion(): string | null {
  const [version, setVersion] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch('/health')
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!cancelled && data && typeof data.version === 'string') {
          setVersion(data.version);
        }
      })
      .catch(() => {
        /* leave version null — the UI shows a graceful fallback */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return version;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /mnt/storage/Repos/Radio-TTY/frontend && npx vitest run src/hooks/__tests__/useVersion.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useVersion.ts frontend/src/hooks/__tests__/useVersion.test.ts
git commit -m "feat(frontend): add useVersion hook reading /health"
```

---

## Task 4: `AboutDialog` component

**Files:**
- Create: `frontend/src/components/AboutDialog/AboutDialog.tsx`
- Test: `frontend/src/components/AboutDialog/__tests__/AboutDialog.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/AboutDialog/__tests__/AboutDialog.test.tsx`:

```tsx
import { render, screen, waitFor } from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { describe, it, expect, vi, afterEach } from 'vitest'
import { makeTheme } from '../../../theme'
import { AboutDialog } from '../AboutDialog'

function renderDialog(open: boolean) {
  return render(
    <ThemeProvider theme={makeTheme(false)}>
      <AboutDialog open={open} onClose={vi.fn()} />
    </ThemeProvider>
  )
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('AboutDialog', () => {
  it('shows tagline, links, FCC note, and version when open', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true, version: '2.5.2' }),
    } as Response)

    renderDialog(true)

    expect(screen.getByText(/self-hosted gmrs hub for your household/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /github repository/i })).toHaveAttribute(
      'href',
      'https://github.com/Xpiatio/Hearthwave'
    )
    expect(screen.getByText(/fcc part 95/i)).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('v2.5.2')).toBeInTheDocument())
  })

  it('renders nothing visible when closed', () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true, version: '2.5.2' }),
    } as Response)
    renderDialog(false)
    expect(screen.queryByText(/self-hosted gmrs hub/i)).not.toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /mnt/storage/Repos/Radio-TTY/frontend && npx vitest run src/components/AboutDialog`
Expected: FAIL — cannot resolve `../AboutDialog`.

- [ ] **Step 3: Implement the component**

Create `frontend/src/components/AboutDialog/AboutDialog.tsx`:

```tsx
import {
  Box,
  Dialog,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  Link,
  Typography,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { Logo } from '../Logo/Logo';
import { useVersion } from '../../hooks/useVersion';

interface Props {
  open: boolean;
  onClose: () => void;
}

const GITHUB_URL = 'https://github.com/Xpiatio/Hearthwave';
const WEBSITE_URL = 'https://xpiatio.github.io/Hearthwave/';

export function AboutDialog({ open, onClose }: Props) {
  const version = useVersion();

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        About Hearthwave
        <IconButton onClick={onClose} aria-label="Close about dialog" size="small" sx={{ color: 'inherit' }}>
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1, pt: 1, textAlign: 'center' }}>
          <Logo size={72} />
          <Typography variant="h6" sx={{ fontWeight: 800 }}>Hearthwave</Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            {version ? `v${version}` : 'version unavailable'}
          </Typography>
          <Typography variant="body2">Self-hosted GMRS hub for your household.</Typography>
        </Box>

        <Divider sx={{ my: 2 }} />

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          <Link href={GITHUB_URL} target="_blank" rel="noopener noreferrer">GitHub repository</Link>
          <Link href={WEBSITE_URL} target="_blank" rel="noopener noreferrer">Documentation &amp; website</Link>
        </Box>

        <Divider sx={{ my: 2 }} />

        <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
          Operates on GMRS under FCC Part 95 Subpart E. Every transmission is station-identified;
          you are responsible for holding a valid GMRS license and using your assigned call sign.
        </Typography>
        <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 1 }}>
          A fork of GMRS-TTY. Speech-to-text by Whisper; text-to-speech by Piper.
        </Typography>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /mnt/storage/Repos/Radio-TTY/frontend && npx vitest run src/components/AboutDialog`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/AboutDialog/
git commit -m "feat(frontend): add AboutDialog component"
```

---

## Task 5: Login screen — logo lockup + About/version footer

**Files:**
- Modify: `frontend/src/components/LoginScreen/LoginScreen.tsx`
- Test: `frontend/src/components/LoginScreen/__tests__/LoginScreen.test.tsx` (new)

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/LoginScreen/__tests__/LoginScreen.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '@mui/material/styles'
import { describe, it, expect, vi, afterEach } from 'vitest'
import { makeTheme } from '../../../theme'
import { LoginScreen } from '../LoginScreen'

function renderLogin() {
  return render(
    <ThemeProvider theme={makeTheme(false)}>
      <LoginScreen onLogin={vi.fn().mockResolvedValue(undefined)} />
    </ThemeProvider>
  )
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('LoginScreen', () => {
  it('shows the logo lockup', () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true, version: '2.5.2' }),
    } as Response)
    renderLogin()
    expect(screen.getByRole('img', { name: /hearthwave logo/i })).toBeInTheDocument()
  })

  it('opens the About dialog from the footer link', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true, version: '2.5.2' }),
    } as Response)
    renderLogin()
    await userEvent.click(screen.getByRole('button', { name: /about/i }))
    expect(screen.getByText(/self-hosted gmrs hub for your household/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /mnt/storage/Repos/Radio-TTY/frontend && npx vitest run src/components/LoginScreen`
Expected: FAIL — no element with role `img`/name "hearthwave logo"; no "About" button.

- [ ] **Step 3: Update imports and add state**

In `frontend/src/components/LoginScreen/LoginScreen.tsx`, replace the import block at lines 1-12:

```tsx
import { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Alert,
  CircularProgress,
} from '@mui/material';
import type { AuthError } from '../../hooks/useAuth';
```

with:

```tsx
import { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Alert,
  CircularProgress,
} from '@mui/material';
import type { AuthError } from '../../hooks/useAuth';
import { Logo } from '../Logo/Logo';
import { AboutDialog } from '../AboutDialog/AboutDialog';
import { useVersion } from '../../hooks/useVersion';
```

Then add this state inside the component, immediately after the existing `const [loading, setLoading] = useState(false);` line:

```tsx
  const [aboutOpen, setAboutOpen] = useState(false);
  const version = useVersion();
```

- [ ] **Step 4: Replace the title with the logo lockup**

In the same file, replace this block:

```tsx
          <Typography variant="h5" sx={{ fontWeight: 700, mb: 0.5, textAlign: 'center' }}>
            Hearthwave
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', textAlign: 'center', mb: 3 }}>
            Sign in to continue
          </Typography>
```

with:

```tsx
          <Box sx={{ display: 'flex', justifyContent: 'center', mb: 1 }}>
            <Logo size={56} withWordmark />
          </Box>
          <Typography variant="body2" sx={{ color: 'text.secondary', textAlign: 'center', mb: 3 }}>
            Sign in to continue
          </Typography>
```

- [ ] **Step 5: Add the footer link and dialog**

In the same file, find the closing of the form `Box` and the `CardContent`. Replace this tail:

```tsx
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}
```

with:

```tsx
          </Box>

          <Box sx={{ mt: 2, textAlign: 'center' }}>
            <Button
              size="small"
              onClick={() => setAboutOpen(true)}
              sx={{ textTransform: 'none', color: 'text.secondary' }}
            >
              About{version ? ` · v${version}` : ''}
            </Button>
          </Box>
        </CardContent>
      </Card>

      <AboutDialog open={aboutOpen} onClose={() => setAboutOpen(false)} />
    </Box>
  );
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd /mnt/storage/Repos/Radio-TTY/frontend && npx vitest run src/components/LoginScreen`
Expected: PASS (2 tests).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/LoginScreen/
git commit -m "feat(frontend): logo lockup and About link on login screen"
```

---

## Task 6: Account menu — "About Hearthwave" item

**Files:**
- Modify: `frontend/src/components/AccountMenu/AccountMenu.tsx`
- Test: `frontend/src/components/AccountMenu/__tests__/AccountMenu.test.tsx` (new)

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/AccountMenu/__tests__/AccountMenu.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '@mui/material/styles'
import { describe, it, expect, vi, afterEach } from 'vitest'
import { makeTheme } from '../../../theme'
import { AccountMenu } from '../AccountMenu'
import type { UserProfile } from '../../../types/ws'

const profile: UserProfile = {
  id: 'u1',
  display_name: 'Alice',
  avatar_emoji: '👤',
  operator_name: 'Alice',
  callsign: 'WRAA123',
  location: 'MI',
  is_admin: false,
  created_at: '2026-01-01T00:00:00Z',
  prefs: {} as UserProfile['prefs'],
}

function renderMenu() {
  return render(
    <ThemeProvider theme={makeTheme(false)}>
      <AccountMenu
        profile={profile}
        onUpdateProfile={vi.fn()}
        onChangePassword={vi.fn()}
        onLogout={vi.fn()}
        voices={[]}
        voicePreviewBusy={false}
        onPreviewVoice={vi.fn()}
        stationLengthScale={1}
        onSaveTtsPrefs={vi.fn()}
        showConfig={false}
        onToggleConfig={vi.fn()}
        showAdmin={false}
        onToggleAdmin={vi.fn()}
      />
    </ThemeProvider>
  )
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('AccountMenu', () => {
  it('opens the About dialog from the menu', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true, version: '2.5.2' }),
    } as Response)

    renderMenu()
    await userEvent.click(screen.getByRole('button', { name: /account menu/i }))
    await userEvent.click(screen.getByRole('menuitem', { name: /about hearthwave/i }))
    expect(screen.getByText(/self-hosted gmrs hub for your household/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /mnt/storage/Repos/Radio-TTY/frontend && npx vitest run src/components/AccountMenu`
Expected: FAIL — no menu item named "About Hearthwave".

- [ ] **Step 3: Add imports**

In `frontend/src/components/AccountMenu/AccountMenu.tsx`, add these imports after the existing `import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings';` line (line 27):

```tsx
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { AboutDialog } from '../AboutDialog/AboutDialog';
```

- [ ] **Step 4: Add dialog state**

In the same file, add this state alongside the other `useState` calls near the top of the component (e.g. right after `const [pwOpen, setPwOpen] = useState(false);` at line 63):

```tsx
  const [aboutOpen, setAboutOpen] = useState(false);
```

- [ ] **Step 5: Add the menu item**

In the same file, replace the existing "Sign Out" block (lines 180-184):

```tsx
        <Divider />
        <MenuItem onClick={() => { handleClose(); onLogout(); }}>
          <ListItemIcon><LogoutIcon fontSize="small" /></ListItemIcon>
          Sign Out
        </MenuItem>
```

with (adds "About Hearthwave" above "Sign Out", keeping a single divider):

```tsx
        <Divider />
        <MenuItem onClick={() => { setAboutOpen(true); handleClose(); }}>
          <ListItemIcon><InfoOutlinedIcon fontSize="small" /></ListItemIcon>
          About Hearthwave
        </MenuItem>
        <MenuItem onClick={() => { handleClose(); onLogout(); }}>
          <ListItemIcon><LogoutIcon fontSize="small" /></ListItemIcon>
          Sign Out
        </MenuItem>
```

- [ ] **Step 6: Render the dialog**

In the same file, add the dialog just before the closing `</>` fragment at the end of the component (after the change-password `</Dialog>` on line 330):

```tsx
      <AboutDialog open={aboutOpen} onClose={() => setAboutOpen(false)} />
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd /mnt/storage/Repos/Radio-TTY/frontend && npx vitest run src/components/AccountMenu`
Expected: PASS (1 test).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/AccountMenu/
git commit -m "feat(frontend): add About Hearthwave item to account menu"
```

---

## Task 7: Topbar — clickable logo opens About

**Files:**
- Modify: `frontend/src/components/TopBar/TopBar.tsx`

- [ ] **Step 1: Add imports and state**

In `frontend/src/components/TopBar/TopBar.tsx`, change the React import. The file currently imports only from `@mui/material` and icon packages (no `react` import). Add at the very top of the file:

```tsx
import { useState } from 'react';
```

Add these imports after the existing `import { VoicePTT } from '../VoicePTT/VoicePTT';` line:

```tsx
import { Logo } from '../Logo/Logo';
import { AboutDialog } from '../AboutDialog/AboutDialog';
```

Also add `Tooltip` and `IconButton` — verify they are already imported from `@mui/material` (they are, per the existing import list). No change needed there.

- [ ] **Step 2: Add dialog state inside the component**

Immediately inside the `TopBar({ ... }: Props) {` function body, before the `return (`, add:

```tsx
  const [aboutOpen, setAboutOpen] = useState(false);
```

- [ ] **Step 3: Wrap the return in a fragment and add the clickable logo**

The component currently returns a single `<AppBar>`. Change the structure so it also renders the dialog. Replace the opening of the return:

```tsx
  return (
    <AppBar position="static" color="default" elevation={0}
      sx={{ borderBottom: 1, borderColor: 'divider' }}>
      <Toolbar sx={{ gap: 1, flexWrap: 'wrap', py: 0.5 }}>

        {/* Group 1 — Identity */}
        <AccountMenu
```

with:

```tsx
  return (
    <AppBar position="static" color="default" elevation={0}
      sx={{ borderBottom: 1, borderColor: 'divider' }}>
      <Toolbar sx={{ gap: 1, flexWrap: 'wrap', py: 0.5 }}>

        {/* Brand — click to open About */}
        <Tooltip title="About Hearthwave">
          <IconButton
            onClick={() => setAboutOpen(true)}
            aria-label="About Hearthwave"
            size="small"
            sx={{ p: 0.5 }}
          >
            <Logo size={28} />
          </IconButton>
        </Tooltip>

        <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />

        {/* Group 1 — Identity */}
        <AccountMenu
```

- [ ] **Step 4: Close the AppBar with the dialog**

Replace the end of the return:

```tsx
      </Toolbar>
    </AppBar>
  );
}
```

with:

```tsx
      </Toolbar>
      <AboutDialog open={aboutOpen} onClose={() => setAboutOpen(false)} />
    </AppBar>
  );
}
```

- [ ] **Step 5: Typecheck + run the full frontend suite**

Run: `cd /mnt/storage/Repos/Radio-TTY/frontend && npx tsc -p tsconfig.build.json --noEmit && npx vitest run`
Expected: typecheck passes; all tests pass (including new Logo/useVersion/AboutDialog/LoginScreen/AccountMenu tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/TopBar/
git commit -m "feat(frontend): clickable Hearthwave logo in topbar opens About"
```

---

## Task 8: Favicon + Dockerfile

**Files:**
- Create: `frontend/public/favicon.svg`
- Modify: `frontend/index.html`
- Modify: `frontend/Dockerfile`

- [ ] **Step 1: Create the favicon**

Create `frontend/public/favicon.svg` (theme-independent: fixed blues + amber, matching the validated favicon preview):

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
  <rect width="100" height="100" rx="20" fill="#0F2540"/>
  <path d="M12 50 Q31 24 50 37 Q69 50 88 30" fill="none" stroke="#60A5FA" stroke-width="6" stroke-linecap="round"/>
  <path d="M22 54 L22 82 L78 82 L78 44" fill="none" stroke="#93C5FD" stroke-width="5" stroke-linejoin="round"/>
  <path d="M44 82 L44 64 Q44 57 51 57 L57 57 Q64 57 64 64 L64 82 Z" fill="#FBBF24"/>
</svg>
```

- [ ] **Step 2: Link the favicon**

In `frontend/index.html`, add inside `<head>` after the `<meta name="viewport" ...>` line:

```html
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
```

- [ ] **Step 3: Ship the public dir in the Docker build**

In `frontend/Dockerfile`, the builder stage currently copies sources without `public/`. Replace this line:

```dockerfile
COPY index.html tsconfig.json tsconfig.build.json vite.config.ts ./
```

with:

```dockerfile
COPY index.html tsconfig.json tsconfig.build.json vite.config.ts ./
COPY public/ ./public/
```

- [ ] **Step 4: Verify the build includes the favicon**

Run: `cd /mnt/storage/Repos/Radio-TTY/frontend && npx vite build && test -f dist/favicon.svg && echo FAVICON_OK`
Expected: build succeeds and prints `FAVICON_OK` (Vite copies `public/*` into `dist/`).

- [ ] **Step 5: Commit**

```bash
git add frontend/public/favicon.svg frontend/index.html frontend/Dockerfile
git commit -m "feat(frontend): add favicon and ship public/ in Docker build"
```

---

## Task 9: Ignore `.superpowers/` working dir

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Append the ignore rule**

Append to `.gitignore`:

```
# Superpowers brainstorming / scratch working dir
.superpowers/
```

- [ ] **Step 2: Verify it is ignored**

Run: `cd /mnt/storage/Repos/Radio-TTY && git status --porcelain | grep '.superpowers' || echo "ignored-ok"`
Expected: prints `ignored-ok` (the `.superpowers/` entries no longer show as untracked).

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: ignore .superpowers working directory"
```

---

## Final verification

- [ ] **Run the whole frontend suite + typecheck:**

Run: `cd /mnt/storage/Repos/Radio-TTY/frontend && npx tsc -p tsconfig.build.json --noEmit && npx vitest run`
Expected: typecheck clean; all tests pass.

- [ ] **Run the backend integration suite:**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/integration/test_server_ws.py -v`
Expected: all pass, including `test_health_reports_version`.

- [ ] **Manual smoke (optional, via the `run`/`verify` skill):** start the stack, confirm the logo on the login screen, the "About · v2.5.2" link opens the dialog, the topbar logo and account-menu item open it post-login, and the browser tab shows the favicon.

---

## Notes / follow-ups (out of scope for this plan)

- **Release process:** the `/release` skill (per `CLAUDE.md`) must be updated to bump `backend/__init__.py.__version__` alongside `frontend/package.json` and the docs, or the displayed version will drift from the frontend. Track separately.
- **No LICENSE file** exists in the repo, so the About dialog intentionally omits a license link. Add one later if a license is chosen.
- The Radio-TTY → Hearthwave naming/volume cleanup is tracked separately and is not part of this plan.
