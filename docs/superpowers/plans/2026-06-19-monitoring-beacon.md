# Monitoring Beacon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in, fixed-interval "monitoring" beacon that transmits `{callsign} Hearthwave base, monitoring.` over the air, coordinated with the existing FCC ID pump so the two never identify redundantly.

**Architecture:** A new isolated module `backend/beacon/monitoring.py` holds two pure functions — the phrase formatter and the gating decision. A thin async pump in `server.py` (`_monitoring_beacon_pump`, sibling of `_id_rule_pump`) polls once a minute, applies the gate, and on fire enqueues TX and resets the FCC ID timer. Three new config keys control it; it is disabled by default.

**Tech Stack:** Python 3, asyncio, pytest (asyncio_mode=auto — async tests need no decorator), faster-whisper/Piper unaffected.

## Global Constraints

- Beacon is **disabled by default** (`monitoring_beacon_enabled` default `False`).
- Default interval `900` seconds; default phrase `"{callsign} Hearthwave base, monitoring."`.
- `{callsign}` is the only supported template placeholder; substitute with `str.replace` (never `str.format`) so stray braces don't raise.
- Beacon is **suppressed while NCS mode is active**.
- Beacon fires only when **the channel is clear** at the tick.
- When the beacon fires it **resets the FCC ID timer** (`_last_id_time = now`, `_has_transmitted = False`) — the phrase contains the callsign and satisfies the FCC 15-min ID.
- Digit-spelling helper: `spell_digits_in_callsigns` from `backend/text/callsigns.py` (`'WSLZ233' -> 'WSLZ 2 3 3'`).
- Follow existing patterns: `ServerConfig` is a dict subclass with typed `@property` accessors using `self.get(key, default)`; tests live under `backend/tests/unit/<area>/`.

---

### Task 1: Beacon module — formatter + gating (pure functions)

**Files:**
- Create: `backend/beacon/__init__.py`
- Create: `backend/beacon/monitoring.py`
- Create: `backend/tests/unit/beacon/__init__.py`
- Test: `backend/tests/unit/beacon/test_monitoring.py`

**Interfaces:**
- Consumes: `spell_digits_in_callsigns(text: str) -> str` from `backend.text.callsigns`.
- Produces:
  - `format_monitoring_call(template: str, callsign: str) -> str`
  - `should_emit_beacon(*, enabled: bool, ncs_active: bool, channel_clear: bool, elapsed: float, interval: float) -> bool`

- [ ] **Step 1: Create the test package init**

Create `backend/tests/unit/beacon/__init__.py` as an empty file.

```python
```

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/unit/beacon/test_monitoring.py`:

```python
from backend.beacon.monitoring import format_monitoring_call, should_emit_beacon


# ---------------------------------------------------------------------------
# format_monitoring_call
# ---------------------------------------------------------------------------

class TestFormatMonitoringCall:
    def test_substitutes_callsign(self):
        result = format_monitoring_call(
            "{callsign} Hearthwave base, monitoring.", "WSLZ233"
        )
        assert result.startswith("WSLZ")
        assert "Hearthwave base, monitoring." in result

    def test_digits_in_callsign_are_spelled(self):
        result = format_monitoring_call(
            "{callsign} Hearthwave base, monitoring.", "WSLZ233"
        )
        assert "WSLZ 2 3 3" in result

    def test_custom_template(self):
        result = format_monitoring_call("CQ from {callsign}.", "WSLZ233")
        assert "CQ from WSLZ 2 3 3." == result

    def test_stray_brace_is_not_an_error(self):
        # {weird} is not {callsign}; it must be left untouched, no exception.
        result = format_monitoring_call("{callsign} {weird}.", "WSLZ233")
        assert "{weird}." in result


# ---------------------------------------------------------------------------
# should_emit_beacon
# ---------------------------------------------------------------------------

class TestShouldEmitBeacon:
    def _kwargs(self, **over):
        base = dict(
            enabled=True, ncs_active=False, channel_clear=True,
            elapsed=1000.0, interval=900.0,
        )
        base.update(over)
        return base

    def test_fires_when_all_conditions_met(self):
        assert should_emit_beacon(**self._kwargs()) is True

    def test_skips_when_disabled(self):
        assert should_emit_beacon(**self._kwargs(enabled=False)) is False

    def test_skips_when_ncs_active(self):
        assert should_emit_beacon(**self._kwargs(ncs_active=True)) is False

    def test_skips_when_channel_busy(self):
        assert should_emit_beacon(**self._kwargs(channel_clear=False)) is False

    def test_skips_when_interval_not_elapsed(self):
        assert should_emit_beacon(**self._kwargs(elapsed=10.0, interval=900.0)) is False

    def test_fires_exactly_at_interval(self):
        assert should_emit_beacon(**self._kwargs(elapsed=900.0, interval=900.0)) is True
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/unit/beacon/test_monitoring.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.beacon'`

- [ ] **Step 4: Create the package init**

Create `backend/beacon/__init__.py` as an empty file.

```python
```

- [ ] **Step 5: Implement the module**

Create `backend/beacon/monitoring.py`:

```python
"""Monitoring beacon — periodic presence announcement.

Pure helpers only (no I/O). The async pump that drives these lives in
server.py as _monitoring_beacon_pump.
"""
from __future__ import annotations

from backend.text.callsigns import spell_digits_in_callsigns


def format_monitoring_call(template: str, callsign: str) -> str:
    """Build the spoken monitoring-beacon phrase.

    Substitutes {callsign} into *template*, then spells out digits in the
    callsign for radio intelligibility (the same treatment the FCC ID pump
    applies). Uses str.replace, not str.format, so stray braces in a custom
    template do not raise.
    """
    phrase = template.replace("{callsign}", callsign)
    return spell_digits_in_callsigns(phrase)


def should_emit_beacon(
    *,
    enabled: bool,
    ncs_active: bool,
    channel_clear: bool,
    elapsed: float,
    interval: float,
) -> bool:
    """Pure gating decision: True only when the beacon should transmit now.

    Order matters for clarity, not correctness: disabled and NCS-active are
    hard stops; a busy channel defers; otherwise fire once the interval has
    elapsed.
    """
    if not enabled:
        return False
    if ncs_active:
        return False
    if not channel_clear:
        return False
    return elapsed >= interval
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/unit/beacon/test_monitoring.py -v`
Expected: PASS (10 tests)

- [ ] **Step 7: Commit**

```bash
cd /mnt/storage/Repos/Radio-TTY
git add backend/beacon backend/tests/unit/beacon
git commit -m "feat(beacon): monitoring-call formatter and gating helpers"
```

---

### Task 2: Config properties

**Files:**
- Modify: `backend/config.py` (add three properties after `ncs_announcement_interval`, ~line 280)
- Modify: `data/config.json` (add the three keys with defaults)
- Test: `backend/tests/unit/test_config.py` (append a test class)

**Interfaces:**
- Produces: `ServerConfig.monitoring_beacon_enabled -> bool`, `ServerConfig.monitoring_beacon_interval -> int`, `ServerConfig.monitoring_beacon_text -> str`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/unit/test_config.py` (the file already defines `make_config(**kwargs)` and imports `ServerConfig`):

```python
# ---------------------------------------------------------------------------
# Monitoring beacon
# ---------------------------------------------------------------------------

class TestMonitoringBeaconDefaults:
    def test_enabled_default_false(self):
        assert ServerConfig().monitoring_beacon_enabled is False

    def test_interval_default_900(self):
        assert ServerConfig().monitoring_beacon_interval == 900

    def test_text_default(self):
        assert ServerConfig().monitoring_beacon_text == "{callsign} Hearthwave base, monitoring."


class TestMonitoringBeaconOverrides:
    def test_enabled_override(self):
        assert make_config(monitoring_beacon_enabled=True).monitoring_beacon_enabled is True

    def test_interval_override(self):
        assert make_config(monitoring_beacon_interval=300).monitoring_beacon_interval == 300

    def test_text_override(self):
        assert make_config(monitoring_beacon_text="CQ {callsign}").monitoring_beacon_text == "CQ {callsign}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/unit/test_config.py -k MonitoringBeacon -v`
Expected: FAIL — `AttributeError: 'ServerConfig' object has no attribute 'monitoring_beacon_enabled'`

- [ ] **Step 3: Add the properties**

In `backend/config.py`, immediately after the `ncs_announcement_interval` property (ends ~line 280), add:

```python
    # ---- monitoring beacon ----------------------------------------------

    @property
    def monitoring_beacon_enabled(self) -> bool:
        """Emit a periodic presence beacon over the air (default off)."""
        return bool(self.get("monitoring_beacon_enabled", False))

    @property
    def monitoring_beacon_interval(self) -> int:
        """Seconds between monitoring beacons (default 900)."""
        return int(self.get("monitoring_beacon_interval", 900))

    @property
    def monitoring_beacon_text(self) -> str:
        """Beacon phrase template; {callsign} is substituted before TTS."""
        return self.get("monitoring_beacon_text", "{callsign} Hearthwave base, monitoring.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/unit/test_config.py -k MonitoringBeacon -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Add keys to the example config**

In `data/config.json`, add these three keys (preserve existing JSON; place near the `ncs_*` keys). Match the file's existing indentation and trailing-comma rules:

```json
  "monitoring_beacon_enabled": false,
  "monitoring_beacon_interval": 900,
  "monitoring_beacon_text": "{callsign} Hearthwave base, monitoring.",
```

If a separate seed template exists (e.g. `data/config.example.json`), add the same three keys there too. Verify the file still parses:

Run: `cd /mnt/storage/Repos/Radio-TTY && python -c "import json; json.load(open('data/config.json'))"`
Expected: no output (valid JSON)

- [ ] **Step 6: Commit**

```bash
cd /mnt/storage/Repos/Radio-TTY
git add backend/config.py backend/tests/unit/test_config.py data/config.json
git commit -m "feat(config): monitoring beacon settings (default off)"
```

---

### Task 3: NCSPlugin.is_active()

**Files:**
- Modify: `backend/plugins/ncs.py` (add a public accessor on `NCSPlugin`)
- Test: `backend/tests/unit/plugins/test_ncs.py` (append a test class)

**Interfaces:**
- Produces: `NCSPlugin.is_active(self) -> bool` — returns the plugin's `_active` flag. Consumed by Task 4's pump.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/unit/plugins/test_ncs.py` (the file already defines `make_ncs(...)`):

```python
class TestIsActive:
    def test_inactive_by_default(self):
        ncs = make_ncs()
        assert ncs.is_active() is False

    def test_active_after_flag_set(self):
        ncs = make_ncs()
        ncs._active = True
        assert ncs.is_active() is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/unit/plugins/test_ncs.py -k IsActive -v`
Expected: FAIL — `AttributeError: 'NCSPlugin' object has no attribute 'is_active'`

- [ ] **Step 3: Add the accessor**

In `backend/plugins/ncs.py`, add this method to the `NCSPlugin` class (place it near the other small state methods, e.g. just after `__init__` or before `_handle_start`):

```python
    def is_active(self) -> bool:
        """True while NCS / net-control mode is running."""
        return self._active
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/unit/plugins/test_ncs.py -k IsActive -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
cd /mnt/storage/Repos/Radio-TTY
git add backend/plugins/ncs.py backend/tests/unit/plugins/test_ncs.py
git commit -m "feat(ncs): public is_active() accessor"
```

---

### Task 4: Wire the beacon pump into the server

**Files:**
- Modify: `backend/server.py` — import, two module globals, capture NCS instance, new pump, task registration, restart reset
- Test: `backend/tests/unit/test_server_beacon.py` (new)

**Interfaces:**
- Consumes: `format_monitoring_call`, `should_emit_beacon` (Task 1); `NCSPlugin.is_active` (Task 3); config properties (Task 2).
- Produces: async task `_monitoring_beacon_pump()`; module globals `_last_beacon_time`, `_ncs_plugin`.

Reference points (verify line numbers before editing — they drift):
- Import block ends ~`server.py:147` (the `from backend.tts.synthesizer import TTSSynthesizer` line).
- FCC-ID globals at `server.py:199-200` (`_last_id_time`, `_has_transmitted`).
- `_id_rule_pump` defined `server.py:1190-1211` — copy its shape.
- Startup `global` statement at `server.py:1265`; restart resets at `server.py:1347-1349`.
- NCS construction at `server.py:1387-1388`; `_background_tasks` set at ~`server.py:1406-1414`.

- [ ] **Step 1: Write the failing pump test**

Create `backend/tests/unit/test_server_beacon.py`:

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import backend.server as server
from backend.config import ServerConfig


def _arm_server(*, enabled=True, ncs_active=False, channel_clear=True):
    cfg = ServerConfig()
    cfg.update({
        "monitoring_beacon_enabled": enabled,
        "monitoring_beacon_interval": 900,
        "callsign": "WSLZ233",
    })
    server._config = cfg
    server._tx_queue = asyncio.Queue()
    server._manager = MagicMock()
    server._manager.broadcast = AsyncMock()
    server._channel_clear = channel_clear
    server._last_beacon_time = None
    server._last_id_time = None
    server._has_transmitted = True
    if ncs_active:
        ncs = MagicMock()
        ncs.is_active.return_value = True
        server._ncs_plugin = ncs
    else:
        server._ncs_plugin = None


async def _run_one_tick():
    """Drive the pump through exactly one loop body, then break via CancelledError."""
    calls = 0

    async def fake_sleep(_):
        nonlocal calls
        calls += 1
        if calls >= 2:
            raise asyncio.CancelledError()

    with patch("asyncio.sleep", side_effect=fake_sleep):
        await server._monitoring_beacon_pump()


class TestMonitoringBeaconPump:
    async def test_fires_and_resets_fcc_id_timer(self):
        _arm_server(enabled=True)
        await _run_one_tick()
        assert not server._tx_queue.empty()
        item = server._tx_queue.get_nowait()
        assert item["_pre_formatted"] is True
        assert "monitoring" in item["text"]
        # Beacon counts as the FCC ID:
        assert server._has_transmitted is False
        assert server._last_id_time is not None
        assert server._last_beacon_time is not None

    async def test_skips_when_disabled(self):
        _arm_server(enabled=False)
        await _run_one_tick()
        assert server._tx_queue.empty()

    async def test_skips_when_ncs_active(self):
        _arm_server(enabled=True, ncs_active=True)
        await _run_one_tick()
        assert server._tx_queue.empty()

    async def test_skips_when_channel_busy(self):
        _arm_server(enabled=True, channel_clear=False)
        await _run_one_tick()
        assert server._tx_queue.empty()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/unit/test_server_beacon.py -v`
Expected: FAIL — `AttributeError: module 'backend.server' has no attribute '_monitoring_beacon_pump'`

- [ ] **Step 3: Add the import**

In `backend/server.py`, after the `from backend.tts.synthesizer import TTSSynthesizer` import (~line 147), add:

```python
from backend.beacon.monitoring import format_monitoring_call, should_emit_beacon
```

- [ ] **Step 4: Add module globals**

In `backend/server.py`, just after the FCC-ID globals (`_has_transmitted: bool = False`, ~line 200), add:

```python
# Monitoring-beacon state — asyncio-only (single writer: the beacon pump task).
_last_beacon_time: datetime.datetime | None = None

# Set at startup to the live NCSPlugin instance so the beacon can suppress
# itself while a net is active.
_ncs_plugin = None
```

- [ ] **Step 5: Add the pump function**

In `backend/server.py`, immediately after `_id_rule_pump` (ends ~line 1211), add:

```python
async def _monitoring_beacon_pump() -> None:
    """Emit a periodic presence beacon when enabled and the channel is clear.

    Unlike _id_rule_pump (activity-gated), this fires on a fixed cadence. It is
    suppressed while NCS mode is active, and when it fires it also resets the
    FCC ID timer — the phrase contains the callsign, so it satisfies the ID.
    """
    global _last_beacon_time, _last_id_time, _has_transmitted
    while True:
        try:
            await asyncio.sleep(60)
            if _config is None:
                continue
            now = datetime.datetime.now(datetime.timezone.utc)
            elapsed = (now - _last_beacon_time).total_seconds() if _last_beacon_time else float("inf")
            ncs_active = _ncs_plugin.is_active() if _ncs_plugin is not None else False
            if not should_emit_beacon(
                enabled=_config.monitoring_beacon_enabled,
                ncs_active=ncs_active,
                channel_clear=_channel_clear,
                elapsed=elapsed,
                interval=_config.monitoring_beacon_interval,
            ):
                continue
            spoken = format_monitoring_call(_config.monitoring_beacon_text, _config.callsign)
            _last_beacon_time = now
            _last_id_time = now
            _has_transmitted = False
            _log.info("Monitoring beacon: broadcasting presence announcement.")
            await _manager.broadcast({"type": "tx_status", "status": "transmitting"})
            await _tx_queue.put({"text": spoken, "_pre_formatted": True})
        except asyncio.CancelledError:
            break
        except Exception as exc:
            _log.error("_monitoring_beacon_pump error: %s", exc)
```

- [ ] **Step 6: Capture the NCS instance + extend the startup global statement**

In `backend/server.py`, find the startup `global` statement at ~line 1265 (begins `global _audio_level, _radio_error, _channel_clear, _last_id_time, _has_transmitted`). Append the two new globals:

```python
    global _audio_level, _radio_error, _channel_clear, _last_id_time, _has_transmitted, _last_beacon_time, _ncs_plugin
```

Then change the NCS construction at ~line 1387-1388 from:

```python
    from backend.plugins.ncs import NCSPlugin
    plugin_registry.register(NCSPlugin(
```

to capture the instance first:

```python
    from backend.plugins.ncs import NCSPlugin
    _ncs_plugin = NCSPlugin(
```

…and update the matching closing line. The original call ends with `))` (the `register(` paren plus the `NCSPlugin(` paren). After the edit the constructor's closing `)` stands alone, followed by a register call. Concretely, the block that currently reads:

```python
    plugin_registry.register(NCSPlugin(
        broadcast_fn=_manager.broadcast,
        tx_queue=_tx_queue,
        config_getter=lambda: _config,
        channel_clear_fn=lambda: _channel_clear,
        contacts_getter=lambda: _contacts_store.get_all() if _contacts_store else [],
        add_contact_fn=lambda c: _contacts_store.add_contact(c) if _contacts_store else [],
        update_contact_fn=lambda cs, u, original_name=None: _contacts_store.update_contact(cs, u, original_name=original_name) if _contacts_store else [],
        ...   # (leave every remaining kwarg exactly as-is)
    ))
```

becomes:

```python
    _ncs_plugin = NCSPlugin(
        broadcast_fn=_manager.broadcast,
        tx_queue=_tx_queue,
        config_getter=lambda: _config,
        channel_clear_fn=lambda: _channel_clear,
        contacts_getter=lambda: _contacts_store.get_all() if _contacts_store else [],
        add_contact_fn=lambda c: _contacts_store.add_contact(c) if _contacts_store else [],
        update_contact_fn=lambda cs, u, original_name=None: _contacts_store.update_contact(cs, u, original_name=original_name) if _contacts_store else [],
        ...   # (leave every remaining kwarg exactly as-is)
    )
    plugin_registry.register(_ncs_plugin)
```

Only the first line and the final `))` → `)` + new `register` line change; every kwarg in between stays identical.

- [ ] **Step 7: Register the task and reset on restart**

In `backend/server.py`, add the beacon to the `_background_tasks` set (~line 1406-1414), next to the id-rule pump:

```python
        asyncio.create_task(_id_rule_pump(), name="id-rule-pump"),
        asyncio.create_task(_monitoring_beacon_pump(), name="monitoring-beacon-pump"),
```

Then, where the FCC-ID state is reset on radio (re)start (~line 1347-1349, `_last_id_time = None` / `_has_transmitted = False`), add:

```python
    _last_beacon_time = None
```

- [ ] **Step 8: Run the pump tests to verify they pass**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/unit/test_server_beacon.py -v`
Expected: PASS (4 tests)

- [ ] **Step 9: Run the full backend suite for regressions**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/unit -q`
Expected: PASS (all tests, including the new beacon/config/ncs ones; no regressions)

- [ ] **Step 10: Commit**

```bash
cd /mnt/storage/Repos/Radio-TTY
git add backend/server.py backend/tests/unit/test_server_beacon.py
git commit -m "feat(server): wire monitoring beacon pump (opt-in, NCS-suppressed, resets FCC ID)"
```

---

## Self-Review

**Spec coverage:**
- Separate transmitter / FCC ID untouched → Task 4 (new pump; `_id_rule_pump` unchanged). ✅
- Fixed-interval, channel-clear gated → Task 1 `should_emit_beacon` + Task 4 pump. ✅
- Suppressed during NCS → Task 3 `is_active` + Task 4 gate. ✅
- Beacon resets FCC ID timer → Task 4 pump (`_last_id_time`, `_has_transmitted`). ✅
- Opt-in + configurable interval/phrase → Task 2 config keys (default off). ✅
- `{callsign}`-only placeholder via `str.replace`; digit spelling → Task 1 `format_monitoring_call`. ✅
- Module isolation (`backend/beacon/monitoring.py`) → Task 1. ✅
- Tests: formatter, gating matrix, config, is_active, pump fire+reset+skips → Tasks 1-4. ✅
- Out of scope (no UI toggle, no per-user pref, no idle reset, no site-copy change) → honored; none added.

**Placeholder scan:** No TBD/TODO; every code step shows complete code. The `...   # (leave every remaining kwarg as-is)` in Task 4 Step 6 refers to existing lines the engineer must not alter, not missing content. ✅

**Type consistency:** `format_monitoring_call(template, callsign) -> str` and `should_emit_beacon(*, enabled, ncs_active, channel_clear, elapsed, interval) -> bool` are used with identical signatures in Task 4. `is_active()` defined in Task 3, called in Task 4. Globals `_last_beacon_time` / `_ncs_plugin` defined (Step 4), declared global (Step 6), reset (Step 7), read (Step 5). ✅
