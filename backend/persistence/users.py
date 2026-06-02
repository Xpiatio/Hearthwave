"""User profiles and authentication for Radio-TTY.

Stores named user profiles in /data/users.json. Each profile has a password
(PBKDF2-SHA256 with per-user salt) and per-user preferences that override the
global station config for that connection.

Bootstrap: creates one admin profile on first startup seeded from the station
config. Uses RADIO_TTY_ADMIN_PASS env var or prints a random password to stdout.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.persistence._utils import atomic_json_write

_log = logging.getLogger(__name__)

_DEFAULT_PATH = Path(os.environ.get("RADIO_TTY_USERS", "/data/users.json"))

# Fields stripped from all public-facing user profile responses.
SENSITIVE_PROFILE_FIELDS: frozenset[str] = frozenset(
    {"password_hash", "password_salt", "failed_attempts", "locked_until"}
)

LOCKOUT_MAX_ATTEMPTS = 3
LOCKOUT_DURATION_MINUTES = 15

DEFAULT_PREFS: dict = {
    "dark_mode": False,
    "panel_order": ["config", "attendance", "journal"],
    "filter_profanity": True,
    "listen_only": False,
    "read_aloud": False,
    "spectro_colormap": "viridis",
    "spectro_time_window_s": 30,
    "tts_voice": "",
    "tts_length_scale": 0,  # 0 = inherit station default
}


def _hash_password(password: str, salt_hex: str) -> str:
    """Return PBKDF2-SHA256 hex digest for *password* using *salt_hex*."""
    salt = bytes.fromhex(salt_hex)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260_000)
    return dk.hex()


class UsersStore:
    """Thin persistence layer for users.json.

    Follows the ContactsStore pattern: in-memory list, atomic writes via
    tempfile + rename, no Qt, no threads.
    """

    def __init__(self, path: Path = _DEFAULT_PATH) -> None:
        self._path = Path(path)
        self._users: list[dict] = self._load()

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
            _log.warning("Could not load %s: %s; starting empty", self._path, exc)
            return []

    def _save(self) -> None:
        atomic_json_write(self._path, self._users)

    def _find_index(self, user_id: str) -> int:
        for i, u in enumerate(self._users):
            if u.get("id") == user_id:
                return i
        raise KeyError(f"No user with id {user_id!r}")

    def _make_id(self, display_name: str) -> str:
        """Generate a URL-safe ID from display_name, ensuring uniqueness."""
        base = "".join(
            c if (c.isalnum() or c == "-") else "-"
            for c in display_name.lower().replace(" ", "-")
        ).strip("-") or "user"
        existing = {u.get("id", "") for u in self._users}
        candidate = base
        i = 2
        while candidate in existing:
            candidate = f"{base}-{i}"
            i += 1
        return candidate

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_all(self) -> list[dict]:
        return list(self._users)

    def get_public(self) -> list[dict]:
        """Strip sensitive fields for API responses."""
        return [{k: v for k, v in u.items() if k not in SENSITIVE_PROFILE_FIELDS} for u in self._users]

    def get(self, user_id: str) -> dict | None:
        for u in self._users:
            if u.get("id") == user_id:
                return dict(u)
        return None

    def get_by_display_name(self, display_name: str) -> dict | None:
        for u in self._users:
            if u.get("display_name") == display_name:
                return dict(u)
        return None

    def get_public_one(self, user_id: str) -> dict | None:
        u = self.get(user_id)
        if u is None:
            return None
        return {k: v for k, v in u.items() if k not in SENSITIVE_PROFILE_FIELDS}

    def is_empty(self) -> bool:
        return len(self._users) == 0

    def create(
        self,
        *,
        display_name: str,
        password: str,
        avatar_emoji: str = "👤",
        operator_name: str = "",
        callsign: str = "",
        location: str = "",
        is_admin: bool = False,
        prefs: dict | None = None,
    ) -> dict:
        user_id = self._make_id(display_name)
        salt_hex = secrets.token_hex(32)
        pw_hash = _hash_password(password, salt_hex)
        now = datetime.now(timezone.utc).isoformat()
        profile: dict = {
            "id": user_id,
            "display_name": display_name,
            "avatar_emoji": avatar_emoji,
            "operator_name": operator_name or display_name,
            "callsign": callsign,
            "location": location,
            "password_hash": pw_hash,
            "password_salt": salt_hex,
            "is_admin": is_admin,
            "failed_attempts": 0,
            "locked_until": None,
            "created_at": now,
            "prefs": {**DEFAULT_PREFS, **(prefs or {})},
        }
        self._users.append(profile)
        self._save()
        return dict(profile)

    def update_prefs(self, user_id: str, prefs: dict) -> dict:
        """Merge *prefs* into the user's saved prefs; persist atomically."""
        i = self._find_index(user_id)
        merged = {**DEFAULT_PREFS, **self._users[i].get("prefs", {}), **prefs}
        self._users[i] = {**self._users[i], "prefs": merged}
        self._save()
        return dict(self._users[i])

    def update_profile(self, user_id: str, updates: dict) -> dict:
        """Update identity fields on a profile (not password — use change_password)."""
        allowed = {"display_name", "avatar_emoji", "operator_name", "callsign", "location", "is_admin"}
        i = self._find_index(user_id)
        merged = dict(self._users[i])
        for k in allowed:
            if k in updates:
                merged[k] = updates[k]
        self._users[i] = merged
        self._save()
        return dict(merged)

    def change_password(self, user_id: str, new_password: str) -> None:
        i = self._find_index(user_id)
        salt_hex = secrets.token_hex(32)
        self._users[i]["password_salt"] = salt_hex
        self._users[i]["password_hash"] = _hash_password(new_password, salt_hex)
        self._users[i]["failed_attempts"] = 0
        self._users[i]["locked_until"] = None
        self._save()

    def delete(self, user_id: str) -> None:
        self._find_index(user_id)  # raises KeyError if not found
        self._users = [u for u in self._users if u.get("id") != user_id]
        self._save()

    def is_locked(self, user_id: str) -> bool:
        try:
            i = self._find_index(user_id)
        except KeyError:
            return False
        u = self._users[i]
        locked_until = u.get("locked_until")
        if not locked_until:
            return False
        try:
            expiry = datetime.fromisoformat(locked_until)
        except (ValueError, TypeError):
            expiry = datetime.now(timezone.utc)
        if datetime.now(timezone.utc) >= expiry:
            self._users[i]["locked_until"] = None
            self._users[i]["failed_attempts"] = 0
            self._save()
            return False
        return True

    def locked_until_str(self, user_id: str) -> str | None:
        try:
            i = self._find_index(user_id)
            return self._users[i].get("locked_until")
        except KeyError:
            return None

    def verify_password(self, user_id: str, password: str) -> bool:
        """Check password; manage attempt counter and lockout. Returns True on success."""
        if self.is_locked(user_id):
            return False
        try:
            i = self._find_index(user_id)
        except KeyError:
            return False
        u = self._users[i]
        pw_hash = _hash_password(password, u.get("password_salt", ""))
        ok = secrets.compare_digest(pw_hash, u.get("password_hash", ""))
        if ok:
            self._users[i]["failed_attempts"] = 0
            self._users[i]["locked_until"] = None
        else:
            attempts = self._users[i].get("failed_attempts", 0) + 1
            self._users[i]["failed_attempts"] = attempts
            if attempts >= LOCKOUT_MAX_ATTEMPTS:
                expiry = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
                self._users[i]["locked_until"] = expiry.isoformat()
                _log.warning("Account %s locked after %d failed attempts.", user_id, attempts)
        self._save()
        return ok

    def reset_lockout(self, user_id: str) -> None:
        i = self._find_index(user_id)
        self._users[i]["failed_attempts"] = 0
        self._users[i]["locked_until"] = None
        self._save()
