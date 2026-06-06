# GMRS Tail-ID Feature Design

**Date:** 2026-06-06
**Status:** Approved

## Problem

The hub's TTS transmission pipeline only appends the station call sign to untargeted messages when the 15-minute FCC timer has elapsed. During active sessions, listeners on the channel may hear many transmissions with no audible identification.

## Goal

Append a short TTS call sign ID to the end of every untargeted hub-initiated TTS transmission, and keep the 15-minute background safety-net pump (already implemented) — both using a consistent short format.

## Decisions

| Decision | Choice | Reason |
|---|---|---|
| Trigger | Per-TX + 15-min pump | Both: tail on every message, pump as safety net for long pauses |
| Tail format | Short — call sign only | Unobtrusive; matches common radio practice ("...over. WQXX123.") |
| Targeted TX | Skip tail | Preface already contains both call signs; no double-ID |
| Pump format | Short — "This is WQXX123." | Consistent with tail; "This is" prefix added since it's a standalone transmission |
| "This is" button | Unchanged | Full NATO-phonetic format stays; user-initiated, different purpose |
| Configurability | Always on | No toggle needed |

## Architecture

Two files change. No frontend changes, no new WS messages, no config changes.

### `backend/fcc/id_rule.py`

**New:** `format_tail_id(my_call: str) -> str`
- Returns `f"{my_call}."` — the single source of truth for the short ID text.
- Pure function, no side effects.

**Modified:** `format_outgoing_message(text, target_call, target_name, my_call, my_name, now, service=SERVICE_GMRS)`
- Drops `last_id_time` and `id_interval_seconds` from signature (timer gate removed).
- Untargeted GMRS path: always appends `. {format_tail_id(my_call)}`.
- Targeted GMRS path: unchanged — preface already IDs the station.
- FRS path: unchanged — Part 95 Subpart B requires no ID.
- Returns `(spoken_text, now)` unconditionally for GMRS (so `_last_id_time` in server.py stays accurate for the pump).

**Unchanged:** `format_standalone_id()` — still used by "This is" button; full NATO-phonetic format retained.

### `backend/server.py`

- **`_tx_pump()` normal path:** Remove `last_id_time=_last_id_time` from `format_outgoing_message()` call (signature no longer accepts it).
- **`_id_rule_pump()`:**
  - Replace `format_standalone_id(...)` call with `f"This is {format_tail_id(_config.callsign)}"`.
  - Apply `spell_digits_in_callsigns()` before queuing — fixes pre-existing inconsistency where the pump bypassed digit-spacing that the "This is" button applies.
- Import `format_tail_id` alongside existing imports from `fcc.id_rule`.

## Data Flow

### Per-transmission tail ID

```
user sends tx_message (target="ALL")
  → _tx_pump() pulls from queue
  → expand_tty_abbreviations → mask_profanity
  → format_outgoing_message(text, "ALL", ..., my_call, my_name, now)
       untargeted GMRS:
         spoken_text = f"{text}. {format_tail_id(my_call)}"
                     = "Hello net, heading out now. WQXX123."
       returns (spoken_text, now)   ← _last_id_time updated
  → spell_digits_in_callsigns(spoken_text)
       = "Hello net, heading out now. W Q X X 1 2 3."
  → synthesize → PTT key → broadcast tx_audio
```

### 15-min safety-net pump

```
_id_rule_pump() wakes every 60s
  if _has_transmitted and elapsed(_last_id_time) > 15min:
    tail = format_tail_id(_config.callsign)         → "WQXX123."
    spoken = spell_digits_in_callsigns(f"This is {tail}")
           = "This is W Q X X 1 2 3."
    _last_id_time = now
    _has_transmitted = False
    → _tx_queue.put({"text": spoken, "_pre_formatted": True})
    → _tx_pump synthesizes + keys PTT
```

### "This is" button — unchanged

```
standalone_id WS message
  → format_standalone_id(my_call, my_name, my_loc, now)
       = "This is WQXX123, Whiskey Quebec X-ray X-ray one two three. John from Grand Rapids."
  → spell_digits_in_callsigns(...)
  → synthesize + PTT
```

## Error Handling

No new failure modes. `format_tail_id` is a pure string function. Existing `except Exception` handlers in `_tx_pump` and `_id_rule_pump` cover synthesis/PTT failures. If `_config.callsign` is blank, `format_tail_id` produces `"."` — same pre-existing risk as the full ID path; no new handling needed.

## Testing

**`backend/tests/unit/fcc/test_id_rule.py`**

- **New:** `test_format_tail_id` — verifies `"WQXX123."` output.
- **Updated:** `format_outgoing_message` tests — remove `last_id_time` / `id_interval_seconds` args; replace timer-gated assertions with "always appends tail" assertions; add case confirming targeted TX gets no tail.
- **Updated:** `format_standalone_id` tests — behavior unchanged, no test changes needed.

No new integration tests — pump and PTT paths are covered by existing tests; behavioral change is fully captured at the unit level.
