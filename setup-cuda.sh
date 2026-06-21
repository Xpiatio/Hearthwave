#!/usr/bin/env bash
# Hearthwave — NVIDIA CUDA setup (build-from-source Docker path).  *** STUB ***
#
# This profile is scaffolded but NOT yet validated on an NVIDIA host. It mirrors
# setup-cpu.sh for dirs/config/models/voices and writes COMPUTE_BACKEND=cuda, but
# the GPU-acceleration path (NVIDIA Container Toolkit + STT final pass on CUDA)
# has not been tested. Validate on real NVIDIA hardware before relying on it.
#
# Prerequisites to wire before use:
#   - NVIDIA driver + NVIDIA Container Toolkit installed on the host
#   - `docker run --rm --gpus all nvidia/cuda:12.4.0-base nvidia-smi` succeeds
#
# Usage (after the above):
#   bash setup-cuda.sh
#   docker compose -f docker-compose.cuda.yml up --build

set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  setup-cuda.sh is a STUB — NVIDIA support is not yet validated."
echo ""
echo "  For now, use the CPU or ROCm profiles:"
echo "        bash setup-cpu.sh    &&  docker compose -f docker-compose.yml up --build"
echo "        bash setup-rocm.sh   &&  docker compose -f docker-compose.rocm.yml up --build"
echo ""
echo "  To finish CUDA support: install the NVIDIA Container Toolkit, confirm"
echo "  'docker run --rm --gpus all nvidia/cuda:12.4.0-base nvidia-smi', then"
echo "  flesh out this script from setup-cpu.sh (writing COMPUTE_BACKEND=cuda)"
echo "  and validate docker-compose.cuda.yml on real hardware."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
exit 0
