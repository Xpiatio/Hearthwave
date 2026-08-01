# Coordinator Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A desktop-only single-viewport coordinator dashboard for the Neighborhood net (radio-first split layout), plus round-table no-answer tracking and per-row call in both views.

**Architecture:** The backend gains a `no_answer` roster flag and two coordinator-only WS ops (`neighborhood_no_answer`, `neighborhood_call_station`) in the pure state machine `NeighborhoodNet` + the `server.py` handler ladder. The frontend gains a `CoordinatorDashboard` component that `NeighborhoodPanel` renders instead of the stacked view when `isCoordinator && !isKid` and the viewport is ≥1200px; it reuses `ChatDisplay`, `MessageInput`, `RosterList`, `IncidentLog`, and `RadioCheckinForm`. Net-session history persists and displays the no-answer flag.

**Tech Stack:** FastAPI/Starlette WS backend (pytest), React 18 + MUI frontend (vitest + testing-library + jest-axe).

**Spec:** `docs/superpowers/specs/2026-08-01-coordinator-dashboard-design.md`

## Global Constraints

- Branch: `feat/coordinator-dashboard` (stacks on unmerged `feat/radio-caller-checkin` → `feat/net-session-history`). Do NOT rebase or touch the two branches beneath.
- Commit messages: conventional-commit style, **no Co-Authored-By trailer** (repo convention).
- `RosterList` is shared by the stacked view and the dashboard — new coordinator controls must not disturb the participant self-toggle or the density grid (`frontend/src/neighborhood/density.ts`).
- "No answer" never touches `current_call`; no auto-revisit of flagged stations (explicit ruling).
- Reuse `ChatDisplay`/`MessageInput` — do not fork them.
- Backend tests: `python -m pytest <path> -v` from repo root. Frontend tests: `cd frontend && npx vitest run <path>`.
- Working dir: `/mnt/storage/Repos/Radio-TTY`.

---

### Task 1: `no_answer` state in `NeighborhoodNet`

**Files:**
- Modify: `backend/neighborhood/net.py`
- Test: `backend/tests/unit/neighborhood/test_net.py`

**Interfaces:**
- Consumes: existing `NeighborhoodNet` (rows shaped `{"user_id", "callsign", "name", "location", "status", "checkin_time", "called", ["via"]}`, plus internal `seq`).
- Produces (Task 2 relies on these exact signatures):
  - `set_no_answer(self, key: str, no_answer: bool) -> bool` — returns False for unknown key; setting True also sets `called = True`; clearing leaves `called` alone; never touches `current_call`.
  - `call_station(self, key: str) -> Optional[dict]` — returns the row (or None if unknown); sets `called = True`, `no_answer = False`, `current_call = key`.
  - Every roster row now carries `no_answer: bool` (default False); `start()` and `call_reset()` reset it with `called`.

- [ ] **Step 1: Write failing tests** — append to `backend/tests/unit/neighborhood/test_net.py`:

```python
def test_rows_carry_no_answer_false_by_default():
    n = NeighborhoodNet()
    n.checkin("u1", "A", "Ann", "5th St")
    n.checkin_radio("WRAB123", "Maria", "Maple St")
    assert [r["no_answer"] for r in n.roster()] == [False, False]


def test_set_no_answer_flags_row_and_marks_it_called():
    n = NeighborhoodNet()
    n.start()
    n.checkin("u1", "A", "Ann", "5th St")
    assert n.set_no_answer("u1", True) is True
    row = n.roster()[0]
    assert row["no_answer"] is True
    assert row["called"] is True


def test_set_no_answer_never_touches_current_call():
    n = NeighborhoodNet()
    n.start()
    n.checkin("u1", "A", "Ann", "5th St")
    n.checkin("u2", "B", "Bea", "6th St")
    n.call_next()  # u1 becomes current
    n.set_no_answer("u1", True)
    assert n.current_call == "u1"


def test_clearing_no_answer_leaves_called_alone():
    n = NeighborhoodNet()
    n.start()
    n.checkin("u1", "A", "Ann", "5th St")
    n.set_no_answer("u1", True)
    assert n.set_no_answer("u1", False) is True
    row = n.roster()[0]
    assert row["no_answer"] is False
    assert row["called"] is True  # they still burned their turn this round


def test_set_no_answer_unknown_key_returns_false():
    n = NeighborhoodNet()
    assert n.set_no_answer("nobody", True) is False


def test_call_next_skips_no_answer_rows():
    n = NeighborhoodNet()
    n.start()
    n.checkin("u1", "A", "Ann", "5th St")
    n.checkin("u2", "B", "Bea", "6th St")
    n.set_no_answer("u1", True)
    row = n.call_next()
    assert row is not None and row["user_id"] == "u2"


def test_call_station_calls_out_of_order_and_clears_no_answer():
    n = NeighborhoodNet()
    n.start()
    n.checkin("u1", "A", "Ann", "5th St")
    n.checkin_radio("WRAB123", "Maria", "Maple St")
    radio_key = n.roster()[1]["user_id"]
    n.set_no_answer(radio_key, True)
    row = n.call_station(radio_key)
    assert row is not None
    assert n.current_call == radio_key
    assert row["called"] is True
    assert row["no_answer"] is False


def test_call_station_unknown_key_returns_none_and_leaves_current_call():
    n = NeighborhoodNet()
    n.start()
    n.checkin("u1", "A", "Ann", "5th St")
    n.call_next()
    assert n.call_station("nobody") is None
    assert n.current_call == "u1"


def test_start_and_call_reset_clear_no_answer():
    n = NeighborhoodNet()
    n.start()
    n.checkin("u1", "A", "Ann", "5th St")
    n.set_no_answer("u1", True)
    n.call_reset()
    assert n.roster()[0]["no_answer"] is False
    n.set_no_answer("u1", True)
    n.start()
    assert n.roster()[0]["no_answer"] is False
```

- [ ] **Step 2: Run tests, verify they fail**
  Run: `python -m pytest backend/tests/unit/neighborhood/test_net.py -v -k "no_answer or call_station"`
  Expected: FAIL — `KeyError: 'no_answer'` / `AttributeError: ... has no attribute 'set_no_answer'`

- [ ] **Step 3: Implement** in `backend/neighborhood/net.py`:
  - Add `"no_answer": False,` to the new-row dicts in `checkin()` (after `"called": False,`, net.py:141) and `checkin_radio()` (net.py:178).
  - In `start()` (net.py:90-91) and `call_reset()` (net.py:214-215), add `row["no_answer"] = False` beside `row["called"] = False`.
  - Update the row-shape docstring at net.py:33 to include `no_answer`.
  - Add after `call_reset()`:

```python
    def set_no_answer(self, key: str, no_answer: bool) -> bool:
        """Flag (or unflag) a station the round-table reached but couldn't raise.

        Setting the flag also marks the row `called`, so `call_next` skips it
        for the rest of the round — re-calling a no-answer station is a manual
        `call_station`, never automatic. Clearing the flag leaves `called`
        alone (the turn was still spent), and neither direction touches
        `current_call`. Returns False for an unknown key.
        """
        row = self._find(key)
        if row is None:
            return False
        row["no_answer"] = no_answer
        if no_answer:
            row["called"] = True
        return True

    def call_station(self, key: str) -> Optional[dict]:
        """Call a specific station out of order (e.g. retrying a no-answer row).

        Marks it called, clears any no-answer flag (they're being given a
        fresh chance to answer), and makes it the current call. Returns the
        row, or None for an unknown key.
        """
        row = self._find(key)
        if row is None:
            return None
        row["called"] = True
        row["no_answer"] = False
        self.current_call = row["user_id"]
        return row
```

- [ ] **Step 4: Run the full unit file, verify green**
  Run: `python -m pytest backend/tests/unit/neighborhood/test_net.py -v`
  Expected: ALL PASS (new + pre-existing)

- [ ] **Step 5: Commit**

```bash
git add backend/neighborhood/net.py backend/tests/unit/neighborhood/test_net.py
git commit -m "feat(neighborhood): track no-answer stations and out-of-order calls in the net state machine"
```

---

### Task 2: WS ops `neighborhood_no_answer` + `neighborhood_call_station`

**Files:**
- Modify: `backend/server.py` (handler ladder — insert both after the `neighborhood_call_reset` handler, which ends near server.py:4095; also add the two ops to the WS-op comment block at the top, near server.py:49-50)
- Test: `backend/tests/integration/test_server_ws.py`

**Interfaces:**
- Consumes: Task 1's `set_no_answer` / `call_station`; existing `_is_coordinator(state)` (server.py:2491), `_build_neighborhood_state_msg()`, `_tx_enqueue`, `_neighborhood`, `_config`.
- Produces (frontend Tasks 5-6 rely on these wire shapes):
  - `{"type": "neighborhood_no_answer", "user_id": str, "no_answer": bool}` — coordinator-only; unknown user_id is a no-op; broadcasts `neighborhood_state`.
  - `{"type": "neighborhood_call_station", "user_id": str}` — coordinator-only; on a known row, enqueues the same "you're up" TX announcement as `neighborhood_call_next` and broadcasts `neighborhood_state`.

- [ ] **Step 1: Write failing integration tests** — add a class alongside `TestNeighborhoodNetHandlers` (test_server_ws.py:3920), following its `_neighborhood_server(tmp_path)` + `patch(...)` + `TestClient` pattern (see test_server_ws.py:3948-3963 for the exact `with` stack; use `coordinator=True` where the helper supports it, as `TestNeighborhoodRadioCheckin` at test_server_ws.py:4349 does):

```python
class TestNeighborhoodNoAnswerAndCallStation:
    def test_no_answer_rejected_without_coordinator(self, tmp_path):
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
                    ws.send_json({"type": "neighborhood_no_answer",
                                  "user_id": "u1", "no_answer": True})
                    msg = _next_of_type(ws, "error")
        assert msg is not None and "Coordinator" in msg["detail"]

    def test_call_station_rejected_without_coordinator(self, tmp_path):
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
                    ws.send_json({"type": "neighborhood_call_station", "user_id": "u1"})
                    msg = _next_of_type(ws, "error")
        assert msg is not None and "Coordinator" in msg["detail"]

    def test_no_answer_flags_row_in_broadcast_state(self, tmp_path):
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_server(
            tmp_path, coordinator=True)
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
                    ws.send_json({"type": "neighborhood_checkin_radio",
                                  "callsign": "WRAB123", "name": "Maria",
                                  "location": "Maple St"})
                    state = _next_of_type(ws, "neighborhood_state")
                    key = state["roster"][0]["user_id"]
                    ws.send_json({"type": "neighborhood_no_answer",
                                  "user_id": key, "no_answer": True})
                    state = _next_of_type(ws, "neighborhood_state")
        row = state["roster"][0]
        assert row["no_answer"] is True
        assert row["called"] is True

    def test_call_station_sets_current_call_and_announces(self, tmp_path):
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_server(
            tmp_path, coordinator=True)
        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
            patch("backend.server._tx_enqueue", new=AsyncMock()) as mock_tx,
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    ws.send_json({"type": "neighborhood_checkin_radio",
                                  "callsign": "WRAB123", "name": "Maria",
                                  "location": "Maple St"})
                    state = _next_of_type(ws, "neighborhood_state")
                    key = state["roster"][0]["user_id"]
                    ws.send_json({"type": "neighborhood_call_station", "user_id": key})
                    state = _next_of_type(ws, "neighborhood_state")
        assert state["current_call"] == key
        assert mock_tx.await_count == 1
        assert "Maria" in mock_tx.await_args.args[0]["text"]

    def test_call_station_unknown_id_is_a_noop_broadcast(self, tmp_path):
        cfg, mock_stt, mock_tts, mock_users, mock_tokens = _neighborhood_server(
            tmp_path, coordinator=True)
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
                    ws.send_json({"type": "neighborhood_call_station",
                                  "user_id": "nobody"})
                    state = _next_of_type(ws, "neighborhood_state")
        assert state["current_call"] is None
```

  NOTE for the implementer: before writing, open `test_server_ws.py` and confirm the exact `_neighborhood_server` signature (test_server_ws.py:57 shows it takes `coordinator: bool = False`) and whether `_tx_enqueue` is patchable at module level the same way other tests do it — search for an existing `_tx_enqueue` patch and copy that mechanism if it differs.

- [ ] **Step 2: Run tests, verify they fail**
  Run: `python -m pytest backend/tests/integration/test_server_ws.py -v -k "NoAnswerAndCallStation"`
  Expected: FAIL — no handler, so no `error`/`neighborhood_state` reply arrives (timeout or missing frame), or the server treats the op as unknown.

- [ ] **Step 3: Implement handlers** in `backend/server.py`, immediately after the `neighborhood_call_reset` block (ends ~server.py:4095):

```python
            elif msg_type == "neighborhood_no_answer":
                if not _is_coordinator(state):
                    await _manager.send_to(ws, {"type": "error", "detail": "Coordinator access required"})
                    continue
                target_id = str(data.get("user_id") or "")
                if _neighborhood is not None:
                    # Unknown ids no-op (row may have been removed mid-click);
                    # broadcasting anyway keeps every client's state converged.
                    _neighborhood.set_no_answer(target_id, bool(data.get("no_answer", True)))
                await _manager.broadcast(_build_neighborhood_state_msg())

            elif msg_type == "neighborhood_call_station":
                if not _is_coordinator(state):
                    await _manager.send_to(ws, {"type": "error", "detail": "Coordinator access required"})
                    continue
                target_id = str(data.get("user_id") or "")
                row = _neighborhood.call_station(target_id) if _neighborhood is not None else None
                if row is not None:
                    # Same on-air announcement as neighborhood_call_next: an
                    # out-of-order call is still a call.
                    station_callsign = _config.callsign if _config else ""
                    text = f"{row['name']}, you're up. Anything to report? {station_callsign}."
                    await _tx_enqueue(
                        {"text": text, "_pre_formatted": True, "_operator_initiated": True}
                    )
                await _manager.broadcast(_build_neighborhood_state_msg())
```

  Also add to the op list comment near server.py:49-50:

```python
    neighborhood_no_answer      (coordinator) flag/unflag a station the round couldn't raise
    neighborhood_call_station   (coordinator) call a specific station out of order
```

- [ ] **Step 4: Run tests, verify green**
  Run: `python -m pytest backend/tests/integration/test_server_ws.py -v -k "NoAnswerAndCallStation"`
  Expected: ALL PASS

- [ ] **Step 5: Run the whole backend suite** (state-machine change could ripple)
  Run: `python -m pytest backend/tests/ -q`
  Expected: ALL PASS. `neighborhood_state` roster rows now carry `no_answer` — if any existing exact-equality assertion on roster rows fails (e.g. in `TestNeighborhoodNetHandlers` or `TestNeighborhoodRadioCheckin`), update that assertion to include `"no_answer": False`.

- [ ] **Step 6: Commit**

```bash
git add backend/server.py backend/tests/integration/test_server_ws.py
git commit -m "feat(neighborhood): coordinator WS ops for no-answer flag and out-of-order call"
```

---

### Task 3: Persist `no_answer` in net-session records

**Files:**
- Modify: `backend/persistence/net_sessions.py` (`normalize_roster`, net_sessions.py:60-81)
- Test: `backend/tests/unit/persistence/test_net_sessions.py`

**Interfaces:**
- Consumes: roster rows from Task 1 (carrying `no_answer: bool`).
- Produces: stored session roster rows gain `"no_answer": bool` (False when absent — old live rows and NCS rosters lack it). Task 4's frontend types mirror this.

- [ ] **Step 1: Write failing test** — add to `backend/tests/unit/persistence/test_net_sessions.py` beside `test_normalize_roster_carries_the_radio_marker` (test_net_sessions.py:198):

```python
def test_normalize_roster_carries_no_answer_defaulting_false():
    rows = [
        {"callsign": "wraa111", "name": "Ann", "no_answer": True},
        {"callsign": "wrab222", "name": "Bea"},  # pre-flag record / NCS row
    ]
    result = normalize_roster(rows)
    assert result[0]["no_answer"] is True
    assert result[1]["no_answer"] is False
```

- [ ] **Step 2: Run test, verify it fails**
  Run: `python -m pytest backend/tests/unit/persistence/test_net_sessions.py -v -k no_answer`
  Expected: FAIL — `KeyError: 'no_answer'`

- [ ] **Step 3: Implement** — in `normalize_roster` (net_sessions.py:67-80), after the `"via"` entry add:

```python
            # A station the round-table reached but couldn't raise. Unlike
            # `called` (dropped above as in-progress bookkeeping), this is
            # part of what happened: checked in, never reached.
            "no_answer": bool(row.get("no_answer", False)),
```

- [ ] **Step 4: Run the file, verify green**
  Run: `python -m pytest backend/tests/unit/persistence/test_net_sessions.py -v`
  Expected: ALL PASS (fix any exact-shape assertions by adding `"no_answer": False`)

- [ ] **Step 5: Commit**

```bash
git add backend/persistence/net_sessions.py backend/tests/unit/persistence/test_net_sessions.py
git commit -m "feat(net-sessions): persist the no-answer flag in session rosters"
```

---

### Task 4: No-answer column in Past Nets + CSV

**Files:**
- Modify: `frontend/src/types/ws.ts` (`NetSessionRosterRow`, ws.ts:265), `frontend/src/netsessions/csv.ts` (`sessionToCsv`), `frontend/src/components/JournalPanel/PastNetsTab.tsx` (roster table)
- Test: `frontend/src/netsessions/__tests__/csv.test.ts` (exists — check `ls frontend/src/netsessions/__tests__/` first; if the CSV test file has a different name, use that one), `frontend/src/components/JournalPanel/__tests__/PastNetsTab.test.tsx` (same check)

**Interfaces:**
- Consumes: Task 3's stored `no_answer` field.
- Produces: `NetSessionRosterRow.no_answer?: boolean`; per-session CSV header becomes `callsign,name,location,status,traffic,checkin_time,via,no_answer` with `yes`/`` values; Past Nets roster table gains a sortable "No answer" column rendering `yes`/``.

- [ ] **Step 1: Write failing tests.** In the CSV test file add:

```typescript
it('emits a no_answer column, yes for flagged rows and blank otherwise', () => {
  const session = makeSession({
    roster: [
      makeRow({ callsign: 'WRAA111', no_answer: true }),
      makeRow({ callsign: 'WRAB222' }),
    ],
  });
  const csv = sessionToCsv(session);
  const [header, row1, row2] = csv.split('\n');
  expect(header).toBe('callsign,name,location,status,traffic,checkin_time,via,no_answer');
  expect(row1.endsWith(',"yes"')).toBe(true);
  expect(row2.endsWith(',""')).toBe(true);
});
```

  (Adapt `makeSession`/`makeRow` to that file's actual fixture helpers — read the file first and reuse its builders.) In the PastNetsTab test add a render test asserting a column header "No answer" and a `yes` cell for a flagged row, using that file's existing fixture/render helpers.

- [ ] **Step 2: Run, verify failure**
  Run: `cd frontend && npx vitest run src/netsessions src/components/JournalPanel`
  Expected: new tests FAIL (missing column), pre-existing PASS

- [ ] **Step 3: Implement**
  - `types/ws.ts` — in `NetSessionRosterRow` after `via?: string;`:

```typescript
  /** True when the round-table called this station and got no reply.
   *  Optional because records written before this field existed lack it. */
  no_answer?: boolean;
```

  - `csv.ts` `sessionToCsv` — header `'callsign,name,location,status,traffic,checkin_time,via,no_answer'`; row array gains `r.no_answer ? 'yes' : ''` as the final element.
  - `PastNetsTab.tsx` — add `'no_answer'` to the `RosterColumn` union and the sortable-columns list (PastNetsTab.tsx:38-43), a `TableSortLabel` header cell labeled `No answer` (copy the `via` header cell at PastNetsTab.tsx:243-247), and a body cell `<TableCell>{r.no_answer ? 'yes' : ''}</TableCell>` after the `via` cell (PastNetsTab.tsx:268).

- [ ] **Step 4: Run, verify green**
  Run: `cd frontend && npx vitest run src/netsessions src/components/JournalPanel`
  Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/ws.ts frontend/src/netsessions/csv.ts frontend/src/components/JournalPanel/PastNetsTab.tsx frontend/src/netsessions/__tests__ frontend/src/components/JournalPanel/__tests__
git commit -m "feat(net-sessions): surface the no-answer flag in Past Nets and CSV exports"
```

---

### Task 5: RosterList coordinator controls (Call / No answer)

**Files:**
- Modify: `frontend/src/types/ws.ts` (`NeighborhoodRosterRow`, ws.ts:639), `frontend/src/components/NeighborhoodPanel/RosterList.tsx`
- Test: `frontend/src/components/NeighborhoodPanel/__tests__/RosterList.test.tsx`

**Interfaces:**
- Consumes: `no_answer` on live roster rows (Task 2 broadcasts it).
- Produces (Task 6 wires these):
  - `NeighborhoodRosterRow.no_answer?: boolean`
  - New optional `RosterListProps`: `onCallStation?: (userId: string) => void;` and `onNoAnswer?: (userId: string, noAnswer: boolean) => void;`
  - Rendering rules (all coordinator-only, i.e. `isCoordinator` true and the handler provided): every non-current row gets a **Call** button; the current-turn row gets a **No answer** button; a flagged row shows a warning-colored **No answer** chip that, for a coordinator, is clickable to clear the flag. Chip precedence per row: `Current turn` > `No answer` > `Called ✓` (`called` chip hidden while `no_answer` is set).

- [ ] **Step 1: Write failing tests** — append to `RosterList.test.tsx`, reusing its `render`/`makeProps`/row fixtures (RosterList.test.tsx:10-32):

```typescript
it('gives a coordinator a Call button on every row and fires onCallStation', async () => {
  const user = userEvent.setup();
  const onCallStation = vi.fn();
  render(
    <RosterList
      {...makeProps({ roster: [accountRow, radioRow], isCoordinator: true, onCallStation })}
    />
  );
  const callButtons = screen.getAllByRole('button', { name: /^Call\b/ });
  expect(callButtons).toHaveLength(2);
  await user.click(callButtons[0]);
  expect(onCallStation).toHaveBeenCalledWith('u1');
});

it('hides Call on the current-turn row and shows No answer there instead', async () => {
  const user = userEvent.setup();
  const onNoAnswer = vi.fn();
  render(
    <RosterList
      {...makeProps({
        roster: [accountRow], currentCall: 'u1', isCoordinator: true,
        onCallStation: vi.fn(), onNoAnswer,
      })}
    />
  );
  expect(screen.queryByRole('button', { name: /^Call\b/ })).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'No answer' }));
  expect(onNoAnswer).toHaveBeenCalledWith('u1', true);
});

it('shows a No answer chip instead of Called ✓ and lets a coordinator clear it', async () => {
  const user = userEvent.setup();
  const onNoAnswer = vi.fn();
  const flagged = { ...accountRow, called: true, no_answer: true };
  render(
    <RosterList {...makeProps({ roster: [flagged], isCoordinator: true, onNoAnswer })} />
  );
  expect(screen.queryByText('Called ✓')).not.toBeInTheDocument();
  await user.click(screen.getByText('No answer'));
  expect(onNoAnswer).toHaveBeenCalledWith('u1', false);
});

it('shows participants the No answer chip but no coordinator controls', () => {
  const flagged = { ...accountRow, called: true, no_answer: true };
  render(<RosterList {...makeProps({ roster: [flagged, radioRow] })} />);
  expect(screen.getByText('No answer')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /^Call\b/ })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'No answer' })).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run, verify failure**
  Run: `cd frontend && npx vitest run src/components/NeighborhoodPanel/__tests__/RosterList.test.tsx`
  Expected: new tests FAIL (buttons/chip absent), pre-existing PASS

- [ ] **Step 3: Implement**
  - `types/ws.ts` — in `NeighborhoodRosterRow` after `via?: 'radio';`:

```typescript
  /** True when the round-table called this station and got no reply.
   *  Optional so older server payloads (or NCS-shaped rows) still typecheck. */
  no_answer?: boolean;
```

  - `RosterList.tsx`:
    - Add to `RosterListProps`:

```typescript
  /** Coordinator-only: call this station out of order (round-table). */
  onCallStation?: (userId: string) => void;
  /** Coordinator-only: flag/unflag a station the round couldn't raise. */
  onNoAnswer?: (userId: string, noAnswer: boolean) => void;
```

    - In the row map (after `const canOperate = ...`, RosterList.tsx:206) add `const coordinatorControls = !!isCoordinator;`.
    - Chip row (RosterList.tsx:232-234): replace the bare `{row.called && <Chip ... label="Called ✓" ...>}` with:

```tsx
                  {row.no_answer ? (
                    <Chip
                      size="small"
                      color="warning"
                      label="No answer"
                      sx={{ maxWidth: '100%' }}
                      // Clickable only where clicking can succeed: the server
                      // restricts the flag to coordinators.
                      onClick={
                        coordinatorControls && onNoAnswer
                          ? () => onNoAnswer(row.user_id, false)
                          : undefined
                      }
                    />
                  ) : (
                    row.called && <Chip size="small" label="Called ✓" sx={{ maxWidth: '100%' }} />
                  )}
```

    - In the actions box (beside the existing `isSelf` / `canOperate` buttons, RosterList.tsx:243-276) add:

```tsx
                    {coordinatorControls && onCallStation && !isCurrent && (
                      <Button
                        size="small"
                        variant="text"
                        aria-label={`Call ${row.name}`}
                        onClick={() => onCallStation(row.user_id)}
                      >
                        Call
                      </Button>
                    )}
                    {coordinatorControls && onNoAnswer && isCurrent && !row.no_answer && (
                      <Button
                        size="small"
                        variant="text"
                        color="warning"
                        onClick={() => onNoAnswer(row.user_id, true)}
                      >
                        No answer
                      </Button>
                    )}
```

    - Update the component docstring (RosterList.tsx:88-105) to mention the two new coordinator controls and the chip precedence.
    - NOTE: `getAllByRole('button', { name: /^Call\b/ })` matches via the `aria-label` `Call <name>`; the accessible name must start with "Call".

- [ ] **Step 4: Run the file + the axe test, verify green**
  Run: `cd frontend && npx vitest run src/components/NeighborhoodPanel/__tests__/RosterList.test.tsx`
  Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/ws.ts frontend/src/components/NeighborhoodPanel/RosterList.tsx frontend/src/components/NeighborhoodPanel/__tests__/RosterList.test.tsx
git commit -m "feat(neighborhood): coordinator Call and No-answer controls on roster rows"
```

---

### Task 6: Wire the new ops through App.tsx and the stacked view

**Files:**
- Modify: `frontend/src/types/ws.ts` (payload types — put them beside `NeighborhoodCallResetPayload`), `frontend/src/App.tsx` (senders near App.tsx:1279-1285; pass-through at the `<NeighborhoodPanel>` mount, App.tsx:1820-1849), `frontend/src/components/NeighborhoodPanel/NeighborhoodPanel.tsx` (props + forward to `RosterList`)
- Test: covered by Task 5's component tests + typecheck; `frontend/src/components/NeighborhoodPanel/__tests__/NeighborhoodPanel.test.tsx` gets one pass-through test

**Interfaces:**
- Consumes: Task 2's wire shapes, Task 5's `RosterList` props.
- Produces (Task 7-8 rely on these):
  - `NeighborhoodPanelProps` gains `onCallStation: (userId: string) => void;` and `onNoAnswer: (userId: string, noAnswer: boolean) => void;`
  - App senders `sendNeighborhoodCallStation(userId)` / `sendNeighborhoodNoAnswer(userId, noAnswer)`.

- [ ] **Step 1: Write failing test** — in `NeighborhoodPanel.test.tsx`, following its existing fixture pattern, render the panel as coordinator with one non-current roster row, click the row's `Call <name>` button, and assert the new `onCallStation` prop fires with the row's user_id.

- [ ] **Step 2: Run, verify failure**
  Run: `cd frontend && npx vitest run src/components/NeighborhoodPanel/__tests__/NeighborhoodPanel.test.tsx`
  Expected: FAIL (prop doesn't exist / button not rendered)

- [ ] **Step 3: Implement**
  - `types/ws.ts`, beside the other neighborhood payloads:

```typescript
export interface NeighborhoodNoAnswerPayload {
  type: 'neighborhood_no_answer';
  user_id: string;
  no_answer: boolean;
}

export interface NeighborhoodCallStationPayload {
  type: 'neighborhood_call_station';
  user_id: string;
}
```

  - `App.tsx`, beside `sendNeighborhoodCallReset` (App.tsx:1283):

```typescript
  function sendNeighborhoodNoAnswer(userId: string, noAnswer: boolean) {
    send({ type: 'neighborhood_no_answer', user_id: userId, no_answer: noAnswer } satisfies NeighborhoodNoAnswerPayload);
  }

  function sendNeighborhoodCallStation(userId: string) {
    send({ type: 'neighborhood_call_station', user_id: userId } satisfies NeighborhoodCallStationPayload);
  }
```

    Add both to the `<NeighborhoodPanel>` mount: `onNoAnswer={sendNeighborhoodNoAnswer}` and `onCallStation={sendNeighborhoodCallStation}` (and import the payload types where the others are imported).
  - `NeighborhoodPanel.tsx` — add to `NeighborhoodPanelProps`:

```typescript
  onNoAnswer: (userId: string, noAnswer: boolean) => void;
  onCallStation: (userId: string) => void;
```

    Forward both to `<RosterList>` (NeighborhoodPanel.tsx:203-212), gated the same way the other coordinator handlers are: pass them only when `showCoordinatorSection` is true (`onNoAnswer={showCoordinatorSection ? props.onNoAnswer : undefined}` etc. — RosterList treats absent handlers as "render no control").

- [ ] **Step 4: Run panel tests + typecheck, verify green**
  Run: `cd frontend && npx vitest run src/components/NeighborhoodPanel && npx tsc -p tsconfig.build.json --noEmit`
  Expected: ALL PASS, no type errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/ws.ts frontend/src/App.tsx frontend/src/components/NeighborhoodPanel/NeighborhoodPanel.tsx frontend/src/components/NeighborhoodPanel/__tests__/NeighborhoodPanel.test.tsx
git commit -m "feat(neighborhood): wire no-answer and call-station ops through the app"
```

---

### Task 7: `StreetAlertDialog` + `CoordinatorDashboard` component

**Files:**
- Create: `frontend/src/components/NeighborhoodPanel/StreetAlertDialog.tsx`, `frontend/src/components/NeighborhoodPanel/CoordinatorDashboard.tsx`
- Test: `frontend/src/components/NeighborhoodPanel/__tests__/CoordinatorDashboard.test.tsx` (new)

**Interfaces:**
- Consumes: `RosterList` (Task 5 props), `IncidentLog`, `RadioCheckinForm`, `IncidentDialog`, `ConfirmDialog`, `ChatDisplay` (`entries`, `contacts`, `showCallsignChips`), `MessageInput` (`transmitting`, `contacts`, `onSend`, `onChat`, `onStandaloneId`, `maxBytes`, `composeHint` — see DesktopApp.tsx:408-417), `nextNetLabel` from `../../neighborhood/schedule`, `currentCallLabel` logic from NeighborhoodPanel.
- Produces (Task 8 mounts this):

```typescript
export interface CoordinatorDashboardProps extends NeighborhoodPanelProps {
  messages: ChatEntry[];
  transmitting: boolean;
  showCallsignChips: boolean;
  onSendMessage: (text: string, targetCall: string, targetName: string) => void;
  onChat: (text: string) => void;
  onStandaloneId: () => void;
  txComposition: TxComposition | null;
}
```

  (`TxComposition` from `frontend/src/plugins`, `ChatEntry` from `ChatDisplay`.)

- [ ] **Step 1: Write failing tests** — new `CoordinatorDashboard.test.tsx`, reusing the ThemeProvider `render` helper pattern from `RosterList.test.tsx:10-12`:

```typescript
function makeDashProps(overrides: Partial<CoordinatorDashboardProps> = {}): CoordinatorDashboardProps {
  return {
    roster: [], netActive: true, currentCall: null, incidents: [], alerts: [],
    netDay: 'Saturday', netTime: '09:00', isCoordinator: true, isAdmin: false,
    isKid: false, myUserId: 'u1',
    onCheckin: vi.fn(), onClearCheckins: vi.fn(), onClearIncidents: vi.fn(),
    onStatusChange: vi.fn(), onIncidentReport: vi.fn(), incidentError: null,
    onStreetAlert: vi.fn(), onStartNet: vi.fn(), onEndNet: vi.fn(),
    onCallNext: vi.fn(), onNewRound: vi.fn(), onGoHome: vi.fn(),
    contacts: [], onRadioCheckin: vi.fn(), onStationStatusChange: vi.fn(),
    onRemoveStation: vi.fn(), onNoAnswer: vi.fn(), onCallStation: vi.fn(),
    messages: [], transmitting: false, showCallsignChips: false,
    onSendMessage: vi.fn(), onChat: vi.fn(), onStandaloneId: vi.fn(),
    txComposition: null,
    ...overrides,
  };
}

describe('CoordinatorDashboard', () => {
  it('renders every ops zone on one screen', () => {
    render(<CoordinatorDashboard {...makeDashProps()} />);
    expect(screen.getByRole('button', { name: 'End net' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Call next neighbor' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'New round' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Street alert…' })).toBeInTheDocument();
    expect(screen.getByText('Checked-in neighbors')).toBeInTheDocument();   // RosterList
    expect(screen.getByText('Incident log')).toBeInTheDocument();           // IncidentLog
    expect(screen.getByLabelText('Callsign')).toBeInTheDocument();          // RadioCheckinForm
    expect(screen.getByRole('button', { name: 'Report an incident' })).toBeInTheDocument();
  });

  it('opens the street-alert dialog and sends through the existing confirm flow', async () => {
    const user = userEvent.setup();
    const onStreetAlert = vi.fn();
    render(<CoordinatorDashboard {...makeDashProps({ onStreetAlert })} />);
    await user.click(screen.getByRole('button', { name: 'Street alert…' }));
    await user.type(screen.getByLabelText('Street alert message'), 'Power out on Maple St');
    await user.click(screen.getByRole('button', { name: 'Send street alert' }));
    await user.click(screen.getByRole('button', { name: 'Yes, send the alert' }));
    expect(onStreetAlert).toHaveBeenCalledWith('Power out on Maple St');
  });

  it('shows a compact self check-in chip, not the billboard button', async () => {
    const user = userEvent.setup();
    const onCheckin = vi.fn();
    render(<CoordinatorDashboard {...makeDashProps({ onCheckin })} />);
    await user.click(screen.getByRole('button', { name: 'Check in' }));
    expect(onCheckin).toHaveBeenCalled();
  });

  it('transmits from the dashboard message input', async () => {
    const user = userEvent.setup();
    const onSendMessage = vi.fn();
    render(<CoordinatorDashboard {...makeDashProps({ onSendMessage })} />);
    // MessageInput's send path: type + press Enter (see MessageInput tests for
    // the exact accessible name of its textbox; adapt if it differs).
    const box = screen.getByRole('textbox', { name: /message/i });
    await user.type(box, 'net control standing by{Enter}');
    expect(onSendMessage).toHaveBeenCalled();
  });
});
```

  (Read `MessageInput.tsx` / its tests first for the textbox's accessible name and Enter-to-send behavior; adjust the last test accordingly. Read `RadioCheckinForm.tsx` for the exact field label — `Callsign` — and adjust if it differs.)

- [ ] **Step 2: Run, verify failure**
  Run: `cd frontend && npx vitest run src/components/NeighborhoodPanel/__tests__/CoordinatorDashboard.test.tsx`
  Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement `StreetAlertDialog.tsx`** — small dialog wrapping the existing inline street-alert flow (field + 200-char cap + ConfirmDialog):

```tsx
import { useState } from 'react';
import { Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, TextField } from '@mui/material';
import { ConfirmDialog } from '../ConfirmDialog';

const STREET_ALERT_MAX = 200;

export interface StreetAlertDialogProps {
  open: boolean;
  onClose: () => void;
  onSend: (message: string) => void;
}

/** The stacked view's inline street-alert field, in dialog form for the
 *  coordinator dashboard's command bar. Same 200-char cap, same explicit
 *  confirm step before anything goes out to every screen. */
export function StreetAlertDialog({ open, onClose, onSend }: StreetAlertDialogProps) {
  const [message, setMessage] = useState('');
  const [confirmOpen, setConfirmOpen] = useState(false);

  function handleConfirm() {
    const trimmed = message.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setMessage('');
    onClose();
  }

  return (
    <>
      <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
        <DialogTitle>Street alert</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 1 }}>
            <TextField
              autoFocus
              fullWidth
              size="small"
              label="Street alert message"
              value={message}
              onChange={(e) => setMessage(e.target.value.slice(0, STREET_ALERT_MAX))}
              placeholder="e.g. Power out on Maple St, crews on the way"
              helperText={`${message.length}/${STREET_ALERT_MAX}`}
              slotProps={{ htmlInput: { maxLength: STREET_ALERT_MAX } }}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            variant="contained"
            color="warning"
            disabled={!message.trim()}
            onClick={() => setConfirmOpen(true)}
          >
            Send street alert
          </Button>
        </DialogActions>
      </Dialog>
      <ConfirmDialog
        open={confirmOpen}
        title="Send this alert to everyone?"
        body={message.trim()}
        confirmLabel="Yes, send the alert"
        destructive
        onConfirm={handleConfirm}
        onClose={() => setConfirmOpen(false)}
      />
    </>
  );
}
```

- [ ] **Step 4: Implement `CoordinatorDashboard.tsx`.** Structure (full-viewport grid; every zone `minHeight: 0` + `overflow: 'auto'` on its scroll container so the page itself never scrolls):

```tsx
import { useState } from 'react';
import { Alert, Box, Button, Chip, IconButton, Paper, Tooltip, Typography } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import type { ChatEntry } from '../ChatDisplay/ChatDisplay';
import type { TxComposition } from '../../plugins';
import { ChatDisplay } from '../ChatDisplay/ChatDisplay';
import { MessageInput } from '../MessageInput/MessageInput';
import { useEscapeToHome } from '../../hooks/useEscapeToHome';
import { nextNetLabel } from '../../neighborhood/schedule';
import { RosterList } from './RosterList';
import { IncidentLog } from './IncidentLog';
import { IncidentDialog } from './IncidentDialog';
import { RadioCheckinForm } from './RadioCheckinForm';
import { StreetAlertDialog } from './StreetAlertDialog';
import { ConfirmDialog } from '../ConfirmDialog';
import type { NeighborhoodPanelProps } from './NeighborhoodPanel';

export interface CoordinatorDashboardProps extends NeighborhoodPanelProps {
  messages: ChatEntry[];
  transmitting: boolean;
  showCallsignChips: boolean;
  onSendMessage: (text: string, targetCall: string, targetName: string) => void;
  onChat: (text: string) => void;
  onStandaloneId: () => void;
  txComposition: TxComposition | null;
}

/** Single-viewport net-ops console for a coordinator on a desktop: radio
 *  traffic and check-in entry on the left, roster and incidents on the
 *  right, net controls in a persistent command bar. The stacked
 *  NeighborhoodPanel remains the participant/narrow-screen view; the
 *  ≥1200px switch lives in NeighborhoodPanel. */
export function CoordinatorDashboard(props: CoordinatorDashboardProps) { /* … */ }
```

  Layout inside the component:

```tsx
  <Box sx={{ height: '100vh', display: 'grid', gridTemplateRows: 'auto auto 1fr', gap: 1.5, p: 2, boxSizing: 'border-box', overflow: 'hidden' }}>
    {/* Command bar */}
    <Box component="header" sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
      back IconButton (ArrowBackIcon, aria-label "Back to home", onClick props.onGoHome)
      <Typography variant="h6">Neighborhood</Typography>
      net-status Chip (success "Net running" / default "No net right now"; show nextNetLabel(netDay, netTime, new Date()) beside it when inactive)
      Start/End net Button — reuse the stacked view's onStartNet/onEndNet ternary
      "Call next neighbor" / "New round" Buttons (disabled={!props.netActive})
      "Street alert…" Button (opens StreetAlertDialog)
      current-turn Typography — same currentCallLabel(currentCall, roster) fallback logic as NeighborhoodPanel.tsx:58-61 (copy the helper or export it from NeighborhoodPanel)
      `${roster.length} checked in` Typography
      self check-in: <Chip clickable={!checkedIn} color={checkedIn ? 'success' : 'primary'} label={checkedIn ? "You're checked in ✓" : 'Check in'} onClick={checkedIn ? undefined : props.onCheckin} component="button" disabled={checkedIn} />  — must expose role=button named "Check in" when not checked in
    </Box>

    {/* Street-alert banners — identical to NeighborhoodPanel.tsx:162-170, rendered only when alerts.length > 0 */}

    {/* Main split */}
    <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5, minHeight: 0 }}>
      {/* Left: transcript over TX over check-in form */}
      <Box sx={{ display: 'grid', gridTemplateRows: '1fr auto auto', gap: 1, minHeight: 0 }}>
        <Paper variant="outlined" sx={{ minHeight: 0, overflow: 'auto', p: 1 }}>
          <ChatDisplay entries={props.messages} contacts={props.contacts} showCallsignChips={props.showCallsignChips} />
        </Paper>
        <MessageInput
          transmitting={props.transmitting}
          contacts={props.contacts}
          onSend={props.onSendMessage}
          onChat={props.onChat}
          onStandaloneId={props.onStandaloneId}
          maxBytes={props.txComposition?.maxBytes}
          composeHint={props.txComposition?.hint}
        />
        <Paper variant="outlined" sx={{ p: 1.5 }}>
          <RadioCheckinForm contacts={props.contacts} onCheckin={props.onRadioCheckin} />
        </Paper>
      </Box>

      {/* Right: roster over incidents */}
      <Box sx={{ display: 'grid', gridTemplateRows: '1.6fr 1fr', gap: 1.5, minHeight: 0 }}>
        <Paper variant="outlined" sx={{ minHeight: 0, overflow: 'auto', p: 1.5 }}>
          <RosterList
            roster={props.roster} currentCall={props.currentCall} myUserId={props.myUserId}
            onStatusChange={props.onStatusChange}
            onClear={props.isAdmin ? open clear-checkins confirm : undefined}
            isCoordinator
            onStationStatusChange={props.onStationStatusChange}
            onRemoveStation={props.onRemoveStation}
            onCallStation={props.onCallStation}
            onNoAnswer={props.onNoAnswer}
          />
        </Paper>
        <Paper variant="outlined" sx={{ minHeight: 0, overflow: 'auto', p: 1.5, display: 'flex', flexDirection: 'column', gap: 1 }}>
          <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Button size="small" variant="outlined" onClick={open incident dialog}>Report an incident</Button>
          </Box>
          <IncidentLog incidents={props.incidents} onClear={props.isAdmin ? open clear-incidents confirm : undefined} />
        </Paper>
      </Box>
    </Box>

    {/* Dialogs: IncidentDialog (reuse NeighborhoodPanel's dismissed-error ref pattern from NeighborhoodPanel.tsx:79-127 verbatim), StreetAlertDialog, the two admin ConfirmDialogs (copy titles/bodies from NeighborhoodPanel.tsx:288-310) */}
  </Box>
```

  Also call `useEscapeToHome(props.onGoHome)` at the top (this component replaces the stacked panel wholesale, so it owns the Escape binding when mounted).

- [ ] **Step 5: Run, verify green**
  Run: `cd frontend && npx vitest run src/components/NeighborhoodPanel/__tests__/CoordinatorDashboard.test.tsx`
  Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/NeighborhoodPanel/CoordinatorDashboard.tsx frontend/src/components/NeighborhoodPanel/StreetAlertDialog.tsx frontend/src/components/NeighborhoodPanel/__tests__/CoordinatorDashboard.test.tsx
git commit -m "feat(neighborhood): single-viewport coordinator dashboard (radio-first split)"
```

---

### Task 8: Gate the dashboard in NeighborhoodPanel + App plumbing + full verification

**Files:**
- Modify: `frontend/src/components/NeighborhoodPanel/NeighborhoodPanel.tsx`, `frontend/src/App.tsx` (the `<NeighborhoodPanel>` mount, App.tsx:1820-1849)
- Test: `frontend/src/components/NeighborhoodPanel/__tests__/NeighborhoodPanel.test.tsx`

**Interfaces:**
- Consumes: Task 7's `CoordinatorDashboard`; App state `messages`, `transmitting`, `showCallsignChips`, `handleSend`, `handleChat`, `handleStandaloneId`, `txComposition` (all already in scope at the mount — see `sharedProps`, App.tsx:1629-1669 and `onChat: handleChat` at App.tsx:1690).
- Produces: `NeighborhoodPanelProps` gains the seven dashboard props as **optional** (`messages?: ChatEntry[]` etc. — optional so tests and any other mounts compile unchanged); the panel renders `CoordinatorDashboard` when `isCoordinator && !isKid && useMediaQuery('(min-width:1200px)')` **and** `messages !== undefined`, else the stacked view.

- [ ] **Step 1: Write failing gating tests** — in `NeighborhoodPanel.test.tsx`. jsdom has no `matchMedia`, and MUI's `useMediaQuery` defaults to `false` without it — so the narrow case needs no mock, and the wide case stubs it:

```typescript
function mockMatchMedia(matches: boolean) {
  vi.stubGlobal('matchMedia', vi.fn().mockImplementation((query: string) => ({
    matches, media: query, onchange: null,
    addListener: vi.fn(), removeListener: vi.fn(),
    addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
  })));
}
// afterEach(() => vi.unstubAllGlobals()) — add if the file doesn't already.

it('renders the ops dashboard for a wide-screen coordinator', () => {
  mockMatchMedia(true);
  render(
    <NeighborhoodPanel
      {...makeProps({
        isCoordinator: true,
        messages: [], transmitting: false, showCallsignChips: false,
        onSendMessage: vi.fn(), onChat: vi.fn(), onStandaloneId: vi.fn(),
        txComposition: null,
      })}
    />
  );
  // Dashboard marker: the command-bar street-alert button (stacked view has
  // an inline field, not this button).
  expect(screen.getByRole('button', { name: 'Street alert…' })).toBeInTheDocument();
});

it('keeps the stacked view for a narrow-screen coordinator', () => {
  mockMatchMedia(false);
  render(<NeighborhoodPanel {...makeProps({ isCoordinator: true, messages: [] })} />);
  expect(screen.queryByRole('button', { name: 'Street alert…' })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Check in' })).toBeInTheDocument();
});

it('never shows a kid the dashboard, even wide + coordinator', () => {
  mockMatchMedia(true);
  render(<NeighborhoodPanel {...makeProps({ isCoordinator: true, isKid: true, messages: [] })} />);
  expect(screen.queryByRole('button', { name: 'Street alert…' })).not.toBeInTheDocument();
});
```

  (Adapt `makeProps` to that file's existing helper; extend it with the new optional props.)

- [ ] **Step 2: Run, verify failure**
  Run: `cd frontend && npx vitest run src/components/NeighborhoodPanel/__tests__/NeighborhoodPanel.test.tsx`
  Expected: new tests FAIL

- [ ] **Step 3: Implement**
  - `NeighborhoodPanel.tsx`: add the optional props

```typescript
  /** Dashboard-only (present when App mounts the panel for a desktop session):
   *  live RX/chat entries and TX plumbing for the coordinator ops view. */
  messages?: ChatEntry[];
  transmitting?: boolean;
  showCallsignChips?: boolean;
  onSendMessage?: (text: string, targetCall: string, targetName: string) => void;
  onChat?: (text: string) => void;
  onStandaloneId?: () => void;
  txComposition?: TxComposition | null;
```

    and at the top of the component body (before any early state — keep hooks unconditional; note `useEscapeToHome` runs identically on both branches so calling it before the split is fine):

```tsx
  const wideViewport = useMediaQuery('(min-width:1200px)');
  const showCoordinatorSection = props.isCoordinator && !props.isKid;   // moved up from line 110
  if (showCoordinatorSection && wideViewport && props.messages !== undefined) {
    return (
      <CoordinatorDashboard
        {...props}
        messages={props.messages}
        transmitting={props.transmitting ?? false}
        showCallsignChips={props.showCallsignChips ?? false}
        onSendMessage={props.onSendMessage ?? (() => {})}
        onChat={props.onChat ?? (() => {})}
        onStandaloneId={props.onStandaloneId ?? (() => {})}
        txComposition={props.txComposition ?? null}
      />
    );
  }
```

    CAUTION: the early return must come after ALL of NeighborhoodPanel's own hooks (`useEscapeToHome`, the five `useState`s, the ref, the `useEffect`) or React's hook order breaks between renders when the viewport crosses 1200px. Either (a) place the `useMediaQuery` call with the other hooks and the `return` after the last hook (`useEffect` at NeighborhoodPanel.tsx:94-98), or (b) extract the stacked view into a private `StackedNeighborhoodView` component and make `NeighborhoodPanel` a pure switch with only the `useMediaQuery` hook. Option (b) is cleaner; pick it unless it balloons the diff.
    Note the dashboard mounts its own `useEscapeToHome` (Task 7), so option (b) must move the stacked view's `useEscapeToHome` call into `StackedNeighborhoodView`.
  - `App.tsx` mount gains:

```tsx
          messages={messages}
          transmitting={transmitting}
          showCallsignChips={showCallsignChips}
          onSendMessage={handleSend}
          onChat={handleChat}
          onStandaloneId={handleStandaloneId}
          txComposition={txComposition}
```

- [ ] **Step 4: Run the full frontend suite + typecheck**
  Run: `cd frontend && npx vitest run && npx tsc -p tsconfig.build.json --noEmit`
  Expected: ALL PASS

- [ ] **Step 5: Run the full backend suite**
  Run: `python -m pytest backend/tests/ -q`
  Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/NeighborhoodPanel/NeighborhoodPanel.tsx frontend/src/App.tsx frontend/src/components/NeighborhoodPanel/__tests__/NeighborhoodPanel.test.tsx
git commit -m "feat(neighborhood): auto-switch wide-screen coordinators to the ops dashboard"
```

---

## Verification checklist (end of plan)

- [ ] `python -m pytest backend/tests/ -q` — green
- [ ] `cd frontend && npx vitest run` — green
- [ ] `cd frontend && npx tsc -p tsconfig.build.json --noEmit` — green
- [ ] Manual smoke (Benjamin): dev stack up, log in as coordinator on a wide window → dashboard; shrink window → stacked view; second browser as participant sees stacked view and live roster updates; radio check-in from dashboard appears on both; No answer → warning chip + Call next skips; per-row Call announces over TX and sets Current turn; end net → Past Nets shows the no-answer column; CSV carries it.

## Out of scope (from the spec)

- Participant/stacked view redesign; NCS plugin round-table; auto-revisit of no-answer stations; any coordinator-view toggle or preference.
