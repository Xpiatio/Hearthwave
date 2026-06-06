# GMRS Tail-ID Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Append a short TTS call sign tail to the end of every untargeted hub-initiated GMRS transmission, and switch the 15-min background pump to the same short format.

**Architecture:** Add `format_tail_id(my_call)` as the single short-ID primitive; rewrite `format_outgoing_message()` to always append it for untargeted GMRS (dropping the 15-min timer gate); update `_id_rule_pump()` in `server.py` to use the new helper and apply `spell_digits_in_callsigns` (fixing a pre-existing inconsistency). No frontend changes, no config changes, no new WS messages.

**Tech Stack:** Python 3.11, pytest, `backend/fcc/id_rule.py`, `backend/server.py`

---

## File Map

| File | Change |
|---|---|
| `backend/fcc/id_rule.py` | Add `format_tail_id()`; rewrite `format_outgoing_message()` (drop timer params, always append tail for untargeted GMRS) |
| `backend/tests/unit/fcc/test_id_rule.py` | Add `TestFormatTailId`; rewrite untargeted tests; update FRS and targeted call sites; delete the 15-min timer class |
| `backend/server.py` | Import `format_tail_id`; update `_tx_pump` call site (drop `last_id_time=`); update `_id_rule_pump` to use short format + `spell_digits_in_callsigns` |

---

## Task 1: Add `format_tail_id()` — new pure helper

**Files:**
- Modify: `backend/fcc/id_rule.py`
- Test: `backend/tests/unit/fcc/test_id_rule.py`

- [ ] **Step 1.1 — Write the failing test**

  Open `backend/tests/unit/fcc/test_id_rule.py`. Add this class **before** the existing `TestUntargetedNoIdYet` class:

  ```python
  class TestFormatTailId:
      def test_returns_call_with_period(self):
          from backend.fcc.id_rule import format_tail_id
          assert format_tail_id("WQXX123") == "WQXX123."

      def test_blank_call_returns_period_only(self):
          from backend.fcc.id_rule import format_tail_id
          assert format_tail_id("") == "."
  ```

- [ ] **Step 1.2 — Run test; confirm it fails**

  From the repo root (`/mnt/storage/Repos/Radio-TTY/.claude/worktrees/splendid-wibbling-sky`):

  ```bash
  python -m pytest backend/tests/unit/fcc/test_id_rule.py::TestFormatTailId -v
  ```

  Expected: `ImportError: cannot import name 'format_tail_id'`

- [ ] **Step 1.3 — Add `format_tail_id` to `id_rule.py`**

  Open `backend/fcc/id_rule.py`. Insert the new function **before** `format_outgoing_message`:

  ```python
  def format_tail_id(my_call: str) -> str:
      return f"{my_call}."
  ```

- [ ] **Step 1.4 — Run test; confirm it passes**

  ```bash
  python -m pytest backend/tests/unit/fcc/test_id_rule.py::TestFormatTailId -v
  ```

  Expected: 2 passed.

- [ ] **Step 1.5 — Commit**

  ```bash
  git add backend/fcc/id_rule.py backend/tests/unit/fcc/test_id_rule.py
  git commit -m "feat: add format_tail_id helper to fcc/id_rule"
  ```

---

## Task 2: Rewrite `format_outgoing_message()` — always-append, drop timer params

**Files:**
- Modify: `backend/fcc/id_rule.py`
- Test: `backend/tests/unit/fcc/test_id_rule.py`

- [ ] **Step 2.1 — Replace the test file's untargeted and FRS sections**

  The existing timer-gate tests (`TestUntargetedFifteenMinuteRule`) must be **deleted** — that logic is gone. The untargeted "no ID yet" tests and all other call sites need `last_id_time` removed and expected strings updated.

  Replace the **entire contents** of `backend/tests/unit/fcc/test_id_rule.py` with:

  ```python
  import datetime

  import pytest

  from backend.constants import SERVICE_FRS
  from backend.fcc.id_rule import (
      format_outgoing_message,
      format_standalone_id,
      format_tail_id,
  )


  @pytest.fixture
  def now():
      return datetime.datetime(2026, 5, 15, 12, 0, 0)


  @pytest.fixture
  def me():
      return {"call": "WSLZ233", "name": "Bob"}


  class TestFormatTailId:
      def test_returns_call_with_period(self):
          assert format_tail_id("WQXX123") == "WQXX123."

      def test_blank_call_returns_period_only(self):
          assert format_tail_id("") == "."


  class TestUntargetedAlwaysAppendsTail:
      def test_appends_tail_to_non_empty_text(self, now, me):
          text, new_last = format_outgoing_message(
              "Hello channel",
              target_call="ALL",
              target_name="Everyone",
              my_call=me["call"],
              my_name=me["name"],
              now=now,
          )
          assert text == "Hello channel. WSLZ233."
          assert new_last == now

      def test_target_empty_string_treated_as_untargeted(self, now, me):
          text, new_last = format_outgoing_message(
              "Open call",
              target_call="",
              target_name="",
              my_call=me["call"],
              my_name=me["name"],
              now=now,
          )
          assert text == "Open call. WSLZ233."
          assert new_last == now

      def test_all_lowercase_still_treated_as_untargeted(self, now, me):
          text, new_last = format_outgoing_message(
              "msg",
              target_call="all",
              target_name="Everyone",
              my_call=me["call"],
              my_name=me["name"],
              now=now,
          )
          assert text == "msg. WSLZ233."
          assert new_last == now

      def test_empty_body_returns_tail_only(self, now, me):
          text, new_last = format_outgoing_message(
              "",
              target_call="ALL",
              target_name="",
              my_call=me["call"],
              my_name=me["name"],
              now=now,
          )
          assert text == "WSLZ233."
          assert new_last == now

      def test_always_resets_timer(self, now, me):
          # No timer gate — every untargeted TX resets the ID clock.
          _, new_last = format_outgoing_message(
              "checking in",
              target_call="ALL",
              target_name="",
              my_call=me["call"],
              my_name=me["name"],
              now=now,
          )
          assert new_last == now


  class TestTargetedPreface:
      def test_with_target_name(self, now, me):
          text, new_last = format_outgoing_message(
              "you copy?",
              target_call="KAE1234",
              target_name="Alice",
              my_call=me["call"],
              my_name=me["name"],
              now=now,
          )
          assert text == "WSLZ233 Bob calling KAE1234 Alice. you copy?"
          assert new_last == now

      def test_without_target_name(self, now, me):
          text, new_last = format_outgoing_message(
              "you copy?",
              target_call="KAE1234",
              target_name="",
              my_call=me["call"],
              my_name=me["name"],
              now=now,
          )
          assert text == "WSLZ233 Bob calling KAE1234. you copy?"
          assert new_last == now

      def test_empty_body_text_yields_preface_only(self, now, me):
          text, _ = format_outgoing_message(
              "",
              target_call="KAE1234",
              target_name="Alice",
              my_call=me["call"],
              my_name=me["name"],
              now=now,
          )
          assert text == "WSLZ233 Bob calling KAE1234 Alice."

      def test_targeted_resets_timer(self, now, me):
          _, new_last = format_outgoing_message(
              "ping",
              target_call="KAE1234",
              target_name="Alice",
              my_call=me["call"],
              my_name=me["name"],
              now=now,
          )
          assert new_last == now

      def test_target_call_lowercase_still_treated_as_targeted(self, now, me):
          text, _ = format_outgoing_message(
              "msg",
              target_call="kae1234",
              target_name="alice",
              my_call=me["call"],
              my_name=me["name"],
              now=now,
          )
          assert text == "WSLZ233 Bob calling kae1234 alice. msg"

      def test_no_tail_appended_to_targeted_tx(self, now, me):
          # Preface already IDs the station — no tail should be added.
          text, _ = format_outgoing_message(
              "hello",
              target_call="KAE1234",
              target_name="Alice",
              my_call=me["call"],
              my_name=me["name"],
              now=now,
          )
          assert "WSLZ233." not in text.split(". ", 1)[-1]


  class TestFrsModeSkipsCallsignFraming:
      """FRS doesn't require station ID. Text passes through unchanged and
      format_outgoing_message returns None for new_last_id_time so server.py
      can preserve the existing GMRS timer (FRS mode must not reset it)."""

      def test_untargeted_text_passes_through_unchanged(self, now, me):
          text, new_last = format_outgoing_message(
              "Just a quick check-in",
              target_call="ALL",
              target_name="Everyone",
              my_call=me["call"],
              my_name=me["name"],
              now=now,
              service=SERVICE_FRS,
          )
          assert text == "Just a quick check-in"
          assert new_last is None

      def test_targeted_send_does_not_inject_preface(self, now, me):
          text, new_last = format_outgoing_message(
              "you copy?",
              target_call="WSAC909",
              target_name="Tim",
              my_call=me["call"],
              my_name=me["name"],
              now=now,
              service=SERVICE_FRS,
          )
          assert text == "you copy?"
          assert new_last is None

      def test_default_service_is_gmrs(self, now, me):
          text, _ = format_outgoing_message(
              "Hello channel",
              target_call="ALL",
              target_name="Everyone",
              my_call=me["call"],
              my_name=me["name"],
              now=now,
          )
          assert text == "Hello channel. WSLZ233."


  class TestStandaloneId:
      def test_with_location(self, now, me):
          text, new_last = format_standalone_id(
              my_call=me["call"],
              my_name=me["name"],
              my_location="Boston",
              now=now,
          )
          assert text == "This is WSLZ233, Whiskey Sierra Lima Zulu 2 3 3. Bob from Boston."
          assert new_last == now

      def test_without_location(self, now, me):
          text, new_last = format_standalone_id(
              my_call=me["call"],
              my_name=me["name"],
              my_location="",
              now=now,
          )
          assert text == "This is WSLZ233, Whiskey Sierra Lima Zulu 2 3 3. Bob."
          assert new_last == now

      def test_whitespace_only_location_treated_as_empty(self, now, me):
          text, _ = format_standalone_id(
              my_call=me["call"],
              my_name=me["name"],
              my_location="   ",
              now=now,
          )
          assert text == "This is WSLZ233, Whiskey Sierra Lima Zulu 2 3 3. Bob."

      def test_amateur_callsign_uses_correct_nato_form(self, now):
          text, _ = format_standalone_id(
              my_call="K1ABC",
              my_name="Carol",
              my_location="Denver",
              now=now,
          )
          assert text == "This is K1ABC, Kilo 1 Alpha Bravo Charlie. Carol from Denver."
  ```

- [ ] **Step 2.2 — Run tests; confirm they fail**

  ```bash
  python -m pytest backend/tests/unit/fcc/test_id_rule.py -v
  ```

  Expected: Most tests in `TestUntargetedAlwaysAppendsTail` fail with wrong text or `TypeError` (unexpected `last_id_time` kwarg still in old signature). `TestFormatTailId` should still pass.

- [ ] **Step 2.3 — Rewrite `format_outgoing_message()` in `backend/fcc/id_rule.py`**

  Replace the existing `format_outgoing_message` function (from `def format_outgoing_message(` through its final `return`) with:

  ```python
  def format_outgoing_message(
      text,
      target_call,
      target_name,
      my_call,
      my_name,
      now,
      service=SERVICE_GMRS,
  ):
      """Format an outgoing TX message per FCC Part 95 station-ID rules.

      Returns (spoken_text, new_last_id_time).

      Three cases:
        • Targeted GMRS: emit 'calling' preface containing both callsigns.
          Satisfies FCC ID; no tail appended.
        • Untargeted GMRS: emit body then append short tail ID (call sign only)
          on every transmission. new_last_id_time is always `now`.
        • FRS: speak body verbatim, no callsign framing. Returns None for
          new_last_id_time so the caller can preserve the GMRS timer.
      """
      if service == SERVICE_FRS:
          return text, None

      prefaced = bool(target_call and target_call.upper() != "ALL")

      if prefaced:
          clean_name = (target_name or "").strip()
          target_label = f"{target_call} {clean_name}" if clean_name else target_call
          if text:
              spoken_text = f"{my_call} {my_name} calling {target_label}. {text}"
          else:
              spoken_text = f"{my_call} {my_name} calling {target_label}."
          return spoken_text, now

      tail = format_tail_id(my_call)
      spoken_text = f"{text}. {tail}" if text else tail
      return spoken_text, now
  ```

  Also remove `ID_INTERVAL_SECONDS` from the function's default arguments and the import of `ID_INTERVAL_SECONDS` from `constants` if it was only used there. **Do not** remove the `ID_INTERVAL_SECONDS` module-level constant — `server.py` imports it for the pump.

- [ ] **Step 2.4 — Run tests; confirm they pass**

  ```bash
  python -m pytest backend/tests/unit/fcc/test_id_rule.py -v
  ```

  Expected: All tests pass (including the unchanged `TestStandaloneId` and `TestFormatTailId`).

- [ ] **Step 2.5 — Commit**

  ```bash
  git add backend/fcc/id_rule.py backend/tests/unit/fcc/test_id_rule.py
  git commit -m "feat: always append short tail ID on untargeted GMRS TX"
  ```

---

## Task 3: Update `server.py` — call sites and pump

**Files:**
- Modify: `backend/server.py:105-109` (import block)
- Modify: `backend/server.py:586-598` (`_tx_pump` normal path)
- Modify: `backend/server.py:882-889` (`_id_rule_pump` fire block)

- [ ] **Step 3.1 — Update the import block**

  In `backend/server.py`, find:

  ```python
  from backend.fcc.id_rule import (
      ID_INTERVAL_SECONDS,
      format_outgoing_message,
      format_standalone_id,
  )
  ```

  Replace with:

  ```python
  from backend.fcc.id_rule import (
      ID_INTERVAL_SECONDS,
      format_outgoing_message,
      format_standalone_id,
      format_tail_id,
  )
  ```

- [ ] **Step 3.2 — Update `_tx_pump` normal TX call site**

  In `backend/server.py`, find this block inside `_tx_pump` (approximately lines 582–598):

  ```python
                  processed = expand_tty_abbreviations(raw_text)
                  if payload.get("_filter_profanity", True):
                      processed = mask_profanity(processed)
                  text, _last_id_time = format_outgoing_message(
                      processed,
                      target_call=payload.get("target_call") or "ALL",
                      target_name=payload.get("target_name") or "",
                      my_call=payload.get("callsign") or _config.callsign,
                      my_name=payload.get("operator") or _config.name,
                      last_id_time=_last_id_time,
                      now=now,
                      service=normalize_service(_config.radio_service),
                  )
                  _has_transmitted = True
                  # Space-isolate digits in callsigns so TTS reads them individually.
                  text = spell_digits_in_callsigns(text)
                  chat_text = raw_text
  ```

  Replace with:

  ```python
                  processed = expand_tty_abbreviations(raw_text)
                  if payload.get("_filter_profanity", True):
                      processed = mask_profanity(processed)
                  service = normalize_service(_config.radio_service)
                  text, new_id_time = format_outgoing_message(
                      processed,
                      target_call=payload.get("target_call") or "ALL",
                      target_name=payload.get("target_name") or "",
                      my_call=payload.get("callsign") or _config.callsign,
                      my_name=payload.get("operator") or _config.name,
                      now=now,
                      service=service,
                  )
                  if new_id_time is not None:  # FRS returns None; preserve GMRS timer
                      _last_id_time = new_id_time
                  _has_transmitted = True
                  # Space-isolate digits in callsigns so TTS reads them individually.
                  text = spell_digits_in_callsigns(text)
                  chat_text = raw_text
  ```

- [ ] **Step 3.3 — Update `_id_rule_pump` to use short format**

  In `backend/server.py`, find this block inside `_id_rule_pump` (approximately lines 881–889):

  ```python
              if elapsed > ID_INTERVAL_SECONDS:
                  spoken, new_ts = format_standalone_id(
                      _config.callsign, _config.name, _config.location, now
                  )
                  _last_id_time = new_ts
                  _has_transmitted = False
                  _log.info("FCC ID rule: broadcasting station identification.")
                  await _manager.broadcast({"type": "tx_status", "status": "transmitting"})
                  await _tx_queue.put({"text": spoken, "_pre_formatted": True})
  ```

  Replace with:

  ```python
              if elapsed > ID_INTERVAL_SECONDS:
                  tail = format_tail_id(_config.callsign)
                  spoken = spell_digits_in_callsigns(f"This is {tail}")
                  _last_id_time = now
                  _has_transmitted = False
                  _log.info("FCC ID rule: broadcasting station identification.")
                  await _manager.broadcast({"type": "tx_status", "status": "transmitting"})
                  await _tx_queue.put({"text": spoken, "_pre_formatted": True})
  ```

- [ ] **Step 3.4 — Run the full unit test suite**

  ```bash
  python -m pytest backend/tests/unit/ -q
  ```

  Expected: All tests pass. No new failures. (The 2 pre-existing failures in `test_auto_add.py` are expected — they need `pytest-asyncio` which is not installed.)

- [ ] **Step 3.5 — Run the integration tests**

  ```bash
  python -m pytest backend/tests/integration/ -q
  ```

  Expected: All integration tests pass.

- [ ] **Step 3.6 — Commit**

  ```bash
  git add backend/server.py
  git commit -m "feat: wire tail-ID into tx_pump and id_rule_pump"
  ```

---

## Done

After Task 3:
- Every untargeted hub-initiated TTS transmission ends with `"<CALL>."` spelled digit-by-digit via TTS (e.g. `"W Q X X 1 2 3."`).
- Targeted transmissions are unchanged — the preface already IDs the station.
- The 15-min background pump fires `"This is W Q X X 1 2 3."` when there has been activity but no transmission for 15 minutes.
- The "This is" button (standalone_id) remains full NATO-phonetic — unchanged.
- FRS mode is unchanged: no ID injected, GMRS timer preserved in `server.py`.
