#!/usr/bin/env bash
# Radio-TTY prerequisite setup — run once on the Docker host BEFORE deploying
# the Portainer stack.
#
# Populates the three named volumes the stack expects with models and voices.
# Requires only docker — no Python or pip needed on the host.
#
# Usage:
#   bash prereq.sh                   # full setup: Whisper small.en + all voices
#   bash prereq.sh --model base.en   # use a smaller/faster Whisper model
#   bash prereq.sh --model medium.en # use a higher-accuracy Whisper model
#   bash prereq.sh --voice-only      # add/update voices only (skip Whisper)

set -euo pipefail

VOICE_ONLY=false
WHISPER_MODEL="small.en"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model)
      [[ $# -lt 2 ]] && { echo "Error: --model requires a value." >&2; exit 1; }
      WHISPER_MODEL="$2"; shift 2 ;;
    --voice-only) VOICE_ONLY=true; shift ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "Unknown argument: $1  (try --help)" >&2; exit 1 ;;
  esac
done

BACKEND_IMAGE="ghcr.io/xpiatio/radio-tty-backend:v2.1.0"
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

# ── 0. Validate model choice ─────────────────────────────────────────────────

WHISPER_REPOS=(tiny.en base.en small.en medium.en large-v3)
VALID=false
for m in "${WHISPER_REPOS[@]}"; do [[ "$m" == "$WHISPER_MODEL" ]] && VALID=true; done
if ! $VALID; then
  echo "Error: unknown model '$WHISPER_MODEL'." >&2
  echo "Valid choices: ${WHISPER_REPOS[*]}" >&2
  exit 1
fi

# ── 1. Check prerequisites ────────────────────────────────────────────────────

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
  # Map model name → HuggingFace repo
  case "$WHISPER_MODEL" in
    tiny.en)   REPO_ID="Systran/faster-whisper-tiny.en"   ;;
    base.en)   REPO_ID="Systran/faster-whisper-base.en"   ;;
    small.en)  REPO_ID="Systran/faster-whisper-small.en"  ;;
    medium.en) REPO_ID="Systran/faster-whisper-medium.en" ;;
    large-v3)  REPO_ID="Systran/faster-whisper-large-v3"  ;;
  esac

  echo ""
  echo "==> Whisper STT model (${WHISPER_MODEL})..."
  echo "  Pulling backend image..."
  docker pull "$BACKEND_IMAGE" --quiet

  docker run --rm --user root \
    -v "${MODELS_VOL}:/app/backend/Models" \
    -e "WHISPER_MODEL=${WHISPER_MODEL}" \
    -e "REPO_ID=${REPO_ID}" \
    "$BACKEND_IMAGE" \
    python3 -c "
import os, sys
from huggingface_hub import snapshot_download

model = os.environ['WHISPER_MODEL']
repo  = os.environ['REPO_ID']
target = f'/app/backend/Models/STT/{model}'

if os.path.isdir(target) and os.listdir(target):
    print(f'  {model} already present, skipping.')
    sys.exit(0)

os.makedirs(target, exist_ok=True)
print(f'  Downloading {repo} from HuggingFace...')
snapshot_download(repo, local_dir=target)
print(f'  Whisper {model} download complete.')
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
  echo "  ${MODELS_VOL}  Whisper ${WHISPER_MODEL} STT model"
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
