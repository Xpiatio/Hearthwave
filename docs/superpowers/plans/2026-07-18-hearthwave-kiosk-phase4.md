# Hearthwave Kiosk Wall Display (Phase 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A passive `/display` wall-kiosk screen (presence board, alert banner, last messages, next net, clock) authenticated by admin-issued device tokens, with tap-to-wake limited interaction ("Mark X OK" + household quick messages).

**Architecture:** New `DeviceTokenStore` (`/data/device_tokens.json`, same atomic-JSON idiom as `tokens.py`) feeds a third WS auth path (`?device_token=`). Display connections get `role="display"` ConnectionState with a hard server-side allowlist of two message types. Frontend adds a fourth shell, `DisplayApp`, selected in `main.tsx` by `window.location.pathname === '/display'` (nginx `try_files` already serves the SPA on any path), with its own minimal WS hook — it never touches `useAuth`.

**Tech Stack:** FastAPI WS (backend/server.py), React 18 + MUI v9, vitest + jest-axe, pytest.

## Global Constraints

- Typecheck gate: `cd frontend && npx tsc -p tsconfig.build.json` (NEVER bare `npx tsc` — floods).
- Test runners: `cd frontend && npx vitest run`; `cd backend && python -m pytest`.
- Conventional commits; **no Co-Authored-By trailers, no AI footers**.
- MUI in this repo rejects `inputProps`/`InputLabelProps` — use `slotProps={{ htmlInput, inputLabel }}`.
- localStorage keys keep the legacy `radio_tty_` prefix; env vars keep `RADIO_TTY_` prefix.
- Display connections are **not users**: never call `_users_store` with a display id; `user_id` is `"display:<id>"` only for ConnectionManager bookkeeping.
- Kid-lock precedent applies: any TX from a display must be server-side allowlisted (exact-match against admin config), mirroring the kid quick-message gate at `backend/server.py:2484-2488`.

---

### Task 1: DeviceTokenStore (backend persistence)

**Files:**
- Create: `backend/persistence/device_tokens.py`
- Test: `backend/tests/unit/persistence/test_device_token_store.py`

**Interfaces:**
- Consumes: `backend/persistence/atomic.py` `atomic_json_write` (same import `tokens.py` uses — check that file's exact import line and copy it).
- Produces: `DeviceTokenStore(path=None)` with:
  - `create(label: str) -> dict` — record `{id, token, label, created_at, last_seen}`; `id` = `secrets.token_urlsafe(6)`, `token` = `secrets.token_urlsafe(32)`, `last_seen=None`
  - `list_all() -> list[dict]` — all records, insertion order
  - `revoke(token_id: str) -> bool`
  - `validate(token: str) -> dict | None` — returns record and stamps `last_seen` (persisted)

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/unit/persistence/test_device_token_store.py
import json
from backend.persistence.device_tokens import DeviceTokenStore


def _store(tmp_path):
    return DeviceTokenStore(path=tmp_path / "device_tokens.json")


class TestCreate:
    def test_create_returns_record_with_token(self, tmp_path):
        s = _store(tmp_path)
        rec = s.create("Kitchen tablet")
        assert rec["label"] == "Kitchen tablet"
        assert len(rec["token"]) >= 32
        assert rec["id"] and rec["created_at"]
        assert rec["last_seen"] is None

    def test_create_persists_to_disk(self, tmp_path):
        s = _store(tmp_path)
        rec = s.create("Kitchen tablet")
        data = json.loads((tmp_path / "device_tokens.json").read_text())
        assert data["tokens"][0]["token"] == rec["token"]

    def test_create_rejects_blank_label(self, tmp_path):
        import pytest
        with pytest.raises(ValueError):
            _store(tmp_path).create("   ")

    def test_create_rejects_long_label(self, tmp_path):
        import pytest
        with pytest.raises(ValueError):
            _store(tmp_path).create("x" * 81)


class TestValidate:
    def test_validate_good_token_returns_record_and_stamps_last_seen(self, tmp_path):
        s = _store(tmp_path)
        rec = s.create("Kitchen tablet")
        got = s.validate(rec["token"])
        assert got["id"] == rec["id"]
        assert got["last_seen"] is not None

    def test_validate_unknown_token_returns_none(self, tmp_path):
        assert _store(tmp_path).validate("nope") is None

    def test_validate_survives_reload(self, tmp_path):
        s = _store(tmp_path)
        rec = s.create("Kitchen tablet")
        s2 = _store(tmp_path)
        assert s2.validate(rec["token"])["id"] == rec["id"]


class TestRevoke:
    def test_revoke_removes_token(self, tmp_path):
        s = _store(tmp_path)
        rec = s.create("Kitchen tablet")
        assert s.revoke(rec["id"]) is True
        assert s.validate(rec["token"]) is None

    def test_revoke_unknown_id_returns_false(self, tmp_path):
        assert _store(tmp_path).revoke("nope") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/persistence/test_device_token_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.persistence.device_tokens'`

- [ ] **Step 3: Implement the store**

Open `backend/persistence/tokens.py` first and mirror its structure exactly (default-path env override, load-on-init, atomic write helper import).

```python
# backend/persistence/device_tokens.py
"""Admin-issued device tokens for the /display wall kiosk.

Unlike session tokens these have no expiry — a wall tablet should not
log itself out — so revocation (admin-initiated) is the only removal path.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

from .atomic import atomic_json_write  # match tokens.py's actual import
from ..timeutil import utc_now_iso     # match server.py's actual import

_DEFAULT_PATH = Path(os.environ.get("RADIO_TTY_DEVICE_TOKENS", "/data/device_tokens.json"))

MAX_LABEL_LEN = 80


class DeviceTokenStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _DEFAULT_PATH
        self._tokens: list[dict] = []
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            import json
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
```

Adjust the two imports (`atomic_json_write`, `utc_now_iso`) to whatever `backend/persistence/tokens.py` and `backend/server.py` actually import — do not invent new helpers.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/persistence/test_device_token_store.py -v`
Expected: 9 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/persistence/device_tokens.py backend/tests/unit/persistence/test_device_token_store.py
git commit -m "feat(kiosk): device token store"
```

---

### Task 2: WS auth path + display connection scope gate

**Files:**
- Modify: `backend/server.py` — `websocket_endpoint` (~line 2390), ConnectionState wiring (~2420), snapshot block (~2437-2457), message loop top (~2460)
- Modify: `backend/server.py` — module init where `_token_store`/`_users_store` are constructed (grep `_token_store =`): add `_device_token_store` global, constructed the same way
- Test: `backend/tests/integration/test_display_ws.py`

**Interfaces:**
- Consumes: `DeviceTokenStore` from Task 1.
- Produces:
  - WS query param `device_token` accepted by `/ws`
  - Display connections: `ConnectionState(user_id=f"display:{rec['id']}", is_admin=False, role="display", prefs=dict(DEFAULT_PREFS))`
  - Helper `def _is_display(state) -> bool: return state.role == "display"`
  - `_DISPLAY_ALLOWED_MSGS = {"display_im_ok", "display_quick_message"}` — loop rejects everything else with `{"type": "error", "detail": "Not available on wall display"}` (handlers themselves land in Task 3/4; here they may fall through to the generic unknown-type path)

- [ ] **Step 1: Write the failing tests**

Look at `backend/tests/integration/test_server_ws.py` first for the established fixture idiom (how it builds a TestClient, seeds `_users_store`/`_token_store`, connects `client.websocket_connect("/ws?token=...")`, drains snapshot messages). Reuse those fixtures/helpers — add a `display_token` fixture that seeds a `DeviceTokenStore` into the server module the same way the user/token stores are seeded.

```python
# backend/tests/integration/test_display_ws.py
"""Display (kiosk) WebSocket auth + scope gating."""
# imports/fixtures mirroring test_server_ws.py …


class TestDisplayAuth:
    def test_valid_device_token_connects_and_gets_snapshots(self, client, display_token):
        with client.websocket_connect(f"/ws?device_token={display_token}") as ws:
            types = [ws.receive_json()["type"] for _ in range(4)]
            assert "status" in types
            assert "family_presence" in types
            assert "neighborhood_state" in types
            assert "chat_history" in types

    def test_display_snapshot_excludes_user_only_payloads(self, client, display_token):
        with client.websocket_connect(f"/ws?device_token={display_token}") as ws:
            types = [ws.receive_json()["type"] for _ in range(4)]
            assert "user_profile" not in types
            assert "contacts" not in types

    def test_bad_device_token_closes_4001(self, client):
        # match test_server_ws.py's existing close-code assertion idiom
        ...

    def test_revoked_token_cannot_connect(self, client, display_token, device_store):
        rec = device_store.list_all()[0]
        device_store.revoke(rec["id"])
        # expect close 4001


class TestDisplayScope:
    def test_display_cannot_send_tx_message(self, client, display_token):
        with client.websocket_connect(f"/ws?device_token={display_token}") as ws:
            _drain_snapshots(ws)
            ws.send_json({"type": "tx_message", "callsign": "WABC123", "text": "hi"})
            msg = _next_of_type(ws, "error")
            assert "wall display" in msg["detail"].lower()

    def test_display_cannot_use_admin_messages(self, client, display_token):
        with client.websocket_connect(f"/ws?device_token={display_token}") as ws:
            _drain_snapshots(ws)
            ws.send_json({"type": "device_token_list"})
            msg = _next_of_type(ws, "error")
            assert "wall display" in msg["detail"].lower()
```

Fill `...`/helpers from the existing integration test file's idioms (`_drain_snapshots`, `_next_of_type` style helpers exist there or are trivial to add locally).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/integration/test_display_ws.py -v`
Expected: FAIL — connection closes 4001 (device_token param unknown)

- [ ] **Step 3: Implement**

In `websocket_endpoint` signature add `device_token: str | None = Query(default=None)`. Auth block becomes:

```python
    # Device tokens (wall display) are a separate identity class: no user
    # profile, hard-scoped message allowlist, role="display".
    display_rec = None
    if _device_token_store and device_token:
        display_rec = _device_token_store.validate(device_token)
        if not display_rec:
            await ws.accept()
            await ws.close(code=4001)
            return
    if display_rec is None:
        # existing ticket/token user auth block, unchanged
        ...
```

Display branch after `ws.accept()`:

```python
    if display_rec is not None:
        state = ConnectionState(
            user_id=f"display:{display_rec['id']}",
            is_admin=False,
            prefs=dict(DEFAULT_PREFS),
            role="display",
        )
        history_msgs = _stream_history.render_for(True)  # always profanity-filtered
        _manager.add(ws, state)
        _log.info("Display connected: %s (%s)", ws.client, display_rec["label"])
        if _audit_log:
            _audit_log.log("display_connect", user_id=state.user_id,
                           ip=_extract_ip(ws.headers, str(ws.client.host) if ws.client else "unknown"))
        await _manager.send_to(ws, _build_status())
        await _manager.send_to(ws, _build_family_presence_msg())
        await _manager.send_to(ws, _build_neighborhood_state_msg())
        await _manager.send_to(ws, {"type": "chat_history", "messages": history_msgs})
    else:
        # existing user snapshot block, unchanged
```

Restructure minimally — prefer wrapping the existing user-only snapshot lines in the `else` over duplicating them.

Top of the receive loop, immediately after `msg_type = data.get("type")` and **before** the plugin dispatch (plugins must not see display traffic either):

```python
            if _is_display(state) and msg_type not in _DISPLAY_ALLOWED_MSGS:
                await _manager.send_to(ws, {"type": "error", "detail": "Not available on wall display"})
                continue
```

Module-level, next to `_is_kid`:

```python
_DISPLAY_ALLOWED_MSGS = {"display_im_ok", "display_quick_message"}


def _is_display(state: "ConnectionState") -> bool:
    return state.role == "display"
```

Store init: find where `_token_store` is constructed at startup and add, alongside:

```python
_device_token_store: DeviceTokenStore | None = None
# in the same startup/init function:
_device_token_store = DeviceTokenStore()
```

with the import `from .persistence.device_tokens import DeviceTokenStore` matching the file's existing relative-import style.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/integration/test_display_ws.py tests/integration/test_server_ws.py -v`
Expected: new tests PASS, existing test_server_ws.py stays green

- [ ] **Step 5: Commit**

```bash
git add backend/server.py backend/tests/integration/test_display_ws.py
git commit -m "feat(kiosk): device-token WS auth with display scope gate"
```

---

### Task 3: Admin device-token management + household quick messages config

**Files:**
- Modify: `backend/config.py` — add `display_quick_messages` property (mirror an existing list-or-string property; see `ncs_preamble_text` for the property idiom)
- Modify: `backend/server.py` — three new admin WS handlers + `set_admin_config` acceptance of `display_quick_messages` + status dict field
- Test: `backend/tests/integration/test_display_admin.py`

**Interfaces:**
- Consumes: `DeviceTokenStore.create/list_all/revoke`, `_manager.disconnect_user`.
- Produces:
  - `config.display_quick_messages -> list[str]` (default `[]`)
  - WS `device_token_create {label}` → reply `{"type": "device_token_created", "record": {...incl. full token}}` + follow-up `device_tokens` list msg
  - WS `device_token_list` → `{"type": "device_tokens", "tokens": [{id,label,created_at,last_seen}]}` — **no token field** (full token shown only once at create)
  - WS `device_token_revoke {id}` → refreshed `device_tokens` reply; also `await _manager.disconnect_user(f"display:{id}")`
  - `_build_status()` gains `"display_quick_messages": _config.display_quick_messages`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/integration/test_display_admin.py
# fixtures: admin ws connection idiom from test_server_ws.py


class TestDeviceTokenAdmin:
    def test_create_returns_full_token_once(self, admin_ws):
        admin_ws.send_json({"type": "device_token_create", "label": "Kitchen"})
        msg = _next_of_type(admin_ws, "device_token_created")
        assert msg["record"]["label"] == "Kitchen"
        assert len(msg["record"]["token"]) >= 32

    def test_list_omits_token_field(self, admin_ws):
        admin_ws.send_json({"type": "device_token_create", "label": "Kitchen"})
        _next_of_type(admin_ws, "device_token_created")
        admin_ws.send_json({"type": "device_token_list"})
        msg = _next_of_type(admin_ws, "device_tokens")
        assert msg["tokens"] and "token" not in msg["tokens"][0]

    def test_revoke_disconnects_live_display(self, admin_ws, client):
        admin_ws.send_json({"type": "device_token_create", "label": "Kitchen"})
        rec = _next_of_type(admin_ws, "device_token_created")["record"]
        with client.websocket_connect(f"/ws?device_token={rec['token']}") as dws:
            _drain_display_snapshots(dws)
            admin_ws.send_json({"type": "device_token_revoke", "id": rec["id"]})
            _next_of_type(admin_ws, "device_tokens")
            # display socket should now be closed (receive raises)
            import pytest
            with pytest.raises(Exception):
                while True:
                    dws.receive_json()

    def test_non_admin_rejected(self, user_ws):
        user_ws.send_json({"type": "device_token_create", "label": "Kitchen"})
        msg = _next_of_type(user_ws, "error")
        assert "Admin" in msg["detail"]


class TestDisplayQuickMessagesConfig:
    def test_admin_can_set_and_status_carries_it(self, admin_ws):
        admin_ws.send_json({"type": "set_admin_config",
                            "display_quick_messages": ["Dinner is ready", "Come home please"]})
        # follow existing set_admin_config ack idiom from test_server_ws.py
        admin_ws.send_json({"type": "get_status"})
        msg = _next_of_type(admin_ws, "status")
        assert msg["display_quick_messages"] == ["Dinner is ready", "Come home please"]

    def test_empty_list_allowed(self, admin_ws):
        admin_ws.send_json({"type": "set_admin_config", "display_quick_messages": []})
        admin_ws.send_json({"type": "get_status"})
        msg = _next_of_type(admin_ws, "status")
        assert msg["display_quick_messages"] == []

    def test_invalid_entries_rejected(self, admin_ws):
        admin_ws.send_json({"type": "set_admin_config",
                            "display_quick_messages": ["ok", "x" * 300]})
        msg = _next_of_type(admin_ws, "error")
        assert "quick message" in msg["detail"].lower()
```

Check how `set_admin_config` acks and how `get_status` is requested in existing tests — mirror exactly; if there is no `get_status` message, read the re-broadcast `status` instead.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/integration/test_display_admin.py -v`
Expected: FAIL (unknown message types / missing status key)

- [ ] **Step 3: Implement**

`backend/config.py` — mirror the `ncs_preamble_text` property pattern but list-valued:

```python
    @property
    def display_quick_messages(self) -> list[str]:
        v = self._data.get("display_quick_messages", [])
        return v if isinstance(v, list) else []
```

(Adapt to the file's actual internal dict/property idiom — copy a neighboring property verbatim and change names.)

`backend/server.py` handlers, placed with the other admin handlers (after `set_family_reminder`, same `state.is_admin` guard idiom at line ~2587):

```python
            elif msg_type == "device_token_create":
                if not state.is_admin:
                    await _manager.send_to(ws, {"type": "error", "detail": "Admin access required."})
                    continue
                if _device_token_store is None:
                    continue
                try:
                    rec = _device_token_store.create(data.get("label") or "")
                except ValueError as exc:
                    await _manager.send_to(ws, {"type": "error", "detail": str(exc)})
                    continue
                await _manager.send_to(ws, {"type": "device_token_created", "record": rec})
                await _manager.send_to(ws, _build_device_tokens_msg())

            elif msg_type == "device_token_list":
                if not state.is_admin:
                    await _manager.send_to(ws, {"type": "error", "detail": "Admin access required."})
                    continue
                if _device_token_store is None:
                    continue
                await _manager.send_to(ws, _build_device_tokens_msg())

            elif msg_type == "device_token_revoke":
                if not state.is_admin:
                    await _manager.send_to(ws, {"type": "error", "detail": "Admin access required."})
                    continue
                if _device_token_store is None:
                    continue
                token_id = data.get("id") or ""
                if _device_token_store.revoke(token_id):
                    await _manager.disconnect_user(f"display:{token_id}")
                await _manager.send_to(ws, _build_device_tokens_msg())
```

Builder next to the other `_build_*` helpers:

```python
def _build_device_tokens_msg() -> dict:
    tokens = _device_token_store.list_all() if _device_token_store else []
    return {
        "type": "device_tokens",
        "tokens": [{k: r[k] for k in ("id", "label", "created_at", "last_seen")} for r in tokens],
    }
```

`set_admin_config`: find its handler (grep `set_admin_config` in server.py) and add, following the validation style of its neighbors:

```python
                if "display_quick_messages" in data:
                    raw = data["display_quick_messages"]
                    if raw == []:
                        cleaned = []
                    else:
                        cleaned = _validate_quick_messages(raw)
                        if cleaned is None:
                            await _manager.send_to(ws, {"type": "error",
                                "detail": "Invalid display quick messages (1-20 entries, each 1-200 chars)."})
                            continue
                    # persist via the same _config save path the neighboring keys use
```

`_build_status()`: add `"display_quick_messages": _config.display_quick_messages` (grep `_build_status` and mirror a neighboring config field).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/integration/test_display_admin.py tests/integration/test_display_ws.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/config.py backend/server.py backend/tests/integration/test_display_admin.py
git commit -m "feat(kiosk): admin device-token management and household quick messages config"
```

---

### Task 4: Display interaction handlers (display_im_ok, display_quick_message)

**Files:**
- Modify: `backend/server.py` — two handlers in the WS loop (they are already allowlisted by Task 2)
- Test: `backend/tests/integration/test_display_interact.py`

**Interfaces:**
- Consumes: `_enqueue_family_tts` (server.py:2339), `_broadcast_family_chat` (server.py:2357), `_presence_store.mark_ok`, `_build_family_presence_msg`, `config.display_quick_messages`, `_tx_queue`.
- Produces:
  - WS `display_im_ok {"user_id": "<real user id>"}` — marks that user OK on their behalf (kitchen-tablet trust model), same fan-out as `family_status` (server.py:2566-2584): TTS + chat + presence broadcast. Reply ack `{"type": "display_ack", "action": "im_ok"}`.
  - WS `display_quick_message {"text": "..."}` — text must EXACTLY match an entry in `config.display_quick_messages` (kid-gate precedent); fan-out: TTS enqueue (pre-formatted, operator-initiated, station default voice) + chat echo with `display_name` = the device's label. Reply ack `{"type": "display_ack", "action": "quick_message"}`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/integration/test_display_interact.py


class TestDisplayImOk:
    def test_im_ok_marks_presence_and_broadcasts(self, client, display_token, seeded_user):
        with client.websocket_connect(f"/ws?device_token={display_token}") as ws:
            _drain_display_snapshots(ws)
            ws.send_json({"type": "display_im_ok", "user_id": seeded_user["id"]})
            # presence broadcast reaches the display too
            msg = _next_of_type(ws, "family_presence")
            entry = next(e for e in msg["entries"] if e["user_id"] == seeded_user["id"])
            assert entry["last_ok"] is not None

    def test_im_ok_unknown_user_errors(self, client, display_token):
        with client.websocket_connect(f"/ws?device_token={display_token}") as ws:
            _drain_display_snapshots(ws)
            ws.send_json({"type": "display_im_ok", "user_id": "nope"})
            msg = _next_of_type(ws, "error")
            assert "Unknown" in msg["detail"]

    def test_im_ok_posts_chat_line_with_member_name(self, client, display_token, seeded_user):
        with client.websocket_connect(f"/ws?device_token={display_token}") as ws:
            _drain_display_snapshots(ws)
            ws.send_json({"type": "display_im_ok", "user_id": seeded_user["id"]})
            msg = _next_of_type(ws, "chat_echo")
            assert "is okay" in msg["text"]


class TestDisplayQuickMessage:
    def test_configured_message_is_accepted(self, client, display_token, admin_ws):
        admin_ws.send_json({"type": "set_admin_config",
                            "display_quick_messages": ["Dinner is ready"]})
        with client.websocket_connect(f"/ws?device_token={display_token}") as ws:
            _drain_display_snapshots(ws)
            ws.send_json({"type": "display_quick_message", "text": "Dinner is ready"})
            msg = _next_of_type(ws, "display_ack")
            assert msg["action"] == "quick_message"

    def test_unlisted_text_rejected(self, client, display_token):
        with client.websocket_connect(f"/ws?device_token={display_token}") as ws:
            _drain_display_snapshots(ws)
            ws.send_json({"type": "display_quick_message", "text": "arbitrary free text"})
            msg = _next_of_type(ws, "error")
            assert "not allowed" in msg["detail"].lower()

    def test_chat_echo_uses_device_label(self, client, display_token, admin_ws):
        admin_ws.send_json({"type": "set_admin_config",
                            "display_quick_messages": ["Dinner is ready"]})
        with client.websocket_connect(f"/ws?device_token={display_token}") as ws:
            _drain_display_snapshots(ws)
            ws.send_json({"type": "display_quick_message", "text": "Dinner is ready"})
            msg = _next_of_type(ws, "chat_echo")
            assert msg["display_name"] == "Kitchen"  # fixture label
```

Verify `family_presence` entry field names against `_build_family_presence_msg` (server.py:600) before writing assertions — adjust `entries`/`user_id`/`last_ok` to the real shape.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/integration/test_display_interact.py -v`
Expected: FAIL (handlers missing → generic error or timeout)

- [ ] **Step 3: Implement**

Handlers go in the WS loop next to `family_status` (server.py ~2566). The display's ConnectionState must carry its label for chat attribution: in Task 2's display branch, stash it — `state.voice_tx_operator = display_rec["label"]` is tempting but wrong (that field has PTT semantics); instead add a plain field to ConnectionState:

```python
# in class ConnectionState (server.py:303):
    display_label: str = ""
```

and set `display_label=display_rec["label"]` when constructing the display state in Task 2's branch.

```python
            elif msg_type == "display_im_ok":
                # Wall-display proxy for family_status "I'm OK": the kitchen
                # tablet has no user identity, so the tapped member is named
                # explicitly. Household trust model — any member tile can be
                # tapped; server only validates the user exists.
                target_id = data.get("user_id") or ""
                profile_rec = _users_store.get_public_one(target_id) if _users_store else None
                if not profile_rec:
                    await _manager.send_to(ws, {"type": "error", "detail": "Unknown family member."})
                    continue
                name = (profile_rec.get("operator_name") or profile_rec.get("display_name") or "Operator").strip()
                text = f"Family status: {name} is okay."
                await _enqueue_family_tts(text, state)  # display prefs carry no voice → station default
                await _broadcast_family_chat(text, profile_rec.get("display_name") or "")
                if _presence_store is not None:
                    _presence_store.mark_ok(target_id, utc_now_iso())
                    await _manager.broadcast(_build_family_presence_msg())
                await _manager.send_to(ws, {"type": "display_ack", "action": "im_ok"})

            elif msg_type == "display_quick_message":
                text = (data.get("text") or "").strip()
                allowed = _config.display_quick_messages if _config else []
                if text not in allowed:
                    await _manager.send_to(ws, {"type": "error",
                        "detail": "Message not allowed for this display."})
                    continue
                await _enqueue_family_tts(text, state)
                await _broadcast_family_chat(text, state.display_label or "Wall display")
                await _manager.send_to(ws, {"type": "display_ack", "action": "quick_message"})
```

Use the module's actual config global name (grep how `set_admin_config` reads config — `_config` here is a placeholder for that exact name).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/integration/ tests/unit/persistence/test_device_token_store.py -v`
Expected: all display tests PASS, no regressions

- [ ] **Step 5: Commit**

```bash
git add backend/server.py backend/tests/integration/test_display_interact.py
git commit -m "feat(kiosk): display I'm-OK proxy and allowlisted household quick messages"
```

---

### Task 5: Frontend WS types + useDisplaySocket hook + route split

**Files:**
- Modify: `frontend/src/types/ws.ts` — `DeviceTokenRecord`, `DeviceTokensMsg`, `DisplayAckMsg`; extend `StatusMsg` with `display_quick_messages: string[]`
- Create: `frontend/src/hooks/useDisplaySocket.ts`
- Modify: `frontend/src/main.tsx` — pathname split
- Create: `frontend/src/components/DisplayApp/DisplayApp.tsx` (stub for this task: token-entry screen + "connecting/connected" shell; full layout is Task 6)
- Test: `frontend/src/hooks/useDisplaySocket.test.ts`, `frontend/src/components/DisplayApp/DisplayApp.test.tsx`

**Interfaces:**
- Consumes: server messages from Tasks 2-4.
- Produces:
  - `useDisplaySocket(token: string | null)` returns `{ connected, authFailed, status, presence, neighborhood, messages, alert, send }`:
    - `status: StatusMsg | null`, `presence: FamilyPresenceEntry[]`, `neighborhood: NeighborhoodStateMsg | null`
    - `messages: ChatEntry[]` — capped at last **20** (memory-bounded for overnight running); display shows 3
    - `alert: { kind: 'weather' | 'street'; message: string; ts: string } | null` — latest of `ncs_alert` / `neighborhood_alert`
    - `send(msg: object): void`
    - `authFailed: true` on close code 4001 (no reconnect loop after auth failure)
    - reconnect with capped exponential backoff (1s → 30s) on non-4001 closes
  - localStorage key `radio_tty_device_token`
  - `main.tsx`: `window.location.pathname === '/display'` → render `<DisplayApp />` instead of `<App />`

- [ ] **Step 1: Write the failing tests**

Look at an existing WS-hook or App-level test for the established mock-WebSocket idiom (grep `new WebSocket` mocks under `frontend/src`); reuse it.

```typescript
// frontend/src/hooks/useDisplaySocket.test.ts
import { renderHook, act } from '@testing-library/react';
import { useDisplaySocket } from './useDisplaySocket';
// + the repo's standard WebSocket mock

describe('useDisplaySocket', () => {
  it('connects with device_token query param', () => {
    renderHook(() => useDisplaySocket('tok123'));
    expect(lastSocketUrl()).toContain('device_token=tok123');
  });

  it('stores family_presence, neighborhood_state, status', () => {
    const { result } = renderHook(() => useDisplaySocket('tok123'));
    act(() => mockServerSend({ type: 'family_presence', entries: [{ user_id: 'u1' }] }));
    act(() => mockServerSend({ type: 'neighborhood_state', active: false }));
    expect(result.current.presence).toHaveLength(1);
    expect(result.current.neighborhood?.active).toBe(false);
  });

  it('caps message history at 20', () => {
    const { result } = renderHook(() => useDisplaySocket('tok123'));
    act(() => {
      for (let i = 0; i < 30; i++) {
        mockServerSend({ type: 'chat_echo', ts: `t${i}`, display_name: 'A', text: `m${i}` });
      }
    });
    expect(result.current.messages).toHaveLength(20);
    expect(result.current.messages.at(-1)?.text).toBe('m29');
  });

  it('sets authFailed on close 4001 and does not reconnect', () => {
    const { result } = renderHook(() => useDisplaySocket('bad'));
    act(() => mockServerClose(4001));
    expect(result.current.authFailed).toBe(true);
    expect(socketCount()).toBe(1);
  });

  it('surfaces latest alert from ncs_alert and neighborhood_alert', () => {
    const { result } = renderHook(() => useDisplaySocket('tok123'));
    act(() => mockServerSend({ type: 'neighborhood_alert', message: 'Ice on Elm St', ts: '2026-07-18T00:00:00Z' }));
    expect(result.current.alert?.kind).toBe('street');
  });
});
```

```tsx
// frontend/src/components/DisplayApp/DisplayApp.test.tsx (this task's slice)
import { render, screen, fireEvent } from '@testing-library/react';
import { DisplayApp } from './DisplayApp';

describe('DisplayApp token entry', () => {
  beforeEach(() => localStorage.clear());

  it('asks for a device token when none stored', () => {
    render(<DisplayApp />);
    expect(screen.getByLabelText(/device token/i)).toBeInTheDocument();
  });

  it('stores the token and connects on submit', () => {
    render(<DisplayApp />);
    fireEvent.change(screen.getByLabelText(/device token/i), { target: { value: 'tok123' } });
    fireEvent.click(screen.getByRole('button', { name: /connect/i }));
    expect(localStorage.getItem('radio_tty_device_token')).toBe('tok123');
  });

  it('shows error and re-shows entry after auth failure', () => {
    localStorage.setItem('radio_tty_device_token', 'bad');
    render(<DisplayApp />);
    act(() => mockServerClose(4001));
    expect(screen.getByText(/token was not accepted/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/device token/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/hooks/useDisplaySocket.test.ts src/components/DisplayApp`
Expected: FAIL (modules missing)

- [ ] **Step 3: Implement**

`useDisplaySocket.ts` — build URL the same way `useWebSocket.ts` does (same host/proto derivation; read that file and copy its URL construction), but `?device_token=${encodeURIComponent(token)}` and **no** `/auth/ws-ticket` fetch. Keep one `useEffect` per token; on `message` switch over the six types; on `close` check `evt.code === 4001` → `setAuthFailed(true)`, else schedule reconnect via `setTimeout(min(30_000, 1000 * 2**attempt))`; clear timer on cleanup.

`DisplayApp.tsx` (stub): token state from localStorage; `authFailed` → clear stored token, show entry screen with error `Alert`; entry screen = centered MUI `Paper` with `TextField` (label "Device token", `slotProps` idiom) + `Button` "Connect"; when connected render `<Box data-testid="display-shell">` placeholder for Task 6.

`main.tsx`: read the current file first; wrap the existing root render:

```tsx
const isDisplay = window.location.pathname === '/display';
root.render(isDisplay ? <DisplayApp /> : <App />);
```

keeping any existing providers (StrictMode, theme) around both branches.

`types/ws.ts` additions:

```typescript
export interface DeviceTokenRecord {
  id: string;
  label: string;
  created_at: string;
  last_seen: string | null;
  /** Present only in the one-time device_token_created reply. */
  token?: string;
}

export interface DeviceTokensMsg { type: 'device_tokens'; tokens: DeviceTokenRecord[]; }
export interface DeviceTokenCreatedMsg { type: 'device_token_created'; record: DeviceTokenRecord; }
export interface DisplayAckMsg { type: 'display_ack'; action: 'im_ok' | 'quick_message'; }
// StatusMsg: add display_quick_messages: string[]
```

Register the new msg types in the file's message union the same way neighboring types are.

- [ ] **Step 4: Run tests + typecheck**

Run: `cd frontend && npx tsc -p tsconfig.build.json && npx vitest run src/hooks/useDisplaySocket.test.ts src/components/DisplayApp`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/ws.ts frontend/src/hooks/useDisplaySocket.ts frontend/src/main.tsx frontend/src/components/DisplayApp/
git commit -m "feat(kiosk): display socket hook, device-token entry, /display route split"
```

---

### Task 6: DisplayApp passive layout (clock, presence, alerts, messages, next net, auto-dark, drift)

**Files:**
- Modify: `frontend/src/components/DisplayApp/DisplayApp.tsx`
- Create: `frontend/src/components/DisplayApp/PresenceTile.tsx`
- Create: `frontend/src/display/autoDark.ts`
- Test: `frontend/src/components/DisplayApp/DisplayApp.test.tsx` (extend), `frontend/src/display/autoDark.test.ts`

**Interfaces:**
- Consumes: `useDisplaySocket` (Task 5), `deriveStatus` (`frontend/src/family/presence.ts:10`), `nextNetLabel` (`frontend/src/neighborhood/schedule.ts:19`), `makeTheme(dark, {fontScale})` (`frontend/src/theme.ts:8`).
- Produces:
  - `isDuskDark(now: Date): boolean` — true 19:00–06:59 local (simple fixed dusk rule; documented)
  - `PresenceTile({ entry, now, interactive, onImOk })` — avatar emoji, name, status chip (reuses `deriveStatus` labels: OK green / on air blue / no word grey / missed check-in amber), min touch target 48px
  - Layout: full-viewport grid — header row (clock `HH:MM`, date, alert banner slot), presence tile grid (auto-fit, min 220px), footer (last 3 chat lines + next-net label)
  - Burn-in drift: outer `Box` style `transform: translate(x, y)` cycling through 9 offsets (±8px) every 60s
  - Clock ticks every 30s; theme re-evaluated on the same tick via `isDuskDark`

- [ ] **Step 1: Write the failing tests**

```typescript
// frontend/src/display/autoDark.test.ts
import { isDuskDark } from './autoDark';

describe('isDuskDark', () => {
  it('dark at 19:00', () => expect(isDuskDark(new Date(2026, 6, 18, 19, 0))).toBe(true));
  it('dark at 23:30', () => expect(isDuskDark(new Date(2026, 6, 18, 23, 30))).toBe(true));
  it('dark at 03:00', () => expect(isDuskDark(new Date(2026, 6, 18, 3, 0))).toBe(true));
  it('light at 07:00', () => expect(isDuskDark(new Date(2026, 6, 18, 7, 0))).toBe(false));
  it('light at 12:00', () => expect(isDuskDark(new Date(2026, 6, 18, 12, 0))).toBe(false));
});
```

```tsx
// DisplayApp.test.tsx additions — drive the mock socket from Task 5's idiom
import { axe } from 'jest-axe';

describe('DisplayApp passive layout', () => {
  beforeEach(() => {
    localStorage.setItem('radio_tty_device_token', 'tok123');
    vi.useFakeTimers();
  });
  afterEach(() => vi.useRealTimers());

  it('renders a presence tile per family member with status', () => {
    render(<DisplayApp />);
    act(() => mockServerSend({ type: 'family_presence', entries: [okEntry('Grandma'), noWordEntry('Ben')] }));
    expect(screen.getByText('Grandma')).toBeInTheDocument();
    expect(screen.getByText(/ok/i)).toBeInTheDocument();
  });

  it('shows the latest 3 chat messages only', () => {
    render(<DisplayApp />);
    act(() => {
      for (let i = 0; i < 5; i++) mockServerSend(chatMsg(`msg ${i}`));
    });
    expect(screen.queryByText('msg 1')).not.toBeInTheDocument();
    expect(screen.getByText('msg 4')).toBeInTheDocument();
  });

  it('shows street alert banner when one arrives', () => {
    render(<DisplayApp />);
    act(() => mockServerSend({ type: 'neighborhood_alert', message: 'Ice on Elm St', ts: new Date().toISOString() }));
    expect(screen.getByRole('alert')).toHaveTextContent('Ice on Elm St');
  });

  it('shows next net from neighborhood_state schedule', () => {
    render(<DisplayApp />);
    act(() => mockServerSend({ type: 'neighborhood_state', active: false, net_day: 'Tuesday', net_time: '19:00', roster: [] }));
    expect(screen.getByText(/net tue/i)).toBeInTheDocument();
  });

  it('has no axe violations', async () => {
    const { container } = render(<DisplayApp />);
    act(() => mockServerSend({ type: 'family_presence', entries: [okEntry('Grandma')] }));
    expect(await axe(container)).toHaveNoViolations();
  });
});
```

Match `family_presence` / `neighborhood_state` payload field names to `frontend/src/types/ws.ts` (`FamilyPresenceEntry` at ws.ts:548, neighborhood at :603 area) — fixture helpers `okEntry`/`noWordEntry`/`chatMsg` build real shapes.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/display src/components/DisplayApp`
Expected: FAIL

- [ ] **Step 3: Implement**

```typescript
// frontend/src/display/autoDark.ts
/** Fixed dusk rule: dark 19:00-06:59 local. A wall display has no user
 *  pref surface, so a predictable rule beats a configurable one (YAGNI —
 *  revisit if households ask for sunset-accurate switching). */
export function isDuskDark(now: Date): boolean {
  const h = now.getHours();
  return h >= 19 || h < 7;
}
```

`DisplayApp.tsx` structure (inside its own `ThemeProvider` using `makeTheme(isDuskDark(now), { fontScale: 1.25 })`):

```tsx
<Box sx={{ height: '100vh', display: 'flex', flexDirection: 'column', p: 3, gap: 2,
           transform: `translate(${drift.x}px, ${drift.y}px)` }}>
  <Box component="header" sx={{ display: 'flex', alignItems: 'baseline', gap: 3 }}>
    <Typography sx={{ fontSize: '4rem', fontWeight: 700 }}>{clockHHMM}</Typography>
    <Typography sx={{ fontSize: '1.5rem', color: 'text.secondary' }}>{dateLabel}</Typography>
    {!connected && <Chip color="error" label="Reconnecting…" />}
  </Box>
  {alert && <Alert severity={alert.kind === 'weather' ? 'warning' : 'error'} role="alert"
                   sx={{ fontSize: '1.4rem' }}>{alert.message}</Alert>}
  <Box role="list" aria-label="Family" sx={{ display: 'grid', gap: 2, flexGrow: 1,
       gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', alignContent: 'start' }}>
    {presence.map((e) => <PresenceTile key={e.user_id} entry={e} now={now} interactive={false} />)}
  </Box>
  <Box component="footer" sx={{ display: 'flex', justifyContent: 'space-between', gap: 2 }}>
    <Box aria-label="Recent messages">
      {messages.slice(-3).map((m) => (
        <Typography key={m.ts} noWrap sx={{ fontSize: '1.1rem' }}>
          <b>{m.sender || m.display_name}</b> {m.text}
        </Typography>
      ))}
    </Box>
    <Typography sx={{ fontSize: '1.2rem', color: 'text.secondary' }}>
      {neighborhood?.active ? 'Net running now' : nextNetLabel(netDay, netTime, now)}
    </Typography>
  </Box>
</Box>
```

Timers: single `useEffect` with `setInterval(30_000)` updating `now` (drives clock + theme); second interval 60s advancing drift index through `[-8, 0, 8] × [-8, 0, 8]` offsets; both cleaned up on unmount. `ChatEntry` field names come from `frontend/src/components/ChatDisplay/ChatDisplay.tsx:6` — reuse that type, don't redeclare.

`PresenceTile.tsx`: `Paper` with avatar emoji (2.5rem), name (h6 bold), status `Chip` colored by `deriveStatus(entry, now)` (`ok`→success "OK", `on_air`→info "On air", `no_word`→default "No word"; `entry.missed_checkin`→warning "Missed check-in" takes priority). `interactive`/`onImOk` props are wired in Task 7 — accept and ignore `onImOk` when `interactive` is false.

- [ ] **Step 4: Run tests + typecheck**

Run: `cd frontend && npx tsc -p tsconfig.build.json && npx vitest run src/display src/components/DisplayApp`
Expected: PASS, axe clean

- [ ] **Step 5: Commit**

```bash
git add frontend/src/display/ frontend/src/components/DisplayApp/
git commit -m "feat(kiosk): passive display layout with clock, presence, alerts, auto-dark, drift"
```

---

### Task 7: Tap-to-wake interaction (Mark-OK + household quick messages)

**Files:**
- Modify: `frontend/src/components/DisplayApp/DisplayApp.tsx`, `frontend/src/components/DisplayApp/PresenceTile.tsx`
- Create: `frontend/src/components/DisplayApp/ConfirmOkDialog.tsx`
- Test: extend `DisplayApp.test.tsx`

**Interfaces:**
- Consumes: `useDisplaySocket().send`, `status.display_quick_messages` (Task 3/5), server `display_im_ok` / `display_quick_message` (Task 4).
- Produces:
  - Tap/click anywhere on the passive screen → `interactive` mode for **45s** (any interaction resets the timer; timeout returns to passive)
  - Interactive mode: presence tiles become buttons — tap opens `ConfirmOkDialog` ("Mark {name} as OK?" with huge Yes ≥ 96px / No buttons — the AAC huge-confirm pattern from the design spec §4)
  - Interactive mode: bottom quick-message row — one large `Button` per `display_quick_messages` entry; tap sends `{type: 'display_quick_message', text}` and shows a 3s "Sent" snackbar on `display_ack`
  - Empty `display_quick_messages` → row hidden entirely

- [ ] **Step 1: Write the failing tests**

```tsx
describe('DisplayApp wake interaction', () => {
  beforeEach(() => {
    localStorage.setItem('radio_tty_device_token', 'tok123');
    vi.useFakeTimers();
  });
  afterEach(() => vi.useRealTimers());

  function renderAwake() {
    render(<DisplayApp />);
    act(() => {
      mockServerSend({ type: 'status', display_quick_messages: ['Dinner is ready'] });
      mockServerSend({ type: 'family_presence', entries: [okEntry('Grandma', 'u1')] });
    });
    fireEvent.click(screen.getByTestId('display-shell'));
  }

  it('tap wakes interactive mode; quick messages appear', () => {
    renderAwake();
    expect(screen.getByRole('button', { name: 'Dinner is ready' })).toBeInTheDocument();
  });

  it('reverts to passive after 45s idle', () => {
    renderAwake();
    act(() => vi.advanceTimersByTime(45_000));
    expect(screen.queryByRole('button', { name: 'Dinner is ready' })).not.toBeInTheDocument();
  });

  it('tile tap opens confirm; Yes sends display_im_ok', () => {
    renderAwake();
    fireEvent.click(screen.getByRole('button', { name: /grandma/i }));
    fireEvent.click(screen.getByRole('button', { name: /yes/i }));
    expect(lastSent()).toEqual({ type: 'display_im_ok', user_id: 'u1' });
  });

  it('confirm No sends nothing', () => {
    renderAwake();
    fireEvent.click(screen.getByRole('button', { name: /grandma/i }));
    fireEvent.click(screen.getByRole('button', { name: /no/i }));
    expect(lastSent()).toBeNull();
  });

  it('quick message tap sends display_quick_message and shows Sent on ack', () => {
    renderAwake();
    fireEvent.click(screen.getByRole('button', { name: 'Dinner is ready' }));
    expect(lastSent()).toEqual({ type: 'display_quick_message', text: 'Dinner is ready' });
    act(() => mockServerSend({ type: 'display_ack', action: 'quick_message' }));
    expect(screen.getByText(/sent/i)).toBeInTheDocument();
  });

  it('interactive mode passes axe', async () => {
    renderAwake();
    expect(await axe(document.body)).toHaveNoViolations();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/DisplayApp`
Expected: new tests FAIL

- [ ] **Step 3: Implement**

- `DisplayApp`: `const [awakeUntil, setAwakeUntil] = useState(0)`; root `onClick={() => setAwakeUntil(Date.now() + 45_000)}` (also on any inner interaction via the same handler bubbling); `interactive = awakeUntil > nowMs` where `nowMs` comes from a 1s interval that only runs while `awakeUntil > 0` (don't tick every second forever on a wall display).
- `PresenceTile`: when `interactive`, wrap `Paper` in `ButtonBase` (`aria-label` = member name) calling `onImOk(entry)`; otherwise render as before.
- `ConfirmOkDialog`: MUI `Dialog` — `DialogTitle` "Mark {name} as OK?"; two buttons in a row, `sx={{ minHeight: 96, fontSize: '1.6rem', flex: 1 }}`, "Yes" (`color="success"`, `variant="contained"`) sends and closes, "No" closes.
- Quick row: `Box` of `Button`s `sx={{ minHeight: 72, fontSize: '1.3rem' }}`; on `display_ack` with `action === 'quick_message'` show `Snackbar` autoHideDuration 3000 "Sent".

- [ ] **Step 4: Run tests + typecheck**

Run: `cd frontend && npx tsc -p tsconfig.build.json && npx vitest run src/components/DisplayApp`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/DisplayApp/
git commit -m "feat(kiosk): tap-to-wake Mark-OK confirm and household quick messages"
```

---

### Task 8: Admin Settings UI — Wall displays section

**Files:**
- Modify: `frontend/src/components/AdminPanel/AdminPanel.tsx` — System tab: "Wall displays" section (token list/create/revoke + household quick messages editor)
- Modify: `frontend/src/types/ws.ts` — `AdminConfig` gains `display_quick_messages: string[]` (file per `appTypes.ts` if that's where AdminConfig lives — grep `AdminConfig`)
- Modify: `frontend/src/App.tsx` — plumb `device_tokens`/`device_token_created` messages + `display_quick_messages` status field to AdminPanel; wire send functions
- Test: `frontend/src/components/AdminPanel/AdminPanel.test.tsx` (extend)

**Interfaces:**
- Consumes: WS `device_token_create/list/revoke`, `device_tokens`, `device_token_created` (Task 3), `set_admin_config` + `display_quick_messages` status field.
- Produces (config-plumbing pattern — mirror the `ncs_zone` end-to-end chain: config.py → status dict → ws.ts StatusMsg → App.tsx status mapping → AdminConfig type → AdminPanel seedFromConfig/state/buildValues/UI):
  - AdminPanel props gain: `deviceTokens: DeviceTokenRecord[]`, `createdToken: DeviceTokenRecord | null`, `onCreateDeviceToken(label: string)`, `onRevokeDeviceToken(id: string)`
  - `AdminConfig.display_quick_messages: string[]`; `onSave` payload includes it (AdminPanel.test.tsx asserts the exact `onSave` payload AND has its own `makeConfig` — both need the new key)
  - UI: token table (label, created, last seen, Revoke); "Add display" `TextField` label + Create button; after create, one-time token shown in a copyable read-only field with warning "Copy now — it won't be shown again"; quick-messages editor = multiline `TextField` one-per-line (same idiom as the Phase 2 preset editor — find it in AdminPanel and copy)

- [ ] **Step 1: Write the failing tests**

```tsx
// AdminPanel.test.tsx additions — reuse the file's makeConfig/openSystemTab helpers
describe('Wall displays admin section', () => {
  it('lists device tokens with revoke buttons', () => {
    renderAdmin({ deviceTokens: [{ id: 'd1', label: 'Kitchen', created_at: ts, last_seen: null }] });
    expect(screen.getByText('Kitchen')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /revoke/i }));
    expect(onRevokeDeviceToken).toHaveBeenCalledWith('d1');
  });

  it('creates a token from the label field', () => {
    renderAdmin({});
    fireEvent.change(screen.getByLabelText(/display name/i), { target: { value: 'Kitchen' } });
    fireEvent.click(screen.getByRole('button', { name: /add display/i }));
    expect(onCreateDeviceToken).toHaveBeenCalledWith('Kitchen');
  });

  it('shows the one-time token after creation', () => {
    renderAdmin({ createdToken: { id: 'd1', label: 'Kitchen', created_at: ts, last_seen: null, token: 'SECRET' } });
    expect(screen.getByDisplayValue('SECRET')).toBeInTheDocument();
    expect(screen.getByText(/won't be shown again/i)).toBeInTheDocument();
  });

  it('saves display_quick_messages one-per-line in the onSave payload', () => {
    renderAdmin({});
    fireEvent.change(screen.getByLabelText(/household quick messages/i),
      { target: { value: 'Dinner is ready\nCome home please' } });
    fireEvent.click(screen.getByRole('button', { name: /save/i }));
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
      display_quick_messages: ['Dinner is ready', 'Come home please'],
    }));
  });
});
```

Adapt `renderAdmin`/spy names to the file's real test helpers. Update the file's `makeConfig` and the exact-payload `onSave` assertion with `display_quick_messages: []`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/AdminPanel`
Expected: new tests FAIL; some existing exact-payload tests may also fail until `makeConfig` updated — that's the signal to update them in Step 3

- [ ] **Step 3: Implement**

Follow the `ncs_zone` plumbing chain end-to-end (all seven stops listed in Interfaces). In App.tsx: `deviceTokens` + `createdToken` state fed from `device_tokens` / `device_token_created` WS messages; `onCreateDeviceToken = (label) => sendMessage({type: 'device_token_create', label})`; request `device_token_list` when the settings dialog opens (same trigger the dialog uses to seed other data). Clear `createdToken` when the dialog closes. UI text: section heading "Wall displays"; helper line under quick-messages editor: "Buttons shown on the wall display. One message per line."

- [ ] **Step 4: Run tests + typecheck**

Run: `cd frontend && npx tsc -p tsconfig.build.json && npx vitest run src/components/AdminPanel src/App.test.tsx`
Expected: PASS (run whatever App-level test files exist — grep `App.test`)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/AdminPanel/ frontend/src/App.tsx frontend/src/types/ws.ts
git commit -m "feat(kiosk): admin wall-display token management and quick-message editor"
```

---

### Task 9: Docs + full-suite sweep

**Files:**
- Modify: `USER_MANUAL.md` — new section `## 32. Wall display (kiosk)` after section 31
- Modify: `README.md` — one feature bullet at top of `## Features`
- Test: full suites

**Interfaces:** none (docs).

- [ ] **Step 1: Write USER_MANUAL section 32**

Cover, in the manual's existing voice (see sections 30/31 for tone): what the wall display is (kitchen-tablet glance screen); admin setup — Settings → System → Wall displays → Add display → copy one-time token; on the tablet browse to `http://<host>/display`, paste token; what it shows (presence tiles, weather/street alert banner, last 3 messages, next net, clock, auto-dark 7pm-7am, anti-burn-in pixel drift); tap-to-wake interaction (Mark-OK confirm, household quick messages — admin-configured, exact-match enforced server-side); revoking a display disconnects it immediately; note the display never exposes settings, TX, or user accounts.

- [ ] **Step 2: Add README bullet**

```markdown
- **Wall display (kiosk)** — point any tablet at `/display` with an admin-issued
  device token and it becomes a glanceable family board: who's OK, weather and
  street alerts, the last few messages, the next net, and a clock; tap to mark
  someone OK or send a household quick message — no login screen, no settings
  exposed, and every send is server-checked against the admin's allowlist
```

- [ ] **Step 3: Run both full suites + typecheck**

Run: `cd backend && python -m pytest` then `cd frontend && npx tsc -p tsconfig.build.json && npx vitest run`
Expected: all green (backend 1652+ + new; frontend 863+ + new)

- [ ] **Step 4: Commit**

```bash
git add USER_MANUAL.md README.md
git commit -m "docs: wall display kiosk manual section and README bullet"
```

---

## Verification (from spec §Verification)

- `/display` loads with a device token and NO user login
- Revoke while connected → socket drops, token entry reappears
- Display cannot invoke any non-allowlisted WS message (server-enforced, tested)
- Overnight survivability: message history capped (20), single 30s clock interval, drift cycling — no unbounded state
- Manual smoke (post-merge, at release): docker compose `-p hearthwave` up, `/health` OK, open `/display` on a tablet, tap-wake, Mark-OK heard on air
