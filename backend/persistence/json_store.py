"""Low-level JSON load/save helpers.

Ported from GMRS-TTY. No Qt dependencies.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

_log = logging.getLogger(__name__)


def load_json(filepath: str | Path, default_data):
    """Load JSON from ``filepath``, returning ``default_data`` if the file is
    absent or contains invalid JSON."""
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except json.JSONDecodeError:
            _log.warning("Error decoding %s. Using defaults.", filepath)
    return default_data


def save_json(filepath: str | Path, data) -> None:
    """Write ``data`` to ``filepath`` as pretty-printed JSON.

    Logs an error and re-raises on failure so callers can decide how to handle
    write errors.
    """
    try:
        with open(filepath, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=4, ensure_ascii=False)
    except Exception as exc:
        _log.error("Error saving %s: %s", filepath, exc)
        raise
