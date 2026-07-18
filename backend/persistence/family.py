"""Check-in reminder persistence for Hearthwave.

Tracks, per user, an optional daily check-in reminder ("by this time,
you should have sent an I'm-OK"). Stored in /data/family.json, following
the PresenceStore/TokenStore persistence pattern: in-memory dict, atomic
writes via tempfile + rename, no Qt, no threads.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from backend.family.reminders import _parse_hhmm
from backend.persistence._utils import atomic_json_write

_log = logging.getLogger(__name__)

_DEFAULT_PATH = Path(os.environ.get("RADIO_TTY_FAMILY", "/data/family.json"))


class FamilyStore:
    """Thin persistence layer for family.json (check-in reminders).

    Follows the PresenceStore pattern: in-memory dict keyed by user_id,
    atomic writes via tempfile + rename, no Qt, no threads.
    """

    def __init__(self, path: Path = _DEFAULT_PATH) -> None:
        self._path = Path(path)
        self._data: dict[str, dict] = self._load()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load(self) -> dict[str, dict]:
        if not self._path.exists():
            return {}
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError) as exc:
            _log.warning("Could not load %s: %s; starting empty", self._path, exc)
            return {}

    def _save(self) -> None:
        atomic_json_write(self._path, self._data)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_reminders(self) -> dict[str, dict]:
        return {k: dict(v) for k, v in self._data.items()}

    def set_reminder(self, user_id: str, time_hhmm: str | None, enabled: bool) -> dict:
        """Set (or delete) *user_id*'s check-in reminder.

        `time_hhmm=None` deletes the reminder entirely (enabled is ignored
        in that case). A malformed "HH:MM" string raises ValueError.
        Returns the full reminders dict post-update.
        """
        if time_hhmm is None:
            self._data.pop(user_id, None)
        else:
            if _parse_hhmm(time_hhmm) is None:
                raise ValueError(f"Invalid check-in time: {time_hhmm!r}")
            self._data[user_id] = {"time": time_hhmm, "enabled": bool(enabled)}
        self._save()
        return self.get_reminders()

    def delete(self, user_id: str) -> dict:
        """Remove *user_id*'s check-in reminder entirely, if any.

        No-op (not an error) if the user has no reminder set. Used when a
        profile is deleted, so a removed user doesn't leave an orphaned
        reminder entry behind. Returns the full reminders dict post-delete.
        """
        self._data.pop(user_id, None)
        self._save()
        return self.get_reminders()
