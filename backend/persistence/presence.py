"""Family presence tracking for Hearthwave.

Tracks, per user, when they were last heard from (any TX, or a "family_status"
check-in) and when they last explicitly checked in ok. Stored in
/data/presence.json, following the UsersStore/TokenStore persistence pattern:
in-memory dict, atomic writes via tempfile + rename, no Qt, no threads.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from backend.persistence._utils import atomic_json_write

_log = logging.getLogger(__name__)

_DEFAULT_PATH = Path(os.environ.get("RADIO_TTY_PRESENCE", "/data/presence.json"))

# Shape of a per-user presence entry; also the value returned for a user with
# no record yet (e.g. a profile that has never transmitted or checked in).
_EMPTY: dict = {"last_heard": None, "last_ok": None, "missed_checkin": False}


class PresenceStore:
    """Thin persistence layer for presence.json.

    Follows the TokenStore pattern: in-memory dict keyed by user_id, atomic
    writes via tempfile + rename, no Qt, no threads.
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

    def _entry(self, user_id: str) -> dict:
        return self._data.setdefault(user_id, dict(_EMPTY))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, user_id: str) -> dict:
        return dict(self._data.get(user_id, _EMPTY))

    def all(self) -> dict[str, dict]:
        return {k: dict(v) for k, v in self._data.items()}

    def touch_heard(self, user_id: str, ts_iso: str) -> None:
        """Record that *user_id* was heard from (any TX) at *ts_iso*."""
        self._entry(user_id)["last_heard"] = ts_iso
        self._save()

    def mark_ok(self, user_id: str, ts_iso: str) -> None:
        """Record an explicit "I'm OK" check-in — clears any missed_checkin flag."""
        e = self._entry(user_id)
        e["last_ok"] = ts_iso
        e["last_heard"] = ts_iso
        e["missed_checkin"] = False
        self._save()

    def set_missed(self, user_id: str, missed: bool) -> bool:
        """Set the missed_checkin flag. Returns True if it changed.

        Peeks at the existing entry (if any) rather than calling _entry(),
        which would setdefault-insert a phantom entry for a user we've never
        seen before an early return would fire. Only creates an entry when
        the flag is actually flipping to a different value.
        """
        existing = self._data.get(user_id)
        current = existing["missed_checkin"] if existing is not None else _EMPTY["missed_checkin"]
        if current == missed:
            return False
        self._entry(user_id)["missed_checkin"] = missed
        self._save()
        return True
