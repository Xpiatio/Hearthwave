#!/usr/bin/env bash
# Hearthwave setup — compatibility shim.
#
# Setup is now split by compute backend (build-from-source Docker path):
#   bash setup-cpu.sh    && docker compose -f docker-compose.yml up --build
#   bash setup-rocm.sh   && docker compose -f docker-compose.rocm.yml up --build   # AMD GPU final pass
#   bash setup-cuda.sh   && docker compose -f docker-compose.cuda.yml up --build   # NVIDIA (stub)
#
# This shim forwards to setup-cpu.sh (the previous default) so existing
# `bash setup.sh ...` invocations keep working. Pass any setup-cpu.sh args.

set -euo pipefail

echo "==> setup.sh now forwards to setup-cpu.sh (CPU profile)." >&2
echo "    For GPU, use setup-rocm.sh (AMD) or setup-cuda.sh (NVIDIA, stub)." >&2
exec bash "$(dirname "$0")/setup-cpu.sh" "$@"
