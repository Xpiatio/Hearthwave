# Radio-TTY

A GMRS family hub that turns a Raspberry Pi or home server into a shared radio operating station for every member of your household. Incoming transmissions are transcribed by speech-to-text and streamed to all connected devices; outgoing messages are synthesized to speech, automatically wrapped with the FCC station callsign (§95.1751), and transmitted over the air. Each family member signs in from their own phone, tablet, or laptop — no app install required.

Built-in plugins add Net Control Station mode with a live check-in roster and six traffic priority levels, SKYWARN weather alerts sourced directly from the National Weather Service, and an instant audio replay buffer. The plugin architecture is open — additional capabilities wire into the radio pipeline without touching core server logic.

Radio-TTY is a fork of GMRS-TTY that replaces the desktop PySide6 UI with a browser-based React frontend communicating over WebSocket.

---

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

- **RX pipeline**: audio capture → VAD → squelch → segmentation → Whisper STT (or CW decoder) → callsign span detection → text broadcast to all clients (per-user profanity filter applied; streaming partials update every ~2 s so text appears while the operator is still talking; callsign spans included for chat highlighting)
- **TX pipeline**: text input → abbreviation expansion → profanity filter → FCC ID wrapper → Piper TTS → PTT → audio output → `tx_echo` broadcast to all clients (includes sender, recipient callsign/name, and raw message text)
- **Auth**: session tokens validated on WebSocket connect; unauthenticated connections are rejected

---

## FCC compliance

Radio-TTY is designed as a **remote control point** for a single local station, not an internet repeater gateway or RoIP bridge. This distinction matters for GMRS operation under Part 95.

### What Radio-TTY is not

An internet repeater gateway (RoIP/VoIP bridge) creates an RF-to-internet-to-RF loop — audio received from a radio in one location is streamed across the public internet and retransmitted from a different radio elsewhere:

```
Radio RX → internet → remote gateway → Radio TX (different location)
```

EchoLink, AllStar Link, and IRLP work this way. Under FCC Part 95.1749, this type of internet interconnection is prohibited on GMRS — the service is intended as a localized family and community radio service, not a globally-linked network.

### What Radio-TTY is

The internet connection in Radio-TTY runs in one direction only — from a family member's browser to the local base station server — and terminates there:

```
Family member (internet) → text / TTS request → Base station server → Local radio TX
```

Nothing received over the air is forwarded across the internet to another transmitter. The server is the terminal destination. When a family member sends a TTS message from a phone or laptop, they are acting as a **remote control point** (§ 95.1745) — a licensed family member remotely operating their own local transmitter, equivalent to sitting at the base station microphone.

### Built-in safeguards

Radio-TTY enforces the access controls that § 95.1745 requires for remotely-operated GMRS stations:

- **Authenticated sessions only** — all WebSocket connections must present a valid session token; unauthenticated connections are rejected before any radio access is granted (PBKDF2-SHA256 passwords, 3-attempt lockout)
- **No RF-to-internet forwarding** — the RX pipeline terminates at transcription; received audio is never routed to a remote transmitter
- **Single-point topology** — one server, one radio; no routing layer exists to propagate transmissions across stations in different locations
- **Per-account listen-only mode** — individual users can be restricted to receive-only at the server level, preventing TX entirely

> **Note:** The EchoLink / AllStar gateway entry in the [future plugins table](#potential-future-plugins) describes a capability that would apply to **amateur radio use only**. Connecting a GMRS station to those internet-linked networks would violate Part 95.1749 and is not supported by Radio-TTY's default configuration.

---

## Features

### GMRS family hub

- **Multi-user accounts** — named family member profiles, each with their own password and per-user preferences
- **GMRS family callsign support** — a single GMRS licence covers the whole household; multiple contacts and NCS check-ins can share the same callsign, each identified by a distinct name (John Smith / WQZE123 and Jane Smith / WQZE123 appear as separate, independently editable records)
- **Mobile-optimized interface** — smartphones and tablets automatically receive a touch-friendly layout with bottom tab navigation (Chat, Stations, Journal); the full desktop panel layout is preserved for mouse/keyboard devices
- **Shared TX chat** — outgoing transmissions appear in every connected user's chat stream labeled `[TX]`; directed messages show `→ CALLSIGN — Name` between the sender and message text
- **Per-user settings** — dark mode, panel order, profanity filter, listen-only, read-aloud, notifications, spectrogram display, TTS voice, and speech speed are per-account and sync across devices
- Automatic FCC station ID every 15 minutes (GMRS §95.1751); callsigns spelled in NATO phonetics
- **Shared contacts list** — GMRS + HAM cross-reference, FCC-verified; supports import/export as JSON or CSV; multiple records per callsign for GMRS family licences
- FCC database callsign lookup and verification; **Verify All** batch-checks every contact simultaneously
- Callsign highlighting in chat — amber chips with tooltip; handles compact, NATO phonetic, spaced, and hyphenated forms; verified contacts show a green ✓ badge; fuzzy correction snaps STT near-misses to known callsigns
- **Pending stations bar** — WCAG 2.1 AA accessible; auto-detects unrecognized callsigns from received audio and prompts to add them; screen-reader friendly live region
- Quick messages bar — one-tap access to customisable pre-set phrases; supports `{Name}` placeholder; per-browser
- **Public family journal** — publish session logs to `/journal`, a no-login static page (last 10 entries, ADA-compliant)
- Session attendance tracking; AI-generated session journals (requires Gemini API key)
- Admin panel for station identity and user management

### Net Control Station + SKYWARN (built-in plugin)

NCS mode is admin-only and activates on demand. It is the reference implementation of the plugin architecture.

- **Live roster** — per-operator check-in with name, location, and six traffic priority levels (Routine, Priority, Emergency, General, Short Term, IN-n-Out); status toggling (Checked In / Standby / Out)
- **GMRS family roster** — multiple operators sharing a callsign appear as distinct roster rows; FCC verification badge updates live as background lookups complete
- **BREAK BREAK interrupt** — immediately drains the TX queue and broadcasts an emergency interrupt to all connected clients
- **15-second audio replay buffer** — click replay in the NCS panel to re-listen to the last 15 seconds of received audio at any time
- **Automatic contact handling** — unknown check-in callsigns are auto-added to contacts and FCC-verified in the background; ✓ badge appears in the roster when verification completes
- **SKYWARN weather alerts** — polls api.weather.gov every 5 minutes for Extreme/Severe alerts on a configured NWS county zone; triggers a red banner, browser notification, and auto-TX announcement (listen-before-talk enforced)
- **Periodic net ID announcements** — broadcasts a net ID at a configurable interval (default 10 min) with listen-before-talk check
- **End-of-net journal** — automatically saves a session journal with the full roster and transcript when NCS mode is deactivated

### Plugin system

Plugins subclass `BasePlugin` and receive async hook calls at five points in the radio pipeline — without modifying `server.py`. See [Plugin system](#plugin-system) for hook documentation and future plugin ideas.

### Core radio pipeline

- **Speech-to-text receive** — Whisper STT (`small.en` model) for voice; switchable to CW (Morse code) decoder via `rx_mode` config key
- **CW (Morse code) receive** — FFT-based tone detection (400–1200 Hz), bandpass filter, envelope extraction, adaptive WPM estimation, and full morse table including prosigns
- Text-to-speech transmit using Piper neural voices; voices watcher hot-reloads `.onnx` files without restart
- **Voice PTT (browser microphone)** — streams browser mic audio to the server for radio output with PTT keying; Whisper transcribes the audio and it appears in chat as a TX echo; max 120 s; self-echo prevention via STT mute during TX
- **Read Aloud** — per-user toggle that pipes finalized RX transcripts through Piper TTS and plays audio in the operator's browser
- **Browser notifications** — opt-in Web Notifications for final RX transcripts and SKYWARN alerts when the tab is in the background
- Real-time spectrogram waterfall with VAD and squelch indicators
- PTT modes: manual (UI-controlled), serial (RTS/DTR hardware line), or VOX (voice-operated)
- TTY/TDD abbreviation expansion and Q-signal support
- **Server Config panel** — admin UI for VAD threshold, Whisper model, PTT mode/port, audio monitor passthrough, and attendance tracking

---

## Plugin system

Plugins subclass `BasePlugin` (`backend/plugins/base.py`), register with the `PluginRegistry` singleton, and receive async hook calls at defined points in the RX and TX pipelines. No core files need modification to add a plugin.

### Hook points

| Hook | When it fires |
|------|--------------|
| `on_client_message_received` | A WebSocket message arrives from any connected client |
| `on_audio_rx_start` | Squelch opens — audio capture begins |
| `on_audio_rx_chunk` | Each VAD-segmented audio chunk delivered to STT |
| `on_rx_final` | Final Whisper transcript and detected callsign spans are ready |
| `on_audio_tx_pre_queue` | Synthesized audio is about to be sent to the PTT/TX queue |

### Reference implementation: NCS / SKYWARN

`backend/plugins/ncs.py` is the built-in reference plugin. It uses `on_rx_final` to detect callsigns in check-in transmissions, maintains a live roster broadcast over WebSocket, polls NWS CAP for weather alerts, and injects emergency announcements directly into the TX queue — all without touching `server.py`.

The frontend mirrors this pattern: `frontend/src/plugins/index.ts` defines `PluginDefinition` and `registerPlugin`, and `frontend/src/components/NCSPanel/` is the NCS plugin's React panel, mounted via `PluginSlot`.

### Adding a plugin

1. Create `backend/plugins/your_plugin.py` subclassing `BasePlugin`.
2. Override whichever async hook methods you need.
3. Register the plugin instance in `server.py` alongside the existing NCS registration.
4. Optionally create a React panel under `frontend/src/plugins/` and register it with `registerPlugin`.

### Potential future plugins

| Plugin | Hooks | What it would do |
|--------|-------|-----------------|
| **Meshtastic bridge** | `on_rx_final`, `on_audio_tx_pre_queue` | Forward GMRS transcripts to a LoRa mesh network; relay inbound mesh messages as TTS transmissions |
| **Repeater controller** | `on_audio_rx_start`, `on_audio_rx_chunk` | Auto-ID on interval, transmit timeout timer, courtesy tone, autopatch logic |
| **EchoLink / AllStar gateway** | `on_rx_final`, `on_audio_tx_pre_queue` | Bridge GMRS audio to internet-linked repeater networks via VoIP |
| **Scheduled voice briefing** | *(timer)* | Announce NWS hourly forecasts or custom reminders at configured times — without entering NCS mode |
| **DTMF decoder / paging** | `on_audio_rx_chunk` | Detect DTMF touch-tones and trigger macros, alerts, or automations |
| **Transmission logger** | `on_audio_rx_start`, `on_rx_final` | Write each transmission — timestamp, duration, detected callsigns, and transcript — to a log file or SQLite database |
| **EAS tone detector** | `on_audio_rx_chunk` | Recognize Emergency Alert System two-tone attention signals and surface an immediate visual/audio alert |
| **AI call summarizer** | `on_rx_final` | Generate a one-sentence briefing for each received transmission and push it alongside the transcript to all clients |

---

## Requirements

**Host machine:**
- Linux (Debian/Ubuntu recommended)
- PulseAudio (for audio routing)
- `/dev/snd` access (USB audio adapter or built-in)
- Serial port for hardware PTT (optional — manual PTT also supported)
- 2 GB RAM minimum (Whisper `small.en` ~464 MB)

**Models (not included in repo — downloaded by `setup.sh` before first run):**

| Path | Description | Size |
|------|-------------|------|
| `Models/STT/small.en/` | Whisper faster-whisper model | ~464 MB |
| `Voices/*.onnx` | Piper TTS voice models | varies |

`bash setup.sh` downloads both automatically (see [Installation](#installation)). To download only the Whisper model manually:
```bash
python bootstrap_models.py --model small.en
```

---

## Installation

### Option A — Docker Compose (recommended)

```bash
# Clone and enter the repo
git clone https://github.com/Xpiatio/Radio-TTY.git && cd Radio-TTY

# One-shot setup: creates directories, downloads models + voices,
# seeds data/config.json, and writes .env with your PulseAudio UID
bash setup.sh

# Set your callsign (and optionally audio devices / voice)
nano data/config.json

# Production start (frontend on :80, backend on :8765)
docker compose up --build
```

`setup.sh` accepts `--model base.en` / `--model medium.en` to use a different Whisper size, and `--voice-only` / `--skip-voices` to skip parts of the download. Run `bash setup.sh --help` for details.

Open `http://<host-ip>` from any browser on the network. On first startup, the **Setup** screen appears in the browser — enter your name, a password, and optional station info to create the admin account. You are signed in automatically once you submit.

**Headless / unattended deployment:** Set `RADIO_TTY_ADMIN_PASS` to skip the browser setup and create the admin account at startup instead:
```yaml
environment:
  - RADIO_TTY_ADMIN_PASS=your-password-here
```

**Development start** (frontend on :5173 with hot reload):
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

### Option B — Portainer (pre-built images)

The easiest Portainer path uses pre-built images from GitHub Container Registry — no source checkout needed.

**0. On the Docker host, run the prerequisite script to download models and voices into Docker volumes:**

```bash
# Download the script (or clone the repo and run from there)
curl -fsSL https://raw.githubusercontent.com/Xpiatio/Radio-TTY/master/prereq.sh -o prereq.sh
bash prereq.sh
```

This creates the three named volumes and populates them with the Whisper STT model (~464 MB) and default Piper TTS voices. Requires only `docker` — no Python or pip needed.

> **Why this step?** Docker named volumes are not visible as regular host folders. Files must be loaded into the volume before the stack starts — you can't add them by copying to a directory on the host after the fact.

**1. The volumes are created automatically by `prereq.sh`.** Verify in Portainer under Volumes → you should see:

| Volume name | Contents |
|---|---|
| `radio-tty-data` | Config, contacts, users, tokens, journals (auto-created on first run) |
| `radio-tty-voices` | Piper ONNX voice files (`*.onnx` + `*.onnx.json`) |
| `radio-tty-models` | faster-whisper model directory |

**2. In Portainer: Stacks → Add stack → Web editor**, paste the contents of [`docker-compose.portainer.yml`](docker-compose.portainer.yml) from this repository.

- Set `PULSE_UID` to your host user's UID before deploying: in Portainer go to **Stack → Environment variables** and add `PULSE_UID=<your UID>`. Find yours with `id -u`. The default is `1000`; if that matches your user you can skip this.
- Optionally set `RADIO_TTY_ADMIN_PASS` to bootstrap the admin account without the browser setup screen.

**3. Deploy the stack.** Visit `http://<host-ip>` — the Setup screen appears on first run.

**After a Radio-TTY update:** change the image tags in the stack file to the new version and click **Update the stack** in Portainer.


### Option B (alt) — Portainer with locally-built images

If you need to deploy custom source changes via Portainer:

```bash
cd /path/to/Radio-TTY
docker compose build
# Images are now available locally as radio-tty-backend and radio-tty-frontend
```

In Portainer use the same stack YAML but replace the `image:` lines with the local image names (`radio-tty-backend` / `radio-tty-frontend`) and substitute bind-mount paths for the named volumes.

### Option C — Native install

```bash
bash install.sh           # full install (downloads Whisper model)
bash install.sh --no-models  # skip model download

# Start the backend
source .venv/bin/activate
uvicorn backend.server:app --host 0.0.0.0 --port 8765

# Build and serve the frontend
cd frontend && npm ci && npm run build
# Serve dist/ with any static file server (nginx, caddy, etc.)
```

---

## First-time setup

1. Open `http://<host-ip>` — the **Setup** screen appears (only on first launch when no accounts exist).
2. Enter your display name, a password, and optionally your operator name, call sign, and location. Click **Create Account** — you are signed in immediately as admin.
   - The call sign and location you enter here are saved to your personal profile **and** written to the station config (`config.json`) as the station defaults. You can adjust them independently later — your profile under **Account → Edit Profile**, and the station defaults under **ADMIN → Station Identity**.
3. Open **ADMIN → Users** to create accounts for each family member.
4. Each person signs in from their own browser or device and sets their personal preferences.

> **HTTPS:** For public internet access, place a TLS-terminating reverse proxy (nginx, Caddy) in front of the app. Without TLS, session tokens travel in plaintext.

---

## Configuration

### Station config — `data/config.json`

Created from `data/config.json.example` on first install. Station-wide settings editable by admin users via the Admin panel.

| Key | Default | Description |
|-----|---------|-------------|
| `callsign` | `"N0CALL"` | Station callsign (shared by all users) |
| `name` | `""` | Station name |
| `location` | `""` | Station location |
| `radio_service` | `""` | `"GMRS"` or `"FRS"` |
| `voice` | `""` | Station-default Piper voice path (e.g. `"/app/Voices/en_US-ryan-high.onnx"`); settable via Admin Settings UI; used when a user has no personal voice set |
| `voices_dir` | *(derived)* | Directory to scan for `.onnx` voice files; defaults to the parent directory of `voice` or `/app/Voices` |
| `tts_length_scale` | `1.0` | TTS speed (lower = faster) |
| `input_device` | `-1` | Audio input device index (-1 = default) |
| `output_device` | `-1` | Audio output device index (-1 = default) |
| `system_monitor_sink` | `""` | PulseAudio sink name for loopback monitoring |
| `whisper_model` | `"small.en"` | Whisper model name |
| `vad_threshold` | `0.5` | Silero VAD sensitivity (0.0–1.0) |
| `rx_mode` | `"voice"` | `"voice"` (Whisper STT, default) or `"cw"` (Morse code decoder) |
| `ptt_mode` | `"manual"` | `"manual"`, `"serial"`, or `"vox"` |
| `ptt_serial_port` | `""` | e.g. `"/dev/ttyUSB0"` |
| `ptt_serial_line` | `"RTS"` | `"RTS"` or `"DTR"` |
| `fuzzy_callsign` | `false` | Fuzzy callsign matching in received text (station-wide) |
| `monitor_enabled` | `false` | Audio monitor passthrough |
| `monitor_passthrough` | `false` | Route captured audio to output device simultaneously (monitor passthrough) |
| `spectro_freq_range` | `"full"` | `"voice"` (300–3400 Hz) or `"full"` (0–8 kHz) |
| `gemini_api_key` | `""` | Google Gemini API key (for AI journals) |
| `journals_dir` | `"/data/journals"` | Where session journals are saved |
| `contacts_file` | `"/data/contacts.json"` | Shared contacts store |
| `attendance` | `{"enabled": false}` | Session attendance tracking toggle |
| `ncs_zone` | `""` | NWS county zone code for SKYWARN alerts (e.g. `"MIZ025"`); empty = disabled |
| `ncs_announcement_interval` | `600` | Seconds between periodic net ID announcements when NCS mode is active |

> **Note:** `filter_profanity`, `listen_only`, `spectro_colormap`, and `spectro_time_window_s` are **per-user preferences** stored in `data/users.json`, not in `config.json`.

### Per-user preferences

Each user account stores these settings independently. They are managed through the in-app UI and do not need manual editing.

| Preference | Default | Description |
|------------|---------|-------------|
| `dark_mode` | `false` | Dark/light theme |
| `panel_order` | `["config","attendance","journal"]` | Drag-and-drop panel layout |
| `filter_profanity` | `true` | PG-13 profanity masking for this user |
| `listen_only` | `false` | Disable TX for this user |
| `spectro_colormap` | `"viridis"` | `"viridis"` or `"grayscale"` |
| `spectro_time_window_s` | `30` | Spectrogram scroll window in seconds |
| `tts_voice` | `""` | Piper voice for this user's transmissions (`""` = use station default) |
| `tts_length_scale` | `0` | TTS speech speed override (`0` = use station default; lower = faster, e.g. `0.8`) |
| `read_aloud` | `false` | Play finalized RX transcripts through TTS audio in the browser |
| `notifications_enabled` | `false` | Browser notifications for incoming RX and SKYWARN alerts when the tab is in the background (requires browser permission) |

### Environment variables

**Docker Compose (`.env` file — generated by `setup.sh`, see `.env.example`):**

| Variable | Default | Description |
|----------|---------|-------------|
| `PULSE_UID` | `1000` | Host user ID used to locate the PulseAudio socket at `/run/user/<UID>/pulse`. Run `id -u` to find yours. |
| `COMPUTE_BACKEND` | `cpu` | Whisper inference backend: `cpu`, `cuda` (NVIDIA GPU + Container Toolkit), or `openvino`. |

**Backend (set in the service's `environment:` block):**

| Variable | Description |
|----------|-------------|
| `RADIO_TTY_ADMIN_PASS` | If set and no users exist, creates an "Admin" account with this password at startup (headless deployments). Without it, the browser Setup screen handles first-run account creation. |
| `RADIO_TTY_CONFIG` | Path to `config.json` (default: `/data/config.json`) |
| `RADIO_TTY_USERS` | Path to `users.json` (default: `/data/users.json`) |
| `RADIO_TTY_TOKENS` | Path to `tokens.json` (default: `/data/tokens.json`) |

---

## Project structure

```
Radio-TTY/
├── backend/
│   ├── server.py               # FastAPI app + WebSocket router
│   ├── config.py               # ServerConfig typed wrapper
│   ├── auth_routes.py          # /auth/setup-status, /auth/setup, /auth/login, /auth/logout, /auth/me, /auth/profiles
│   ├── audio/
│   │   ├── capture.py          # PulseAudio loopback / sounddevice input
│   │   ├── squelch.py          # SquelchDetector with pre-trigger ring buffer
│   │   ├── spectro_task.py     # SpectroTask — FFT → broadcast
│   │   └── silence_watchdog.py
│   ├── stt/
│   │   ├── worker.py           # STTWorker — capture → VAD → segment → transcribe (voice or CW)
│   │   ├── segmenter.py        # SpeechSegmenter
│   │   └── transcriber.py      # WhisperTranscriber + hallucination filter
│   ├── cw/
│   │   └── decoder.py          # CWDecoder — FFT tone detection, adaptive WPM, morse table
│   ├── text/
│   │   ├── shorthand.py        # TTY/TDD + Q-signal + CW abbreviation expansion
│   │   ├── phonetics.py        # NATO phonetic alphabet conversion
│   │   ├── callsigns.py        # Callsign detection (compact, NATO phonetic, spaced, hyphenated), span location, fuzzy match, digit spacing
│   │   ├── profanity.py        # Profanity masking
│   │   └── placeholders.py     # {N} token substitution
│   ├── fcc/
│   │   ├── crossref.py         # FCC API client + callsign verification
│   │   ├── auto_add.py         # Async background FCC lookup worker
│   │   └── id_rule.py          # FCC 15-minute ID rule + format helpers
│   ├── persistence/
│   │   ├── contacts.py         # ContactsStore + GMRS/HAM cross-reference; deduplicates by (callsign, name) to support GMRS family licences
│   │   ├── attendance.py       # Session attendance tracker
│   │   ├── journal.py          # Journal save/load/publish (public HTML generation)
│   │   ├── users.py            # UsersStore — PBKDF2 passwords, lockout, per-user prefs
│   │   └── tokens.py           # TokenStore — session tokens, expiry, purge
│   ├── ai/
│   │   └── gemini_client.py    # AI journal generation
│   ├── net/
│   │   └── online.py           # Internet connectivity check (60s TTL cache)
│   └── plugins/
│       ├── base.py             # BasePlugin with async hook methods
│       ├── registry.py         # PluginRegistry singleton — collects and dispatches hooks
│       └── ncs.py              # NCS/SKYWARN plugin — roster (keyed by callsign|name for GMRS family support), BREAK BREAK, replay buffer, NWS CAP
├── frontend/
│   └── src/
│       ├── App.tsx             # Root component — auth guard, WS state, message dispatch
│       ├── hooks/
│       │   ├── useAuth.ts      # Login/logout, token management
│       │   ├── useMobileDetect.ts  # Detects touch devices via pointer:coarse media query
│       │   └── useWebSocket.ts # WS connection with token auth + backoff reconnect
│       ├── plugins/
│       │   └── index.ts        # PluginDefinition, PluginProps, registerPlugin helper
│       ├── components/
│       │   ├── SetupScreen/    # First-run admin account creation form
│       │   ├── LoginScreen/    # Profile picker + password form
│       │   ├── AccountMenu/    # Profile chip — edit, change password, settings, admin, sign out
│       │   ├── UsersPanel/     # Admin user management
│       │   ├── NCSPanel/       # Net Control Station panel — roster (supports GMRS family), BREAK BREAK, replay, alerts
│       │   ├── ContactsDialog/ # Contacts CRUD with multi-callsign support, import/export, FCC lookup
│       │   ├── PluginSlot/     # Thin wrapper mounting plugin React components
│       │   ├── DesktopApp/     # Desktop layout shell
│       │   ├── MobileApp/      # Mobile layout shell with BottomNavigation tabs
│       │   └── …               # (other existing components)
│       ├── theme.ts            # MUI theme factory makeTheme(dark)
│       └── types/ws.ts         # All WebSocket message TypeScript types
├── data/
│   ├── config.json             # Station config (gitignored)
│   ├── contacts.json           # Shared contacts (gitignored)
│   ├── users.json              # User accounts (gitignored)
│   ├── tokens.json             # Active session tokens (gitignored)
│   ├── journals/               # Saved session journals
│   └── public/
│       ├── journal.html        # Public family journal page
│       └── journal-manifest.json
├── setup.sh                    # one-shot setup for docker compose (run first)
├── prereq.sh                   # one-shot setup for Portainer / named volumes
├── install.sh                  # native (non-Docker) install
├── bootstrap_models.py         # manual Whisper model downloader
├── .env.example                # documents PULSE_UID / COMPUTE_BACKEND for docker compose
├── docker-compose.yml          # production build-from-source compose
├── docker-compose.dev.yml      # dev overlay (hot reload)
└── docker-compose.portainer.yml  # pre-built image stack for Portainer
```

---

## Development

**Run tests:**
```bash
cd /path/to/Radio-TTY
python -m pytest backend/tests/ -q
```

**Backend only (hot reload):**
```bash
source .venv/bin/activate
uvicorn backend.server:app --host 0.0.0.0 --port 8765 --reload
```

**Frontend only (Vite dev server):**
```bash
cd frontend && npm run dev
```

Set `VITE_WS_URL=ws://localhost:8765/ws` if the backend is not on the same host.

---

## License

See [LICENSE](LICENSE). Radio-TTY is derived from GMRS-TTY under its original license terms.
