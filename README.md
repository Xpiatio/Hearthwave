# Radio-TTY

A web-based TTY/TDD radio communication system for GMRS and amateur radio operators. Family members each sign in with their own account and operate from any tablet, phone, or browser — no software installation required on client devices.

Radio-TTY is a fork of GMRS-TTY that replaces the desktop PySide6 UI with a browser-based React frontend communicating over WebSocket.

---

## How it works

```
Browser (any device)
      │  WebSocket :8765 (?token=…)
      ▼
FastAPI Backend  ──►  PulseAudio / sounddevice
      │                     │
   Piper TTS            Whisper STT
      │                     │
   Serial PTT          Silero VAD
      ▼                     ▼
    Radio               Spectrogram
```

- **RX pipeline**: audio capture → VAD → squelch → segmentation → Whisper STT → text broadcast to all clients (per-user profanity filter applied)
- **TX pipeline**: text input → abbreviation expansion → profanity filter → FCC ID wrapper → Piper TTS → PTT → audio output → `tx_echo` broadcast to all clients
- **Auth**: session tokens validated on WebSocket connect; unauthenticated connections are rejected

---

## Features

- **Multi-user accounts** — named family member profiles, each with their own password and per-user preferences
- **Shared TX chat** — outgoing transmissions appear in every connected user's chat stream, labeled `[TX]` with the sender's callsign
- **Per-user settings** — dark mode, panel order, profanity filter, listen-only, spectrogram display, and TTS voice are per-account and sync across devices
- **Public family journal** — publish session logs to `/journal`, a no-login static page (last 10 entries, ADA-compliant)
- Real-time spectrogram with VAD and squelch indicators
- Speech-to-text receive using Whisper (`small.en` model)
- Text-to-speech transmit using Piper neural voices
- Automatic FCC station ID every 15 minutes (GMRS requirement)
- FCC database callsign lookup and verification
- Shared contacts list (GMRS + HAM cross-reference, FCC-verified)
- TTY abbreviation expansion and Q-signal support
- NATO phonetic callsign spelling
- Session attendance tracking
- AI-generated session journals (requires Gemini API key)
- Admin panel for station identity and user management

---

## Requirements

**Host machine:**
- Linux (Debian/Ubuntu recommended)
- PulseAudio (for audio routing)
- `/dev/snd` access (USB audio adapter or built-in)
- Serial port for hardware PTT (optional — manual PTT also supported)
- 4 GB RAM minimum (Whisper `small.en` ~464 MB, speaker model ~86 MB)

**Models (not included in repo — must be placed before first run):**

| Path | Description | Size |
|------|-------------|------|
| `Models/STT/small.en/` | Whisper faster-whisper model | ~464 MB |
| `Models/Speaker/ecapa-tdnn/` | Speaker recognition model | ~86 MB |
| `Voices/*.onnx` | Piper TTS voice models | varies |

Download the Whisper model:
```bash
python bootstrap_models.py --model small.en
```

Voices and the speaker model must be copied from an existing install or obtained separately.

---

## Installation

### Option A — Docker Compose (recommended)

```bash
# Clone and enter the repo
git clone https://github.com/Xpiatio/Radio-TTY.git && cd Radio-TTY

# Place models (see Requirements above)

# Copy and edit config
cp data/config.json.example data/config.json
nano data/config.json   # set callsign, audio devices, voice

# Production start (frontend on :80, backend on :8765)
docker compose up --build
```

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

**1. Create three Docker volumes in Portainer (Volumes → Add volume):**

| Volume name | Contents |
|---|---|
| `radio-tty-data` | Config, contacts, users, tokens, journals (auto-created on first run) |
| `radio-tty-voices` | Piper ONNX voice files (`*.onnx` + `*.onnx.json`) |
| `radio-tty-models` | faster-whisper and speaker recognition model directories |

If your models/voices live at a known host path, use bind mounts instead (see the stack file comments).

**2. In Portainer: Stacks → Add stack → Web editor**, paste the contents of [`docker-compose.portainer.yml`](docker-compose.portainer.yml) from this repository.

- Adjust `/run/user/1000/pulse` if your host user is not UID 1000 (`id -u` to check).
- Optionally set `RADIO_TTY_ADMIN_PASS` to bootstrap the admin account without the browser setup screen.

**3. Deploy the stack.** Visit `http://<host-ip>` — the Setup screen appears on first run.

**After a Radio-TTY update:** change the image tags in the stack file to the new version and click **Update the stack** in Portainer.

> **Note:** The PulseAudio socket path `/run/user/1000/pulse` assumes UID 1000. Adjust if your user has a different UID (`id -u`).

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
| `voice` | `""` | Station-default Piper voice path (e.g. `"/Voices/en_US-ryan-high.onnx"`); used when a user has no personal voice set |
| `voices_dir` | *(derived)* | Directory to scan for `.onnx` voice files; defaults to the parent directory of `voice` or `/Voices` |
| `tts_length_scale` | `1.0` | TTS speed (lower = faster) |
| `input_device` | `-1` | Audio input device index (-1 = default) |
| `output_device` | `-1` | Audio output device index (-1 = default) |
| `system_monitor_sink` | `""` | PulseAudio sink name for loopback monitoring |
| `whisper_model` | `"small.en"` | Whisper model name |
| `vad_threshold` | `0.5` | Silero VAD sensitivity (0.0–1.0) |
| `ptt_mode` | `"manual"` | `"manual"` or `"serial"` |
| `ptt_serial_port` | `""` | e.g. `"/dev/ttyUSB0"` |
| `ptt_serial_line` | `"RTS"` | `"RTS"` or `"DTR"` |
| `fuzzy_callsign` | `false` | Fuzzy callsign matching in received text (station-wide) |
| `monitor_enabled` | `false` | Audio monitor passthrough |
| `spectro_freq_range` | `"full"` | `"voice"` (300–3400 Hz) or `"full"` (0–8 kHz) |
| `gemini_api_key` | `""` | Google Gemini API key (for AI journals) |
| `journals_dir` | `"/data/journals"` | Where session journals are saved |
| `contacts_file` | `"/data/contacts.json"` | Shared contacts store |

> **Note:** `filter_profanity`, `listen_only`, `spectro_colormap`, and `spectro_time_window_s` are now **per-user preferences** stored in `data/users.json`, not in `config.json`.

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

### Environment variables

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
│   │   ├── worker.py           # STTWorker — capture → VAD → segment → transcribe
│   │   ├── segmenter.py        # SpeechSegmenter
│   │   └── transcriber.py      # WhisperTranscriber + hallucination filter
│   ├── text/
│   │   ├── shorthand.py        # TTY/TDD + Q-signal + CW abbreviation expansion
│   │   ├── phonetics.py        # NATO phonetic alphabet conversion
│   │   ├── callsigns.py        # Callsign detection, fuzzy match, digit spacing
│   │   ├── profanity.py        # Profanity masking
│   │   └── placeholders.py     # {N} token substitution
│   ├── fcc/
│   │   ├── crossref.py         # FCC API client + callsign verification
│   │   ├── auto_add.py         # Async background FCC lookup worker
│   │   └── id_rule.py          # FCC 15-minute ID rule + format helpers
│   ├── persistence/
│   │   ├── contacts.py         # ContactsStore + GMRS/HAM cross-reference
│   │   ├── attendance.py       # Session attendance tracker
│   │   ├── journal.py          # Journal save/load/publish (public HTML generation)
│   │   ├── users.py            # UsersStore — PBKDF2 passwords, lockout, per-user prefs
│   │   └── tokens.py           # TokenStore — session tokens, expiry, purge
│   ├── ai/
│   │   └── gemini_client.py    # AI journal generation
│   └── net/
│       └── online.py           # Internet connectivity check (60s TTL cache)
├── frontend/
│   └── src/
│       ├── App.tsx             # Root component — auth guard, WS state, message dispatch
│       ├── hooks/
│       │   ├── useAuth.ts      # Login/logout, token management
│       │   └── useWebSocket.ts # WS connection with token auth + backoff reconnect
│       ├── components/
│       │   ├── SetupScreen/    # First-run admin account creation form
│       │   ├── LoginScreen/    # Profile picker + password form
│       │   ├── AccountMenu/    # Profile chip — edit, change password, sign out
│       │   ├── UsersPanel/     # Admin user management
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
├── docker-compose.yml
├── docker-compose.dev.yml
└── install.sh
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
