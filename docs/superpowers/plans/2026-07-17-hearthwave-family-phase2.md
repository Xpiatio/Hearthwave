# Hearthwave Family Activity (Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Family activity — presence board, one-tap "I'm OK" (TTS on air + chat + presence), scheduled check-in reminders, server-synced per-user quick messages, and a `kid` role with server-side TX gating.

**Architecture:** Backend adds a `role` field to user profiles, a JSON-file presence store, a `family_status` WS message that fans out to TTS/chat/presence, and a reminder pump modeled on the monitoring-beacon pump. Frontend adds a full-screen Family activity (new `activity: 'family'` state on desktop, new bottom-nav tab on mobile, both tiers), a Family home card, and kid-mode UI gating. Spec: `docs/superpowers/specs/2026-07-17-hearthwave-home-redesign-design.md` §2, §6.

**Tech Stack:** FastAPI + WS (backend/server.py), JSON persistence (backend/persistence/*), React 18 + MUI v9 + TypeScript, Vitest + Testing Library + jest-axe, pytest.

## Global Constraints

- Branch `feat/hearthwave-family-phase2` (base 2f2ac68). Conventional commits. **No Co-Authored-By trailers, no Claude footers.**
- Frontend typecheck gate: `cd frontend && npx tsc -p tsconfig.build.json` (bare `npx tsc --noEmit` floods with pre-existing test-file errors — never use it as the gate).
- Frontend tests: `cd frontend && npx vitest run` (863+ tests must stay green; baseline 752). Backend: `cd backend && python -m pytest` (baseline 1652 green).
- `role ∈ {'admin','adult','kid'}`. Invariant: `role == 'admin'` ⇔ `is_admin == True`. Existing users migrate on load: `is_admin ? 'admin' : 'adult'`. `is_admin` remains the authority for admin checks everywhere; `role` only adds the adult/kid distinction.
- Kid locks (server-enforced, not just UI): `filter_profanity` forced `True`; `ui_level` forced `'simple'`; `save_user_prefs` allowed keys for kids = `{'dark_mode','font_scale','high_contrast'}` only; `tx_message` text must exactly match one of the kid's `quick_messages` presets or the reply is `{"type":"error","detail":"TX not allowed for this account"}`.
- New pref `quick_messages`: list of 1-20 strings, each 1-200 chars, no control chars. Absent ⇒ client falls back to existing `DEFAULTS` in QuickMessages.
- Presence store `/data/presence.json` (env `RADIO_TTY_PRESENCE`), keyed by user_id: `{"last_heard": iso|null, "last_ok": iso|null}`. Reminders store `/data/family.json` (env `RADIO_TTY_FAMILY`): `{"reminders": {user_id: {"time": "HH:MM", "enabled": bool}}}`.
- Server→client broadcast `{"type":"family_presence","entries":[{"user_id","display_name","avatar_emoji","last_heard","last_ok","missed_checkin"}]}` — sent on connect, on any presence change, and when the reminder pump flips `missed_checkin`.
- "I'm OK" standardized on-air phrase: `f"Family status: {operator_name} is okay."` (spoken via TTS with the sender's voice prefs; profanity-safe by construction).
- Client status derivation (no status enum on server): OK = `last_ok` today (local); on-air = `last_heard` within 10 min; else no-word; amber = `missed_checkin`.
- Family activity/card visible in BOTH tiers (simple included) — do NOT gate on `isOperatorTier`.
- All new interactive components: jest-axe assertion + roving-focus/keyboard support consistent with HomeScreen; "I'm OK" button uses AAC-scale target (`minHeight: 88+`).
- localStorage keys keep `radio_tty_` prefix; env vars keep `RADIO_TTY_` prefix.

---

### Task 1: Backend — `role` field, migration, admin role management, kid pref locking

**Files:**
- Modify: `backend/persistence/users.py` (DEFAULT fields ~140-173, load migration, `set_role`)
- Modify: `backend/server.py` (`save_user_prefs` handler ~2779-2800; `create_profile` handler; new `set_role` handler near other admin handlers; `ConnectionState` ~261)
- Test: `backend/tests/unit/persistence/test_users_roles.py` (new), extend `backend/tests/integration/test_server_ws.py`

**Interfaces:**
- Consumes: `UsersStore` (users.py:59), `ConnectionState` (server.py:261), `_build_user_profile_msg` (server.py:1283).
- Produces: `profile["role"]: str`; `UsersStore.set_role(user_id, role) -> dict|None`; WS `{"type":"set_role","user_id","role"}` (admin-only) → broadcasts updated `profiles`; `ConnectionState.role` attribute; helper `_is_kid(state) -> bool` in server.py. Kid pref locking inside `save_user_prefs`.

- [ ] **Step 1: Write failing unit tests**

```python
# backend/tests/unit/persistence/test_users_roles.py
import pytest
from backend.persistence.users import UsersStore


@pytest.fixture
def store(tmp_path):
    return UsersStore(str(tmp_path / "users.json"))


class TestRoleField:
    def test_create_defaults_to_adult(self, store):
        u = store.create("Kid Sis", "🙂", "Sis", "WRXB123", "Home", "pw12345678")
        assert u["role"] == "adult"

    def test_create_admin_gets_admin_role(self, store):
        u = store.create("Dad", "🙂", "Dad", "WRXB123", "Home", "pw12345678", is_admin=True)
        assert u["role"] == "admin"

    def test_set_role_kid(self, store):
        u = store.create("Kid", "🙂", "Kid", "WRXB123", "Home", "pw12345678")
        out = store.set_role(u["id"], "kid")
        assert out["role"] == "kid" and out["is_admin"] is False

    def test_set_role_admin_syncs_is_admin(self, store):
        u = store.create("Mom", "🙂", "Mom", "WRXB123", "Home", "pw12345678")
        out = store.set_role(u["id"], "admin")
        assert out["is_admin"] is True

    def test_set_role_rejects_unknown(self, store):
        u = store.create("X", "🙂", "X", "WRXB123", "Home", "pw12345678")
        with pytest.raises(ValueError):
            store.set_role(u["id"], "superuser")

    def test_legacy_user_without_role_migrates_on_load(self, store, tmp_path):
        u = store.create("Old", "🙂", "Old", "WRXB123", "Home", "pw12345678", is_admin=True)
        # simulate pre-role data
        for rec in store._users:
            rec.pop("role", None)
        store._save()
        reloaded = UsersStore(str(tmp_path / "users.json"))
        assert reloaded.get(u["id"])["role"] == "admin"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && python -m pytest tests/unit/persistence/test_users_roles.py -v`
Expected: FAIL — `KeyError: 'role'` / `AttributeError: set_role`.

- [ ] **Step 3: Implement in users.py**

In `UsersStore.create` (after `is_admin` assignment): `"role": "admin" if is_admin else "adult",`. Add migration in `_load` (or wherever the JSON list is read):

```python
ROLES = ("admin", "adult", "kid")

# in load path, after reading self._users:
changed = False
for rec in self._users:
    if "role" not in rec:
        rec["role"] = "admin" if rec.get("is_admin") else "adult"
        changed = True
if changed:
    self._save()
```

```python
def set_role(self, user_id: str, role: str) -> dict | None:
    """Set a user's role; keeps is_admin in sync (role == 'admin' <=> is_admin)."""
    if role not in ROLES:
        raise ValueError(f"unknown role: {role}")
    rec = self._find(user_id)
    if rec is None:
        return None
    rec["role"] = role
    rec["is_admin"] = role == "admin"
    self._save()
    return rec
```

(Match actual private helper names in the file — `_find`/`_save` per existing style; keep `role` OUT of `SENSITIVE_PROFILE_FIELDS` so `_safe_profile` passes it through.)

- [ ] **Step 4: Run unit tests — pass; commit**

```bash
git add backend/persistence/users.py backend/tests/unit/persistence/test_users_roles.py
git commit -m "feat(roles): role field admin|adult|kid with migration and set_role"
```

- [ ] **Step 5: Write failing WS integration tests**

Extend `backend/tests/integration/test_server_ws.py` (use `_make_auth_mocks`, `_ws_server`, `_next_of_type` helpers at lines 51/71/100). Add a `kid_client`-style fixture: mock profile dict gains `"role": "kid"`; non-admin fixture gains `"role": "adult"`.

```python
class TestRoleHandlers:
    def test_set_role_requires_admin(self, non_admin_client):
        ws = non_admin_client
        ws.send_json({"type": "set_role", "user_id": "other", "role": "kid"})
        msg = _next_of_type(ws, "error")
        assert "admin" in msg["detail"].lower()

    def test_set_role_broadcasts_profiles(self, client):
        ws = client  # admin fixture
        ws.send_json({"type": "set_role", "user_id": "test-user", "role": "kid"})
        msg = _next_of_type(ws, "profiles")
        assert any(p.get("role") == "kid" for p in msg["profiles"])

    def test_kid_prefs_locked(self, kid_client):
        ws = kid_client
        ws.send_json({"type": "save_user_prefs",
                      "prefs": {"filter_profanity": False, "ui_level": "operator",
                                "listen_only": True, "dark_mode": True}})
        msg = _next_of_type(ws, "user_profile")
        prefs = msg["profile"]["prefs"]
        assert prefs["filter_profanity"] is True
        assert prefs["ui_level"] == "simple"
        assert prefs["dark_mode"] is True   # allowed key applied
        assert prefs["listen_only"] is False  # disallowed key dropped
```

- [ ] **Step 6: Run — fail; implement in server.py**

`ConnectionState`: add `role: str = "adult"` field; populate from profile at the `ConnectionState` construction (~2165): `role=profile.get("role", "admin" if profile.get("is_admin") else "adult")`. Helper near `_check_listen_only` (2133):

```python
KID_ALLOWED_PREF_KEYS = {"dark_mode", "font_scale", "high_contrast"}

def _is_kid(state) -> bool:
    return getattr(state, "role", "adult") == "kid"
```

In `save_user_prefs` handler, after building `updates` (~2783):

```python
if _is_kid(state):
    updates = {k: v for k, v in updates.items() if k in KID_ALLOWED_PREF_KEYS}
```

And ensure kid connections always see locked values: where `state.prefs` is built on connect (~2165-2169), after the merge:

```python
if profile.get("role") == "kid":
    state.prefs["filter_profanity"] = True
    state.prefs["ui_level"] = "simple"
    state.prefs["listen_only"] = False
```

Also force the same three keys in `_safe_profile`'s prefs output for kid profiles (so the client renders locked values) — implement as a small `_effective_prefs(profile)` used by `_build_user_profile_msg`.

New handler in the WS dispatch chain (near other admin handlers, style-match `create_profile`):

```python
elif msg_type == "set_role":
    if not state.is_admin:
        await _manager.send_to(ws, {"type": "error", "detail": "Admin required"})
    else:
        role = data.get("role")
        try:
            updated = _users_store.set_role(data.get("user_id", ""), role)
        except ValueError:
            updated = None
        if updated is None:
            await _manager.send_to(ws, {"type": "error", "detail": "Bad user or role"})
        else:
            await _manager.broadcast_all(_build_profiles_msg())
```

(`_build_profiles_msg` — reuse whatever builder the existing `profiles` broadcast uses after `create_profile`/`delete_profile`; match its name.) Also add `role` to `create_profile` handler input (optional, default `"adult"`, validate against `ROLES`, pass through to `UsersStore.create` — extend `create` signature with `role: str | None = None` overriding the is_admin-derived default).

- [ ] **Step 7: Run integration tests — pass; run full backend suite**

Run: `cd backend && python -m pytest tests/integration/test_server_ws.py -v` then `python -m pytest -q`
Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add backend/server.py backend/tests/integration/test_server_ws.py backend/persistence/users.py
git commit -m "feat(roles): set_role handler, kid pref locking, role on connection state"
```

---

### Task 2: Backend — `quick_messages` pref + kid TX allowlist gate

**Files:**
- Modify: `backend/persistence/users.py` (DEFAULT_PREFS ~34-49)
- Modify: `backend/server.py` (`save_user_prefs` validation ~2779-2794; `tx_message` handler guards ~2211-2220)
- Test: extend `backend/tests/integration/test_server_ws.py`

**Interfaces:**
- Consumes: Task 1's `_is_kid(state)`, `KID_ALLOWED_PREF_KEYS`.
- Produces: pref key `quick_messages: list[str]` (validated); kid TX gate inside `tx_message`. NOTE: `quick_messages` must ALSO be added to `KID_ALLOWED_PREF_KEYS`? **No — kids cannot edit their own allowlist.** Only adults/admins set a kid's presets (via existing admin `update_profile`-style path or their own prefs). Admin edits another user's presets via new admin branch in `save_user_prefs`? **No** — keep it minimal: new admin-only WS msg `{"type":"set_user_quick_messages","user_id","quick_messages"}` reusing the same validator.

- [ ] **Step 1: Write failing tests**

```python
class TestQuickMessagesPref:
    def test_save_valid_list(self, client):
        ws = client
        ws.send_json({"type": "save_user_prefs",
                      "prefs": {"quick_messages": ["Standing by", "QSL"]}})
        msg = _next_of_type(ws, "user_profile")
        assert msg["profile"]["prefs"]["quick_messages"] == ["Standing by", "QSL"]

    def test_reject_bad_shapes(self, client):
        ws = client
        ws.send_json({"type": "save_user_prefs",
                      "prefs": {"quick_messages": ["ok", 42], "dark_mode": True}})
        msg = _next_of_type(ws, "user_profile")
        assert "quick_messages" not in msg["profile"]["prefs"] or \
            msg["profile"]["prefs"]["quick_messages"] != ["ok", 42]
        assert msg["profile"]["prefs"]["dark_mode"] is True

    def test_admin_sets_kid_presets(self, client):
        ws = client
        ws.send_json({"type": "set_user_quick_messages", "user_id": "test-user",
                      "quick_messages": ["I'm home", "Call me"]})
        msg = _next_of_type(ws, "profiles")
        target = next(p for p in msg["profiles"] if p["id"] == "test-user")
        assert target["prefs"]["quick_messages"] == ["I'm home", "Call me"]


class TestKidTxGate:
    def test_kid_tx_preset_allowed(self, kid_client):
        ws = kid_client  # fixture profile prefs include quick_messages ["I'm home"]
        ws.send_json({"type": "tx_message", "callsign": "WRXB123", "text": "I'm home"})
        msg = _next_of_type(ws, "tx_ack")  # match whatever ack type tx_message sends
        assert msg is not None

    def test_kid_tx_freetext_rejected(self, kid_client):
        ws = kid_client
        ws.send_json({"type": "tx_message", "callsign": "WRXB123", "text": "arbitrary words"})
        msg = _next_of_type(ws, "error")
        assert "not allowed" in msg["detail"].lower()
```

(Adjust `tx_ack` to the actual success frame the existing TX tests assert — read a neighboring `tx_message` test first and mirror it.)

- [ ] **Step 2: Run — fail. Implement**

`users.py` DEFAULT_PREFS: do NOT add a default (absent means client defaults) — instead just allow the key. In `server.py`:

```python
def _validate_quick_messages(value) -> list[str] | None:
    """Return sanitized list or None if invalid."""
    if not isinstance(value, list) or not (1 <= len(value) <= 20):
        return None
    out = []
    for item in value:
        if not isinstance(item, str):
            return None
        item = item.strip()
        if not (1 <= len(item) <= 200) or any(ord(c) < 32 for c in item):
            return None
        out.append(item)
    return out
```

In `save_user_prefs` allowed set (2779): add `"quick_messages"`; validation block (pattern of 2790-2794):

```python
if "quick_messages" in updates:
    qm = _validate_quick_messages(updates["quick_messages"])
    if qm is None:
        updates.pop("quick_messages")
    else:
        updates["quick_messages"] = qm
```

New admin handler `set_user_quick_messages` (same shape as `set_role` from Task 1): admin check → `_validate_quick_messages` → `_users_store.update_prefs(user_id, {"quick_messages": qm})` → broadcast profiles msg; errors as `{"type":"error","detail":...}`.

Kid TX gate in `tx_message` handler, immediately after `_check_listen_only` (2220):

```python
if _is_kid(state):
    presets = state.prefs.get("quick_messages") or []
    if data.get("text", "").strip() not in presets:
        await _manager.send_to(ws, {"type": "error", "detail": "TX not allowed for this account"})
        continue  # match the handler chain's early-exit idiom (return/continue per surrounding code)
```

Same gate in `chat_message` handler (2269)? **No** — chat is not on-air; kids may chat freely (profanity filter is forced on). Leave chat ungated.

- [ ] **Step 3: Run tests + full backend suite — pass; commit**

```bash
git add backend/server.py backend/persistence/users.py backend/tests/integration/test_server_ws.py
git commit -m "feat(family): quick_messages pref with validation, kid TX allowlist gate"
```

---

### Task 3: Backend — presence store + `family_status` ("I'm OK") + last-heard hooks

**Files:**
- Create: `backend/persistence/presence.py`
- Modify: `backend/server.py` (config path, lifespan init ~1443, WS dispatch: new `family_status` handler; `tx_message` success path ~2246-2267; connect send ~2182)
- Test: `backend/tests/unit/persistence/test_presence.py` (new), extend `backend/tests/integration/test_server_ws.py`

**Interfaces:**
- Consumes: `atomic_json_write` pattern (persistence/_utils.py), `_tx_queue` enqueue idiom from ncs.py:556 (`_operator_initiated: True`), `broadcast_rx`/`_stream_history.record_rx` chat idiom (server.py:2269-2294), `_manager.broadcast_all`.
- Produces:
  - `PresenceStore(path)` with `touch_heard(user_id, ts_iso) -> None`, `mark_ok(user_id, ts_iso) -> None`, `get(user_id) -> dict`, `all() -> dict[str, dict]`, `set_missed(user_id, missed: bool) -> bool` (returns changed), entries `{"last_heard","last_ok","missed_checkin"}`.
  - server helper `_build_family_presence_msg() -> dict` (joins presence entries with `_users_store` display_name/avatar for ALL users — users with no presence record get nulls).
  - WS client→server `{"type":"family_status","status":"ok"}`; effects: TTS enqueue of standardized phrase, chat entry, `mark_ok` + `touch_heard`, broadcast `family_presence`.
  - `tx_message` success calls `touch_heard(state.user_id, now_iso)` + broadcasts `family_presence`.

- [ ] **Step 1: Failing unit tests**

```python
# backend/tests/unit/persistence/test_presence.py
from backend.persistence.presence import PresenceStore


def test_touch_and_ok_roundtrip(tmp_path):
    p = PresenceStore(str(tmp_path / "presence.json"))
    p.touch_heard("u1", "2026-07-17T09:00:00Z")
    p.mark_ok("u1", "2026-07-17T09:05:00Z")
    e = p.get("u1")
    assert e["last_heard"] == "2026-07-17T09:00:00Z"
    assert e["last_ok"] == "2026-07-17T09:05:00Z"
    assert e["missed_checkin"] is False


def test_mark_ok_clears_missed_and_touches_heard(tmp_path):
    p = PresenceStore(str(tmp_path / "presence.json"))
    p.set_missed("u1", True)
    p.mark_ok("u1", "2026-07-17T09:05:00Z")
    e = p.get("u1")
    assert e["missed_checkin"] is False and e["last_heard"] == "2026-07-17T09:05:00Z"


def test_persists_across_reload(tmp_path):
    path = str(tmp_path / "presence.json")
    PresenceStore(path).mark_ok("u1", "2026-07-17T09:05:00Z")
    assert PresenceStore(path).get("u1")["last_ok"] == "2026-07-17T09:05:00Z"


def test_unknown_user_returns_nulls(tmp_path):
    e = PresenceStore(str(tmp_path / "presence.json")).get("nope")
    assert e == {"last_heard": None, "last_ok": None, "missed_checkin": False}


def test_set_missed_reports_change(tmp_path):
    p = PresenceStore(str(tmp_path / "presence.json"))
    assert p.set_missed("u1", True) is True
    assert p.set_missed("u1", True) is False
```

- [ ] **Step 2: Run — fail. Implement `presence.py`**

```python
"""Per-user family presence: last-heard / last-OK timestamps + missed-check-in flag."""
from backend.persistence.json_store import load_json  # match actual helper names in json_store.py
from backend.persistence._utils import atomic_json_write

_EMPTY = {"last_heard": None, "last_ok": None, "missed_checkin": False}


class PresenceStore:
    def __init__(self, path: str):
        self._path = path
        self._data: dict[str, dict] = load_json(path, default={}) or {}

    def _save(self) -> None:
        atomic_json_write(self._path, self._data)

    def _entry(self, user_id: str) -> dict:
        return self._data.setdefault(user_id, dict(_EMPTY))

    def get(self, user_id: str) -> dict:
        return dict(self._data.get(user_id, _EMPTY))

    def all(self) -> dict[str, dict]:
        return {k: dict(v) for k, v in self._data.items()}

    def touch_heard(self, user_id: str, ts_iso: str) -> None:
        self._entry(user_id)["last_heard"] = ts_iso
        self._save()

    def mark_ok(self, user_id: str, ts_iso: str) -> None:
        e = self._entry(user_id)
        e["last_ok"] = ts_iso
        e["last_heard"] = ts_iso
        e["missed_checkin"] = False
        self._save()

    def set_missed(self, user_id: str, missed: bool) -> bool:
        e = self._entry(user_id)
        if e["missed_checkin"] == missed:
            return False
        e["missed_checkin"] = missed
        self._save()
        return True
```

(Verify `load_json`/`atomic_json_write` real signatures in `json_store.py`/`_utils.py` first; match them.)

- [ ] **Step 3: Unit tests pass; commit**

```bash
git add backend/persistence/presence.py backend/tests/unit/persistence/test_presence.py
git commit -m "feat(family): presence store (last_heard/last_ok/missed_checkin)"
```

- [ ] **Step 4: Failing integration tests**

```python
class TestFamilyStatus:
    def test_im_ok_fans_out(self, client):
        ws = client
        ws.send_json({"type": "family_status", "status": "ok"})
        presence = _next_of_type(ws, "family_presence")
        me = next(e for e in presence["entries"] if e["user_id"] == "test-user")
        assert me["last_ok"] is not None and me["missed_checkin"] is False
        # chat entry visible (rx-style broadcast)
        # and standardized phrase queued for TTS — assert via the mocked TTS/tx queue
        # (mirror how ncs spot-report tests assert enqueue; read those first)

    def test_kid_can_send_family_status(self, kid_client):
        ws = kid_client
        ws.send_json({"type": "family_status", "status": "ok"})
        assert _next_of_type(ws, "family_presence") is not None

    def test_presence_sent_on_connect(self, client):
        # connect frames already consumed by fixture helper; assert family_presence among them
        # (mirror how session_attendance-on-connect is asserted, if it is; else reconnect and scan)
        pass  # implement per existing connect-frame test idiom

    def test_tx_message_touches_last_heard(self, client):
        ws = client
        ws.send_json({"type": "tx_message", "callsign": "WRXB123", "text": "hello net"})
        presence = _next_of_type(ws, "family_presence")
        me = next(e for e in presence["entries"] if e["user_id"] == "test-user")
        assert me["last_heard"] is not None
```

- [ ] **Step 5: Run — fail. Implement server wiring**

Config: add `presence_file` to config (default `/data/presence.json`, env `RADIO_TTY_PRESENCE`) following `users_file` pattern. Lifespan (~1443): `_presence_store = PresenceStore(_config.presence_file)`.

```python
def _build_family_presence_msg() -> dict:
    entries = []
    for prof in _users_store.list_profiles():  # match actual list method name
        e = _presence_store.get(prof["id"])
        entries.append({
            "user_id": prof["id"],
            "display_name": prof["display_name"],
            "avatar_emoji": prof["avatar_emoji"],
            "last_heard": e["last_heard"],
            "last_ok": e["last_ok"],
            "missed_checkin": e["missed_checkin"],
        })
    return {"type": "family_presence", "entries": entries}
```

Handler (dispatch chain; kid-allowed, listen_only does NOT block it — it IS the safety feature, but it does TX… decision: `family_status` bypasses `_check_listen_only`? **No.** Respect listen_only for the TTS leg but still record presence + chat: if listen-only, skip TTS enqueue, still mark_ok + chat + broadcast):

```python
elif msg_type == "family_status":
    if data.get("status") != "ok":
        await _manager.send_to(ws, {"type": "error", "detail": "Unknown family status"})
    else:
        now_iso = datetime.now(timezone.utc).isoformat()
        profile = _users_store.get(state.user_id) or {}
        name = profile.get("operator_name") or profile.get("display_name") or "Operator"
        phrase = f"Family status: {name} is okay."
        _presence_store.mark_ok(state.user_id, now_iso)
        if not state.prefs.get("listen_only"):
            # enqueue TTS exactly like ncs spot report (ncs.py:556): voice per sender prefs
            await _enqueue_family_tts(phrase, state)   # thin wrapper around the tx-queue put
        await _broadcast_family_chat(phrase, state)     # broadcast_rx + _stream_history.record_rx, chat_message idiom
        await _manager.broadcast_all(_build_family_presence_msg())
```

Write `_enqueue_family_tts`/`_broadcast_family_chat` by copying the exact enqueue/broadcast lines from the spot-report handler (ncs.py:546-579) and the `chat_message` handler (server.py:2269-2294) — same fields, same profanity raw/filtered split. In `tx_message` success path (after plugin dispatch/queue put, ~2260): `_presence_store.touch_heard(state.user_id, now_iso)` + `await _manager.broadcast_all(_build_family_presence_msg())`. On connect (~2182, after `user_profile` send): `await _manager.send_to(ws, _build_family_presence_msg())`.

- [ ] **Step 6: Tests pass; full backend suite; commit**

```bash
git add backend/server.py backend/tests/integration/test_server_ws.py
git commit -m "feat(family): family_status I'm-OK fan-out (TTS+chat+presence) and last-heard on TX"
```

---

### Task 4: Backend — check-in reminders store + admin handlers + pump

**Files:**
- Create: `backend/family/__init__.py`, `backend/family/reminders.py` (pure gating logic)
- Create: `backend/persistence/family.py` (reminders store)
- Modify: `backend/server.py` (config `family_file` env `RADIO_TTY_FAMILY`; lifespan init; pump registration ~1580-1588; WS handlers `set_family_reminder`, `get_family_reminders`)
- Test: `backend/tests/unit/family/test_reminders.py`, `backend/tests/unit/persistence/test_family_store.py`, extend integration

**Interfaces:**
- Consumes: `PresenceStore` (Task 3), beacon pump pattern (`backend/beacon/monitoring.py:23` `should_emit_beacon`, `_online_status_pump` server.py:1360).
- Produces:
  - `FamilyStore(path)`: `get_reminders() -> dict[str, dict]`, `set_reminder(user_id, time_hhmm: str|None, enabled: bool) -> dict` (None time deletes), entries `{"time": "HH:MM", "enabled": bool}`.
  - Pure helper `backend/family/reminders.py`: `is_checkin_missed(reminder: dict, last_ok_iso: str|None, now_local: datetime) -> bool` — True when `enabled`, `now_local.time() >= reminder time`, and `last_ok` is absent or before today's reminder time (local day).
  - `_family_reminder_pump()` async task, 30 s period: for each reminder, compute missed; on change `presence.set_missed(uid, missed)`; if any changed → broadcast `family_presence`. Day rollover: before today's reminder time, missed=False.
  - WS `{"type":"set_family_reminder","user_id","time":"09:00","enabled":true}` admin-only → ack via broadcast `{"type":"family_reminders","reminders":{...}}`; `{"type":"get_family_reminders"}` (any adult/admin; kids get error) → same msg to requester.

- [ ] **Step 1: Failing pure-logic tests**

```python
# backend/tests/unit/family/test_reminders.py
from datetime import datetime
from backend.family.reminders import is_checkin_missed

R = {"time": "09:00", "enabled": True}


def dt(h, m=0):
    return datetime(2026, 7, 17, h, m)


def test_not_missed_before_deadline():
    assert is_checkin_missed(R, None, dt(8, 59)) is False


def test_missed_after_deadline_no_ok():
    assert is_checkin_missed(R, None, dt(9, 1)) is True


def test_ok_today_before_deadline_counts():
    assert is_checkin_missed(R, "2026-07-17T07:30:00", dt(10)) is False


def test_ok_yesterday_does_not_count():
    assert is_checkin_missed(R, "2026-07-16T09:30:00", dt(10)) is True


def test_ok_today_after_deadline_clears():
    assert is_checkin_missed(R, "2026-07-17T09:30:00", dt(10)) is False


def test_disabled_never_missed():
    assert is_checkin_missed({"time": "09:00", "enabled": False}, None, dt(12)) is False


def test_bad_time_never_missed():
    assert is_checkin_missed({"time": "9am", "enabled": True}, None, dt(12)) is False
```

Note: `last_ok` stored UTC ISO; `is_checkin_missed` receives `now_local` and must convert `last_ok` to the same local zone before comparing dates — implement with `datetime.fromisoformat(...).astimezone(now_local.tzinfo)` when `now_local` is aware, naive-compare otherwise (tests above use naive).

- [ ] **Step 2: Implement `reminders.py`**

```python
"""Pure check-in reminder gating — no I/O, mirrors backend/beacon/monitoring.py style."""
from datetime import datetime, time


def _parse_hhmm(value: str) -> time | None:
    try:
        h, m = value.split(":")
        return time(int(h), int(m))
    except (ValueError, AttributeError):
        return None


def is_checkin_missed(reminder: dict, last_ok_iso: str | None, now_local: datetime) -> bool:
    if not reminder.get("enabled"):
        return False
    deadline = _parse_hhmm(reminder.get("time", ""))
    if deadline is None or now_local.time() < deadline:
        return False
    if not last_ok_iso:
        return True
    try:
        last_ok = datetime.fromisoformat(last_ok_iso.replace("Z", "+00:00"))
    except ValueError:
        return True
    if now_local.tzinfo is not None:
        last_ok = last_ok.astimezone(now_local.tzinfo)
    elif last_ok.tzinfo is not None:
        last_ok = last_ok.replace(tzinfo=None)
    return last_ok.date() != now_local.date()
```

Rule: enabled + past deadline + no OK **today** (local) ⇒ missed. An OK at any time today clears the miss.

- [ ] **Step 3: Pure tests pass. FamilyStore tests + implementation**

```python
# backend/tests/unit/persistence/test_family_store.py
from backend.persistence.family import FamilyStore


def test_set_get_delete_reminder(tmp_path):
    s = FamilyStore(str(tmp_path / "family.json"))
    s.set_reminder("u1", "09:00", True)
    assert s.get_reminders() == {"u1": {"time": "09:00", "enabled": True}}
    s.set_reminder("u1", None, False)
    assert s.get_reminders() == {}


def test_persists(tmp_path):
    path = str(tmp_path / "family.json")
    FamilyStore(path).set_reminder("u1", "21:30", True)
    assert FamilyStore(path).get_reminders()["u1"]["time"] == "21:30"


def test_rejects_bad_time(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        FamilyStore(str(tmp_path / "family.json")).set_reminder("u1", "25:99", True)
```

`FamilyStore` implementation mirrors `PresenceStore` (same load/atomic-write helpers); validate time via `backend.family.reminders._parse_hhmm` (raise `ValueError` if None and time arg not None).

- [ ] **Step 4: Commit stores + logic**

```bash
git add backend/family backend/persistence/family.py backend/tests/unit/family backend/tests/unit/persistence/test_family_store.py
git commit -m "feat(family): check-in reminder store and pure missed-checkin logic"
```

- [ ] **Step 5: Server wiring + integration tests**

Integration tests: admin `set_family_reminder` → `family_reminders` broadcast; non-admin rejected; kid `get_family_reminders` rejected; pump flip test — set reminder in the past with no OK, call the pump body once directly (extract body as `_family_reminder_tick()` so tests invoke it without the sleep loop, mirroring how beacon logic is testable), assert `family_presence` broadcast has `missed_checkin: true` for that user.

Pump (register alongside 1580-1588 tasks):

```python
async def _family_reminder_pump():
    while True:
        try:
            await _family_reminder_tick()
        except Exception:
            logger.exception("family reminder tick failed")
        await asyncio.sleep(30)


async def _family_reminder_tick():
    changed = False
    now_local = datetime.now().astimezone()
    for uid, rem in _family_store.get_reminders().items():
        missed = is_checkin_missed(rem, _presence_store.get(uid)["last_ok"], now_local)
        if _presence_store.set_missed(uid, missed):
            changed = True
    if changed:
        await _manager.broadcast_all(_build_family_presence_msg())
```

Handlers: `set_family_reminder` (admin-only; `time=None or "HH:MM"`, ValueError → error frame; on success broadcast `{"type":"family_reminders","reminders":_family_store.get_reminders()}` to all admins/adults — simplest: broadcast_all, kids' client just ignores). `get_family_reminders`: `_is_kid(state)` → error; else `send_to` the same msg. Also send `family_reminders` on connect for non-kid users (~2182).

- [ ] **Step 6: Full backend suite green; commit**

```bash
git add backend/server.py backend/tests/integration/test_server_ws.py
git commit -m "feat(family): reminder admin handlers and missed-checkin pump"
```

---

### Task 5: Frontend — WS types + App plumbing (presence, reminders, family activity state, kid gating)

**Files:**
- Modify: `frontend/src/types/ws.ts` (UserProfile ~403-413, UserPrefs ~386-401, WsMessage union ~544-600, new msg types)
- Modify: `frontend/src/App.tsx` (state ~158, switch ~312-731, handlers ~963+, sharedProps ~1191-1270, shells ~1282-1335)
- Test: `frontend/src/__tests__/App.presence.test.ts` — pure helpers only (App.tsx has no mount harness; put derivation logic in a helper module so it's testable)
- Create: `frontend/src/family/presence.ts` (pure status derivation)

**Interfaces:**
- Consumes: backend msgs from Tasks 1-4.
- Produces (later tasks rely on these exact names):
  - Types: `role: 'admin' | 'adult' | 'kid'` on `UserProfile`; `quick_messages?: string[]` on `UserPrefs`; `FamilyPresenceEntry { user_id: string; display_name: string; avatar_emoji: string; last_heard: string | null; last_ok: string | null; missed_checkin: boolean }`; `FamilyPresenceMsg { type: 'family_presence'; entries: FamilyPresenceEntry[] }`; `FamilyRemindersMsg { type: 'family_reminders'; reminders: Record<string, { time: string; enabled: boolean }> }` — both added to `WsMessage` union.
  - `frontend/src/family/presence.ts`: `export type MemberStatus = 'ok' | 'on_air' | 'no_word'`; `export function deriveStatus(e: FamilyPresenceEntry, now: Date): MemberStatus` (on_air if last_heard within 10 min; ok if last_ok same local day; else no_word).
  - App state: `familyPresence: FamilyPresenceEntry[]`, `familyReminders: Record<string, {time: string; enabled: boolean}>`; `activity` union extended to `'home' | 'station' | 'family'`; `handleOpenActivity(a: 'station' | 'ncs' | 'family')`; sends `sendImOk(): void` (`send({type:'family_status',status:'ok'})`), `sendSetReminder(userId, time, enabled)`, `sendSetRole(userId, role)`, `sendSetUserQuickMessages(userId, list)`.
  - Kid gating: `isKid = profile?.role === 'kid'`; when kid — Settings entry points hidden (HomeScreen `onOpenSettings` becomes undefined; shells receive `settingsLocked: true`… simplest: pass `isKid: boolean` through sharedProps and to HomeScreen).
  - `quickMessages: string[]` resolved: `profile?.prefs?.quick_messages ?? QUICK_DEFAULTS` — one-time localStorage migration: on first `user_profile` where pref absent and `localStorage['radio_tty_quick_messages']` parses non-default, `send save_user_prefs` with it.

- [ ] **Step 1: Failing tests for `deriveStatus`**

```typescript
// frontend/src/family/__tests__/presence.test.ts
import { describe, it, expect } from 'vitest'
import { deriveStatus } from '../presence'

const base = { user_id: 'u', display_name: 'U', avatar_emoji: '🙂', missed_checkin: false }
const now = new Date('2026-07-17T15:00:00')

describe('deriveStatus', () => {
  it('on_air when heard within 10 min', () => {
    expect(deriveStatus({ ...base, last_heard: '2026-07-17T14:55:00', last_ok: null }, now)).toBe('on_air')
  })
  it('ok when last_ok today', () => {
    expect(deriveStatus({ ...base, last_heard: '2026-07-17T08:00:00', last_ok: '2026-07-17T08:00:00' }, now)).toBe('ok')
  })
  it('no_word when ok was yesterday', () => {
    expect(deriveStatus({ ...base, last_heard: null, last_ok: '2026-07-16T08:00:00' }, now)).toBe('no_word')
  })
  it('no_word for all-null', () => {
    expect(deriveStatus({ ...base, last_heard: null, last_ok: null }, now)).toBe('no_word')
  })
})
```

- [ ] **Step 2: Implement `presence.ts`; tests pass**

```typescript
import type { FamilyPresenceEntry } from '../types/ws'

export type MemberStatus = 'ok' | 'on_air' | 'no_word'

const ON_AIR_WINDOW_MS = 10 * 60 * 1000

export function deriveStatus(e: FamilyPresenceEntry, now: Date): MemberStatus {
  if (e.last_heard && now.getTime() - new Date(e.last_heard).getTime() < ON_AIR_WINDOW_MS) return 'on_air'
  if (e.last_ok && new Date(e.last_ok).toDateString() === now.toDateString()) return 'ok'
  return 'no_word'
}
```

- [ ] **Step 3: Types + App wiring**

ws.ts: add fields/types/union entries exactly as in Interfaces. App.tsx: new state, two new `case 'family_presence'` / `case 'family_reminders'` in `handleWsMessage`; extend `activity` union + `handleOpenActivity`; `handleGoHome` unchanged. Add sends. Thread `familyPresence`, `familyReminders`, `isKid`, `quickMessages`, and the send callbacks into `sharedProps`; HomeScreen gets `onOpenActivity('family')` and `unreadCount` unchanged. Kid: `onOpenSettings` prop to HomeScreen/shells passed as no-op + `isKid` flag so they hide the buttons (implemented in Task 6/7 components; App only supplies the flag).

- [ ] **Step 4: Typecheck + full frontend suite green; commit**

Run: `cd frontend && npx tsc -p tsconfig.build.json && npx vitest run`

```bash
git add frontend/src/types/ws.ts frontend/src/App.tsx frontend/src/family
git commit -m "feat(family): presence/reminder plumbing, family activity state, kid flag"
```

---

### Task 6: Frontend — FamilyPanel (presence board, I'm OK, quick messages, reminders admin) + home card + desktop wiring

**Files:**
- Create: `frontend/src/components/FamilyPanel/FamilyPanel.tsx`, `MemberCard.tsx`, `ReminderEditor.tsx`
- Test: `frontend/src/components/FamilyPanel/__tests__/FamilyPanel.test.tsx`
- Modify: `frontend/src/components/HomeScreen/HomeScreen.tsx` (cards array ~34-47, Props ~9-18)
- Modify: `frontend/src/App.tsx` (shell ladder ~1282-1335: render FamilyPanel full-screen when `activity === 'family'` on desktop)
- Test: extend `frontend/src/components/HomeScreen/__tests__/HomeScreen.test.tsx`

**Interfaces:**
- Consumes: Task 5's types/`deriveStatus`/send callbacks; ActivityCard pattern (Paper minHeight 140); AAC sizing (`minHeight: 88`, AACGridButton precedent); QuickMessages component `{operatorName, onSelect}`.
- Produces:

```typescript
export interface FamilyPanelProps {
  profile: UserProfile
  entries: FamilyPresenceEntry[]
  reminders: Record<string, { time: string; enabled: boolean }>
  isKid: boolean
  isAdmin: boolean
  quickMessages: string[]
  onImOk: () => void
  onQuickMessage: (text: string) => void   // sends as tx_message via existing handleSend path
  onSetReminder: (userId: string, time: string | null, enabled: boolean) => void
  onGoHome: () => void
}
```

  - HomeScreen `Props` gains `familyEntries: FamilyPresenceEntry[]` + card pushed for BOTH tiers: `{ key: 'family', emoji: '🏠', title: 'Family', subtitle: <summary>, onClick: () => onOpenActivity('family') }` where summary = `'Everyone OK'` when every entry with a reminder-or-any-data derives `ok`, `'{n} missed check-in'` when any `missed_checkin`, else `''`. `onOpenActivity` union gains `'family'`. HomeScreen also gains `isKid: boolean` — when true, hide the Settings IconButton (line ~68-84 header).

- [ ] **Step 1: Failing FamilyPanel tests**

```tsx
// FamilyPanel.test.tsx — follow HomeScreen.test.tsx conventions (ThemeProvider wrap, makeProps factory, axe)
import { render as rtlRender, screen, fireEvent, within } from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { makeTheme } from '../../../theme'
import { describe, it, expect, vi } from 'vitest'
import { axe } from 'jest-axe'
import { FamilyPanel } from '../FamilyPanel'

// makeProps factory: two entries (one ok-today, one missed_checkin), reminders for u2,
// quickMessages ['I love you', 'Heading home'], vi.fn() handlers, isKid false, isAdmin true.

describe('FamilyPanel', () => {
  it('renders a member card per entry with status text', () => {
    render(<FamilyPanel {...makeProps()} />)
    const board = screen.getByRole('list', { name: 'Family members' })
    const items = within(board).getAllByRole('listitem')
    expect(items).toHaveLength(2)
    expect(within(items[0]).getByText(/OK/)).toBeInTheDocument()
    expect(within(items[1]).getByText('Missed check-in')).toBeInTheDocument()
  })
  it('giant I\'m OK button fires onImOk', () => {
    const props = makeProps()
    render(<FamilyPanel {...props} />)
    fireEvent.click(screen.getByRole('button', { name: "I'm OK" }))
    expect(props.onImOk).toHaveBeenCalledOnce()
  })
  it('quick messages fire onQuickMessage with preset text', () => {
    const props = makeProps()
    render(<FamilyPanel {...props} />)
    fireEvent.click(screen.getByRole('button', { name: 'Heading home' }))
    expect(props.onQuickMessage).toHaveBeenCalledWith('Heading home')
  })
  it('reminder editor hidden for non-admin, saves for admin', () => {
    const nonAdmin = makeProps({ isAdmin: false })
    const { unmount } = render(<FamilyPanel {...nonAdmin} />)
    expect(screen.queryByLabelText(/Check-in reminder/)).not.toBeInTheDocument()
    unmount()
    const admin = makeProps()
    render(<FamilyPanel {...admin} />)
    fireEvent.change(screen.getByLabelText('Check-in reminder for U2'), { target: { value: '09:00' } })
    expect(admin.onSetReminder).toHaveBeenCalledWith('u2', '09:00', true)
  })
  it('kid mode hides reminder editor and shows only I\'m OK + quick messages', () => {
    render(<FamilyPanel {...makeProps({ isKid: true, isAdmin: false })} />)
    expect(screen.getByRole('button', { name: "I'm OK" })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Heading home' })).toBeInTheDocument()
    expect(screen.queryByLabelText(/Check-in reminder/)).not.toBeInTheDocument()
  })
  it('back button returns home', () => {
    const props = makeProps()
    render(<FamilyPanel {...props} />)
    fireEvent.click(screen.getByRole('button', { name: 'Back to home' }))
    expect(props.onGoHome).toHaveBeenCalledOnce()
  })
  it('has no axe violations', async () => {
    const { container } = render(<FamilyPanel {...makeProps()} />)
    expect(await axe(container)).toHaveNoViolations()
  })
})
```

Write these as REAL assertions (the skeleton comments above name the queries — implement them fully; every `it` must assert).

- [ ] **Step 2: Implement components**

`FamilyPanel.tsx`: full-screen `Box` layout — header (Back IconButton `aria-label="Back to home"`, title "Family"), presence board `role="list" aria-label="Family members"` grid of `MemberCard`s, then giant I'm OK `ButtonBase` (`minHeight: 96`, emoji ✅ + "I'm OK", `fontSize: '1.4rem'`, AACApp send-bar precedent), then `QuickMessages`-style preset row (render buttons from `quickMessages` prop directly — do NOT reuse the localStorage component; simple `Button` list `minHeight: 56` calling `onQuickMessage(text)`), and (admin, not kid) `ReminderEditor` per member. `MemberCard.tsx`: Paper with avatar emoji (2.5rem), display_name, status chip — `ok` success "OK ✓ {time}", `on_air` info "On air", `no_word` default "No word", `missed_checkin` warning "Missed check-in" (overrides others), last-heard line "Last heard {relative}". Status colors via theme palette (success/info/warning), never color-only: text label always present. `ReminderEditor.tsx`: `TextField type="time"` + `Switch` + save on change → `onSetReminder`; label `Check-in reminder for {name}`.

Use `deriveStatus(entry, new Date())` from Task 5.

- [ ] **Step 3: FamilyPanel tests pass; commit**

```bash
git add frontend/src/components/FamilyPanel
git commit -m "feat(family): FamilyPanel presence board, I'm OK button, presets, reminder editor"
```

- [ ] **Step 4: HomeScreen card + desktop wiring + tests**

HomeScreen tests (extend existing file): family card present in simple AND operator tier; subtitle "Everyone OK" when all ok; "1 missed check-in" when a missed entry; clicking fires `onOpenActivity('family')`; kid hides Settings button. Implement: push family card after Chat card (before Net Control) in cards array; summary helper inline; `isKid` prop hides settings IconButton. App.tsx ladder: `activity === 'family'` branch renders `<FamilyPanel …/>` (desktop, before the DesktopApp else-branch, mirroring the `activity === 'home'` branch); wire `onImOk={() => send({type:'family_status',status:'ok'})}` etc. from Task 5 callbacks; `useEscapeToHome` already active — verify Escape from FamilyPanel returns home (it will, since hook is desktop-global; just don't double-bind).

- [ ] **Step 5: Typecheck + suite green; commit**

```bash
git add frontend/src/components/HomeScreen frontend/src/App.tsx
git commit -m "feat(family): family home card with summary, desktop full-screen activity"
```

---

### Task 7: Frontend — mobile Family tab, kid UI gating in shells, UsersPanel role controls

**Files:**
- Modify: `frontend/src/components/MobileApp/MobileApp.tsx` (tab union ~221, activeTab clamp ~234, BottomNavigation ~340-354)
- Modify: `frontend/src/components/DesktopApp/DesktopApp.tsx` (kid: hide Settings toggle; kid composer = presets only)
- Modify: `frontend/src/components/MobileApp/MobileApp.tsx` (same kid gating)
- Modify: `frontend/src/components/UsersPanel/UsersPanel.tsx` (role select in create dialog ~226-229; role chip/menu in table ~130)
- Modify: `frontend/src/components/MessageInput` or composer call sites (kid: replace free-text composer with preset buttons)
- Test: extend `MobileApp.tier.test.tsx` (family tab both tiers), new `MobileApp.kid.test.tsx` + `DesktopApp.kid.test.tsx`, extend `UsersPanel.test.tsx`

**Interfaces:**
- Consumes: `isKid`, `quickMessages`, send callbacks from sharedProps (Task 5); `sendSetRole` for UsersPanel.
- Produces: `MobileAppProps` + `DesktopAppProps` gain `isKid: boolean`, `quickMessages: string[]`; `UsersPanelProps` gains `onSetRole: (userId: string, role: 'admin' | 'adult' | 'kid') => void` and rows read `profile.role`.

- [ ] **Step 1: Failing tests**

MobileApp: family tab visible in BOTH tiers (`getByRole('button', {name: 'Family'})` with uiLevel 'simple' and 'operator'); tapping shows FamilyPanel content; simple-tier clamp keeps `'family'` valid (adjust clamp: `activeTab = isOperatorTier ? tab : (tab === 'family' ? 'family' : 'chat')`). Kid tests (both shells): Settings button absent; free-text message input absent; preset buttons render from `quickMessages` and fire send. UsersPanel: role select renders 3 options; changing fires `onSetRole('u2','kid')`; create dialog has role select defaulting 'adult' (replaces is_admin checkbox — create payload sends `role`).

- [ ] **Step 2: Implement**

MobileApp: `tab` union += `'family'`; nav action `<BottomNavigationAction label="Family" value="family" icon={<span aria-hidden>🏠</span>} />` UNGATED (both tiers); panel block `{activeTab === 'family' && <FamilyPanel …/>}` (reuse same props from sharedProps; `onGoHome` → `setTab('chat')` on mobile). Kid gating both shells: `{!isKid && <SettingsButton/>}` pattern at each Settings entry point; composer: `{isKid ? <PresetComposer quickMessages={…} onSend={…}/> : <MessageInput …/>}` — `PresetComposer` = small inline component (button row, minHeight 56) living in `frontend/src/components/FamilyPanel/PresetComposer.tsx`, shared by both shells. UsersPanel: replace `is_admin` Chip with role `Select` (admin/adult/kid) per row wired to `onSetRole`; create dialog: `Select` role replaces checkbox; payload `{...form, role}` (App's create handler passes `role` through in `create_profile` send).

- [ ] **Step 3: Typecheck + full suite + axe green; commit**

```bash
git add frontend/src/components
git commit -m "feat(family): mobile family tab, kid-mode shells, role management UI"
```

---

### Task 8: Docs + whole-feature verification

**Files:**
- Modify: `USER_MANUAL.md` (Family activity section: presence board, I'm OK, reminders, kid accounts, quick messages), `README.md` (feature bullet), `docs/index.html` ONLY if it lists features (no version bump — that's release-time via /release skill)
- Verify: nothing else changes.

- [ ] **Step 1: Write docs** — plain language, mirror the NCS/SKYWARN doc sections' structure: what it is, who sees it (both tiers; kid specifics), how to use, admin setup (roles, reminders, kid presets).
- [ ] **Step 2: Full verification**

```bash
cd backend && python -m pytest -q          # all green
cd frontend && npx tsc -p tsconfig.build.json && npx vitest run && npm run build
```

- [ ] **Step 3: Commit**

```bash
git add USER_MANUAL.md README.md docs/index.html
git commit -m "docs: family activity, roles, check-in reminders"
```

---

## Self-review notes (spec §2/§6 coverage)

- Presence board ✅ T3/T5/T6. "I'm OK" ✅ T3/T6. Check-in reminders ✅ T4/T6 (amber = missed_checkin chip; notification via existing `notifications_enabled` client behavior on `family_presence` flip — covered in T5 App wiring: fire browser notification when an entry flips to missed and pref enabled — implementer: add to `case 'family_presence'`). Family quick messages ✅ T2/T5/T6. Kid accounts ✅ T1/T2/T7. Role field + server TX gating ✅ T1/T2. Structured status msg + presence store ✅ T3.
- Out of scope (later phases): neighborhood activity, kiosk, switch scanning. Wall-display "I'm OK" reuse comes with Phase 4.
- Known simplifications (deliberate): reminder = one daily HH:MM per member; presence has no historical log; STT-heard-callsign → presence mapping deferred (only own TX updates last_heard).
