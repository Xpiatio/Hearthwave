# Hearthwave Neighborhood Activity (Phase 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Neighborhood activity — plain-language watch roster with check-ins, incident reports (standardized voice TX + persistent filterable log), coordinator one-tap street alert, and a next-net schedule card.

**Architecture:** All server logic lives in CORE `backend/server.py` handlers + new `backend/neighborhood/` module (identity-aware — the NCS plugin's `dispatch_client_message` carries no caller identity, so coordinator/kid gating cannot live there; this mirrors how Phase 2 built Family in core). Pure formatting reuses `backend/plugins/ncs.py` module-level helpers by import. Frontend: new full-screen NeighborhoodPanel (both tiers), home card, mobile tab — mirroring FamilyPanel wiring exactly. Spec: `docs/superpowers/specs/2026-07-17-hearthwave-home-redesign-design.md` §3.

**Tech Stack:** FastAPI + WS, JSON persistence (`atomic_json_write`), React 18 + MUI v9 + TS, Vitest + Testing Library + jest-axe, pytest.

## Global Constraints

- Branch `feat/hearthwave-neighborhood-phase3` (base 5420c42). Conventional commits, **no Co-Authored-By / Claude footers**.
- Gates: `cd backend && python -m pytest -q` (baseline 1803); `cd frontend && npx tsc -p tsconfig.build.json` (NEVER bare tsc) + `npx vitest run` (baseline 820) + `npm run build`.
- **Coordinator** = per-user pref `neighborhood_coordinator: bool` (default absent/false). Admin-set ONLY via new WS `{"type":"set_neighborhood_coordinator","user_id","coordinator":bool}` (mirror `set_role` idiom incl. live-session propagation via `_sync_live_state_for_user`). NOT in `KID_ALLOWED_PREF_KEYS`; NOT settable via `save_user_prefs` (exclude from allowed set). Coordinator-only actions: street alert, neighborhood round-table (call next / new round), net start/end.
- Kid rules: check-in ALLOWED (roster-only, transmits nothing); `neighborhood_incident_report` REJECTED for kids (error idiom "TX not allowed for this account"); street alert unreachable (coordinator pref can't be set on kids — reject in handler like brace-presets rule).
- Incident categories exactly: `suspicious | hazard | medical | lost | utility` (labels: Suspicious activity, Hazard, Medical, Lost pet or person, Utility outage). Description required for all; location required.
- On-air incident phrase: `f"NEIGHBORHOOD {label upper}. {description}. LOCATION {location}. TIME {HH:MM} LOCAL. {callsign}."` — uppercased, mirroring `_format_spot_report` (ncs.py:534-544).
- Street alert phrase: `f"NEIGHBORHOOD ALERT. {message}. {callsign}."`; broadcast msg type `neighborhood_alert` `{id, message, issued_by, ts}`; client shows banner + browser Notification (existing 3-condition guard idiom in App.tsx) — visible in BOTH tiers.
- Incidents store: `/data/incidents.json` (env `RADIO_TTY_INCIDENTS`, config `incidents_file` per `presence_file` pattern) — newest-first list capped at 500, entries `{id, category, description, location, reporter, ts}`. **Deliberate deviation from spec's literal "journal-backed"**: journal entries carry no category field; a dedicated store is what makes "filterable" real. Record in ledger for final review.
- Net schedule: config keys `neighborhood_net_day` (`""|mon|tue|wed|thu|fri|sat|sun`) + `neighborhood_net_time` (`""` or `HH:MM`), top-level config like `ncs_zone` (config.py:338-340 pattern), edited in AdminPanel "Station Identity" section alongside NCS fields.
- Neighborhood roster: in-memory per-session (like NCS `self._roster`, cleared on server start), rows `{user_id, callsign, name, location, status: 'checked_in'|'standby', checkin_time, called: bool}`; keyed by user_id (members are known users — unlike NCS's over-the-air strangers).
- Neighborhood card + activity visible in BOTH tiers; `activity` union += `'neighborhood'`; mobile tab += `'neighborhood'` (survives simple-tier clamp like `'family'`).
- All new interactive components: jest-axe (open-dialog states included — UsersPanel lesson), text labels never color-only, plain language (no ham jargon: "Check in", "Report an incident", "Send street alert", not QST/QSL).
- localStorage `radio_tty_` / env `RADIO_TTY_` prefixes.

---

### Task 1: Backend — coordinator pref, incidents store, net-schedule config

**Files:**
- Create: `backend/persistence/incidents.py`
- Modify: `backend/config.py` (after `presence_file`/`family_file` props: `incidents_file`; after `ncs_zone` ~338: `neighborhood_net_day`, `neighborhood_net_time`)
- Modify: `backend/server.py` (lifespan store init near `_presence_store`; new `set_neighborhood_coordinator` handler by `set_role` ~3131; `_is_coordinator(state)` helper by `_is_kid` ~2257; exclude pref from `save_user_prefs` allowed set)
- Test: `backend/tests/unit/persistence/test_incidents.py`, extend `backend/tests/integration/test_server_ws.py` (add `incidents_file` to `_minimal_cfg` + `test_tx_watchdog.py::_cfg` like `presence_file` was)

**Interfaces:**
- Consumes: `atomic_json_write`/`load_json` (persistence/_utils.py, json_store.py — match real names), `_sync_live_state_for_user` (server.py ~1340), `_make_auth_mocks`/`kid_client` test helpers.
- Produces: `IncidentsStore(path)`: `add(entry: dict) -> dict` (assigns `id` = uuid4 hex, `ts` = caller-supplied iso, prepends, caps 500, saves), `list() -> list[dict]` (newest-first copy). `_is_coordinator(state) -> bool` reading `state.prefs.get("neighborhood_coordinator") is True`. WS `set_neighborhood_coordinator`: admin-only; target kid → error `"Kid accounts cannot be coordinators"`; success → `update_prefs` + live-sync + broadcast profiles. Config props with defaults `""` and validation (day in allowed set, time HH:MM or empty) at the `save_config` merge point following existing validated keys.

- [ ] **Step 1: Failing unit tests**

```python
# backend/tests/unit/persistence/test_incidents.py
from backend.persistence.incidents import IncidentsStore


def _entry(i=0):
    return {"category": "hazard", "description": f"tree down {i}",
            "location": "5th and Main", "reporter": "Ben", "ts": f"2026-07-17T09:0{i}:00Z"}


def test_add_assigns_id_and_prepends(tmp_path):
    s = IncidentsStore(str(tmp_path / "incidents.json"))
    a = s.add(_entry(0)); b = s.add(_entry(1))
    assert a["id"] != b["id"]
    assert [e["description"] for e in s.list()][:2] == ["tree down 1", "tree down 0"]


def test_persists_across_reload(tmp_path):
    p = str(tmp_path / "incidents.json")
    IncidentsStore(p).add(_entry())
    assert IncidentsStore(p).list()[0]["category"] == "hazard"


def test_caps_at_500(tmp_path):
    s = IncidentsStore(str(tmp_path / "incidents.json"))
    for i in range(505):
        s.add({**_entry(), "description": str(i)})
    lst = s.list()
    assert len(lst) == 500 and lst[0]["description"] == "504"


def test_corrupt_file_recovers_empty(tmp_path):
    p = tmp_path / "incidents.json"; p.write_text("{not json")
    assert IncidentsStore(str(p)).list() == []
```

- [ ] **Step 2: Run (fail) → implement `incidents.py`** mirroring `presence.py` structure (load/_save/atomic; `uuid.uuid4().hex` for id). Run (pass). Commit `feat(neighborhood): incidents store`.

- [ ] **Step 3: Failing integration tests** — `TestNeighborhoodCoordinator`: non-admin rejected; admin sets coordinator=true on adult → profiles broadcast shows pref; target kid → error frame + store untouched; live-sync: connected target's next coordinator-gated action works without reconnect (defer full assertion to Task 3's gated handlers if cleaner — then here assert state.prefs updated via a `get_family_reminders`-style probe or unit-level `_sync_live_state_for_user` call). Kid `save_user_prefs {"neighborhood_coordinator": true}` → key dropped (not in allowed set — assert profile unchanged).

- [ ] **Step 4: Implement** — helper, handler, config props + `save_config` validation, allowed-set exclusion. Run integration + full suite. Commit `feat(neighborhood): coordinator pref, admin handler, net-schedule config keys`.

---

### Task 2: Backend — neighborhood state, check-ins, simplified round-table

**Files:**
- Create: `backend/neighborhood/__init__.py`, `backend/neighborhood/net.py`
- Modify: `backend/server.py` (module instance in lifespan; WS handlers `neighborhood_get_state`, `neighborhood_checkin`, `neighborhood_status`, `neighborhood_start`, `neighborhood_end`, `neighborhood_call_next`, `neighborhood_call_reset`; connect-time state send after `family_presence`)
- Test: `backend/tests/unit/neighborhood/test_net.py`, extend integration

**Interfaces:**
- Consumes: `_is_coordinator`/`_is_kid` (Task 1), `_tx_queue` enqueue idiom (`{"text","_pre_formatted":True,"_operator_initiated":True}` — ncs.py:556), `_manager.broadcast`, `utc_now_iso`.
- Produces: `NeighborhoodNet` class (pure state, no I/O):
  - `active: bool`; `start()`, `end() -> dict` (returns summary: roster snapshot + duration for journal), `checkin(user_id, callsign, name, location) -> dict row` (idempotent per user_id — re-checkin updates), `set_status(user_id, status)`, `call_next() -> row|None` (first checked_in not called; marks called), `call_reset()`, `roster() -> list[dict]`, `current_call: str|None` (user_id).
  - Server broadcast `{"type":"neighborhood_state","active","roster","current_call","net_day","net_time"}` on every mutation + connect. Coordinator gates on start/end/call_next/call_reset (error `"Coordinator access required"`); check-in/status open to ALL roles (incl. kid — transmits nothing).
  - `call_next` TX enqueue: plain language `f"{name}, you're up. Anything to report? {station_callsign}."` — get station callsign the way NCS does (config `station_callsign`-ish; find the real key ncs.py uses in `_announce_call` 625-637 and reuse).
  - `neighborhood_end` with non-empty roster → journal entry via `save_journal(title=f"Neighborhood net {date}", summary=..., callsigns_with_locations=..., transcript=roster lines, journals_dir=config.journals_dir)` (journal.py:15-35) + broadcast `journal_saved`-consistent msg (match NCS's `ncs_journal_saved` shape or reuse `journals` refresh idiom — read `_save_ncs_journal` ncs.py:674-701 and mirror).

- [ ] **Step 1: Failing unit tests for `NeighborhoodNet`** — start/end lifecycle; checkin idempotent per user_id; call_next ordering + round completion (returns None when all called); call_reset clears called + current; set_status standby excluded from call_next.

```python
# backend/tests/unit/neighborhood/test_net.py — representative core
from backend.neighborhood.net import NeighborhoodNet


def test_checkin_idempotent_updates():
    n = NeighborhoodNet(); n.start()
    n.checkin("u1", "WRXB123", "Ben", "5th St")
    n.checkin("u1", "WRXB123", "Ben", "Oak Ave")
    assert len(n.roster()) == 1 and n.roster()[0]["location"] == "Oak Ave"


def test_call_next_round():
    n = NeighborhoodNet(); n.start()
    n.checkin("u1", "A", "Ann", ""); n.checkin("u2", "B", "Bob", "")
    first = n.call_next(); second = n.call_next()
    assert (first["user_id"], second["user_id"]) == ("u1", "u2")
    assert n.call_next() is None          # round complete
    n.call_reset()
    assert n.call_next()["user_id"] == "u1"


def test_standby_skipped():
    n = NeighborhoodNet(); n.start()
    n.checkin("u1", "A", "Ann", ""); n.set_status("u1", "standby")
    assert n.call_next() is None
```

- [ ] **Step 2: Implement class (pure). Commit** `feat(neighborhood): net state machine (roster, check-ins, round-table)`.
- [ ] **Step 3: Failing integration tests** — get_state on connect; checkin (any role incl. kid) broadcasts state; start requires coordinator (adult w/o pref → error, coordinator fixture → active); call_next enqueues TX + broadcasts current_call; end saves journal (assert `save_journal` called via tmp journals_dir file existence or mock).
- [ ] **Step 4: Wire handlers + connect send + coordinator fixture (`_make_auth_mocks` gains `coordinator=` param setting the pref). Full suite. Commit** `feat(neighborhood): WS handlers, coordinator gates, net journal on end`.

---

### Task 3: Backend — incident reports + street alert

**Files:**
- Create: `backend/neighborhood/incidents.py` (pure validate/format)
- Modify: `backend/server.py` (handlers `neighborhood_incident_report`, `neighborhood_list_incidents`, `neighborhood_street_alert`)
- Test: `backend/tests/unit/neighborhood/test_incidents.py`, extend integration

**Interfaces:**
- Consumes: `IncidentsStore` (Task 1), `_is_kid`/`_is_coordinator`, TX enqueue idiom, `_broadcast_family_chat`-style chat echo (read `tx_echo` idiom ncs.py:564-573 — incident + alert should appear in chat like spot reports do; mirror the display_name pattern with "NEIGHBORHOOD").
- Produces:
  - `CATEGORIES = {"suspicious": "Suspicious activity", "hazard": "Hazard", "medical": "Medical", "lost": "Lost pet or person", "utility": "Utility outage"}`.
  - `validate_incident(payload) -> str|None` (category in CATEGORIES, non-empty stripped description ≤500, non-empty location ≤200).
  - `format_incident(category_label, description, location, hhmm_local, callsign) -> str` per Global Constraints phrase.
  - WS `neighborhood_incident_report {category, description, location}`: kid → error; validate → error frame `{"type":"neighborhood_incident_error","detail"}`; success → TX enqueue + tx_echo chat + `IncidentsStore.add` (reporter = profile display_name, ts = utc_now_iso) + broadcast `{"type":"neighborhood_incidents","incidents":store.list()}` + reply `{"type":"neighborhood_incident_sent","text","ts"}`.
  - WS `neighborhood_list_incidents`: any role → send_to same `neighborhood_incidents` msg. Also send on connect.
  - WS `neighborhood_street_alert {message}`: coordinator only; message 1-200 chars stripped; TX enqueue phrase + tx_echo + broadcast `{"type":"neighborhood_alert","id":uuid hex,"message","issued_by":display_name,"ts"}` to ALL (kids included — safety info); respect listen_only for TTS leg only (family_status precedent server.py:2457 region).

- [ ] **Step 1: Failing pure tests** (validate: each category ok, bad category, empty description/location, oversize; format: exact phrase assembly incl. uppercase + label).
- [ ] **Step 2: Implement pure module. Commit** `feat(neighborhood): incident validation and on-air formatting`.
- [ ] **Step 3: Failing integration** — kid incident rejected; adult incident → TX enqueued + incidents broadcast grows + sent reply; bad payload → incident_error; street alert coordinator-only (adult rejected); alert broadcast reaches kid client; listen-only coordinator alert skips TTS still broadcasts.
- [ ] **Step 4: Wire, full suite, commit** `feat(neighborhood): incident report and street alert handlers`.

---

### Task 4: Frontend — types + App plumbing

**Files:**
- Modify: `frontend/src/types/ws.ts` (new types + union), `frontend/src/App.tsx`
- Create: `frontend/src/neighborhood/schedule.ts` (pure next-net helper)
- Test: `frontend/src/neighborhood/__tests__/schedule.test.ts`

**Interfaces:**
- Consumes: backend msgs Tasks 1-3; App patterns from Phase 2 (activity union App.tsx:166, switch, sharedProps ~1283, notification guard idiom App.tsx:739-754 region).
- Produces:
  - Types: `NeighborhoodRosterRow {user_id, callsign, name, location, status: 'checked_in'|'standby', checkin_time, called}`; `NeighborhoodStateMsg {type:'neighborhood_state', active, roster, current_call, net_day, net_time}`; `IncidentEntry {id, category, description, location, reporter, ts}`; `NeighborhoodIncidentsMsg`; `NeighborhoodAlertMsg {type:'neighborhood_alert', id, message, issued_by, ts}`; `NeighborhoodIncidentSentMsg`/`ErrorMsg` — all in `WsMessage` union. `UserPrefs.neighborhood_coordinator?: boolean`.
  - `schedule.ts`: `export function nextNetLabel(day: string, time: string, now: Date): string` → `""` when unset/invalid; else `"Net Tue 7:00 PM"` style (next occurrence day name + 12h time).
  - App: `activity` union += `'neighborhood'`; state `neighborhoodState`, `incidents`, `neighborhoodAlerts` (last 3, dedup by id); switch cases; `neighborhood_alert` → banner state + browser Notification (3-condition guard) — fires for ALL tiers/roles; sends: `sendNeighborhoodCheckin`, `sendNeighborhoodStatus`, `sendIncidentReport`, `sendStreetAlert`, `sendNeighborhoodStart/End/CallNext/CallReset`, `sendSetNeighborhoodCoordinator`; `isCoordinator = profile?.prefs?.neighborhood_coordinator === true`; thread all through sharedProps; `handleOpenActivity` += `'neighborhood'`.

- [ ] **Step 1: Failing schedule tests** (unset → ""; Tue 19:00 with now=Mon → "Net Tue 7:00 PM"; today-before-time → today; today-after-time → next week same day label; bad time → "").
- [ ] **Step 2: Implement helper; types; App wiring. Typecheck + suite. Commit** `feat(neighborhood): ws types, app state, alert notifications, next-net helper`.

---

### Task 5: Frontend — NeighborhoodPanel + home card + desktop wiring

**Files:**
- Create: `frontend/src/components/NeighborhoodPanel/NeighborhoodPanel.tsx`, `IncidentDialog.tsx`, `IncidentLog.tsx`, `__tests__/NeighborhoodPanel.test.tsx`, `__tests__/IncidentDialog.test.tsx`
- Modify: `frontend/src/components/HomeScreen/HomeScreen.tsx` (+card), `frontend/src/App.tsx` (ladder branch), extend HomeScreen tests

**Interfaces:**
- Consumes: Task 4 types/sends; SpotReportDialog form pattern (frontend/src/components/NCSPanel/SpotReportDialog.tsx — props/valid-gating/conditional fields); FamilyPanel full-screen layout + Escape hook precedent (hook INSIDE panel, conditional mount); ActivityCard alertText plumbing (folds into accessible name).
- Produces:

```typescript
export interface NeighborhoodPanelProps {
  roster: NeighborhoodRosterRow[]
  netActive: boolean
  currentCall: string | null
  incidents: IncidentEntry[]
  alerts: NeighborhoodAlertMsg[]
  netDay: string
  netTime: string
  isCoordinator: boolean
  isKid: boolean
  myUserId: string
  onCheckin: () => void            // uses own profile fields server-side
  onIncidentReport: (p: { category: string; description: string; location: string }) => void
  incidentError: string | null
  onStreetAlert: (message: string) => void
  onStartNet: () => void
  onEndNet: () => void
  onCallNext: () => void
  onNewRound: () => void
  onGoHome: () => void
}
```

  - Layout (plain language throughout): header (Back "Back to home", title "Neighborhood", net status chip "Net running"/"No net right now" + `nextNetLabel`); big "Check in" button (minHeight 96, disabled+"You're checked in ✓" state when own user_id in roster); alert banner (last alerts, warning styling + text); "Report an incident" button → IncidentDialog; IncidentLog (filter `Select` all/5 categories + `List` newest-first, each entry: category label chip + description + location + reporter + time); coordinator section (only `isCoordinator`): Start net / End net, "Call next neighbor" + "New round", street-alert compose (TextField ≤200 + "Send street alert" button with confirm — destructive-ish, one `window.confirm` like JournalPanel's confirm-twice precedent is overkill; single confirm fine); kids see check-in + log + alerts only (no incident button — server rejects anyway, hide per kid UX rule).
  - IncidentDialog modeled on SpotReportDialog: category Select (5), description (required, multiline), location (required), submit disabled until valid, error prop display.
  - HomeScreen: 🏘 Neighborhood card after Family, BOTH tiers; subtitle = `netActive ? 'Net running now' : nextNetLabel(...)`; `alertText` = latest street alert message when < 30 min old (fold into accessible name via existing alertText mechanism); onClick `onOpenActivity('neighborhood')`; Props gain the needed data.
  - App ladder: `activity === 'neighborhood'` branch beside 'family'.
  - Tests: makeProps factory; roster render + checked-in state flip; incident dialog validation gating + submit payload; filter narrows log; coordinator section hidden for non-coordinator AND kid; street alert confirm + fires; axe with dialog OPEN and panel base state; HomeScreen card both tiers + subtitle/alertText.

- [ ] Steps: failing tests → implement → typecheck+suite → commits (`feat(neighborhood): NeighborhoodPanel with roster, incidents, street alert` + `feat(neighborhood): home card and desktop activity wiring`).

---

### Task 6: Frontend — mobile tab, AdminPanel schedule fields, UsersPanel coordinator toggle

**Files:**
- Modify: `frontend/src/components/MobileApp/MobileApp.tsx` (tab union 242, clamp 256, BottomNav 386-401, panel block), `frontend/src/components/AdminPanel/AdminPanel.tsx` (net day/time fields near ncs_zone fields), `frontend/src/components/UsersPanel/UsersPanel.tsx` (coordinator Switch per row, disabled for kid rows w/ tooltip), `frontend/src/App.tsx` (pass onSetNeighborhoodCoordinator; save_config carries new keys)
- Test: extend MobileApp tier tests (neighborhood tab BOTH tiers, conditional unmount like family), UsersPanel tests (toggle fires, kid row disabled), AdminPanel test if exists

**Interfaces:** consumes everything above; produces `MobileAppProps` + neighborhood props; clamp: simple tier allows chat+family+neighborhood.

- [ ] Steps: failing tests → implement → typecheck+suite → commit `feat(neighborhood): mobile tab, schedule admin fields, coordinator toggle`.

---

### Task 7: Docs + whole-feature verification

**Files:** USER_MANUAL.md (Neighborhood section: check-ins, incident reporting, street alerts, coordinator setup, net schedule; plain language), README.md bullet, docs/index.html only if feature-listing. NO version bump.

- [ ] Docs; full verification (backend suite, frontend tsc+vitest+build); commit `docs: neighborhood activity, incident log, street alerts`.

---

## Self-review notes (spec §3 coverage)

- Watch roster + check-ins ✅ T2/T5 (plain-language relabel = new panel copy; simplified round-table = call next/new round only, no traffic taxonomy). Incident report ✅ T3/T5 (5 spec categories; SpotReportDialog model). Street alert ✅ T3/T5 (TTS + banner + browser notification; reuse = same broadcast/enqueue idioms, new msg type since ncs_alert is NWS-shaped). Incident log ✅ T1/T3/T5 (dedicated store — deliberate deviation from literal "journal-backed", rationale in Global Constraints; net END still writes a journal entry via T2). Net schedule card ✅ T1/T4/T5 (config keys + nextNetLabel + card subtitle; tap = open activity, check-in button one tap inside — spec's "tap = early check-in" satisfied via the panel's primary action; direct-checkin-from-card rejected: accidental single-tap TX-adjacent action from home grid is a misfire hazard on wall displays).
- Coordinator enforcement server-side in core ✅ T1-T3 (plugin identity gap avoided entirely; NCS plugin untouched).
- Out of scope: kiosk (§5/Phase 4), switch scanning (Phase 5), NCS plugin auth follow-up ticket.
