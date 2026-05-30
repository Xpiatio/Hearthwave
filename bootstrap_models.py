#!/usr/bin/env python3
"""Pre-stage the offline Whisper model Radio-TTY needs.

Radio-TTY is designed for fully offline operation — the server never attempts
to fetch a model at runtime. Run this script once on a machine with internet
access; the resulting Models/ directory is portable and can be copied to
air-gapped target machines alongside the source tree.

Usage:
    python bootstrap_models.py                       # default: small.en
    python bootstrap_models.py --model base.en       # smaller, faster
    python bootstrap_models.py --model medium.en     # higher accuracy
"""
import argparse
import os
import sys

WHISPER_REPOS = {
    "tiny.en":   "Systran/faster-whisper-tiny.en",
    "base.en":   "Systran/faster-whisper-base.en",
    "small.en":  "Systran/faster-whisper-small.en",
    "medium.en": "Systran/faster-whisper-medium.en",
    "large-v3":  "Systran/faster-whisper-large-v3",
}


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--model",
        default="small.en",
        choices=sorted(WHISPER_REPOS),
        help="faster-whisper variant to fetch (default: small.en).",
    )
    args = parser.parse_args()

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print(
            "huggingface_hub is required. Install it with:\n"
            "    pip install -r backend/requirements.txt",
            file=sys.stderr,
        )
        return 1

    target = os.path.join("Models", "STT", args.model)
    os.makedirs(target, exist_ok=True)
    repo_id = WHISPER_REPOS[args.model]
    print(f"Whisper: downloading {repo_id} -> {target}")
    snapshot_download(repo_id=repo_id, local_dir=target)
    print(f"Whisper: done. Loaded at runtime from {target}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
