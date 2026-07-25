"""Admin-issued device tokens for the /display wall kiosk.

Unlike session tokens these have no expiry — a wall tablet should not
log itself out — so revocation (admin-initiated) is the only removal path.

Each record also carries the display's own presentation state: the e-ink
flag and the operator's hand-sorted tile order. That lives here rather than
in the kiosk's localStorage because kiosk browsers lose local storage (the
very reason pairing kept getting dropped), and because two wall panels in
different rooms want different orders.

Pairing codes are the short-lived, human-typeable side of a token: a six
digit code the admin reads aloud once. They are deliberately in-memory only
— a code that survived a restart would be a long-lived six-digit secret.
"""
from __future__ import annotations

import json
import logging
import os
import secrets
import time
from pathlib import Path

from backend.constants import utc_now_iso
from backend.persistence._utils import atomic_json_write

_log = logging.getLogger(__name__)

_DEFAULT_PATH = Path(os.environ.get("RADIO_TTY_DEVICE_TOKENS", "/data/device_tokens.json"))

MAX_LABEL_LEN = 80

# Tile order: a household, not a directory — these bounds only exist to stop
# a malformed client writing an unbounded blob into the token file.
MAX_ORDER_LEN = 100
MAX_ORDER_ID_LEN = 64

PAIRING_CODE_TTL_S = 600


class DeviceTokenStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _DEFAULT_PATH
        self._tokens: list[dict] = []
        # code -> (token_id, expires_at_monotonic). Never persisted.
        self._pairing_codes: dict[str, tuple[str, float]] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                self._tokens = list(data.get("tokens", []))
        except (json.JSONDecodeError, OSError) as exc:
            _log.warning("Could not load %s: %s; starting empty", self._path, exc)
            self._tokens = []

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
            "eink": False,
            "order": [],
        }
        self._tokens.append(rec)
        self._save()
        return dict(rec)

    def list_all(self) -> list[dict]:
        return [dict(r) for r in self._tokens]

    def set_eink(self, token_id: str, eink: bool) -> bool:
        for rec in self._tokens:
            if rec["id"] == token_id:
                rec["eink"] = bool(eink)
                self._save()
                return True
        return False

    def set_order(self, token_id: str, order: list) -> bool:
        """Store this display's hand-sorted tile order (a list of user ids).

        Unknown or departed ids are kept as-is: the display merges the order
        against live presence at render time, so a member who is away today
        should not lose their slot.
        """
        if not isinstance(order, list):
            raise ValueError("Order must be a list of user ids.")
        if len(order) > MAX_ORDER_LEN:
            raise ValueError(f"Order may hold at most {MAX_ORDER_LEN} entries.")
        cleaned: list[str] = []
        for item in order:
            if not isinstance(item, str) or not item or len(item) > MAX_ORDER_ID_LEN:
                raise ValueError("Order entries must be non-empty user ids.")
            if item not in cleaned:
                cleaned.append(item)
        for rec in self._tokens:
            if rec["id"] == token_id:
                rec["order"] = cleaned
                self._save()
                return True
        return False

    def revoke(self, token_id: str) -> bool:
        before = len(self._tokens)
        self._tokens = [r for r in self._tokens if r["id"] != token_id]
        if len(self._tokens) != before:
            self._pairing_codes = {
                code: pair for code, pair in self._pairing_codes.items() if pair[0] != token_id
            }
            self._save()
            return True
        return False

    def validate(self, token: str) -> dict | None:
        for rec in self._tokens:
            if secrets.compare_digest(rec["token"].encode(), token.encode()):
                rec["last_seen"] = utc_now_iso()
                self._save()
                return dict(rec)
        return None

    # --- Pairing codes -------------------------------------------------
    # A six-digit code is far too weak to be a credential on its own; it is
    # safe only because it is single-use, expires in ten minutes, and the
    # redeeming endpoint is rate limited.

    def _purge_codes(self) -> None:
        now = time.monotonic()
        self._pairing_codes = {
            code: pair for code, pair in self._pairing_codes.items() if pair[1] > now
        }

    def issue_pairing_code(self, token_id: str) -> str:
        """Mint a fresh code for *token_id*, replacing any outstanding one."""
        self._purge_codes()
        self._pairing_codes = {
            code: pair for code, pair in self._pairing_codes.items() if pair[0] != token_id
        }
        code = f"{secrets.randbelow(1_000_000):06d}"
        self._pairing_codes[code] = (token_id, time.monotonic() + PAIRING_CODE_TTL_S)
        return code

    def redeem_pairing_code(self, code: str) -> str | None:
        """Exchange a code for its token. Single use — hit or miss, it's gone."""
        self._purge_codes()
        entry = self._pairing_codes.pop((code or "").strip(), None)
        if entry is None:
            return None
        token_id = entry[0]
        for rec in self._tokens:
            if rec["id"] == token_id:
                return str(rec["token"])
        return None
