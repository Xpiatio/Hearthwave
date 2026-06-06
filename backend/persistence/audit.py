"""Append-only JSONL audit log for Radio-TTY.

Entries are written to /data/audit.log (or RADIO_TTY_AUDIT_LOG).
Each line is a JSON object: {"ts", "event", "user_id", "ip", "detail"}.

Events:
  login_success, login_fail, login_lockout  — auth_routes
  ws_connect, ws_disconnect                 — server.py WS endpoint
  tx                                        — server.py _tx_pump (PTT keyed)
  token_revoked                             — admin revoke endpoint
  admin_action                              — admin-only WS handlers
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

_log = logging.getLogger(__name__)
_DEFAULT_PATH = Path(os.environ.get("RADIO_TTY_AUDIT_LOG", "/data/audit.log"))


class AuditLog:
    def __init__(self, path: Path = _DEFAULT_PATH) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()

    def log(self, event: str, *, user_id: str = "", ip: str = "", detail: str = "") -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "user_id": user_id,
            "ip": ip,
            "detail": detail,
        }
        line = json.dumps(entry, separators=(",", ":")) + "\n"
        with self._lock:
            try:
                with open(self._path, "a", encoding="utf-8") as fh:
                    fh.write(line)
            except OSError as exc:
                _log.warning("audit log write failed: %s", exc)

    def tail(self, limit: int = 200) -> list[dict]:
        """Return the last *limit* entries as parsed dicts.

        Reads only the trailing portion of the file so a large log doesn't
        consume memory proportional to total history.
        """
        # Each JSONL entry is at most ~512 bytes; read a generous chunk from
        # the end so we can always reconstruct *limit* complete lines.
        chunk_size = max(limit * 512, 65536)
        try:
            with open(self._path, "rb") as fh:
                fh.seek(0, 2)  # seek to end
                file_size = fh.tell()
                start = max(0, file_size - chunk_size)
                fh.seek(start)
                raw = fh.read()
        except FileNotFoundError:
            return []
        except OSError as exc:
            _log.warning("audit log read failed: %s", exc)
            return []

        lines = raw.decode("utf-8", errors="replace").splitlines()
        # The first line after a mid-file seek may be incomplete; drop it.
        if start > 0 and lines:
            lines = lines[1:]

        result = []
        for line in lines[-limit:]:
            line = line.strip()
            if not line:
                continue
            try:
                result.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return result
