#!/usr/bin/env bash
# Radio-TTY native install — run once on a fresh Debian/Ubuntu machine.
# Creates a Python venv at .venv/, installs all deps, and validates the setup.
#
# Usage:
#   bash install.sh            # full install
#   bash install.sh --no-models  # skip model download (copy Models/ manually)

set -euo pipefail

MODELS=true
for arg in "$@"; do
  [[ "$arg" == "--no-models" ]] && MODELS=false
done

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
    espeak-ng-data

# ── 2. Python virtual environment ───────────────────────────────────────────

echo "==> Creating Python venv at .venv/ ..."
python3 -m venv .venv
source .venv/bin/activate

echo "==> Installing Python packages (this will take a few minutes)..."
pip install --upgrade pip --quiet
pip install -r backend/requirements.txt

# ── 3. Models ────────────────────────────────────────────────────────────────

if $MODELS; then
    echo "==> Downloading Whisper STT model (small.en, ~464 MB)..."
    python bootstrap_models.py --model small.en

    echo ""
    echo "NOTE: The speaker recognition model (Models/Speaker/ecapa-tdnn) and"
    echo "      Piper TTS voices (Voices/) must be copied from an existing install"
    echo "      or downloaded separately — see bootstrap_models.py --help."
fi

# ── 4. Data directory ────────────────────────────────────────────────────────

if [ ! -f data/config.json ]; then
    echo "==> Copying seed config..."
    mkdir -p data/voiceprints
    cp data/config.json.example data/config.json 2>/dev/null || true
fi
mkdir -p data/voiceprints

# ── 5. Validate ──────────────────────────────────────────────────────────────

echo ""
echo "==> Validating install..."
python -c "import sounddevice; print('  sounddevice OK')"
python -c "import soundfile; print('  soundfile    OK')"
python -c "import faster_whisper; print('  faster-whisper OK')"
python -c "import piper; print('  piper-tts    OK')"
python -c "import silero_vad; print('  silero-vad   OK')"

echo ""
echo "Done. To start the server:"
echo "  source .venv/bin/activate"
echo "  uvicorn backend.server:app --host 0.0.0.0 --port 8765"
echo ""
echo "Edit data/config.json to set your callsign, audio devices, and voice."
