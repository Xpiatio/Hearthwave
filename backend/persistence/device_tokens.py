"""Admin-issued device tokens for the /display wall kiosk.

Unlike session tokens these have no expiry — a wall tablet should not
log itself out — so revocation (admin-initiated) is the only removal path.
"""
from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

from backend.constants import utc_now_iso
from backend.persistence._utils import atomic_json_write

_DEFAULT_PATH = Path(os.environ.get("RADIO_TTY_DEVICE_TOKENS", "/data/device_tokens.json"))

MAX_LABEL_LEN = 80


class DeviceTokenStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _DEFAULT_PATH
        self._tokens: list[dict] = []
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            data = json.loads(self._path.read_text())
            self._tokens = list(data.get("tokens", []))

    def _save(self) -> None:
        atomic_json_write(self._path, {"tokens": self._tokens})

    def create(self, label: str) -> dict:
        label = (label or "").strip()
        if not label or len(label) > MAX_LABEL_LEN:
            raise ValueError(f"Label must be 1-{MAX_LABEL_LEN} characters.")
        rec = {
            "id": secrets.token_urlsafe(6),
            "token": secrets.token_urlsafe(32),
            "label": label,
            "created_at": utc_now_iso(),
            "last_seen": None,
        }
        self._tokens.append(rec)
        self._save()
        return dict(rec)

    def list_all(self) -> list[dict]:
        return [dict(r) for r in self._tokens]

    def revoke(self, token_id: str) -> bool:
        before = len(self._tokens)
        self._tokens = [r for r in self._tokens if r["id"] != token_id]
        if len(self._tokens) != before:
            self._save()
            return True
        return False

    def validate(self, token: str) -> dict | None:
        for rec in self._tokens:
            if secrets.compare_digest(rec["token"], token):
                rec["last_seen"] = utc_now_iso()
                self._save()
                return dict(rec)
        return None
