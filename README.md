# Radio-TTY

A web-based TTY/TDD radio communication system for GMRS and amateur radio operators. Multiple household members can operate from their own tablets, phones, or browsers simultaneously — no software installation required on client devices.

Radio-TTY is a fork of GMRS-TTY that replaces the desktop PySide6 UI with a browser-based React frontend communicating over WebSocket.

---

## How it works

```
Browser (any device)
      │  WebSocket :8765
      ▼
FastAPI Backend  ──►  PulseAudio / sounddevice
      │                     │
   Piper TTS            Whisper STT
      │                     │
   Serial PTT          Silero VAD
      ▼                     ▼
    Radio               Spectrogram
```

- **RX pipeline**: audio capture → VAD → squelch → segmentation → Whisper STT → text broadcast to all clients
- **TX pipeline**: text input → abbreviation expansion → profanity filter → FCC ID wrapper → Piper TTS → PTT → audio output
- **Clients**: receive the same real-time chat stream; any client can transmit

---

## Features

- Real-time spectrogram with VAD and squelch indicators
- Speech-to-text receive using Whisper (`small.en` model)
- Text-to-speech transmit using Piper neural voices
- Automatic FCC station ID every 15 minutes (GMRS requirement)
- FCC database callsign lookup and verification
- Shared contacts list (GMRS + HAM cross-reference, FCC-verified)
- TTY abbreviation expansion and Q-signal support
- NATO phonetic callsign spelling
- Profanity filter (PG-13, configurable)
- Session attendance tracking
- AI-generated session journals (requires Gemini API key)
- Dark mode + touch-optimized UI
- Multi-operator: any number of browser clients, all views stay in sync

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

# Development start (frontend on :5173 with hot reload)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Open `http://<host-ip>` from any browser on the network.

### Option B — Native install

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

## Configuration

Config file: `data/config.json` (created from `data/config.json.example` on first install).

| Key | Default | Description |
|-----|---------|-------------|
| `callsign` | `"N0CALL"` | Your station callsign |
| `name` | `""` | Operator name |
| `location` | `""` | Station location |
| `radio_service` | `""` | `"GMRS"` or `"FRS"` |
| `voice` | `""` | Piper voice name (e.g. `"ryan-high"`) |
| `tts_length_scale` | `1.0` | TTS speed (lower = faster) |
| `input_device` | `-1` | Audio input device index (-1 = default) |
| `output_device` | `-1` | Audio output device index (-1 = default) |
| `system_monitor_sink` | `""` | PulseAudio sink name for loopback monitoring |
| `whisper_model` | `"small.en"` | Whisper model name |
| `vad_threshold` | `0.5` | Silero VAD sensitivity (0.0–1.0) |
| `ptt_mode` | `"manual"` | `"manual"` or `"serial"` |
| `ptt_serial_port` | `""` | e.g. `"/dev/ttyUSB0"` |
| `ptt_serial_line` | `"RTS"` | `"RTS"` or `"DTR"` |
| `filter_profanity` | `true` | Enable PG-13 profanity masking |
| `fuzzy_callsign` | `false` | Fuzzy callsign matching in received text |
| `listen_only` | `false` | Disable all TX paths |
| `monitor_enabled` | `false` | Audio monitor passthrough |
| `spectro_colormap` | `"viridis"` | `"viridis"` or `"grayscale"` |
| `spectro_freq_range` | `"full"` | `"voice"` (300–3400 Hz) or `"full"` (0–8 kHz) |
| `spectro_time_window_s` | `30` | Spectrogram scroll window in seconds |
| `gemini_api_key` | `""` | Google Gemini API key (for AI journals) |
| `journals_dir` | `"/data/journals"` | Where session journals are saved |
| `contacts_file` | `"/data/contacts.json"` | Shared contacts store |

Config changes made via the UI are persisted automatically. The `set_admin_config` fields (callsign, name, location, Gemini key, journals directory) require a server restart to fully take effect.

---

## Project structure

```
Radio-TTY/
├── backend/
│   ├── server.py           # FastAPI app + WebSocket router
│   ├── config.py           # ServerConfig typed wrapper
│   ├── audio/
│   │   ├── capture.py      # PulseAudio loopback / sounddevice input
│   │   ├── squelch.py      # SquelchDetector with pre-trigger ring buffer
│   │   ├── spectro_task.py # SpectroTask — FFT → broadcast
│   │   └── silence_watchdog.py
│   ├── stt/
│   │   ├── worker.py       # STTWorker — capture → VAD → segment → transcribe
│   │   ├── segmenter.py    # SpeechSegmenter
│   │   └── transcriber.py  # WhisperTranscriber + hallucination filter
│   ├── text/
│   │   ├── shorthand.py    # TTY/TDD + Q-signal + CW abbreviation expansion
│   │   ├── phonetics.py    # NATO phonetic alphabet conversion
│   │   ├── callsigns.py    # Callsign detection, fuzzy match, digit spacing
│   │   ├── profanity.py    # Profanity masking
│   │   └── placeholders.py # {N} token substitution
│   ├── fcc/
│   │   ├── crossref.py     # FCC API client + callsign verification
│   │   ├── auto_add.py     # Async background FCC lookup worker
│   │   └── id_rule.py      # FCC 15-minute ID rule + format helpers
│   ├── persistence/
│   │   ├── contacts.py     # ContactsStore + GMRS/HAM cross-reference
│   │   └── attendance.py   # Session attendance tracker
│   ├── ai/
│   │   └── gemini_client.py  # AI journal generation
│   └── net/
│       └── online.py       # Internet connectivity check (60s TTL cache)
├── frontend/
│   └── src/
│       ├── App.tsx         # Root component — WS state, message dispatch
│       ├── theme.ts        # MUI theme factory makeTheme(dark, touch)
│       └── types/ws.ts     # All WebSocket message TypeScript types
├── data/
│   ├── config.json         # Runtime config (gitignored)
│   └── contacts.json       # Shared contacts (gitignored)
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

390 tests pass. Two pre-existing failures in `test_auto_add.py` require `pytest-asyncio` (not installed by default).

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
