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
