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

> **Latest release:** v2.8.0

## Who uses it

- **Families** — one GMRS license covers the whole household. Each person gets
  their own account with their own voice and preferences. Kids on tablets, parents
  on laptops, grandparents with large-touch mode — everyone on the same channel.
- **Neighborhood watch groups** — deploy Hearthwave as the watch's base station.
  Assign listen-only accounts to patrol volunteers and TX-capable accounts to
  designated net control operators. The NCS roster tracks who is active on each
  patrol; SKYWARN alerts auto-announce over the air when severe weather approaches.

## Features

- **Speech-recognition vocabulary biasing** — transcription is weighted toward radio vocabulary (NATO alphabet, procedure words, Q-codes) and your contacts' callsigns, with auto-refresh on contact changes and a manual Rescan button.
- **Monitoring beacon** — an optional, periodic presence call
  (`{callsign} Hearthwave base, monitoring.`) on a fixed timer. Off by default;
  suppressed during NCS mode, transmits only on a clear channel, and doubles as
  your FCC station ID when it airs (configurable interval and phrase)
- **Refreshed brand** — a new Hearthwave logo (a home sheltering a radio set,
  with signal waves cresting off the roof) across the login screen, top bar,
  About dialog, and favicon, plus a redesigned project website that defaults to
  a warm light theme with a one-click dark-mode toggle
- **Two-tier transcription** — a fast model streams live partials while an
  optional larger model (e.g. `distil-large-v3`) re-transcribes each completed
  transmission in full, replacing the live text with a higher-accuracy final —
  without truncating long overs or dropping a callsign the live pass already heard
- **GPU-accelerated final pass (ROCm)** — the whole-utterance final pass can run
  on an AMD GPU via ROCm while streaming stays on CPU, eliminating the CPU
  contention that otherwise stalls live transcription during a final pass (measured:
  streaming latency during a final pass dropped from +105% to +3% on a Radeon 680M).
  Configurable via `stt_final_device` (`auto` / `gpu` / `cpu`); falls back to CPU
  automatically if no ROCm GPU is present. ROCm deployment is build-from-source only
  (see [deployment profiles](#quick-start))
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
| GPU (optional) | AMD GPU with amdgpu / ROCm kernel driver — offloads the final pass to the GPU, eliminating CPU contention during transcription. CPU-only operation is fully supported without a GPU |
| Audio | A two-way audio path to the radio's combo (speaker/mic) jack — either the computer's built-in 3.5 mm jack or a USB audio adapter (see [Connecting the radio](#connecting-the-radio)) |
| PTT | VOX (no wiring — uses the VOX primer tone), or a USB serial dongle (RTS/DTR) |
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
2. **USB audio adapter** — run the K1 cable into a USB sound card (a DigiRig or
   similar). Useful when the computer has no usable analog jack. Here you can key
   PTT over a USB serial dongle (RTS/DTR) instead of VOX.

Pick the input/output devices and PTT mode on first run from the Setup screen,
and adjust them later under **Admin Settings**.

## Quick start

Hearthwave ships with three deployment profiles. Choose the one that matches your hardware:

| Profile | Compose file | Setup script | Notes |
|---|---|---|---|
| **CPU** (default) | `docker-compose.yml` | `setup-cpu.sh` (or `setup.sh`) | Prebuilt image — recommended for most users |
| **AMD GPU (ROCm)** | `docker-compose.rocm.yml` | `setup-rocm.sh` | Runs the final pass on an AMD GPU; **image built locally** (~28 GB, not published to registry) |
| **NVIDIA GPU (CUDA)** | `docker-compose.cuda.yml` | `setup-cuda.sh` | **Stub — not yet validated**; structure is in place but untested |

### CPU install (default)

```bash
# 1. Clone the repo
git clone https://github.com/Xpiatio/Hearthwave
cd Hearthwave

# 2. Run setup (creates .env and configures audio)
./setup.sh          # forwards to setup-cpu.sh

# 3. Start the stack
docker compose up -d

# 4. Open in your browser
http://your-server-ip
```

### AMD GPU (ROCm) install

```bash
./setup-rocm.sh     # builds the local ROCm image and stages the HF-format final-pass model
docker compose -f docker-compose.rocm.yml up -d
```

Requires an AMD GPU with the amdgpu / ROCm kernel driver, the host `render` group, and
`HSA_OVERRIDE_GFX_VERSION` set appropriately (default `10.3.0`, needed for APUs such as
the Radeon 680M that are not officially listed in the ROCm supported-GPU table). See
[USER_MANUAL.md](USER_MANUAL.md) for full prerequisites.

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

Hearthwave has two independent plugin surfaces: **frontend** plugins (React UI
panels) and **backend** plugins (`BasePlugin` hooks into the audio/message
pipeline). NCS and SKYWARN are implemented as a backend plugin
(`backend/plugins/ncs.py`) with a matching frontend panel.

### Frontend plugins

Frontend plugins are React components that receive `PluginProps` (send,
lastMessage, contacts, channelClear, transmitting) and register themselves at
module init:

```typescript
import { registerPlugin } from '../plugins';

registerPlugin({
  id: 'my-plugin',
  label: 'My Plugin',
  component: MyPluginComponent,
});
```

The app shell mounts registered plugins in the draggable panel area via
`PluginSlot`.

### Backend plugins

Backend plugins subclass `BasePlugin` (`backend/plugins/base.py`) and register an
instance with the singleton `plugin_registry` **before the server accepts
connections** (the NCS plugin is registered this way during server startup). Every
hook is a no-op by default — override only the ones you need.

```python
from backend.plugins.base import BasePlugin
from backend.plugins.registry import plugin_registry


class WordGuard(BasePlugin):
    async def on_rx_final(self, text: str) -> None:
        # Runs after each finalized transcript is broadcast to clients.
        log_to_disk(text)

    async def on_audio_tx_pre_queue(self, payload: dict) -> dict | None:
        # Block any outgoing transmission containing a banned word.
        if "classified" in payload.get("text", "").lower():
            return None            # None blocks the transmit
        return payload             # return the (optionally modified) payload to allow it


plugin_registry.register(WordGuard())
```

#### Hooks

There are five hooks. They fire in plugin **registration order**.

| Hook | Sync/async | Fires when | Return value |
| --- | --- | --- | --- |
| `on_client_message_received(payload, reply=None)` | async | Any connected client sends a WebSocket message | Ignored. `payload` is a copy — mutating it has no effect. `reply(msg: dict)` is an optional async callable that sends `msg` back to the originating client. |
| `on_audio_rx_start()` | async | The squelch detector opens (incoming carrier detected) | Ignored. Bridged from the STT worker thread to the event loop automatically. |
| `on_audio_rx_chunk(chunk)` | **sync** | Each raw audio chunk is captured from the input device | Ignored. `chunk` is a float32 numpy array at 16 kHz. **Hot path on the STT worker thread — keep it fast; do not `await` or call asyncio APIs.** |
| `on_rx_final(text)` | async | Each finalized (non-partial) RX transcript is broadcast | Ignored. |
| `on_audio_tx_pre_queue(payload)` | async | Before TX text enters the synthesis queue | Return `payload` (optionally modified) to allow the transmit, or `None` to block it. Plugins run in registration order and the **first to return `None` wins**. Modifiable fields: `text`, `_filter_profanity`, `_voice_name`, `_length_scale`. |

Dispatch is exception-isolated: if a hook raises, the registry logs it and moves
on to the next plugin (for `on_audio_tx_pre_queue`, a raising plugin is treated as
pass-through, not a block). See `backend/plugins/registry.py` for the dispatchers
and `backend/plugins/ncs.py` for a complete real-world plugin.

## License

MIT
