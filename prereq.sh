#!/usr/bin/env bash
# Radio-TTY prerequisite setup — run once on the Docker host BEFORE deploying
# the Portainer stack.
#
# Downloads Whisper STT and Piper TTS voices into the Docker named volumes the
# stack expects. Requires only docker — no Python or pip needed on the host.
#
# Usage:
#   bash prereq.sh              # full setup: models + voices
#   bash prereq.sh --voice-only # add/update voices only (skip Whisper)

set -euo pipefail

VOICE_ONLY=false
for arg in "$@"; do
  [[ "$arg" == "--voice-only" ]] && VOICE_ONLY=true
done

BACKEND_IMAGE="ghcr.io/xpiatio/radio-tty-backend:v1.1.0"
VOICES_VOL="radio-tty-voices"
MODELS_VOL="radio-tty-models"
DATA_VOL="radio-tty-data"

HF_BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main"

# Default voices: "<stem>|<HuggingFace path without extension>"
# The stem becomes the filename in the Voices/ volume (flat — no subdirs).
VOICES=(
  "en_US-ryan-high|en/en_US/ryan/high/en_US-ryan-high"
  "en_US-amy-medium|en/en_US/amy/medium/en_US-amy-medium"
  "en_US-arctic-medium|en/en_US/arctic/medium/en_US-arctic-medium"
  "en_US-hfc_female-medium|en/en_US/hfc_female/medium/en_US-hfc_female-medium"
  "en_US-kathleen-low|en/en_US/kathleen/low/en_US-kathleen-low"
  "en_US-kristin-medium|en/en_US/kristin/medium/en_US-kristin-medium"
  "en_US-lessac-high|en/en_US/lessac/high/en_US-lessac-high"
  "en_US-libritts-high|en/en_US/libritts/high/en_US-libritts-high"
)

# ── 1. Check prerequisites ─────────────────────────────────────────────────────

if ! command -v docker &>/dev/null; then
  echo "Error: docker not found in PATH." >&2
  echo "Install Docker: https://docs.docker.com/engine/install/" >&2
  exit 1
fi

if ! docker info &>/dev/null; then
  echo "Error: Docker daemon is not running or you lack permission." >&2
  echo "Start Docker and/or add your user to the 'docker' group, then re-run." >&2
  exit 1
fi

# ── 2. Create volumes (idempotent) ────────────────────────────────────────────

echo "==> Creating Docker volumes..."
for vol in "$VOICES_VOL" "$MODELS_VOL" "$DATA_VOL"; do
  if docker volume inspect "$vol" &>/dev/null; then
    echo "  $vol — already exists"
  else
    docker volume create "$vol" > /dev/null
    echo "  $vol — created"
  fi
done

# ── 3. Whisper STT model ──────────────────────────────────────────────────────

if ! $VOICE_ONLY; then
  echo ""
  echo "==> Whisper STT model (small.en, ~464 MB)..."
  echo "  Pulling backend image..."
  docker pull "$BACKEND_IMAGE" --quiet

  docker run --rm --user root \
    -v "${MODELS_VOL}:/app/backend/Models" \
    "$BACKEND_IMAGE" \
    python3 -c "
import os, sys
from huggingface_hub import snapshot_download

target = '/app/backend/Models/STT/small.en'
if os.path.isdir(target) and os.listdir(target):
    print('  small.en already present, skipping.')
    sys.exit(0)

os.makedirs(target, exist_ok=True)
print('  Downloading from HuggingFace (Systran/faster-whisper-small.en)...')
snapshot_download('Systran/faster-whisper-small.en', local_dir=target)
print('  Whisper download complete.')
"
fi

# ── 4. Piper TTS voices ───────────────────────────────────────────────────────

echo ""
echo "==> Piper TTS voices..."

# Build one shell script that downloads all missing voices inside a single
# alpine container (avoids per-file docker startup overhead).
VOICE_SCRIPT=""
for entry in "${VOICES[@]}"; do
  stem="${entry%%|*}"
  hf_path="${entry##*|}"
  for ext in ".onnx" ".onnx.json"; do
    filename="${stem}${ext}"
    url="${HF_BASE}/${hf_path}${ext}"
    VOICE_SCRIPT+="
if [ -f '/v/${filename}' ]; then
  echo '  ${filename} — already present'
else
  echo '  Downloading ${filename}...'
  wget -q -O '/v/${filename}' '${url}' && echo '  ${filename} — done' || echo '  ${filename} — FAILED (check URL)' >&2
fi
"
  done
done

docker run --rm -v "${VOICES_VOL}:/v" alpine sh -c "$VOICE_SCRIPT"

# ── 5. Summary ────────────────────────────────────────────────────────────────

echo ""
echo "Done. Volumes ready:"
if ! $VOICE_ONLY; then
echo "  ${MODELS_VOL}  Whisper small.en STT model"
fi
VOICE_NAMES=""
for entry in "${VOICES[@]}"; do VOICE_NAMES+=" ${entry%%|*}"; done
echo "  ${VOICES_VOL}  Piper voices:${VOICE_NAMES}"
echo "  ${DATA_VOL}   (config and user data — populated on first run)"
echo ""
echo "Next step: deploy the Portainer stack using docker-compose.portainer.yml"
echo ""
echo "To add more voices later:  bash prereq.sh --voice-only"
echo "Browse all Piper voices:   https://huggingface.co/rhasspy/piper-voices"
