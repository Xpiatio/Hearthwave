# Monitoring Beacon — Design Spec

**Date:** 2026-06-19
**Status:** Approved for planning
**Author:** Benjamin (with Claude)

## Summary

Add an opt-in, periodic "presence" announcement that transmits a configurable
phrase — default `"{callsign} Hearthwave base, monitoring."` — over the air on a
fixed timer. It is distinct from the existing FCC station-ID transmitter and is
coordinated with it so the two do not produce redundant back-to-back identifications.

The feature is **disabled by default**.

## Motivation

The marketing site (`docs/index.html`) advertises an automatic
`"{callsign} Hearthwave base, monitoring"` transmission sent "every 15 min during
activity." No such transmission exists in the code. The only automated callsign
transmission is the FCC ID pump, which says `"This is {callsign} {name}."`. This
spec adds the advertised monitoring beacon as a real feature.

## Existing periodic transmitters (context)

Audited before designing, to avoid stacking transmitters and flooding the channel:

| Path | When active | Interval | Transmits | Guard |
|---|---|---|---|---|
| FCC ID pump (`server.py` `_id_rule_pump`) | always running | 15 min (`ID_INTERVAL_SECONDS`) | `"This is {callsign} {name}."` | Only fires if `_has_transmitted` since last ID; silent on dead air |
| NCS announcement (`plugins/ncs.py` `_announcement_loop`) | only when NCS mode active | 600s default (`ncs_announcement_interval`) | `"Net Control Station, {callsign}…"` | Only if `_channel_clear()` |
| SKYWARN auto-announce (`plugins/ncs.py`) | severe/extreme alert | event-driven | `"SKYWARN ALERT…"` | `_channel_clear()` |

The monitoring beacon is a **fourth** periodic transmitter. The design below keeps it
from colliding with the others.

## Design decisions (from brainstorming)

1. **Separate from the FCC ID.** The existing `_id_rule_pump` is left untouched. The
   beacon is its own transmitter on its own timer.
2. **Fixed-interval trigger, channel-clear gated.** The beacon fires every
   `monitoring_beacon_interval` seconds provided the channel is clear at that instant.
   It does *not* use idle-reset logic — a fixed cadence is intended.
3. **Suppressed during NCS mode.** When NCS/net-control mode is active, the beacon is
   skipped (the NCS announcement already covers presence).
4. **Beacon doubles as an FCC ID.** Because the transmitted phrase contains the
   callsign, it legally satisfies the FCC 15-minute ID. When the beacon fires it resets
   the FCC ID timer so `_id_rule_pump` will not separately identify right after.
5. **Opt-in.** Config flag, default `false`. Interval and phrase are configurable.

## Components

### New module: `backend/beacon/monitoring.py`

Single-purpose, isolated like `backend/fcc/id_rule.py`. Pure function, no I/O:

```python
def format_monitoring_call(template: str, callsign: str) -> str:
    """Build the spoken monitoring-beacon phrase.

    Substitutes {callsign} into the template, then runs the result through
    spell_digits_in_callsigns so digits in the callsign are spoken clearly
    (same treatment the FCC ID pump applies)."""
```

- `{callsign}` is the only supported placeholder. Other `{...}` tokens in a
  user-supplied template are left untouched (use `str.replace`, not `str.format`, to
  avoid `KeyError`/`IndexError` on stray braces).
- Reuses the existing digit-spelling helper
  (`spell_digits_in_callsigns`, defined in `backend/text/callsigns.py:188` — the same one
  `_id_rule_pump` uses at `server.py:1202`).

**Interface:** input `(template, callsign)` → output spoken string. Depends only on the
digit-spelling helper. Testable in isolation with no mocks.

### New pump: `server.py` `_monitoring_beacon_pump()`

Async task, added to the `_background_tasks` set next to `_id_rule_pump`
(`server.py` ~line 1410). Structure mirrors `_id_rule_pump`:

```
async def _monitoring_beacon_pump() -> None:
    global _last_beacon_time, _last_id_time, _has_transmitted
    while True:
        try:
            await asyncio.sleep(60)
            if _config is None or not _config.monitoring_beacon_enabled:
                continue
            if _ncs_plugin is not None and _ncs_plugin.is_active():
                continue                      # suppress during NCS
            if not _channel_clear:
                continue                      # don't key over traffic
            now = datetime.datetime.now(datetime.timezone.utc)
            elapsed = (now - _last_beacon_time).total_seconds() if _last_beacon_time else float("inf")
            if elapsed >= _config.monitoring_beacon_interval:
                spoken = format_monitoring_call(_config.monitoring_beacon_text, _config.callsign)
                _last_beacon_time = now
                _last_id_time = now           # beacon satisfies the FCC ID
                _has_transmitted = False
                _log.info("Monitoring beacon: broadcasting presence announcement.")
                await _manager.broadcast({"type": "tx_status", "status": "transmitting"})
                await _tx_queue.put({"text": spoken, "_pre_formatted": True})
        except asyncio.CancelledError:
            break
        except Exception as exc:
            _log.error("_monitoring_beacon_pump error: %s", exc)
```

Notes:
- Poll cadence is 60s (matches `_id_rule_pump`); the effective interval is governed by
  the `elapsed >=` check, so the real interval is accurate to within ~60s.
- `_pre_formatted: True` skips TX text reprocessing (same convention as the FCC pump and
  NCS announcement).
- Reads the module global `_channel_clear` directly (already used this way at
  `server.py:1134`).

### NCS-active detection

- Add `def is_active(self) -> bool: return self._active` to `NCSPlugin`
  (`backend/plugins/ncs.py`). Public accessor instead of reaching into `_active`.
- In `server.py`, capture the constructed plugin into a module global so the pump can
  reach it. Currently (`server.py:1387-1388`):
  ```python
  from backend.plugins.ncs import NCSPlugin
  plugin_registry.register(NCSPlugin(...))
  ```
  Change to:
  ```python
  global _ncs_plugin
  _ncs_plugin = NCSPlugin(...)
  plugin_registry.register(_ncs_plugin)
  ```
  Declare `_ncs_plugin: NCSPlugin | None = None` near the other module globals.

### Timer state

- Add module global `_last_beacon_time: datetime.datetime | None = None` next to
  `_last_id_time`/`_has_transmitted` (`server.py:199-200`).
- Reset it to `None` in the same place those are reset on radio (re)start
  (`server.py:1347-1349`).

### Config: `backend/config.py`

Three new properties, following the existing `ncs_*` property pattern:

```python
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
    """Beacon phrase template; {callsign} is substituted."""
    return self.get("monitoring_beacon_text", "{callsign} Hearthwave base, monitoring.")
```

Add the three keys to the example config (`data/config.json` and any
`config.example.json`) with their defaults, so operators can discover them.

## Data flow

```
_monitoring_beacon_pump (every 60s)
  └─ gates: enabled? · NCS inactive? · channel clear? · interval elapsed?
       └─ format_monitoring_call(template, callsign)   [beacon/monitoring.py]
            └─ _tx_queue.put({"text": ..., "_pre_formatted": True})
                 └─ existing _tx_pump → TTS synth → PTT key → audio out
       └─ side effect: reset _last_id_time + _has_transmitted (FCC ID satisfied)
```

## Error handling

- All exceptions inside the loop are caught and logged; the loop continues (same as
  `_id_rule_pump`). A formatting or TTS failure never kills the pump.
- If `_config` is `None` (radio not yet up) the tick is skipped.
- Unknown placeholders in a custom template are passed through literally rather than
  raising.

## Testing

**Unit — `format_monitoring_call`** (`backend/tests/unit/beacon/test_monitoring.py`):
- Default template + simple callsign → expected phrase.
- Callsign containing digits → digits spelled out via `spell_digits_in_callsigns`.
- Custom template with `{callsign}`.
- Template with a stray non-callsign brace token → left untouched, no exception.

**Pump — `_monitoring_beacon_pump`** (async, patching `asyncio.sleep` the way
`backend/tests/unit/plugins/test_ncs.py` patches it):
- Fires when enabled + interval elapsed + channel clear → item on `_tx_queue` whose
  text matches the formatted phrase.
- Skips when `monitoring_beacon_enabled` is false → queue empty.
- Skips when `_ncs_plugin.is_active()` is true → queue empty.
- Skips when `_channel_clear` is false → queue empty.
- On fire, resets `_last_id_time` (to `now`) and `_has_transmitted` (to `False`).

## Out of scope (YAGNI)

- No frontend UI toggle — configuration is file-based for this iteration.
- No per-user preference — the beacon is a station-wide setting.
- No idle-reset trigger — fixed cadence was chosen deliberately.
- No change to the marketing site copy; updating `docs/index.html` to match is a
  separate follow-up once this ships.

## Affected files

- `backend/beacon/monitoring.py` (new) + `backend/beacon/__init__.py` (new)
- `backend/plugins/ncs.py` (add `is_active`)
- `backend/config.py` (3 new properties)
- `backend/server.py` (new global `_last_beacon_time`, `_ncs_plugin`; new pump; task
  registration; reset on restart; import of `format_monitoring_call`)
- `data/config.json` (+ example) — new keys with defaults
- `backend/tests/unit/beacon/test_monitoring.py` (new)
- pump tests (location alongside existing server/pump tests)
