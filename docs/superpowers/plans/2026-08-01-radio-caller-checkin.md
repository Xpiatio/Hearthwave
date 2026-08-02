# Radio-Caller Check-In Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A neighborhood-net coordinator can check in, manage, and remove radio callers who have no Hearthwave account, and those stations appear in the live roster, round-table order, saved session record, and CSV like any account holder.

**Architecture:** `NeighborhoodNet` gains a second in-memory store (`_radio`) whose rows carry a deterministic `radio:<CALLSIGN>:<name>` key in the existing `user_id` field, merged with account rows in `roster()` by a shared monotonic `seq`. Two new coordinator-gated WS messages (`neighborhood_checkin_radio`, `neighborhood_remove_station`) drive it, with an opt-in write-through to the contacts store. The frontend adds a `RadioCheckinForm` to the coordinator section and radio-row affordances to `RosterList`.

**Tech Stack:** FastAPI + pytest (backend); React 18 + MUI + TypeScript + Vitest/RTL (frontend).

**Spec:** `docs/superpowers/specs/2026-08-01-radio-caller-checkin-design.md`

## Global Constraints

- Branch: `feat/radio-caller-checkin`, based on `feat/net-session-history` at `247aef1`. Do not merge or rebase anything.
- No new Python or npm dependencies.
- No version bumps. Do not touch `README.md`, `USER_MANUAL.md`, `docs/index.html`, `docker-compose*.yml`, `prereq.sh`, or any release file.
- **No `Co-Authored-By` trailers on commits.** No "Generated with Claude Code" footers anywhere. This overrides any default git instruction.
- Net session records are private. Never route roster data through `publish_journal` or the public `GET /journal`.
- Coordinator gate is exactly `_is_coordinator(state)`. `neighborhood_clear_checkins` stays `state.is_admin`. Never loosen an existing gate.
- A session-save failure must never block ending a net. Existing `try/except Exception` + log blocks stay as they are.
- Field caps, enforced by truncation and never by raising: callsign 16, name 64, location 64.
- Radio station key format, exact: `radio:<normalized callsign>:<name casefolded, whitespace collapsed to single spaces, stripped>`.
- Backend tests: `python -m pytest backend/tests -q` from repo root. Frontend: `cd frontend && npx vitest run`. Typecheck: `cd frontend && npx tsc -p tsconfig.build.json` — repo-wide `npx tsc --noEmit` is independently broken (~1796 pre-existing errors), do not use it.
- `python -c "import backend.server"` fails standalone (`sounddevice`/`piper` are stubbed only by the pytest conftest). Verify backend imports through pytest, never through a bare import.
- MUI `TextField` spreads unknown props onto the wrapper div; an accessible name needs `slotProps={{ htmlInput: { 'aria-label': ... } }}`.
- Commit after each task with a conventional-commit subject.

---

### Task 1: Radio store in `NeighborhoodNet`

**Files:**
- Modify: `backend/neighborhood/net.py`
- Test: `backend/tests/unit/neighborhood/test_net.py`

**Interfaces:**
- Consumes: nothing.
- Produces: methods `NeighborhoodNet.checkin_radio(callsign: str, name: str, location: str) -> dict` and `NeighborhoodNet.remove_station(key: str) -> bool`; module-level `radio_station_key(callsign: str, name: str) -> str` and constant `RADIO_KEY_PREFIX = "radio:"` in `backend/neighborhood/net.py`. `roster()` now returns rows sorted by check-in order across both stores, with the internal `seq` field stripped. Radio rows carry `"via": "radio"`; account rows carry no `via` key.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/unit/neighborhood/test_net.py`:

```python
def test_checkin_radio_creates_a_marked_row_with_a_deterministic_key():
    net = NeighborhoodNet()
    row = net.checkin_radio("wrab123", "Maria", "Maple St")
    assert row["user_id"] == "radio:WRAB123:maria"
    assert row["callsign"] == "WRAB123"
    assert row["name"] == "Maria"
    assert row["location"] == "Maple St"
    assert row["via"] == "radio"
    assert row["status"] == "checked_in"
    assert row["called"] is False


def test_checkin_radio_is_idempotent_per_station():
    net = NeighborhoodNet()
    net.checkin_radio("WRAB123", "Maria", "Maple St")
    net.checkin_radio("wrab123", "  maria ", "Oak St")
    roster = net.roster()
    assert len(roster) == 1
    # Latest check-in wins on the mutable fields, key stays stable.
    assert roster[0]["location"] == "Oak St"


def test_same_callsign_different_names_are_two_stations():
    # A GMRS family shares one licensed callsign — two people on it are two
    # stations, not one row overwriting the other.
    net = NeighborhoodNet()
    net.checkin_radio("WRAB123", "Maria", "Maple St")
    net.checkin_radio("WRAB123", "Diego", "Maple St")
    assert len(net.roster()) == 2


def test_roster_interleaves_radio_and_account_rows_in_checkin_order():
    net = NeighborhoodNet()
    net.checkin("u1", "WRAA111", "Ann", "1st St")
    net.checkin_radio("WRAB123", "Maria", "Maple St")
    net.checkin("u2", "WRAC333", "Cy", "3rd St")
    assert [r["name"] for r in net.roster()] == ["Ann", "Maria", "Cy"]


def test_re_checkin_does_not_reorder_the_roster():
    net = NeighborhoodNet()
    net.checkin("u1", "WRAA111", "Ann", "1st St")
    net.checkin_radio("WRAB123", "Maria", "Maple St")
    net.checkin("u1", "WRAA111", "Ann", "1st St")
    assert [r["name"] for r in net.roster()] == ["Ann", "Maria"]


def test_call_next_walks_radio_and_account_rows_in_the_same_order():
    net = NeighborhoodNet()
    net.checkin("u1", "WRAA111", "Ann", "1st St")
    net.checkin_radio("WRAB123", "Maria", "Maple St")
    net.start()
    assert net.call_next()["name"] == "Ann"
    second = net.call_next()
    assert second["name"] == "Maria"
    assert net.current_call == "radio:WRAB123:maria"
    assert net.call_next() is None


def test_set_status_reaches_a_radio_row():
    net = NeighborhoodNet()
    key = net.checkin_radio("WRAB123", "Maria", "Maple St")["user_id"]
    net.set_status(key, "checked_out")
    assert net.roster()[0]["status"] == "checked_out"
    # And a checked-out radio row is skipped by the round table.
    net.start()
    assert net.call_next() is None


def test_call_reset_clears_called_on_radio_rows():
    net = NeighborhoodNet()
    net.checkin_radio("WRAB123", "Maria", "Maple St")
    net.start()
    net.call_next()
    net.call_reset()
    assert net.roster()[0]["called"] is False
    assert net.current_call is None


def test_start_resets_called_on_radio_rows():
    net = NeighborhoodNet()
    net.checkin_radio("WRAB123", "Maria", "Maple St")
    net.start()
    net.call_next()
    net.start()
    assert net.roster()[0]["called"] is False


def test_remove_station_removes_only_radio_rows():
    net = NeighborhoodNet()
    net.checkin("u1", "WRAA111", "Ann", "1st St")
    key = net.checkin_radio("WRAB123", "Maria", "Maple St")["user_id"]
    assert net.remove_station("u1") is False
    assert net.remove_station("radio:NOPE:nobody") is False
    assert net.remove_station(key) is True
    assert [r["name"] for r in net.roster()] == ["Ann"]


def test_remove_station_clears_a_current_call_that_pointed_at_it():
    net = NeighborhoodNet()
    key = net.checkin_radio("WRAB123", "Maria", "Maple St")["user_id"]
    net.start()
    net.call_next()
    assert net.current_call == key
    net.remove_station(key)
    assert net.current_call is None


def test_remove_leaves_radio_rows_alone():
    # remove() is the account-deletion path; a radio key is not an account.
    net = NeighborhoodNet()
    key = net.checkin_radio("WRAB123", "Maria", "Maple St")["user_id"]
    assert net.remove(key) is False
    assert len(net.roster()) == 1


def test_end_includes_radio_rows_then_clears_both_stores():
    net = NeighborhoodNet()
    net.checkin("u1", "WRAA111", "Ann", "1st St")
    net.checkin_radio("WRAB123", "Maria", "Maple St")
    net.start()
    summary = net.end()
    assert [r["name"] for r in summary["roster"]] == ["Ann", "Maria"]
    assert net.roster() == []


def test_clear_checkins_clears_both_stores():
    net = NeighborhoodNet()
    net.checkin("u1", "WRAA111", "Ann", "1st St")
    net.checkin_radio("WRAB123", "Maria", "Maple St")
    assert net.clear_checkins() == 2
    assert net.roster() == []


def test_roster_rows_do_not_leak_the_internal_sequence_field():
    net = NeighborhoodNet()
    net.checkin_radio("WRAB123", "Maria", "Maple St")
    assert "seq" not in net.roster()[0]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest backend/tests/unit/neighborhood/test_net.py -q`
Expected: FAIL — `AttributeError: 'NeighborhoodNet' object has no attribute 'checkin_radio'`.

- [ ] **Step 3: Implement the radio store**

In `backend/neighborhood/net.py`, add this module-level helper below the imports:

```python
RADIO_KEY_PREFIX = "radio:"


def radio_station_key(callsign: str, name: str) -> str:
    """Deterministic roster key for a station with no account.

    Folding case and collapsing whitespace means the same neighbor typed
    twice lands on one row instead of two, which is what makes a re-checkin
    of a radio caller idempotent the way `checkin()` is for an account.
    """
    folded_name = " ".join((name or "").split()).casefold()
    return f"{RADIO_KEY_PREFIX}{(callsign or '').strip().upper()}:{folded_name}"
```

Extend the class docstring's roster paragraph:

```python
    """Tracks the roster and call order for an in-progress (or just-ended) net.

    Roster rows are keyed by user_id and shaped:
        {"user_id", "callsign", "name", "location", "status", "checkin_time", "called"}
    status is "checked_in" (default) or "standby".

    Two stores back the roster: `_roster` holds account holders keyed by their
    real user_id, and `_radio` holds stations a coordinator checked in off the
    air, keyed by `radio_station_key(...)` and additionally carrying
    ``"via": "radio"``. Both are merged by `roster()` in check-in order using a
    shared monotonic `seq`, so a radio caller who checked in first is called
    first. Rows keep the station key in the `user_id` field so clients see one
    flat roster with one keyspace.

    Check-ins are accepted whether or not the net is active — a "tap" before
    `start()` is an early check-in (a spot reserved ahead of the net), and it
    must survive into the started net rather than being wiped by it.
    """
```

Replace `__init__`:

```python
    def __init__(self) -> None:
        self.active: bool = False
        self.current_call: Optional[str] = None
        self._roster: dict[str, dict] = {}
        self._radio: dict[str, dict] = {}
        self._seq: int = 0
        self._started_at: float | None = None
```

Add these private helpers directly after `__init__`:

```python
    def _next_seq(self) -> int:
        """Stamp check-in order across both stores.

        Sorting on `checkin_time` instead would silently reorder an account
        holder who re-checks in (`checkin()` refreshes that field); insertion
        order, which this preserves, does not.
        """
        self._seq += 1
        return self._seq

    def _find(self, key: str) -> Optional[dict]:
        """Resolve a roster key in either store."""
        row = self._roster.get(key)
        if row is None:
            row = self._radio.get(key)
        return row

    def _ordered_rows(self) -> list[dict]:
        return sorted(
            [*self._roster.values(), *self._radio.values()],
            key=lambda row: row["seq"],
        )
```

In `checkin()`, add `"seq": self._next_seq(),` to the new-row dict (after `"called": False,`).

Add `checkin_radio` immediately after `checkin`:

```python
    def checkin_radio(self, callsign: str, name: str, location: str) -> dict:
        """Check in a station that has no account (idempotent per station key).

        Identity is supplied by the coordinator, not by a connection's own
        profile — see the `neighborhood_checkin_radio` handler in
        backend/server.py for why that is safe here.
        """
        key = radio_station_key(callsign, name)
        callsign = (callsign or "").strip().upper()
        name = (name or "").strip()
        location = (location or "").strip()
        row = self._radio.get(key)
        now = utc_now_iso()
        if row is None:
            row = {
                "user_id": key,
                "callsign": callsign,
                "name": name,
                "location": location,
                "status": "checked_in",
                "checkin_time": now,
                "called": False,
                "via": "radio",
                "seq": self._next_seq(),
            }
            self._radio[key] = row
        else:
            row["callsign"] = callsign
            row["name"] = name
            row["location"] = location
            row["checkin_time"] = now
        return row
```

Rewrite `set_status`, `call_next`, `call_reset`, `clear_checkins`, `roster`, and `end`'s clear step to span both stores:

```python
    def set_status(self, user_id: str, status: str) -> None:
        """Set a roster row's status ('checked_in', 'standby', or 'checked_out'); no-op if unknown user."""
        row = self._find(user_id)
        if row is not None:
            row["status"] = status
```

```python
    def call_next(self) -> Optional[dict]:
        """Mark the first checked-in, not-yet-called row as current and return it.

        Walks both stores in check-in order, so a radio caller takes their
        turn where they actually checked in.

        Returns None (and clears current_call) when the round is complete.
        """
        for row in self._ordered_rows():
            if row["status"] == "checked_in" and not row["called"]:
                row["called"] = True
                self.current_call = row["user_id"]
                return row
        self.current_call = None
        return None
```

```python
    def call_reset(self) -> None:
        """Clear all called flags and the current call, starting a fresh round."""
        for row in self._ordered_rows():
            row["called"] = False
        self.current_call = None
```

```python
    def clear_checkins(self) -> int:
        """Drop every roster row, account and radio alike, returning how many were removed.

        Unlike `end()`, this leaves `active` alone: an admin wiping a board
        that filled up with yesterday's check-ins (or a test run) should not
        also close a net that is currently running. Round-table progress goes
        with the rows, since `current_call` would otherwise point at a row
        that no longer exists.
        """
        removed = len(self._roster) + len(self._radio)
        self._roster = {}
        self._radio = {}
        self.current_call = None
        return removed
```

```python
    def remove_station(self, key: str) -> bool:
        """Remove a radio check-in (a coordinator fixing a mis-typed station).

        Refuses anything that isn't a radio station key, so this can never be
        used to bump an account holder off the board — that is `remove()`'s
        job, on account deletion. Returns True if a row was removed.
        """
        if not key.startswith(RADIO_KEY_PREFIX):
            return False
        removed = self._radio.pop(key, None) is not None
        if removed and self.current_call == key:
            self.current_call = None
        return removed

    def roster(self) -> list[dict]:
        """Both stores merged in check-in order, without internal bookkeeping.

        Rows are shallow copies: `seq` is an implementation detail that has no
        business on the wire or in a saved session record.
        """
        return [
            {k: v for k, v in row.items() if k != "seq"}
            for row in self._ordered_rows()
        ]
```

In `start()`, change the reset loop to `for row in self._ordered_rows():`. In `end()`, add `self._radio = {}` beside `self._roster = {}`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest backend/tests/unit/neighborhood/test_net.py -q`
Expected: PASS, all tests in the file.

Then the wider net-touching suites: `python -m pytest backend/tests -q -k "neighborhood or net_session"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/neighborhood/net.py backend/tests/unit/neighborhood/test_net.py
git commit -m "feat(neighborhood): track radio check-ins alongside account roster rows"
```

---

### Task 2: WS handlers for radio check-in and station removal

**Files:**
- Modify: `backend/server.py` (message catalogue docstring at `:44-60`; new handlers after the `neighborhood_checkin` block ending at `:3928`)
- Test: `backend/tests/integration/test_server_ws.py`

**Interfaces:**
- Consumes: `NeighborhoodNet.checkin_radio(callsign, name, location)`, `NeighborhoodNet.remove_station(key)` from Task 1; `RADIO_KEY_PREFIX` from `backend.neighborhood.net`.
- Produces: WS message `neighborhood_checkin_radio {callsign, name, location?, save_contact?}` and `neighborhood_remove_station {user_id}`. Both broadcast `neighborhood_state` on success and send `{"type": "error", "detail": ...}` to the caller on refusal.

- [ ] **Step 1: Write the failing tests**

Add these to `class TestNeighborhoodNetHandlers` (starts at `test_server_ws.py:3920`). The
helpers already exist in that file: `_neighborhood_server(tmp_path, *, role="adult",
is_admin=False, coordinator=False, mock_tts=None, profile=None, journals=False,
listen_only=False, net_sessions_dir=None)` returns `(cfg, mock_stt, mock_tts, mock_users,
mock_tokens)`; `_drain_initial(ws)` clears the connect burst; `_next_of_type(ws, "error")`
reads the next frame of a type. Every test uses the same six-patch block. Use this as the
literal template for all of them:

```python
    def test_radio_checkin_rejected_for_adult_without_coordinator_pref(self, tmp_path):
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_server(tmp_path)
        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    ws.send_json({
                        "type": "neighborhood_checkin_radio",
                        "callsign": "WRAB123", "name": "Maria", "location": "Maple St",
                    })
                    err = _next_of_type(ws, "error")
                    ws.send_json({"type": "neighborhood_get_state"})
                    state = _next_of_type(ws, "neighborhood_state")
        assert err is not None
        assert err["detail"] == "Coordinator access required"
        assert state["roster"] == []

    def test_coordinator_checks_in_a_radio_station(self, tmp_path):
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_server(
            tmp_path, coordinator=True,
        )
        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    ws.send_json({
                        "type": "neighborhood_checkin_radio",
                        "callsign": "wrab123", "name": "Maria", "location": "Maple St",
                    })
                    msg = _next_of_type(ws, "neighborhood_state")
        assert msg is not None
        assert len(msg["roster"]) == 1
        row = msg["roster"][0]
        assert row["user_id"] == "radio:WRAB123:maria"
        assert row["callsign"] == "WRAB123"
        assert row["name"] == "Maria"
        assert row["location"] == "Maple St"
        assert row["via"] == "radio"
        assert row["status"] == "checked_in"
        assert "seq" not in row
```

Then, in the same style and with the same patch block, add tests covering:

```python
def test_radio_checkin_rejects_a_blank_callsign_or_name(...):
    # Two sends: one with callsign "", one with name "   ".
    # Each: {"type": "error", "detail": "Callsign and name are required."}
    # and no roster row created.


def test_radio_checkin_truncates_over_long_fields(...):
    # callsign of 40 chars, name of 200, location of 200.
    # Expect stored lengths 16 / 64 / 64 and no error message.


def test_radio_checkin_saves_a_contact_when_asked(...):
    # save_contact: True -> a "contacts" broadcast arrives containing the new
    # callsign, and the contacts store holds it.


def test_radio_checkin_survives_a_contacts_failure(...):
    # Monkeypatch the contacts store's add_contact to raise ValueError.
    # Expect the check-in row still present in neighborhood_state and an error
    # message delivered to the sending socket only.


def test_radio_checkin_without_save_contact_writes_no_contact(...):
    # save_contact omitted -> contacts store unchanged, no contacts broadcast.


def test_coordinator_can_change_a_radio_station_status(...):
    # neighborhood_status with the radio user_id and status "checked_out"
    # updates that row (no new handler needed — this is a regression guard on
    # set_status reaching the radio store).


def test_remove_station_refuses_an_account_user_id(...):
    # An account holder checks in, coordinator sends neighborhood_remove_station
    # with that user_id.
    # Expect {"type": "error", "detail": "Only radio check-ins can be removed."}
    # and the row still present.


def test_remove_station_requires_coordinator(...):
    # Non-coordinator -> {"type": "error", "detail": "Coordinator access required"}.


def test_coordinator_removes_a_radio_station(...):
    # Check one in, remove it, roster goes empty.
```

Write each of these as a real test with real assertions against the actual fixtures — the bullets above are the required coverage, not a substitute for assertions.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest backend/tests/integration/test_server_ws.py -q -k radio`
Expected: FAIL — the handlers do not exist, so the server ignores the message and no state change or error arrives.

- [ ] **Step 3: Implement the handlers**

Insert directly after the `neighborhood_checkin` block (which ends with its `await _manager.broadcast(_build_neighborhood_state_msg())` at `server.py:3928`):

```python
            elif msg_type == "neighborhood_checkin_radio":
                # Coordinator-only, and the ONE neighborhood handler where
                # identity is client-supplied by design: these are neighbors
                # who called in over the air with no account here. There is no
                # account behind the row to impersonate — no login, no prefs,
                # no profile — so the coordinator gate is the whole control,
                # unlike neighborhood_checkin above where the connection's own
                # profile is the only trustworthy source.
                if not _is_coordinator(state):
                    await _manager.send_to(ws, {"type": "error", "detail": "Coordinator access required"})
                    continue
                callsign = normalize_callsign(data.get("callsign") or "")[:16]
                name = (data.get("name") or "").strip()[:64]
                location = (data.get("location") or "").strip()[:64]
                # Name is required here even though neighborhood_checkin falls
                # back to "Operator": attendance keys on (callsign, name), and
                # neighborhood_call_next speaks the name on the air.
                if not callsign or not name:
                    await _manager.send_to(
                        ws, {"type": "error", "detail": "Callsign and name are required."}
                    )
                    continue
                if _neighborhood is not None:
                    _neighborhood.checkin_radio(callsign, name, location)
                await _manager.broadcast(_build_neighborhood_state_msg())
                # Contacts second, and never fatal: a contacts failure must not
                # cost the coordinator the check-in they just made.
                if data.get("save_contact"):
                    if _contacts_store is None:
                        await _manager.send_to(
                            ws, {"type": "error", "detail": "Contacts store not initialised."}
                        )
                        continue
                    try:
                        updated = _contacts_store.add_contact(
                            {"callsign": callsign, "name": name, "location": location}
                        )
                        await _manager.broadcast({"type": "contacts", "contacts": updated})
                        # Saving the contact also biases Whisper toward this
                        # neighbor's callsign on the air.
                        _rebuild_stt_vocabulary()
                    except ValueError as exc:
                        await _manager.send_to(ws, {"type": "error", "detail": str(exc)})

            elif msg_type == "neighborhood_remove_station":
                if not _is_coordinator(state):
                    await _manager.send_to(ws, {"type": "error", "detail": "Coordinator access required"})
                    continue
                target_id = data.get("user_id") or ""
                if not target_id.startswith(RADIO_KEY_PREFIX):
                    await _manager.send_to(
                        ws, {"type": "error", "detail": "Only radio check-ins can be removed."}
                    )
                    continue
                if _neighborhood is not None:
                    _neighborhood.remove_station(target_id)
                await _manager.broadcast(_build_neighborhood_state_msg())
```

Import support: `RADIO_KEY_PREFIX` from `backend.neighborhood.net` and `normalize_callsign` from `backend.persistence.contacts`. Check whether each is already imported in `server.py` before adding — extend the existing import statement rather than adding a duplicate line.

Add to the message-catalogue docstring at `server.py:44-60`, matching the surrounding formatting exactly:

```
  neighborhood_checkin_radio  (coordinator) check in a station with no account
  neighborhood_remove_station (coordinator) drop a radio check-in row
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest backend/tests/integration/test_server_ws.py -q`
Expected: PASS, whole file — the neighborhood regression tests included.

Then: `python -m pytest backend/tests -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/server.py backend/tests/integration/test_server_ws.py
git commit -m "feat(neighborhood): coordinator WS messages to check in and remove radio stations"
```

---

### Task 3: Carry `via` into the saved session record

**Files:**
- Modify: `backend/persistence/net_sessions.py:60-77` (`normalize_roster`)
- Test: `backend/tests/unit/persistence/test_net_sessions.py`

**Interfaces:**
- Consumes: roster rows from Task 1 (radio rows carry `"via": "radio"`).
- Produces: stored roster rows gain a `via` key, `""` for anything that isn't a radio check-in. Consumed by Task 7's CSV column and Past Nets `Via` column.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/unit/persistence/test_net_sessions.py`:

```python
def test_normalize_roster_carries_the_radio_marker():
    rows = normalize_roster([
        {"callsign": "wrab123", "name": "Maria", "location": "Maple St",
         "status": "checked_in", "checkin_time": "2026-08-01T19:30:00Z",
         "via": "radio"},
    ])
    assert rows[0]["via"] == "radio"


def test_normalize_roster_defaults_via_to_blank():
    # Account rows and NCS rows have no `via` key at all; a stored record
    # should still have the column so a reader never has to guess.
    rows = normalize_roster([
        {"callsign": "WRAA111", "name": "Ann", "location": "1st St",
         "status": "checked_in", "checkin_time": "2026-08-01T19:30:00Z"},
    ])
    assert rows[0]["via"] == ""
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest backend/tests/unit/persistence/test_net_sessions.py -q -k via`
Expected: FAIL — `KeyError: 'via'`.

- [ ] **Step 3: Add the field**

In `normalize_roster`, add one entry to the dict comprehension after `"verified"`:

```python
            "verified": bool(row.get("verified", False)),
            # "radio" for a station a coordinator checked in off the air,
            # blank for anyone who checked themselves in.
            "via": (row.get("via") or "").strip(),
```

Also extend that function's docstring so the dropped-vs-kept split stays accurate:

```python
    """Flatten NCS or neighborhood roster rows into the stored shape.

    Round-table bookkeeping (``called``, ``user_id``) is dropped — it describes
    a net in progress, not what happened. ``via`` is kept: how a station got
    onto the board is part of what happened.
    """
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest backend/tests/unit/persistence/test_net_sessions.py -q`
Expected: PASS.

Then: `python -m pytest backend/tests -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/persistence/net_sessions.py backend/tests/unit/persistence/test_net_sessions.py
git commit -m "feat(net-sessions): record how a station reached the roster"
```

---

### Task 4: Frontend types and the `RadioCheckinForm` component

**Files:**
- Modify: `frontend/src/types/ws.ts` (`NeighborhoodRosterRow` at `:636-644`, `NetSessionRosterRow` at `:265-273`, payload interfaces near `:893-923`)
- Create: `frontend/src/components/NeighborhoodPanel/RadioCheckinForm.tsx`
- Test: `frontend/src/components/NeighborhoodPanel/__tests__/RadioCheckinForm.test.tsx`

**Interfaces:**
- Consumes: the `Contact` type already exported from `frontend/src/types/ws.ts` (check its exact shape and import path before use; it is the same type `App.tsx:168` holds).
- Produces:
  ```ts
  export interface RadioCheckinFormProps {
    contacts: Contact[];
    onCheckin: (p: { callsign: string; name: string; location: string; saveContact: boolean }) => void;
  }
  export function RadioCheckinForm(props: RadioCheckinFormProps): JSX.Element
  ```
  plus types `NeighborhoodCheckinRadioPayload` and `NeighborhoodRemoveStationPayload`, and `via?: 'radio'` on `NeighborhoodRosterRow` / `via?: string` on `NetSessionRosterRow`. Tasks 5-7 consume these.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/NeighborhoodPanel/__tests__/RadioCheckinForm.test.tsx`. Follow the import and render style of the existing `NeighborhoodPanel.test.tsx` in that directory (theme wrapper, `userEvent` setup) rather than inventing one.

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RadioCheckinForm } from '../RadioCheckinForm';

const CONTACTS = [
  { callsign: 'WRAB123', name: 'Maria', location: 'Maple St' },
  { callsign: 'WRAC456', name: 'Diego', location: 'Oak St' },
] as never[];

describe('RadioCheckinForm', () => {
  it('disables the check-in button until callsign and name are filled', async () => {
    const user = userEvent.setup();
    render(<RadioCheckinForm contacts={[]} onCheckin={vi.fn()} />);
    const button = screen.getByRole('button', { name: /check in station/i });
    expect(button).toBeDisabled();
    await user.type(screen.getByLabelText(/callsign/i), 'WRAB123');
    expect(button).toBeDisabled();
    await user.type(screen.getByLabelText(/^name/i), 'Maria');
    expect(button).toBeEnabled();
  });

  it('does not enable on whitespace alone', async () => {
    const user = userEvent.setup();
    render(<RadioCheckinForm contacts={[]} onCheckin={vi.fn()} />);
    await user.type(screen.getByLabelText(/callsign/i), '  ');
    await user.type(screen.getByLabelText(/^name/i), '  ');
    expect(screen.getByRole('button', { name: /check in station/i })).toBeDisabled();
  });

  it('fills the fields from a picked contact', async () => {
    const user = userEvent.setup();
    render(<RadioCheckinForm contacts={CONTACTS} onCheckin={vi.fn()} />);
    await user.click(screen.getByLabelText(/pick a neighbor/i));
    await user.click(screen.getByRole('option', { name: /WRAB123 — Maria/ }));
    expect(screen.getByLabelText(/callsign/i)).toHaveValue('WRAB123');
    expect(screen.getByLabelText(/^name/i)).toHaveValue('Maria');
    expect(screen.getByLabelText(/location/i)).toHaveValue('Maple St');
  });

  it('offers "save to contacts" only for a callsign the book does not have', async () => {
    const user = userEvent.setup();
    render(<RadioCheckinForm contacts={CONTACTS} onCheckin={vi.fn()} />);
    await user.type(screen.getByLabelText(/callsign/i), 'wrab123');
    expect(screen.queryByLabelText(/save to contacts/i)).not.toBeInTheDocument();
    await user.clear(screen.getByLabelText(/callsign/i));
    await user.type(screen.getByLabelText(/callsign/i), 'WRAZ999');
    expect(screen.getByLabelText(/save to contacts/i)).toBeInTheDocument();
  });

  it('submits trimmed, upper-cased values and clears the form', async () => {
    const user = userEvent.setup();
    const onCheckin = vi.fn();
    render(<RadioCheckinForm contacts={CONTACTS} onCheckin={onCheckin} />);
    await user.type(screen.getByLabelText(/callsign/i), ' wraz999 ');
    await user.type(screen.getByLabelText(/^name/i), ' Sam ');
    await user.type(screen.getByLabelText(/location/i), ' Elm St ');
    await user.click(screen.getByLabelText(/save to contacts/i));
    await user.click(screen.getByRole('button', { name: /check in station/i }));
    expect(onCheckin).toHaveBeenCalledWith({
      callsign: 'WRAZ999',
      name: 'Sam',
      location: 'Elm St',
      saveContact: true,
    });
    expect(screen.getByLabelText(/callsign/i)).toHaveValue('');
    expect(screen.getByLabelText(/^name/i)).toHaveValue('');
    expect(screen.getByRole('button', { name: /check in station/i })).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/components/NeighborhoodPanel/__tests__/RadioCheckinForm.test.tsx`
Expected: FAIL — cannot resolve `../RadioCheckinForm`.

- [ ] **Step 3: Add the types**

In `frontend/src/types/ws.ts`, add to `NeighborhoodRosterRow`:

```ts
  called: boolean;
  /** Present only on stations a coordinator checked in off the air. */
  via?: 'radio';
```

Add to `NetSessionRosterRow`:

```ts
  verified: boolean;
  /** "radio" for a coordinator-entered station, "" for a self check-in.
   *  Optional because records written before this field existed lack it. */
  via?: string;
```

Add beside the other neighborhood payloads:

```ts
/** Coordinator-only: check in a neighbor who called in over the air and has
 *  no account here. Unlike neighborhood_checkin, the identity is supplied by
 *  the client — the server gates on the coordinator grant instead. */
export interface NeighborhoodCheckinRadioPayload {
  type: 'neighborhood_checkin_radio';
  callsign: string;
  name: string;
  location: string;
  save_contact?: boolean;
}

/** Coordinator-only: drop a radio check-in row. The server refuses any
 *  user_id that isn't a radio station key. */
export interface NeighborhoodRemoveStationPayload {
  type: 'neighborhood_remove_station';
  user_id: string;
}
```

If `ws.ts` has a union of outgoing payload types, add both to it — check for one before assuming.

- [ ] **Step 4: Implement the component**

Create `frontend/src/components/NeighborhoodPanel/RadioCheckinForm.tsx`:

```tsx
import { useState } from 'react';
import {
  Box,
  Button,
  Checkbox,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
} from '@mui/material';
import type { Contact } from '../../types/ws';

export interface RadioCheckinFormProps {
  contacts: Contact[];
  onCheckin: (p: { callsign: string; name: string; location: string; saveContact: boolean }) => void;
}

const CALLSIGN_MAX = 16;
const NAME_MAX = 64;
const LOCATION_MAX = 64;

/** Coordinator-side check-in for a neighbor who called in on the radio and has
 *  no account here.
 *
 *  A Select over known contacts rather than an Autocomplete: a household's
 *  contact book is short, and the codebase has no Autocomplete anywhere else
 *  to be consistent with. Picking a contact only prefills — every field stays
 *  editable, because the point is to also handle the neighbor who has never
 *  called in before.
 *
 *  "Save to contacts" appears only for an unknown callsign, and matters more
 *  than it looks: attendance history keys on (callsign, name), so a name typed
 *  slightly differently each week fragments a regular's streak. Saving makes
 *  next week a pick instead of a retype. */
export function RadioCheckinForm({ contacts, onCheckin }: RadioCheckinFormProps) {
  const [picked, setPicked] = useState('');
  const [callsign, setCallsign] = useState('');
  const [name, setName] = useState('');
  const [location, setLocation] = useState('');
  const [saveContact, setSaveContact] = useState(false);

  const normalized = callsign.trim().toUpperCase();
  const known = contacts.some((c) => (c.callsign || '').toUpperCase() === normalized);
  const canSubmit = normalized.length > 0 && name.trim().length > 0;

  function handlePick(value: string) {
    setPicked(value);
    const contact = contacts.find((c) => c.callsign === value);
    if (!contact) return;
    setCallsign(contact.callsign || '');
    setName(contact.name || '');
    setLocation(contact.location || '');
    setSaveContact(false);
  }

  function handleSubmit() {
    if (!canSubmit) return;
    onCheckin({
      callsign: normalized,
      name: name.trim(),
      location: location.trim(),
      // A known callsign never writes a contact, whatever the box last held.
      saveContact: saveContact && !known,
    });
    setPicked('');
    setCallsign('');
    setName('');
    setLocation('');
    setSaveContact(false);
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
        Check in a radio caller
      </Typography>

      <FormControl size="small" sx={{ maxWidth: 320 }}>
        <InputLabel id="radio-checkin-contact-label">Pick a neighbor</InputLabel>
        <Select
          labelId="radio-checkin-contact-label"
          label="Pick a neighbor"
          value={picked}
          onChange={(e) => handlePick(e.target.value)}
        >
          <MenuItem value="">Someone new</MenuItem>
          {contacts.map((c) => (
            <MenuItem key={c.callsign} value={c.callsign}>
              {c.callsign} — {c.name || 'unnamed'}
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        <TextField
          size="small"
          label="Callsign"
          value={callsign}
          onChange={(e) => setCallsign(e.target.value.slice(0, CALLSIGN_MAX))}
          slotProps={{ htmlInput: { maxLength: CALLSIGN_MAX } }}
          sx={{ width: 160 }}
        />
        <TextField
          size="small"
          label="Name"
          value={name}
          onChange={(e) => setName(e.target.value.slice(0, NAME_MAX))}
          slotProps={{ htmlInput: { maxLength: NAME_MAX } }}
          sx={{ width: 200 }}
        />
        <TextField
          size="small"
          label="Location"
          value={location}
          onChange={(e) => setLocation(e.target.value.slice(0, LOCATION_MAX))}
          slotProps={{ htmlInput: { maxLength: LOCATION_MAX } }}
          sx={{ width: 200 }}
        />
      </Box>

      {normalized.length > 0 && !known && (
        <FormControlLabel
          control={
            <Checkbox
              checked={saveContact}
              onChange={(e) => setSaveContact(e.target.checked)}
            />
          }
          label="Save to contacts"
        />
      )}

      <Button
        variant="outlined"
        onClick={handleSubmit}
        disabled={!canSubmit}
        sx={{ alignSelf: 'flex-start' }}
      >
        Check in station
      </Button>
    </Box>
  );
}
```

If `Contact`'s real field names differ from `callsign`/`name`/`location`, use the real ones and adjust the test's fixture to match — do not add a translation layer.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/NeighborhoodPanel && npx tsc -p tsconfig.build.json`
Expected: PASS, clean typecheck.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/ws.ts frontend/src/components/NeighborhoodPanel/RadioCheckinForm.tsx frontend/src/components/NeighborhoodPanel/__tests__/RadioCheckinForm.test.tsx
git commit -m "feat(neighborhood): radio-caller check-in form"
```

---

### Task 5: Radio-row affordances in `RosterList`

**Files:**
- Modify: `frontend/src/components/NeighborhoodPanel/RosterList.tsx`
- Test: `frontend/src/components/NeighborhoodPanel/__tests__/RosterList.test.tsx` (create if absent; check first)

**Interfaces:**
- Consumes: `NeighborhoodRosterRow.via` from Task 4.
- Produces: `RosterListProps` gains three optional props:
  ```ts
  isCoordinator?: boolean;
  onStationStatusChange?: (userId: string, status: 'checked_in' | 'standby' | 'checked_out') => void;
  onRemoveStation?: (userId: string) => void;
  ```
  Consumed by Task 6.

- [ ] **Step 1: Write the failing tests**

In `frontend/src/components/NeighborhoodPanel/__tests__/RosterList.test.tsx`, with a helper that builds rows:

```tsx
const accountRow = {
  user_id: 'u1', callsign: 'WRAA111', name: 'Ann', location: '1st St',
  status: 'checked_in' as const, checkin_time: '2026-08-01T19:30:00Z', called: false,
};
const radioRow = {
  user_id: 'radio:WRAB123:maria', callsign: 'WRAB123', name: 'Maria',
  location: 'Maple St', status: 'checked_in' as const,
  checkin_time: '2026-08-01T19:31:00Z', called: false, via: 'radio' as const,
};
```

Tests to write:

```tsx
it('marks radio rows and only radio rows', () => {
  // render with [accountRow, radioRow], myUserId 'u1'
  // expect exactly one 'By radio' chip in the document
});

it('gives a coordinator a status control on a radio row', async () => {
  // isCoordinator, myUserId 'u1', roster [radioRow]
  // click the 'Standby' button -> onStationStatusChange called with
  // ('radio:WRAB123:maria', 'standby')
});

it('cycles a radio row through third-person labels', () => {
  // status 'standby' -> button reads 'Check out'
  // status 'checked_out' -> button reads 'Check back in' and fires 'checked_in'
});

it('keeps first-person labels on the viewer own row', () => {
  // roster [accountRow], myUserId 'u1', isCoordinator
  // expect a 'Step away' button, and clicking it calls onStatusChange (not
  // onStationStatusChange)
});

it('shows no radio controls to a non-coordinator', () => {
  // isCoordinator false, roster [radioRow], myUserId 'u1'
  // expect no 'Standby' button and no remove button
});

it('does not offer remove on an account row', () => {
  // isCoordinator, roster [accountRow, radioRow]
  // exactly one 'Remove Maria' button, none for Ann
});

it('removes a radio row without a confirmation step', async () => {
  // isCoordinator, roster [radioRow]
  // one click -> onRemoveStation('radio:WRAB123:maria')
});
```

Write these as real assertions. If `RosterList.test.tsx` already exists, extend it and reuse its existing render helper.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/NeighborhoodPanel/__tests__/RosterList.test.tsx`
Expected: FAIL — no `By radio` chip, no coordinator status control, no remove button.

- [ ] **Step 3: Implement**

Add the import:

```tsx
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
```

Extend `RosterListProps`:

```tsx
export interface RosterListProps {
  roster: NeighborhoodRosterRow[];
  currentCall: string | null;
  myUserId: string;
  onStatusChange: (status: 'checked_in' | 'standby' | 'checked_out') => void;
  /** Admin-only board wipe. Omitted (not disabled) for everyone else, so a
   *  control that can't succeed never appears. */
  onClear?: () => void;
  /** Coordinator-only radio-row controls. A radio caller has no browser, so
   *  the coordinator is the only one who can move their status. */
  isCoordinator?: boolean;
  onStationStatusChange?: (userId: string, status: 'checked_in' | 'standby' | 'checked_out') => void;
  onRemoveStation?: (userId: string) => void;
}
```

Add the third-person label map next to `NEXT_ACTION_LABEL`:

```tsx
/** The self-toggle copy above is first-person and reads wrong when a
 *  coordinator moves someone else's station, so radio rows get their own
 *  labels over the same STATUS_CYCLE. */
const STATION_ACTION_LABEL: Record<NeighborhoodRosterRow['status'], string> = {
  checked_in: 'Standby',
  standby: 'Check out',
  checked_out: 'Check back in',
};
```

Update the function signature and destructuring to take the three new props, then inside the row map add:

```tsx
            const isCurrent = row.user_id === currentCall;
            const isSelf = row.user_id === myUserId;
            const isRadio = row.via === 'radio';
            const canOperate = isRadio && !!isCoordinator;
```

Add the chip beside the callsign, after the `<Typography>` holding `row.callsign`:

```tsx
                  {isRadio && <Chip size="small" variant="outlined" label="By radio" sx={{ maxWidth: '100%' }} />}
```

Replace the status-button block at the bottom of the card:

```tsx
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: density.gap, mt: 'auto' }}>
                  <Chip size="small" color={STATUS_COLORS[row.status]} label={STATUS_LABELS[row.status]} />
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: density.gap }}>
                    {isSelf && (
                      <Button
                        size="small"
                        variant="text"
                        onClick={() => onStatusChange(nextStatus(row.status))}
                      >
                        {NEXT_ACTION_LABEL[row.status]}
                      </Button>
                    )}
                    {canOperate && onStationStatusChange && (
                      <Button
                        size="small"
                        variant="text"
                        onClick={() => onStationStatusChange(row.user_id, nextStatus(row.status))}
                      >
                        {STATION_ACTION_LABEL[row.status]}
                      </Button>
                    )}
                    {canOperate && onRemoveStation && (
                      // No confirm: this row is a coordinator's typo that never
                      // reached disk, and re-adding it costs one pick. Confirms
                      // stay for the board wipe and street alerts.
                      <Tooltip title={`Remove ${row.name}`}>
                        <IconButton
                          size="small"
                          aria-label={`Remove ${row.name}`}
                          onClick={() => onRemoveStation(row.user_id)}
                        >
                          <DeleteOutlineIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    )}
                  </Box>
                </Box>
```

Update the component's doc comment paragraph about the status toggle so it describes both cases (self row, and coordinator-operated radio row) rather than claiming the toggle only ever appears on the viewer's own row.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/NeighborhoodPanel && npx tsc -p tsconfig.build.json`
Expected: PASS, clean typecheck.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/NeighborhoodPanel/RosterList.tsx frontend/src/components/NeighborhoodPanel/__tests__/RosterList.test.tsx
git commit -m "feat(neighborhood): mark and operate radio rows in the roster"
```

---

### Task 6: Wire the panel and `App.tsx`

**Files:**
- Modify: `frontend/src/components/NeighborhoodPanel/NeighborhoodPanel.tsx` (props at `:12-39`, coordinator block at `:210-258`, `RosterList` render at `:197-203`)
- Modify: `frontend/src/App.tsx` (senders near `:1220-1231`, panel render at `:1797-1822`)
- Test: `frontend/src/components/NeighborhoodPanel/__tests__/NeighborhoodPanel.test.tsx`

**Interfaces:**
- Consumes: `RadioCheckinForm` (Task 4), `RosterList`'s new props (Task 5), `NeighborhoodCheckinRadioPayload` / `NeighborhoodRemoveStationPayload` (Task 4).
- Produces: nothing downstream.

- [ ] **Step 1: Write the failing tests**

Extend `NeighborhoodPanel.test.tsx`, reusing its existing props-builder helper:

```tsx
it('offers the radio check-in form to a coordinator', () => {
  // isCoordinator true, isKid false
  // expect a 'Check in station' button
});

it('hides the radio check-in form from a non-coordinator', () => {
  // expect no 'Check in station' button
});

it('hides the radio check-in form from a kid holding the grant', () => {
  // isCoordinator true, isKid true -> no 'Check in station' button
  // (mirrors showCoordinatorSection)
});

it('passes a radio check-in through to onRadioCheckin', async () => {
  // fill callsign + name in the form, submit
  // expect onRadioCheckin called with
  // { callsign: 'WRAZ999', name: 'Sam', location: '', saveContact: false }
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/NeighborhoodPanel/__tests__/NeighborhoodPanel.test.tsx`
Expected: FAIL — no `Check in station` button rendered.

- [ ] **Step 3: Implement the panel changes**

Add imports:

```tsx
import type { Contact, IncidentEntry, NeighborhoodAlertMsg, NeighborhoodRosterRow } from '../../types/ws';
import { RadioCheckinForm } from './RadioCheckinForm';
```

Add to `NeighborhoodPanelProps`, keeping the existing ordering style:

```tsx
  /** Contact book, used to prefill the radio check-in form. */
  contacts: Contact[];
  onRadioCheckin: (p: { callsign: string; name: string; location: string; saveContact: boolean }) => void;
  onStationStatusChange: (userId: string, status: 'checked_in' | 'standby' | 'checked_out') => void;
  onRemoveStation: (userId: string) => void;
```

Pass the new props to `RosterList`:

```tsx
      <RosterList
        roster={props.roster}
        currentCall={props.currentCall}
        myUserId={props.myUserId}
        onStatusChange={props.onStatusChange}
        onClear={props.isAdmin ? () => setClearCheckinsConfirmOpen(true) : undefined}
        isCoordinator={showCoordinatorSection}
        onStationStatusChange={props.onStationStatusChange}
        onRemoveStation={props.onRemoveStation}
      />
```

Note the deliberate choice: `showCoordinatorSection`, not `props.isCoordinator` — a kid holding the grant gets no radio controls anywhere, same as the rest of the coordinator surface.

Render the form inside the coordinator block, directly after the net-buttons `<Box>` that closes at `:235`:

```tsx
          <RadioCheckinForm contacts={props.contacts} onCheckin={props.onRadioCheckin} />
```

- [ ] **Step 4: Implement the App wiring**

Add senders after `sendNeighborhoodStatus`:

```tsx
  function sendNeighborhoodRadioCheckin(p: {
    callsign: string;
    name: string;
    location: string;
    saveContact: boolean;
  }) {
    send({
      type: 'neighborhood_checkin_radio',
      callsign: p.callsign,
      name: p.name,
      location: p.location,
      ...(p.saveContact ? { save_contact: true } : {}),
    } satisfies NeighborhoodCheckinRadioPayload);
  }

  function sendNeighborhoodRemoveStation(userId: string) {
    send({ type: 'neighborhood_remove_station', user_id: userId } satisfies NeighborhoodRemoveStationPayload);
  }
```

Add both payload types to the existing `import type { ... } from './types/ws'` list, along with `Contact` if it isn't already imported there.

Pass them to the panel in the `activity === 'neighborhood'` branch:

```tsx
          contacts={contacts}
          onRadioCheckin={sendNeighborhoodRadioCheckin}
          onStationStatusChange={(userId, status) => sendNeighborhoodStatus(status, userId)}
          onRemoveStation={sendNeighborhoodRemoveStation}
```

`sendNeighborhoodStatus` already takes an optional `userId` — do not add a second status sender.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run && npx tsc -p tsconfig.build.json && npm run build`
Expected: PASS across the whole frontend suite, clean typecheck, clean build.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/NeighborhoodPanel/NeighborhoodPanel.tsx frontend/src/App.tsx frontend/src/components/NeighborhoodPanel/__tests__/NeighborhoodPanel.test.tsx
git commit -m "feat(neighborhood): wire radio check-in and station controls into the panel"
```

---

### Task 7: `Via` in the CSV export and Past Nets table

**Files:**
- Modify: `frontend/src/netsessions/csv.ts:9-17` (`sessionToCsv`)
- Modify: `frontend/src/components/JournalPanel/PastNetsTab.tsx` (roster column type at `:38`, search fields at `:42-44`, table head, table body, `colSpan` at `:247`)
- Test: `frontend/src/netsessions/__tests__/csv.test.ts`
- Test: `frontend/src/components/JournalPanel/__tests__/PastNetsTab.test.tsx` (check the exact existing path before writing)

**Interfaces:**
- Consumes: `NetSessionRosterRow.via` (Task 4), populated by Task 3.
- Produces: nothing downstream.

- [ ] **Step 1: Write the failing tests**

In `csv.test.ts`, extend the existing `sessionToCsv` tests:

```ts
it('includes a via column so radio check-ins are identifiable in a spreadsheet', () => {
  const csv = sessionToCsv({
    id: 'x', net_type: 'neighborhood', started_at: '', ended_at: '',
    duration_seconds: 0, transcript: '',
    roster: [
      { callsign: 'WRAB123', name: 'Maria', location: 'Maple St', status: 'CheckedIn',
        traffic: null, checkin_time: '2026-08-01T19:30:00Z', verified: false, via: 'radio' },
      { callsign: 'WRAA111', name: 'Ann', location: '1st St', status: 'CheckedIn',
        traffic: null, checkin_time: '2026-08-01T19:31:00Z', verified: false },
    ],
  } as never);
  const [header, maria, ann] = csv.split('\n');
  expect(header).toBe('callsign,name,location,status,traffic,checkin_time,via');
  expect(maria.endsWith('"radio"')).toBe(true);
  expect(ann.endsWith('""')).toBe(true);
});

it('leaves the all-sessions export unchanged', () => {
  // Summaries only carry callsign+name per station, so this export has no via
  // column to fill.
  expect(allSessionsToCsv([]).split('\n')[0]).toBe('net_id,net_type,net_date,callsign,name');
});
```

Match the existing `NetSessionDetail` fixture style in that file rather than the `as never` shortcut if the file already has a builder.

In the `PastNetsTab` test file:

```tsx
it('shows how each station reached the roster', () => {
  // render with a selected session holding one radio row and one blank-via row
  // expect a 'Via' column header and one cell reading 'radio'
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/netsessions src/components/JournalPanel`
Expected: FAIL — header mismatch, no `Via` column.

- [ ] **Step 3: Implement**

`csv.ts`:

```ts
/** One session's roster: header plus one row per check-in. */
export function sessionToCsv(session: NetSessionDetail): string {
  const header = 'callsign,name,location,status,traffic,checkin_time,via';
  const rows = session.roster.map((r) =>
    [r.callsign, r.name, r.location, r.status, r.traffic ?? '', r.checkin_time, r.via ?? '']
      .map(quote)
      .join(',')
  );
  return [header, ...rows].join('\n');
}
```

Leave `allSessionsToCsv` alone.

`PastNetsTab.tsx` — widen the sort column type and search fields:

```tsx
type RosterColumn = 'callsign' | 'name' | 'location' | 'status' | 'traffic' | 'via';

const PAST_NETS_SEARCH_FIELDS: (keyof NetSessionRosterRow)[] = [
  'callsign', 'name', 'location', 'status', 'traffic', 'via',
];
```

Add a sortable header cell after the `traffic` one, copying that cell's exact structure:

```tsx
                    <TableCell scope="col" sx={{ fontWeight: 700 }}>
                      <TableSortLabel
                        active={sortColumn === 'via'}
                        direction={sortColumn === 'via' ? sortDirection : 'asc'}
                        onClick={() => handleSort('via')}
                      >
                        Via
                      </TableSortLabel>
                    </TableCell>
```

Add the body cell after the `traffic` cell, and bump the empty-state `colSpan` from 5 to 6:

```tsx
                        <TableCell>{r.traffic ?? ''}</TableCell>
                        <TableCell>{r.via ?? ''}</TableCell>
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run && npx tsc -p tsconfig.build.json && npm run build`
Expected: PASS, clean typecheck, clean build.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/netsessions/csv.ts frontend/src/netsessions/__tests__/csv.test.ts frontend/src/components/JournalPanel/PastNetsTab.tsx frontend/src/components/JournalPanel/__tests__/PastNetsTab.test.tsx
git commit -m "feat(net-sessions): surface how a station reached the roster in the CSV and Past Nets table"
```

---

## Verification

Automated, after Task 7:

- `python -m pytest backend/tests -q` — full backend suite green.
- `cd frontend && npx vitest run` — full frontend suite green.
- `cd frontend && npx tsc -p tsconfig.build.json && npm run build` — clean.

Manual smoke (Benjamin, on the live ROCm install; no subagent can do this):

1. Grant a non-admin account the coordinator pref; open the Neighborhood panel as that account.
2. Check in one account holder from a second browser profile.
3. Check in two radio callers, one picked from Contacts and one new with "Save to contacts" ticked. Confirm the new callsign appears in the contacts dialog afterward.
4. Start the net, then Call next neighbor three times — confirm the order matches check-in order and the TX speaks each radio caller's name.
5. Move one radio caller to Standby, then Check out. Remove the other with the trash icon; confirm it vanishes with no confirm dialog and no error.
6. End the net. In the container: `docker exec hearthwave-backend-1 ls /data/net_sessions` and confirm the new record contains `"via": "radio"` for the caller who stayed.
7. Past Nets tab: the `Via` column reads `radio` for that station and blank for the account holder. Download the per-session CSV and confirm the `via` column opens correctly in a spreadsheet.
8. As a non-coordinator, confirm the radio check-in form and all radio-row controls are absent.
