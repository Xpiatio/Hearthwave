# Design: Hearthwave logo, About page, and version display

**Date:** 2026-06-14
**Status:** Approved (design)

## Goal

Give Hearthwave a visual identity and surface its version:

1. A Hearthwave logo, shown on the login screen and inside the app.
2. An About page (dialog) reachable from three entry points.
3. A visible, single-sourced version number.

## Background

- The login screen (`frontend/src/components/LoginScreen/LoginScreen.tsx`) currently
  shows the word "Hearthwave" as plain text. No logo or icon exists anywhere in the app.
- No image/SVG assets exist; `index.html` sets `<title>` but has no favicon.
- The app theme (`frontend/src/theme.ts`) is a maritime-blue palette
  (deep navy `#0F2540`, blue `#2563EB`/`#60A5FA`) with light and dark modes.
- The version (`2.5.2`) lives only in `frontend/package.json`. There is **no**
  backend version constant. The `/release` skill currently bumps README,
  USER_MANUAL, and docs/index.html.
- The frontend calls the backend **same-origin** (`fetch('/auth/...')`, nginx proxies).
  `/health` (`backend/server.py:1354`) is unauthenticated and returns `{"ok": true}`.

## Logo

**Concept A — "wave-roof house," warm amber doorway.** A radio wave crests into a
rooftop over a glowing doorway. The wave/roof strokes use theme palette blues
(adapting to light/dark); the doorway glow is fixed warm amber (`#FBBF24` /
`#FB923C`) to play up the "hearth." Validated legible at favicon sizes (20–32px).

### Components / assets

- `frontend/src/components/Logo/Logo.tsx` — inline SVG React component, the single
  source of truth for the mark. Props:
  - `size?: number` (px, default ~32)
  - `withWordmark?: boolean` — mark only vs. mark + "Hearthwave" wordmark lockup
  - Strokes derive from theme palette (via `useTheme`/`currentColor`) so the mark
    works in both color modes; the doorway stays amber.
- `frontend/public/favicon.svg` — mark-only SVG favicon.
- `frontend/index.html` — add `<link rel="icon" type="image/svg+xml" href="/favicon.svg">`.
- `frontend/Dockerfile` — add `COPY public/ ./public/` **before** `npm run build`
  (the Dockerfile does not currently copy a `public/` dir, so the favicon would not
  otherwise ship). Vite copies `public/*` into `dist/` during build.

## Version sourcing (backend single source)

- Add `__version__ = "2.5.2"` to `backend/__init__.py` — the single source of truth
  for the running app's version.
- `/health` returns `{"ok": true, "version": __version__}`.
- Frontend: a small `useVersion()` hook (or one-shot fetch) that reads `/health` and
  caches the version; shared by the login screen and the About dialog. Unauthenticated,
  so it works on the login screen pre-auth.
- **Follow-up (out of scope for code, but must be wired):** update the `/release` skill
  (and CLAUDE.md release note) to also bump `backend/__init__.py.__version__`, so the
  frontend `package.json` and backend versions stay in lockstep.

## About dialog

`frontend/src/components/AboutDialog/AboutDialog.tsx` — reusable MUI `Dialog`. Contents:

- Logo lockup + app name + version (e.g. "v2.5.2").
- Tagline: **"Self-hosted GMRS hub for your household."**
- Project links:
  - GitHub repo — https://github.com/Xpiatio/Hearthwave
  - Docs / website — https://xpiatio.github.io/Hearthwave/ (and/or USER_MANUAL)
  - License — link to `LICENSE` if present; otherwise omit. (No LICENSE file currently
    exists in the repo — confirm before linking.)
- FCC compliance note: short line on GMRS / FCC Part 95 operation and station ID.
- Credits: Whisper (STT), Piper (TTS), and fork origin (fork of GMRS-TTY).

## Entry points to About (all three)

1. **Account menu** — new "About Hearthwave" `MenuItem` in
   `frontend/src/components/AccountMenu/AccountMenu.tsx`.
2. **Login screen** — small "About · v2.5.2" link under the form that opens the dialog.
3. **Topbar** — add the small clickable `Logo` mark at the start of the `Toolbar` in
   `frontend/src/components/TopBar/TopBar.tsx`; clicking it opens the About dialog.

State for whether the dialog is open lives in the nearest sensible owner for each
entry point (login screen manages its own; the in-app entry points share one piece of
state, likely lifted to `App.tsx` or `DesktopApp`/`MobileApp` so the topbar logo and
account-menu item open the same dialog instance).

## Login screen change

Replace the plain "Hearthwave" `Typography` with the `Logo` lockup (mark + wordmark),
and add the version/About footer link beneath the form.

## Testing

- vitest: `Logo` renders (mark-only and with wordmark); `AboutDialog` shows version,
  tagline, and links; login-screen footer link opens the dialog.
- pytest: `/health` response includes a `version` field equal to `backend.__version__`.

## Housekeeping

- Add `.superpowers/` to `.gitignore` (currently untracked, not ignored).

## Out of scope

- The separate Radio-TTY → Hearthwave naming/volume cleanup (paused, tracked separately).
- Marketing-website (`docs/index.html`) logo adoption — can reuse the same SVG later.
