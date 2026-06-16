# Hearthwave

A GMRS hub that turns a home server or x86 mini PC into a shared radio
operating station for every member of your household or neighborhood watch group.
Incoming transmissions are transcribed by speech-to-text and streamed to all
connected devices; outgoing messages are synthesized to speech, automatically
wrapped with the FCC station callsign (§95.1751), and transmitted over the air.
Each family member or watch volunteer signs in from their own phone, tablet, or
laptop — no app install required.

Built-in plugins add Net Control Station (NCS) mode with a live check-in roster
and six traffic priority levels, SKYWARN weather alerts sourced directly from the
National Weather Service, and an instant audio replay buffer. The plugin
architecture is open — additional capabilities wire into the radio pipeline
without touching core server logic.

Hearthwave is a fork of GMRS-TTY that replaces the desktop PySide6 UI with a
browser-based React frontend communicating over WebSocket.

> **Latest release:** v2.6.2

## Who uses it

- **Families** — one GMRS license covers the whole household. Each person gets
  their own account with their own voice and preferences. Kids on tablets, parents
  on laptops, grandparents with large-touch mode — everyone on the same channel.
- **Neighborhood watch groups** — deploy Hearthwave as the watch's base station.
  Assign listen-only accounts to patrol volunteers and TX-capable accounts to
  designated net control operators. The NCS roster tracks who is active on each
  patrol; SKYWARN alerts auto-announce over the air when severe weather approaches.

## Features

- **Refreshed brand** — a new Hearthwave logo (a home sheltering a radio set,
  with signal waves cresting off the roof) across the login screen, top bar,
  About dialog, and favicon, plus a redesigned project website that defaults to
  a warm light theme with a one-click dark-mode toggle
- **Two-tier transcription** — a fast model streams live partials while an
  optional larger model (e.g. `distil-large-v3`) re-transcribes each completed
  transmission in full, replacing the live text with a higher-accuracy final —
  without truncating long overs or dropping a callsign the live pass already heard
- **Cuts through static** — adaptive squelch tracks the channel noise floor so
  weak carriers pre-trigger capture, a 1-second pre-roll plus carrier-drop
  finalize stops the first and last words from being clipped
- **Clearer transmit audio** — optional TX conditioning band-limits, compresses,
  and levels synthesized speech for intelligibility over narrowband FM
- **STT accuracy tuning** — built-in debug capture and an offline word-error-rate
  eval harness for measuring and improving recognition on real recordings
- **Live transcription** — Whisper STT converts every received transmission to
  text in real time and broadcasts it to all connected users; admin-configurable
  saved-phrases list biases recognition toward group-specific vocabulary
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
- **Contacts** — shared contact book with FCC license lookup; multiple family members sharing the same GMRS callsign are stored as separate records and addressed individually by name
- **Spectrogram** — real-time frequency display (voice or full range, viridis or
  grayscale colormaps)
- **Attendance panel** — automatic log of every station heard this session
- **Draggable panels** — desktop layout fully customisable with drag-and-drop
- **WCAG 2.2 AA** — full keyboard navigation, screen reader support, and ARIA
  labelling throughout the interface
- **Chat vs Transmit split** — a CHAT action broadcasts a message to all operators' displays without keying the radio; TRANSMIT is the over-the-air action; chat lines are marked `[CHAT]` and are profanity-filtered per recipient
- **Shared message stream** — the message log (RX, TX, and CHAT entries) is held server-side and shared across the base station and every web/mobile login, so a client that signs in or refreshes later sees the history accumulated since the last clear. The stream is kept in memory (a backend restart starts fresh) and capped to the most recent messages. Clearing the log is **admin-only and global** — an admin clear wipes the chat for everyone at once, after a confirmation prompt
- **Unified Admin Settings** — the Admin panel and Server Config are merged into a single tabbed "Admin Settings" dialog (Station and System tabs, each with its own Save button)
- **VOX primer tone** — an optional short tone prepended to each transmission so a VOX-keyed radio is fully keyed before the message starts; configurable on/off and tone duration in milliseconds (System tab, off by default)
- **Logo, About & version** — a Hearthwave logo on the login screen and in the top bar, plus an About dialog (opened from the account menu, the login-screen footer, or the top-bar logo) showing the running version, project links, and FCC information. The version is sourced from the backend `/health` endpoint
- **Docker install** — single `docker compose up -d` gets you running

## UI Overview

The interface uses a navy/blue design language that matches the
[Hearthwave website](https://xpiatio.github.io/Hearthwave/):

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

Hearthwave is designed as a **remote control point** for a single local station,
not an internet repeater gateway or RoIP bridge. All transmissions originate
from the licensed station's transceiver under direct operator control. The system
automatically prepends and appends the station callsign per §95.1751.

Remote access over the internet is the operator's responsibility. Hearthwave
provides no port-forwarding, relay, or TURN/STUN infrastructure — use a VPN or
private tunnel.

## Hardware requirements

| Component | Requirement |
|---|---|
| Server | x86 mini PC or NUC (e.g. Intel N100; N305 or better recommended when running the two-tier final pass); ARM not supported |
| RAM | 8 GB minimum, 16 GB recommended — Whisper STT is memory-intensive, and the optional two-tier final-pass model adds ~1.5 GB while active |
| Audio | A two-way audio path to the radio's combo (speaker/mic) jack — either the computer's built-in 3.5 mm jack or a USB audio adapter (see [Connecting the radio](#connecting-the-radio)) |
| PTT | VOX (no wiring — uses the VOX primer tone), a USB serial dongle (RTS/DTR), or a CM108 sound-card GPIO |
| OS | Ubuntu 22.04+ or Debian 12+ recommended; Docker required |
| Radio | Any GMRS transceiver with an external speaker/mic (combo) jack |

### Connecting the radio

Hearthwave needs a two-way audio path between the computer and the radio's
**combo (speaker/mic) jack** — most handhelds and mobiles expose this as a
Kenwood-style **K1** connector (a 3.5 mm + 2.5 mm plug pair). **A USB connection
to the radio is _not_ required** — USB, when present, is only the computer-side
sound card. Two paths both work:

1. **Direct 3.5 mm (no USB)** — run the K1 cable from the radio's combo jack into
   the computer's built-in 3.5 mm headset/combo jack. Simplest setup; key the
   radio with **VOX** and enable the **VOX primer tone** so the radio is fully
   keyed before speech begins.
2. **USB audio adapter** — run the K1 cable into a USB sound card (a CM108 fob,
   DigiRig, or similar). Useful when the computer has no usable analog jack, or
   when you want a dedicated card with hardware PTT. Here you can key PTT over a
   USB serial dongle (RTS/DTR) or a CM108 adapter's GPIO pin instead of VOX.

Pick the input/output devices and PTT mode on first run from the Setup screen,
and adjust them later under **Admin Settings**.

## Quick start

```bash
# 1. Clone the repo
git clone https://github.com/Xpiatio/Hearthwave
cd Hearthwave

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
