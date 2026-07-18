"""Neighborhood incident reports for Hearthwave.

Stores hazard/incident reports (tree down, power out, suspicious activity,
etc.) contributed by any household on the neighborhood net, kept as a
newest-first feed capped at 500 entries so the file can't grow unbounded.
Stored in /data/incidents.json, following PresenceStore's persistence
pattern: in-memory list, atomic writes via tempfile + rename, no Qt, no
threads.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path

from backend.persistence._utils import atomic_json_write

_log = logging.getLogger(__name__)

_DEFAULT_PATH = Path(os.environ.get("RADIO_TTY_INCIDENTS", "/data/incidents.json"))

_MAX_ENTRIES = 500


class IncidentsStore:
    """Thin persistence layer over incidents.json.

    Newest-first list of incident report dicts, capped at _MAX_ENTRIES.
    Follows PresenceStore's pattern: in-memory list, atomic writes via
    tempfile + rename, no Qt, no threads.
    """

    def __init__(self, path: Path = _DEFAULT_PATH) -> None:
        self._path = Path(path)
        self._data: list[dict] = self._load()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load(self) -> list[dict]:
        if not self._path.exists():
            return []
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError) as exc:
            _log.warning("Could not load %s: %s; starting empty.", self._path, exc)
            return []

    def _save(self) -> None:
        atomic_json_write(self._path, self._data)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, entry: dict) -> dict:
        """Record a new incident report.

        Assigns a fresh ``id`` (uuid4 hex); ``ts`` is caller-supplied (not
        derived here) so callers control the reported timestamp. Prepends
        (newest-first) and caps the feed at _MAX_ENTRIES before saving.
        """
        record = dict(entry)
        record["id"] = uuid.uuid4().hex
        self._data.insert(0, record)
        del self._data[_MAX_ENTRIES:]
        self._save()
        return dict(record)

    def list(self) -> list[dict]:
        """Return a newest-first copy of all incident reports."""
        return [dict(e) for e in self._data]
