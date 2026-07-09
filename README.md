# Hearthwave

A GMRS hub that turns a home server or x86 mini PC into a shared radio
operating station for every member of your household or neighborhood watch group.
Incoming transmissions are transcribed by speech-to-text and streamed to all
connected devices; outgoing messages are synthesized to speech, automatically
wrapped with the FCC station callsign (§95.1751), and transmitted over the air.
Each family member or watch volunteer signs in from their own phone, tablet, or
laptop — no app install required.

Net Control Station (NCS) mode is built in, with a live check-in roster, six
traffic priority levels, and SKYWARN weather alerts sourced directly from the
National Weather Service. On top of that, Hearthwave has a true installable plugin
system: drop a plugin into `/data/plugins` (or upload a `.zip` from the admin
Settings) and it hot-loads into the radio pipeline without touching core server
logic. MeshCore — a bridge that forwards every transmission onto a LoRa mesh for
off-grid reach — ships as an example plugin, alongside a Meshtastic equivalent, to
show how it's done.

Hearthwave is a fork of GMRS-TTY that replaces the desktop PySide6 UI with a
browser-based React frontend communicating over WebSocket.

> **Latest release:** v2.15.0

## Who uses it

- **Families** — one GMRS license covers the whole household. Each person gets
  their own account with their own voice and preferences. Kids on tablets, parents
  on laptops, grandparents with large, high-contrast type — everyone on the same channel.
- **Neighborhood watch groups** — deploy Hearthwave as the watch's base station.
  Assign listen-only accounts to patrol volunteers and TX-capable accounts to
  designated net control operators. The NCS roster tracks who is active on each
  patrol; SKYWARN alerts auto-announce over the air when severe weather approaches,
  and trained spotters can file standardized SKYWARN spot reports straight from the net.
- **Non-speaking operators** — the AAC interface turns Hearthwave into a
  communication device that transmits: tap large symbol buttons to build a
  message, press SEND, and it is spoken over the air in your own chosen voice.
  Deaf and hard-of-hearing operators read every transmission as live text.

## Features

- **AAC interface** — a per-user toggle swaps the entire UI for a full-screen
  AAC (Augmentative and Alternative Communication) screen, like the
  symbol-button speech devices used by non-speaking people: category tabs of
  large emoji + label buttons build a message in a sentence strip, and one big
  SEND button speaks it over the radio. The button grid is fully user-editable
  (buttons, categories, `{Name}`/`{callsign}` placeholders) and follows the
  user to any device
- **STT calibration wizard** — read a fixed reference passage into the radio
  and Hearthwave automatically sweeps gain mode, noise-profile denoise, and
  Whisper model against it, ranks each combination by word-error-rate, and
  applies whichever one you choose
- **RX audio level meter** — a live receive-audio level meter sits above the
  chat, so you can see signal strength and confirm the radio is feeding audio at
  a glance
- **Stations & Journal open full-size** — on tablets and desktop, the Stations
  and Journal views now open as centered modal dialogs (the same treatment as
  Contacts), filling the window instead of a cramped inline strip. Phones keep
  their bottom-navigation tabs
- **Noise-profile denoise** — samples the channel's own noise floor while the
  squelch is closed and hands it to the denoiser as a stationary noise estimate,
  instead of letting it guess from the speech-bearing audio. Off by default
  pending word-error-rate proof on real recordings; A/B it offline with the
  eval harness's `--noise-profile auto`
- **Callsign auto-correct** — optionally rewrites a misheard callsign in the
  final transcript to your roster's canonical call (single-character corrections
  only; if two known calls are equally close, nothing changes). Corrected chips
  get a dotted underline and a tooltip showing what was actually heard, and the
  journal, read-aloud, and plugins all see the corrected text
- **Deeper eval harness** — the offline word-error-rate harness can now A/B
  decode tuning (beam size, repetition penalty, hotwords, per-word confidence),
  VAD timing, prompt phrasing, and the noise profile against labelled recordings
- **Selectable audio gain stage** — choose how receive audio is leveled before
  transcription, right from admin Settings: dynamic AGC (default), a gentler
  one-shot RMS normalize, or off. The offline STT eval harness can A/B all three
  against word-error-rate, so you can tune for your radios instead of guessing.
- **Installable plugins** — extend the radio pipeline without touching core code:
  drop a plugin folder into `/data/plugins` or upload a `.zip` from admin Settings,
  and it hot-loads with its own declarative config UI. Install, reload, and remove
  plugins live from the Settings dialog; namespaced config keeps each plugin's
  settings isolated. MeshCore and Meshtastic ship as example plugins; NCS stays
  built in
- **Speech-recognition vocabulary biasing** — transcription is weighted toward radio vocabulary (NATO alphabet, procedure words, Q-codes) and your contacts' callsigns, with auto-refresh on contact changes and a manual Rescan button.
- **Monitoring beacon** — an optional, periodic presence call
  (`{callsign} Hearthwave base, monitoring.`) on a fixed timer. Off by default;
  suppressed during NCS mode, transmits only on a clear channel, and doubles as
  your FCC station ID when it airs (configurable interval and phrase)
- **Refreshed brand** — a new Hearthwave logo (a home sheltering a radio set,
  with signal waves cresting off the roof) across the login screen, top bar,
  About dialog, and favicon, plus a redesigned project website that defaults to
  a warm light theme with a one-click dark-mode toggle
- **Two-tier transcription** — a fast model streams live partials while a
  larger model (`large-v3-turbo`, `distil-large-v3`, or `large-v3`) re-transcribes
  each completed transmission in full, replacing the live text with a
  higher-accuracy final — without truncating long overs or dropping a callsign
  the live pass already heard. New installs default to **Auto**: stage a final
  model and it's picked up on the next Listen toggle, no configuration needed
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
- **Net scripts & round-table** — configurable opening preamble and closing
  scripts read over the air, plus a round-table caller that cycles the roster
  prompting each station for traffic
- **SKYWARN alerts** — live National Weather Service alerts pushed to all users
  with browser notification support
- **SKYWARN spot reports** — file a severe-weather report from a criteria-gated
  form (hail ≥1″, wind ≥40 mph, tornado/funnel/wall cloud, flooding) that builds
  a standardized on-air report and transmits, logs, and journals it
- **Installable plugin system** — drop a plugin directory under `/data/plugins`
  or upload it as a `.zip` from the admin **Settings → Plugins** tab; plugins
  hot-load (install/reload/uninstall with no restart) and declare their settings
  declaratively, so the frontend renders a generic settings form automatically —
  no browser code in a plugin. MeshCore (a USB Companion LoRa-mesh bridge) and
  Meshtastic ship as mutually-exclusive **example plugins** you can study and
  copy; see the authoring guide at [docs/plugins.md](docs/plugins.md)
- **Journals** — AI-assisted session summaries with full transcript export
- **Contacts** — shared contact book with FCC license lookup; multiple family members sharing the same GMRS callsign are stored as separate records and addressed individually by name
- **Spectrogram** — real-time frequency display (voice or full range, viridis or
  grayscale colormaps)
- **Attendance panel** — automatic log of every station heard this session
- **Responsive layout** — phone, tablet, and desktop layouts chosen automatically; tablets get the full desktop view with larger, touch-friendly controls
- **WCAG 2.2 AA** — full keyboard navigation, screen reader support, and ARIA
  labelling throughout the interface
- **Chat vs Transmit split** — a CHAT action broadcasts a message to all operators' displays without keying the radio; TRANSMIT is the over-the-air action; chat lines are marked `[CHAT]` and are profanity-filtered per recipient
- **Shared message stream** — the message log (RX, TX, and CHAT entries) is held server-side and shared across the base station and every web/mobile login, so a client that signs in or refreshes later sees the history accumulated since the last clear. The stream is kept in memory (a backend restart starts fresh) and capped to the most recent messages. Clearing the log is **admin-only and global** — an admin clear wipes the chat for everyone at once, after a confirmation prompt
- **Unified Settings** — one **Settings** dialog for everyone: a **Preferences** tab available to all users (audio input/output devices, profanity filter, fuzzy callsign match, callsign auto-correct, spectrogram options) plus admin-only **Station** and **System** tabs. A single **Save** in the footer commits changes across every tab at once; non-admins see only the Preferences tab
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
- **Gradient panel headers** — each panel type has a typed gradient (NCS uses a
  deeper blue; Journals and Attendance use base navy)
- **WCAG 2.2 AA compliant** — all colour pairs meet 4.5:1 contrast for normal
  text and 3:1 for large text and UI components

### Desktop layout

```
┌──────────────────────────── TopBar ─────────────────────────────┐
│ Callsign · Status · PTT · ABORT TX · Waterfall · Account        │
├─────────────────────────────────────────────────────────────────┤
│  NCS panel (when opened) · Stations/Journal open as modal dialogs │
├─────────────────────────────────────────────────────────────────┤
│  Pending Stations bar                                             │
├──────────────────────────┬──────────────────────────────────────┤
│  Spectrogram (waterfall)  │   Chat Display (scrollable log)       │
├──────────────────────────┴──────────────────────────────────────┤
│  StatusRow · QuickMessages · Message Input                        │
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

For the full rule-by-rule breakdown — verbatim Part 95E citations, the
remote-control vs. repeater-linking distinction, and every automated function
disclosed — see [Legality & FCC compliance](https://xpiatio.github.io/Hearthwave/legality.html).

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

Pick the input/output devices and PTT mode on first run from the Setup screen.
Audio devices can be changed later on the **Preferences** tab of **Settings**;
PTT mode lives on the admin-only **System** tab.

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

Hearthwave has a true installable plugin system. A plugin is a directory
containing a `plugin.py` placed under `/data/plugins/<id>/` (the directory name is
the plugin id), or uploaded as a `.zip` from the admin **Settings → Plugins** tab.
Plugins hot-load — install, reload, and uninstall happen live with no restart (a
server restart is always a safe fallback). **Plugins ship no browser/React code:**
they declare their settings via a config schema and the frontend renders a generic
settings form automatically.

### Writing a plugin

Plugins import everything from the stable SDK at `backend/plugins/sdk.py`:

```python
from backend.plugins.sdk import BasePlugin, PluginManifest, ConfigField, PluginContext
```

A plugin subclasses `BasePlugin` and declares a `PluginManifest`:

```python
from backend.plugins.sdk import BasePlugin, PluginManifest, ConfigField


class WordGuard(BasePlugin):
    manifest = PluginManifest(
        id="word-guard",
        name="Word Guard",
        description="Blocks outgoing transmissions containing a banned word.",
        version="1.0.0",
        default_enabled=False,
        config_schema=(
            ConfigField(key="banned_word", label="Banned word", type="text", default="classified"),
        ),
    )

    async def on_audio_tx_pre_queue(self, payload: dict) -> dict | None:
        cfg = self.ctx.get_config().plugin_config("word-guard")
        word = cfg.get("banned_word", "")
        if word and word in payload.get("text", "").lower():
            return None            # None blocks the transmit
        return payload             # return the (optionally modified) payload to allow it
```

The loader binds a `PluginContext` to `self.ctx`, calls `setup()`, registers the
plugin, then dispatches `on_config_changed`. Core services are reached through
`self.ctx` — `broadcast`, `enqueue_tx`, `get_config`, `channel_clear`, `data_dir`,
and `logger`. The `PluginManifest` fields are `id`, `name`, `description`,
`version`, `default_enabled`, `conflicts_with`, `config_schema`, and
`tx_composition`.

### Configuration

Each plugin's settings live under `config["plugins"][<id>]` — an `enabled` flag
plus one key per `config_schema` field — and are managed from the admin-only
**Settings → Plugins** tab: a list of installed plugins each with an enable
toggle, an auto-generated settings form, version, a conflicts note, and
Reload/Uninstall buttons, plus an **Install plugin (.zip)** button. Because
plugins run with full server access, the tab carries a warning to that effect.

### Hooks

Every hook is a no-op by default — override only the ones you need. They fire in
registration order, and dispatch is exception-isolated (a raising hook is logged
and skipped; for `on_audio_tx_pre_queue` a raising plugin is treated as
pass-through, not a block).

| Hook | Sync/async | Fires when | Return value |
| --- | --- | --- | --- |
| `setup()` | async | Once when the plugin is loaded, after `ctx` is bound | Ignored. Acquire resources here. |
| `on_unload()` | async | When the plugin is reloaded or uninstalled | Ignored. Release resources here. |
| `on_config_changed(config)` | async | Server config is (re)loaded — once at load and again after every admin save | Ignored. React to setting changes here: open/close connections, restart pollers, re-read tunables. MeshCore uses it to connect or disconnect its serial link when its settings change. |
| `on_client_message_received(payload, reply=None)` | async | Any connected client sends a WebSocket message | Ignored. `payload` is a copy — mutating it has no effect. `reply(msg: dict)` is an optional async callable that sends `msg` back to the originating client. |
| `on_audio_rx_start()` | async | The squelch detector opens (incoming carrier detected) | Ignored. Bridged from the STT worker thread to the event loop automatically. |
| `on_audio_rx_chunk(chunk)` | **sync** | Each raw audio chunk is captured from the input device | Ignored. `chunk` is a float32 numpy array at 16 kHz. **Hot path on the STT worker thread — keep it fast; do not `await` or call asyncio APIs.** |
| `on_rx_final(text)` | async | Each finalized (non-partial) RX transcript is broadcast | Ignored. |
| `on_audio_tx_pre_queue(payload)` | async | Before TX text enters the synthesis queue | Return `payload` (optionally modified) to allow the transmit, or `None` to block it. Plugins run in registration order and the **first to return `None` wins**. Modifiable fields: `text`, `_filter_profanity`, `_voice_name`, `_length_scale`. |

A plugin can also constrain the core message input without the input knowing
anything about it, by declaring the `tx_composition` field on its manifest. The
input honours the most restrictive declaration across enabled plugins (live
character counter + length cap). MeshCore declares one so its packet-length budget
is enforced as you type.

### Examples and built-ins

MeshCore and Meshtastic are **example plugins**, shipped under
`examples/plugins/` and seeded into `/data/plugins` on first run — reference
implementations for writing your own, not core features. They are mutually
exclusive (enabling one disables the other via `conflicts_with`). MeshCore bridges
to a USB Companion radio over serial (with a configurable baud rate); Meshtastic
is serial too (no baud setting). Both build on a shared `MeshForwarderPlugin` base
(`backend/plugins/mesh_forwarder.py`, re-exported by the SDK) so a concrete
forwarder supplies only its config mapping and transport.

**NCS / SKYWARN remains built-in** — it is registered by the app rather than
loaded from `/data/plugins`, because it is deeply integrated (contacts, FCC
lookup, journals, and a rich panel). It still appears in the Plugins tab as a
toggle (enabled by default), and its UI hides when disabled.

See `backend/plugins/sdk.py` and `backend/plugins/loader.py` for the contract and
loader, `examples/plugins/` for the example plugins, and
[docs/plugins.md](docs/plugins.md) for the full authoring guide (package layout,
SDK API, config schema, install/reload, trust model, and a copy-paste
hello-world).

## License

MIT
