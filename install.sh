#!/usr/bin/env bash
# Hearthwave native install — run once on a fresh Debian/Ubuntu machine.
# Creates a Python venv at .venv/, installs all deps, and validates the setup.
#
# Usage:
#   bash install.sh                            # full install (small.en + large-v3-turbo)
#   bash install.sh --no-models                # skip model download (copy Models/ manually)
#   bash install.sh --final-model distil-large-v3   # stage a different two-tier
#                                              # final-pass model
#   bash install.sh --final-model none         # skip the final-pass model (single-pass RX)
#   bash install.sh --dev                      # also install test deps (pytest, httpx)

set -euo pipefail

MODELS=true
DEV=false
# Two-tier final-pass model staged by default. whisper_model_final="auto" (the
# fresh-install default) resolves to the best staged model, and its preference
# order puts large-v3-turbo first — so staging turbo here is what makes "auto"
# resolve to anything at all on a new install.
FINAL_MODEL="large-v3-turbo"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-models) MODELS=false; shift ;;
    --dev) DEV=true; shift ;;
    --final-model)
      [[ $# -lt 2 ]] && { echo "Error: --final-model requires a value." >&2; exit 1; }
      FINAL_MODEL="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

# "none"/"off" (and "") mean: single-pass RX, stage no final model.
[[ "$FINAL_MODEL" == "none" || "$FINAL_MODEL" == "off" ]] && FINAL_MODEL=""

# ── 1. System packages ───────────────────────────────────────────────────────

echo "==> Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
    python3 \
    python3-venv \
    python3-pip \
    build-essential \
    gcc \
    libportaudio2 \
    libsndfile1 \
    espeak-ng \
    espeak-ng-data \
    pulseaudio-utils \
    curl \
    ca-certificates

# Node.js 20 (LTS) via NodeSource — skip if already at v18+.
NODE_MAJOR=$(node --version 2>/dev/null | grep -oP '(?<=v)\d+' || echo 0)
if [ "$NODE_MAJOR" -lt 18 ]; then
    echo "==> Installing Node.js 20 (LTS)..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
else
    echo "==> Node.js $(node --version) already installed, skipping."
fi

# ── 2. Frontend dependencies ─────────────────────────────────────────────────

echo "==> Installing frontend npm packages (MUI, React, Vite, …)..."
(cd frontend && npm ci)

# ── 3. Docker image cache (optional but speeds up first `docker compose up`) ──

if command -v docker &>/dev/null; then
    echo "==> Pulling Docker base images..."
    docker compose pull --quiet 2>/dev/null || true
    docker compose -f docker-compose.yml -f docker-compose.dev.yml pull --quiet 2>/dev/null || true
fi

# ── 4. Python virtual environment ───────────────────────────────────────────

echo "==> Creating Python venv at .venv/ ..."
python3 -m venv .venv
source .venv/bin/activate

echo "==> Installing Python packages (this will take a few minutes)..."
pip install --upgrade pip --quiet
if $DEV; then
    pip install -r backend/requirements.txt -r backend/requirements-dev.txt
    echo "    Test deps installed — run the suite with: cd backend && python -m pytest"
else
    pip install -r backend/requirements.txt
fi

# ── 5. Models ────────────────────────────────────────────────────────────────

if $MODELS; then
    if [[ -n "$FINAL_MODEL" ]]; then
        echo "==> Downloading Whisper STT models (small.en ~464 MB + ${FINAL_MODEL} ~1.6 GB)..."
        python bootstrap_models.py --model small.en "$FINAL_MODEL"
        echo "    whisper_model_final=\"auto\" (new-install default) picks this up automatically."
        echo "    If data/config.json has whisper_model_final=\"\" (explicit off), set it to \"auto\""
        echo "    or \"${FINAL_MODEL}\" to enable the two-tier pass."
    else
        echo "==> Downloading Whisper STT model (small.en, ~464 MB)..."
        python bootstrap_models.py --model small.en
    fi

    echo "==> Downloading Piper TTS voices..."
    mkdir -p Voices
    python - <<'PYEOF'
import os, shutil
from huggingface_hub import hf_hub_download

REPO = "rhasspy/piper-voices"
VOICES = [
    "en/en_US/ryan/high/en_US-ryan-high.onnx",
    "en/en_US/ryan/high/en_US-ryan-high.onnx.json",
    "en/en_US/amy/medium/en_US-amy-medium.onnx",
    "en/en_US/amy/medium/en_US-amy-medium.onnx.json",
    "en/en_US/arctic/medium/en_US-arctic-medium.onnx",
    "en/en_US/arctic/medium/en_US-arctic-medium.onnx.json",
    "en/en_US/hfc_female/medium/en_US-hfc_female-medium.onnx",
    "en/en_US/hfc_female/medium/en_US-hfc_female-medium.onnx.json",
    "en/en_US/kathleen/low/en_US-kathleen-low.onnx",
    "en/en_US/kathleen/low/en_US-kathleen-low.onnx.json",
    "en/en_US/kristin/medium/en_US-kristin-medium.onnx",
    "en/en_US/kristin/medium/en_US-kristin-medium.onnx.json",
    "en/en_US/lessac/high/en_US-lessac-high.onnx",
    "en/en_US/lessac/high/en_US-lessac-high.onnx.json",
    "en/en_US/libritts/high/en_US-libritts-high.onnx",
    "en/en_US/libritts/high/en_US-libritts-high.onnx.json",
]
for path in VOICES:
    name = os.path.basename(path)
    out = os.path.join("Voices", name)
    if os.path.exists(out):
        print(f"  {name} already present, skipping.")
        continue
    print(f"  Downloading {name}...")
    cached = hf_hub_download(REPO, path)
    shutil.copy2(os.path.realpath(cached), out)
    print(f"  {name} done.")
PYEOF
fi

# ── 6. Data directory ────────────────────────────────────────────────────────

mkdir -p data/journals
# Drop directory for installable 3rd-party plugins (loaded from /data/plugins).
mkdir -p data/plugins

if [ ! -f data/config.json ]; then
    echo "==> Copying seed config..."
    if [ -f data/config.json.example ]; then
        cp data/config.json.example data/config.json
    else
        echo "  (no data/config.json.example found — you must create data/config.json manually)"
        echo "  Minimum required fields: callsign, voice"
    fi
fi

# ── 7. Validate ──────────────────────────────────────────────────────────────

echo ""
echo "==> Validating install..."
python -c "import sounddevice; print('  sounddevice    OK')"
python -c "import faster_whisper; print('  faster-whisper OK')"
python -c "import piper; print('  piper-tts      OK')"
python -c "import silero_vad; print('  silero-vad     OK')"
python -c "import numpy; print('  numpy          OK')"
python -c "import huggingface_hub; print('  huggingface_hub OK')"

echo ""
echo "Done. To start the server:"
echo "  source .venv/bin/activate"
echo "  uvicorn backend.server:app --host 0.0.0.0 --port 8765"
echo ""
echo "Edit data/config.json to set your callsign, audio devices, and voice."
