"""Session token store for Radio-TTY.

Tokens are opaque URL-safe strings (32 bytes). They are stored in /data/tokens.json
and survive server restarts. Expiry is checked on validation; expired tokens are
removed lazily. purge_expired() should be called at startup to clean up stale entries.
"""
from __future__ import annotations

import json
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.persistence._utils import atomic_json_write

_log = logging.getLogger(__name__)

_DEFAULT_PATH = Path(os.environ.get("RADIO_TTY_TOKENS", "/data/tokens.json"))
_DEFAULT_TTL_DAYS = 7


def _is_expired(token: dict, now: datetime) -> bool:
    try:
        return datetime.fromisoformat(token.get("expires_at", "")) <= now
    except (ValueError, TypeError):
        return True  # malformed entry → treat as expired


class TokenStore:
    def __init__(self, path: Path = _DEFAULT_PATH) -> None:
        self._path = Path(path)
        self._tokens: dict[str, dict] = self._load()

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
        atomic_json_write(self._path, self._tokens)

    def create(self, user_id: str, ttl_days: int = _DEFAULT_TTL_DAYS) -> str:
        token = secrets.token_urlsafe(32)
        expires_at = (datetime.now(timezone.utc) + timedelta(days=ttl_days)).isoformat()
        self._tokens[token] = {"user_id": user_id, "expires_at": expires_at}
        self._save()
        return token

    def validate(self, token: str) -> str | None:
        """Return user_id if token is valid and not expired, else None."""
        entry = self._tokens.get(token)
        if not entry:
            return None
        try:
            expires_at = datetime.fromisoformat(entry["expires_at"])
        except (KeyError, ValueError, TypeError):
            return None
        if datetime.now(timezone.utc) >= expires_at:
            self._tokens.pop(token, None)
            return None
        return entry.get("user_id")

    def revoke(self, token: str) -> None:
        if token in self._tokens:
            self._tokens.pop(token)
            self._save()

    def purge_expired(self) -> int:
        now = datetime.now(timezone.utc)
        expired = [t for t, entry in list(self._tokens.items()) if _is_expired(entry, now)]
        for t in expired:
            del self._tokens[t]
        if expired:
            self._save()
        return len(expired)
