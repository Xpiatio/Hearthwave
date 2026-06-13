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
#   bash prereq.sh --final-model distil-large-v3  # also stage the two-tier
#                                    # final-pass model (set whisper_model_final to match)
#   bash prereq.sh --voice-only      # add/update voices only (skip Whisper)

set -euo pipefail

VOICE_ONLY=false
WHISPER_MODEL="small.en"
FINAL_MODEL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model)
      [[ $# -lt 2 ]] && { echo "Error: --model requires a value." >&2; exit 1; }
      WHISPER_MODEL="$2"; shift 2 ;;
    --final-model)
      [[ $# -lt 2 ]] && { echo "Error: --final-model requires a value." >&2; exit 1; }
      FINAL_MODEL="$2"; shift 2 ;;
    --voice-only) VOICE_ONLY=true; shift ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "Unknown argument: $1  (try --help)" >&2; exit 1 ;;
  esac
done

BACKEND_IMAGE="ghcr.io/xpiatio/radio-tty-backend:v2.5.0"
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

# Map a model name → HuggingFace repo id, or exit with an error.
repo_for_model() {
  case "$1" in
    tiny.en)          echo "Systran/faster-whisper-tiny.en"   ;;
    base.en)          echo "Systran/faster-whisper-base.en"   ;;
    small.en)         echo "Systran/faster-whisper-small.en"  ;;
    medium.en)        echo "Systran/faster-whisper-medium.en" ;;
    large-v3)         echo "Systran/faster-whisper-large-v3"  ;;
    distil-large-v3)  echo "Systran/faster-distil-whisper-large-v3" ;;
    *)
      echo "Error: unknown model '$1'." >&2
      echo "Valid choices: tiny.en base.en small.en medium.en large-v3 distil-large-v3" >&2
      exit 1 ;;
  esac
}

repo_for_model "$WHISPER_MODEL" > /dev/null            # validate primary
[[ -n "$FINAL_MODEL" ]] && repo_for_model "$FINAL_MODEL" > /dev/null  # validate final

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

# Download one Whisper model into the models volume (idempotent).
fetch_whisper_model() {
  local model="$1"
  local repo
  repo="$(repo_for_model "$model")"
  echo ""
  echo "==> Whisper STT model (${model})..."
  docker run --rm --user root \
    --entrypoint python3 \
    -v "${MODELS_VOL}:/app/backend/Models" \
    -e "WHISPER_MODEL=${model}" \
    -e "REPO_ID=${repo}" \
    "$BACKEND_IMAGE" \
    -c "
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
}

if ! $VOICE_ONLY; then
  echo ""
  echo "  Pulling backend image..."
  docker pull "$BACKEND_IMAGE" --quiet
  fetch_whisper_model "$WHISPER_MODEL"
  if [[ -n "$FINAL_MODEL" ]]; then
    echo ""
    echo "==> Two-tier final-pass model:"
    fetch_whisper_model "$FINAL_MODEL"
    echo "  Set whisper_model_final=\"${FINAL_MODEL}\" in the data volume's config.json to enable it."
  fi
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
  [[ -n "$FINAL_MODEL" ]] && echo "  ${MODELS_VOL}  Whisper ${FINAL_MODEL} final-pass model (two-tier)"
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
