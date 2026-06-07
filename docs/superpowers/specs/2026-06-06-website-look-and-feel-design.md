# Website Look & Feel — App Refresh Design

**Date:** 2026-06-06
**Approach:** Theme-First (Approach A)
**Scope:** Frontend visual refresh · full test suite · full code audit · docs expansion

---

## 1. Color Palette

Both dark and light modes adopt the website's navy/blue identity. Green is preserved exclusively for radio status indicators.

### Dark Mode

| Token | Value | Purpose |
|---|---|---|
| `primary.main` | `#60A5FA` | Primary actions (buttons, links, focus) |
| `primary.dark` | `#2563EB` | Hover state |
| `background.default` | `#0F2540` | Page background (navy-darkest) |
| `background.paper` | `#1A3A5C` | Cards, panels, dialogs (navy-dark) |
| `success.main` | `#4ADE80` | Radio status: connected, transmitting, PTT |
| `info.main` | `#93C5FD` | Informational accents |
| `text.primary` | `#F9FAFB` | Body text |
| `divider` | `rgba(37,99,235,0.3)` | Borders and dividers |

### Light Mode

| Token | Value | Purpose |
|---|---|---|
| `primary.main` | `#2563EB` | Primary actions |
| `primary.dark` | `#1D4ED8` | Hover state |
| `background.default` | `#E8EEF7` | Page background (navy-tinted white) |
| `background.paper` | `#C8D8EC` | Cards, panels, dialogs |
| `success.main` | `#15803D` | Radio status |
| `info.main` | `#1E4976` | Informational accents |
| `text.primary` | `#0F2540` | Body text |
| `divider` | `rgba(30,73,118,0.25)` | Borders and dividers |

### Radio Status Green (both modes)

Green (`success` palette) is used only for: connected dot, transmitting indicator, PTT active state, recording state, and the SKYWARN plugin gradient. No other component uses green as a primary color.

---

## 2. MUI Global Component Overrides (theme.ts)

Four `styleOverrides` handle the card/panel treatment globally.

### MuiPaper
- `border: 1px solid` using theme divider color
- `borderRadius: 8`

### MuiCard
- Inherits Paper border/radius
- `overflow: hidden` (clips gradient header)

### MuiAppBar
- `backgroundColor`: `#0F2540` dark / `#1A3A5C` light
- Replaces default surface color with navy

### MuiDialog / MuiDialogTitle
- Dialog Paper: inherits navy border
- DialogTitle: `background: linear-gradient(135deg, #0F2540 0%, #1E4976 100%)`

---

## 3. PanelHeader Component

**Path:** `frontend/src/components/PanelHeader/PanelHeader.tsx`

A stateless `<Box>` wrapper used as the first child inside typed panels. Props: `title: string`, `gradient: string` (CSS gradient string), optional `icon?: React.ReactNode`.

### Per-Panel Gradient Assignments

| Panel | Gradient | Rationale |
|---|---|---|
| NCSPanel | `#1E4976 → #2563EB` | Blue — matches website NCS card |
| AdminPanel | `#1E4976 → #2563EB` | Blue — admin authority |
| ConfigPanel | `#1A3A5C → #1E4976` | Base navy — settings/neutral |
| ServerConfigPanel | `#1A3A5C → #1E4976` | Base navy |
| JournalPanel | `#1A3A5C → #1E4976` | Base navy |
| AttendancePanel | `#1A3A5C → #1E4976` | Base navy |
| SKYWARN plugin slot | `#14532D → #15803D` | Green — matches website SKYWARN card |

Panels that are full-viewport (DesktopApp, MobileApp) or toolbar-based (TopBar, MobileTopBar) use the AppBar override instead of PanelHeader.

---

## 4. Test Suite Strategy

1. Run `npm run test` to capture baseline failures before any changes.
2. Apply theme + PanelHeader changes.
3. Fix failures in priority order:
   - **Style/snapshot failures** from palette or override changes
   - **Structural failures** from PanelHeader additions
   - **Pre-existing failures** unrelated to this work
4. All 26 component tests + 3 hook tests must be green before proceeding to audit.

---

## 5. Code Audit (All 26 Components)

Full audit of `frontend/src/components/` checking:

- **Hardcoded colors** bypassing the theme (`#4ADE80`, `#1F2937`, `#111827`, etc.) — replace with theme tokens
- **WCAG 2.2 AA** — missing/incorrect ARIA labels, roles, `aria-live` regions, focus management
- **TypeScript** — missing prop types, incorrect types, `any` escapes without justification
- **Dead code** — unused imports, unreachable branches, unused state
- **Component scope** — flag oversized components, fix only clearly wrong cases (no speculative refactoring)
- **Security** — no user-controlled strings injected as HTML (`dangerouslySetInnerHTML`)

Findings fixed inline. Out-of-scope refactors get a `// TODO:` comment only.

---

## 6. Documentation Updates

### README.md
- Updated feature list (a11y, multi-user auth, voice PTT, audio pipeline, WCAG 2.2 AA)
- Architecture diagram updated to current state
- Hardware requirements section updated to reflect current supported hardware (x86 mini PC / NUC, USB audio interface, USB serial PTT dongle; Raspberry Pi removed)
- Docker quick-start kept current
- New "UI overview" section describing the navy/blue interface and dark/light modes

### USER_MANUAL.md
- All 23 sections reviewed and updated
- Interface descriptions updated for navy/blue UI
- Section 2 (interface) and 2a (mobile) expanded with current layout descriptions
- New features documented: TokenPromptDialog, keyboard PTT, panel drag, audio pre-roll, priority mixer
- Dark/light mode behavior documented

### docs/index.html
- Hero chat preview colors updated to navy/blue scheme
- Feature grid updated to reflect current feature set
- New entries: voice PTT keyboard support, WCAG 2.2 AA badge, audio pre-roll, priority mixer
- All copy cross-checked against README for consistency
- ADA 2.2 AA compliance maintained throughout

---

## Implementation Order

1. Run test baseline
2. Update `theme.ts` — palette + global overrides
3. Create `PanelHeader` component
4. Add PanelHeader to 7 panels
5. Run tests, fix failures
6. Full code audit — all 26 components, fix inline
7. Update README.md
8. Update USER_MANUAL.md
9. Update docs/index.html
