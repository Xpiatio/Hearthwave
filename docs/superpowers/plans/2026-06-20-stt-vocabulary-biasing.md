# STT Vocabulary Biasing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bias both Whisper STT engines toward curated radio vocabulary (CB, HAM, GMRS, MURS, NATO) plus known contact callsigns, and keep that bias current automatically (on contact/phrase change) and via a manual rescan button.

**Architecture:** A new pure module `backend/stt/vocab.py` holds the curated word lists and an `assemble_phrases()` function that orders terms lowest-priority-first (curated → saved phrases → callsigns) so Whisper's tail-keeping `initial_prompt` retains the high-priority items. `server.py` owns orchestration: it assembles the list from contacts + config and pushes it to the live worker. The transcriber frames + front-trims to a token budget. Frontend gains a rescan button and a success toast.

**Tech Stack:** Python 3.12 (faster-whisper, pytest), React + TypeScript (MUI, Vitest).

## Global Constraints

- Whisper `initial_prompt` keeps only ~224 tokens (the tail). Order phrases lowest-priority-first; callsigns last.
- Prompt char budget: `_MAX_PROMPT_CHARS = 700` (≈200 tokens, headroom under 224).
- Priority on overflow: callsigns + saved phrases win; curated vocab is trimmed.
- `stt_vocab_max_callsigns` default `100`; on overflow keep the last N in contacts-file order (newest), `log()` the dropped count.
- Mechanism stays `initial_prompt` (not `hotwords`).
- No Co-Authored-By trailers / PR footers (project convention).
- Existing callsign-field tuple: `_CALLSIGN_FIELDS = ("callsign", "gmrs_callsign", "ham_callsign")`; skip `"ALL"` and blanks; normalize via `normalize_callsign()` (strip+upper).

---

### Task 1: `vocab.py` — curated sets + `assemble_phrases()`

**Files:**
- Create: `backend/stt/vocab.py`
- Test: `backend/tests/unit/stt/test_vocab.py`

**Interfaces:**
- Produces: `assemble_phrases(callsigns: list[str], saved_phrases: list[str], *, max_callsigns: int) -> list[str]` and module constant `CURATED: tuple[str, ...]`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/stt/test_vocab.py
from backend.stt import vocab


def test_curated_sets_present():
    # NATO alphabet fully represented; a few band terms present.
    assert "Alfa" in vocab.CURATED and "Zulu" in vocab.CURATED
    assert "breaker" in vocab.CURATED      # CB
    assert "QSL" in vocab.CURATED          # HAM
    assert "repeater" in vocab.CURATED     # GMRS
    assert "MURS" in vocab.CURATED         # MURS


def test_callsigns_come_last_so_they_survive_tail_trim():
    out = vocab.assemble_phrases(["KE8AAA", "KE8BBB"], ["my custom"], max_callsigns=100)
    assert out[-2:] == ["KE8AAA", "KE8BBB"]
    assert out.index("my custom") < out.index("KE8AAA")
    assert out.index("Alfa") < out.index("my custom")   # curated ranks below saved


def test_dedup_keeps_highest_priority_occurrence():
    # "QSL" is curated; if it's also a saved phrase it should appear once,
    # at the later (higher-priority) position — after the curated block.
    out = vocab.assemble_phrases([], ["QSL"], max_callsigns=100)
    assert out.count("QSL") == 1
    # the surviving QSL is the saved-phrase one (after the curated block start)
    assert out.index("QSL") > out.index("Alfa")


def test_callsign_cap_keeps_newest_and_logs(caplog):
    import logging
    calls = [f"K{i:04d}" for i in range(105)]
    with caplog.at_level(logging.INFO):
        out = vocab.assemble_phrases(calls, [], max_callsigns=100)
    tail = out[-100:]
    assert tail == calls[-100:]          # newest (file-order tail) kept
    assert "K0000" not in out            # oldest dropped
    assert any("dropped 5" in r.message for r in caplog.records)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/unit/stt/test_vocab.py -v`
Expected: FAIL — `ModuleNotFoundError: backend.stt.vocab`.

- [ ] **Step 3: Write the implementation**

```python
# backend/stt/vocab.py
"""Curated radio-domain vocabulary and the phrase-assembly logic used to bias
both Whisper engines via initial_prompt.

Pure module (no I/O). Terms are stored as ordered tuples for deterministic
output and so the tail-trim in WhisperTranscriber._build_prompt drops the
lowest-priority terms first.
"""
from __future__ import annotations

import logging

_log = logging.getLogger(__name__)

NATO: tuple[str, ...] = (
    "Alfa", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf", "Hotel",
    "India", "Juliett", "Kilo", "Lima", "Mike", "November", "Oscar", "Papa",
    "Quebec", "Romeo", "Sierra", "Tango", "Uniform", "Victor", "Whiskey",
    "X-ray", "Yankee", "Zulu",
)

CB: tuple[str, ...] = (
    "breaker", "breaker breaker", "what's your twenty", "smokey", "bear",
    "handle", "good buddy", "back door", "front door", "ratchet jaw", "ears",
    "negatory", "come back", "wall to wall", "ten codes", "kojak with a kodak",
)

HAM: tuple[str, ...] = (
    "CQ", "QSL", "QSY", "QRZ", "QRM", "QRN", "QTH", "QSO", "QRP", "QRT", "QSB",
    "QRO", "roger", "affirmative", "say again", "monitoring", "seventy three",
)

GMRS: tuple[str, ...] = (
    "GMRS", "repeater", "simplex", "duplex", "privacy code", "PL tone",
    "kerchunk", "channel", "split tone", "travel tone",
)

MURS: tuple[str, ...] = (
    "MURS", "blue dot", "green dot", "multi use radio service",
)

# Priority order among curated sets does not matter (all rank below saved
# phrases and callsigns), but the concatenation is fixed for determinism.
CURATED: tuple[str, ...] = NATO + CB + HAM + GMRS + MURS


def assemble_phrases(callsigns, saved_phrases, *, max_callsigns) -> list[str]:
    """Build the ordered bias list, lowest priority first.

    Order: CURATED -> saved_phrases -> callsigns (callsigns last so they sit in
    the surviving tail of Whisper's initial_prompt). Callsigns over
    ``max_callsigns`` are trimmed from the FRONT (oldest), keeping the newest;
    the dropped count is logged. Case-insensitive dedup keeps the last
    (highest-priority) occurrence of any repeated term.
    """
    callsigns = list(callsigns or [])
    if len(callsigns) > max_callsigns:
        dropped = len(callsigns) - max_callsigns
        callsigns = callsigns[-max_callsigns:]
        _log.info("STT vocab: callsign list over cap, dropped %d oldest", dropped)

    ordered = list(CURATED) + list(saved_phrases or []) + callsigns

    seen: set[str] = set()
    deduped: list[str] = []
    for term in reversed(ordered):
        cleaned = (term or "").strip()
        key = cleaned.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
    deduped.reverse()
    return deduped
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/unit/stt/test_vocab.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/stt/vocab.py backend/tests/unit/stt/test_vocab.py
git commit -m "feat(stt): curated radio vocabulary + assemble_phrases"
```

---

### Task 2: `ordered_callsigns()` helper in contacts.py

**Files:**
- Modify: `backend/persistence/contacts.py` (add after `known_callsigns`, ~line 66)
- Test: `backend/tests/unit/persistence/test_contacts.py`

**Interfaces:**
- Produces: `ordered_callsigns(contacts: list[ContactDict]) -> list[str]` — file-order, normalized, deduped (first appearance), skips `"ALL"`/blanks.

- [ ] **Step 1: Write the failing test** (append to `test_contacts.py`)

```python
def test_ordered_callsigns_preserves_file_order_and_dedups():
    from backend.persistence.contacts import ordered_callsigns
    contacts = [
        {"callsign": "ke8aaa", "gmrs_callsign": "WRAA111"},
        {"callsign": "ALL"},                       # skipped
        {"callsign": "KE8BBB", "ham_callsign": ""},  # blank skipped
        {"callsign": "KE8AAA"},                    # dup of first, skipped
    ]
    assert ordered_callsigns(contacts) == ["KE8AAA", "WRAA111", "KE8BBB"]


def test_ordered_callsigns_empty():
    from backend.persistence.contacts import ordered_callsigns
    assert ordered_callsigns([]) == []
    assert ordered_callsigns(None) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/unit/persistence/test_contacts.py -k ordered_callsigns -v`
Expected: FAIL — `ImportError: cannot import name 'ordered_callsigns'`.

- [ ] **Step 3: Write the implementation** (insert after `known_callsigns`, before `index_contacts_by_callsign`)

```python
def ordered_callsigns(contacts: list[ContactDict]) -> list[str]:
    """Return UPPERCASED callsigns in contacts-file insertion order, pulled from
    every populated callsign field, deduped preserving first appearance. Skips
    the 'ALL' open-call shortcut and blanks. Order matters here (unlike
    known_callsigns, which returns an unordered set) so the STT vocabulary cap
    can keep the most-recently-added callsigns."""
    seen: set[str] = set()
    out: list[str] = []
    for c in contacts or []:
        for field in _CALLSIGN_FIELDS:
            cs = normalize_callsign(c.get(field, ""))
            if not cs or cs == "ALL" or cs in seen:
                continue
            seen.add(cs)
            out.append(cs)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/unit/persistence/test_contacts.py -k ordered_callsigns -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/persistence/contacts.py backend/tests/unit/persistence/test_contacts.py
git commit -m "feat(contacts): ordered_callsigns helper for STT vocab cap"
```

---

### Task 3: Budget-aware prompt framing in transcriber.py

**Files:**
- Modify: `backend/stt/transcriber.py:50-55` (`_build_prompt`)
- Test: `backend/tests/unit/stt/test_transcriber.py`

**Interfaces:**
- Consumes: ordered phrase list from `vocab.assemble_phrases` (Task 1).
- Produces: `_build_prompt(phrases) -> str` framed as `"GMRS radio. Phrases: …."`, front-trimmed to `_MAX_PROMPT_CHARS`.

- [ ] **Step 1: Write the failing test** (append to `test_transcriber.py`)

```python
def test_build_prompt_empty_returns_base():
    from backend.stt.transcriber import WhisperTranscriber
    assert WhisperTranscriber._build_prompt([]) == "GMRS radio."


def test_build_prompt_frames_phrases():
    from backend.stt.transcriber import WhisperTranscriber
    assert WhisperTranscriber._build_prompt(["over", "KE8AAA"]) == \
        "GMRS radio. Phrases: over, KE8AAA."


def test_build_prompt_front_trims_keeping_tail():
    from backend.stt.transcriber import WhisperTranscriber
    # Many long low-priority terms followed by a high-priority callsign tail.
    phrases = [f"longgenericterm{i:03d}" for i in range(100)] + ["KE8ZZZ"]
    prompt = WhisperTranscriber._build_prompt(phrases)
    assert len(prompt) <= WhisperTranscriber._MAX_PROMPT_CHARS
    assert prompt.endswith("KE8ZZZ.")          # tail survived
    assert "longgenericterm000" not in prompt   # front dropped
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/unit/stt/test_transcriber.py -k build_prompt -v`
Expected: FAIL — `_MAX_PROMPT_CHARS` missing / front-trim absent.

- [ ] **Step 3: Write the implementation** (replace `_build_prompt`, add the constant beside the other thresholds ~line 48)

```python
    # Whisper keeps only ~224 tokens of initial_prompt. ~700 chars ≈ ~200 tokens
    # leaves headroom. Callers order phrases lowest-priority-first, so trimming
    # from the front drops generic vocab while callsigns/custom phrases survive.
    _MAX_PROMPT_CHARS = 700

    @staticmethod
    def _build_prompt(phrases) -> str:
        base = "GMRS radio."
        phrases = [p for p in (phrases or []) if p]
        if not phrases:
            return base
        while phrases:
            prompt = f"{base} Phrases: {', '.join(phrases)}."
            if len(prompt) <= WhisperTranscriber._MAX_PROMPT_CHARS:
                return prompt
            phrases.pop(0)
        return base
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/unit/stt/test_transcriber.py -k build_prompt -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/stt/transcriber.py backend/tests/unit/stt/test_transcriber.py
git commit -m "feat(stt): budget-aware prompt framing with front-trim"
```

---

### Task 4: Config — `stt_vocab_max_callsigns` + empty saved_phrases default

**Files:**
- Modify: `backend/config.py:163-168`
- Test: `backend/tests/unit/test_config.py` (append — file exists; imports `ServerConfig`)

**Interfaces:**
- Produces: `ServerConfig.saved_phrases` (default `[]`), `ServerConfig.stt_vocab_max_callsigns` (default `100`). `ServerConfig` is a `dict` subclass; `ServerConfig()` (empty) yields defaults — matches the existing default-checking tests in this file.

- [ ] **Step 1: Write the failing test** (append to `test_config.py`)

```python
def test_saved_phrases_default_empty():
    assert ServerConfig().saved_phrases == []


def test_stt_vocab_max_callsigns_default():
    assert ServerConfig().stt_vocab_max_callsigns == 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/unit/test_config.py -k "saved_phrases_default_empty or stt_vocab_max_callsigns" -v`
Expected: FAIL — default still the old phrase list / property missing.

- [ ] **Step 3: Write the implementation**

Replace the `saved_phrases` property body (165-168):

```python
    @property
    def saved_phrases(self) -> list:
        # Default empty: curated radio vocabulary now lives in backend/stt/vocab.py
        # and is assembled server-side. saved_phrases holds only the operator's
        # custom additions.
        return list(self.get("saved_phrases", []))

    @property
    def stt_vocab_max_callsigns(self) -> int:
        return int(self.get("stt_vocab_max_callsigns", 100))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/unit/test_config.py -k "saved_phrases_default_empty or stt_vocab_max_callsigns" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/config.py backend/tests/unit/test_config.py
git commit -m "feat(config): empty saved_phrases default + stt_vocab_max_callsigns"
```

---

### Task 5: server.py orchestration + `rescan_vocabulary` handler

**Files:**
- Modify: `backend/server.py` — import (line 128), new helpers, `_make_stt_worker:457`, `set_server_config:1657-1658`, contact handlers (1866, 1885, ~2113, 2145), new WS message branch (~after 2147).
- Test: `backend/tests/unit/test_server_vocab.py` (create)

**Interfaces:**
- Consumes: `vocab.assemble_phrases` (Task 1), `ordered_callsigns` (Task 2), `Config.stt_vocab_max_callsigns` (Task 4), `STTWorker.update_phrases` (existing).
- Produces: `_assemble_stt_phrases() -> list[str]`, `_rebuild_stt_vocabulary() -> int`, WS message `{"type": "vocabulary_rescanned", "term_count": int, "callsign_count": int}`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_server_vocab.py
import backend.server as server


class _FakeStore:
    def __init__(self, contacts): self._c = contacts
    def get_all(self): return self._c


class _FakeWorker:
    def __init__(self): self.last = None
    def update_phrases(self, phrases): self.last = phrases


class _FakeConfig:
    saved_phrases = ["my custom phrase"]
    stt_vocab_max_callsigns = 100


def test_assemble_stt_phrases_orders_callsigns_last(monkeypatch):
    monkeypatch.setattr(server, "_contacts_store", _FakeStore([{"callsign": "KE8AAA"}]))
    monkeypatch.setattr(server, "_config", _FakeConfig())
    out = server._assemble_stt_phrases()
    assert out[-1] == "KE8AAA"
    assert "my custom phrase" in out
    assert out.index("my custom phrase") < out.index("KE8AAA")


def test_rebuild_pushes_to_worker_and_counts(monkeypatch):
    worker = _FakeWorker()
    monkeypatch.setattr(server, "_contacts_store", _FakeStore([{"callsign": "KE8AAA"}]))
    monkeypatch.setattr(server, "_config", _FakeConfig())
    monkeypatch.setattr(server, "_stt_worker", worker)
    count = server._rebuild_stt_vocabulary()
    assert worker.last[-1] == "KE8AAA"
    assert count == len(worker.last)


def test_rebuild_no_worker_is_noop(monkeypatch):
    monkeypatch.setattr(server, "_stt_worker", None)
    assert server._rebuild_stt_vocabulary() == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/unit/test_server_vocab.py -v`
Expected: FAIL — `_assemble_stt_phrases` / `_rebuild_stt_vocabulary` not defined.

- [ ] **Step 3: Add the import** — extend the contacts import block (line ~128, currently importing `known_callsigns`):

```python
    known_callsigns,
    ordered_callsigns,
```

- [ ] **Step 4: Add the helpers** — place them just above `_make_stt_worker` (~line 444):

```python
def _assemble_stt_phrases() -> "list[str]":
    """Assemble the full STT bias list (curated vocab + saved phrases + contact
    callsigns) ordered lowest-priority-first. Shared by worker construction and
    live rebuilds."""
    from backend.stt import vocab
    contacts = _contacts_store.get_all() if _contacts_store else []
    callsigns = ordered_callsigns(contacts)
    phrases = _config.saved_phrases if _config else []
    max_cs = _config.stt_vocab_max_callsigns if _config else 100
    return vocab.assemble_phrases(callsigns, phrases, max_callsigns=max_cs)


def _rebuild_stt_vocabulary() -> int:
    """Push a freshly assembled bias list to the live worker. Returns the term
    count (0 if no worker yet)."""
    if _stt_worker is None:
        return 0
    phrases = _assemble_stt_phrases()
    _stt_worker.update_phrases(phrases)
    return len(phrases)
```

- [ ] **Step 5: Wire worker construction** — `_make_stt_worker`, line 457, change:

```python
        saved_phrases=_assemble_stt_phrases(),
```

(This covers startup and all three restart paths, since they all call `_make_stt_worker()`.)

- [ ] **Step 6: Wire `set_server_config`** — replace lines 1657-1658:

```python
            if _stt_worker is not None:
                _rebuild_stt_vocabulary()
```

- [ ] **Step 7: Wire contact mutations** — after each `await _manager.broadcast({"type": "contacts", ...})`, add `_rebuild_stt_vocabulary()`:
  - `add_contact` (after line 1866)
  - `update_contact` (after line 1885)
  - the FCC verify-all batch (after its `broadcast` near line 2113)
  - `delete_contact` (after line 2145)

Example (add_contact):

```python
                    updated = _contacts_store.add_contact(contact)
                    await _manager.broadcast({"type": "contacts", "contacts": updated})
                    _rebuild_stt_vocabulary()
```

- [ ] **Step 8: Add the `rescan_vocabulary` handler** — insert a new branch after the `delete_contact` block (~line 2147):

```python
            elif msg_type == "rescan_vocabulary":
                count = _rebuild_stt_vocabulary()
                contacts = _contacts_store.get_all() if _contacts_store else []
                max_cs = _config.stt_vocab_max_callsigns if _config else 100
                cs_count = min(len(ordered_callsigns(contacts)), max_cs)
                await _manager.send_to(ws, {
                    "type": "vocabulary_rescanned",
                    "term_count": count,
                    "callsign_count": cs_count,
                })
```

- [ ] **Step 9: Run tests**

Run: `python -m pytest backend/tests/unit/test_server_vocab.py -v`
Expected: PASS (3 tests).

- [ ] **Step 10: Commit**

```bash
git add backend/server.py backend/tests/unit/test_server_vocab.py
git commit -m "feat(server): assemble + auto/manual rescan of STT vocabulary"
```

---

### Task 6: Frontend — rescan button + success toast

**Files:**
- Modify: `frontend/src/components/ServerConfigPanel/ServerConfigPanel.tsx` (Props + button near saved-phrases section ~305-345)
- Modify: `frontend/src/components/SettingsDialog/SettingsDialog.tsx` (thread `onRescanVocabulary` to the server-config panel, ~line 91)
- Modify: `frontend/src/App.tsx` (send handler, inbound `vocabulary_rescanned` case, `vocabSnack` state, pass to apps, wire prop)
- Modify: `frontend/src/components/DesktopApp/DesktopApp.tsx` and `frontend/src/components/MobileApp/MobileApp.tsx` (vocabSnack prop + Snackbar block mirroring `journalSavedSnack`)
- Test: `frontend/src/components/ServerConfigPanel/__tests__/ServerConfigPanel.test.tsx`

**Interfaces:**
- Consumes: WS message `vocabulary_rescanned` (Task 5).
- Produces: `onRescanVocabulary?: () => void` prop on `ServerConfigPanel` and `SettingsDialog`; sends `{ type: 'rescan_vocabulary' }`.

- [ ] **Step 1: Write the failing test** (append to `ServerConfigPanel.test.tsx`)

```tsx
it('calls onRescanVocabulary when the rescan button is clicked', () => {
  const onRescanVocabulary = vi.fn();
  render(
    <ServerConfigPanel {...makeDefaultProps()} onRescanVocabulary={onRescanVocabulary} />,
  );
  fireEvent.click(screen.getByRole('button', { name: /rescan vocabulary/i }));
  expect(onRescanVocabulary).toHaveBeenCalledTimes(1);
});
```

> Uses the file's existing `makeDefaultProps()` helper (returns `{ open, onClose, config, onSave }` from `makeConfig()`). `render`, `screen`, `fireEvent`, and `vi` are already imported in this test file.

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `npx vitest run src/components/ServerConfigPanel/__tests__/ServerConfigPanel.test.tsx`
Expected: FAIL — no button matching /rescan vocabulary/i.

- [ ] **Step 3: Add the prop** — in `ServerConfigPanel.tsx` `Props` (line 86) and the destructure (line 96):

```tsx
  onRescanVocabulary?: () => void;
```
```tsx
export function ServerConfigPanel({ open, onClose, config, onSave, onRescanVocabulary, embedded = false }: Props) {
```

- [ ] **Step 4: Render the button** — directly beneath the saved-phrases block (after the phrase list / add-phrase row, ~line 345), only when the handler is provided:

```tsx
{onRescanVocabulary && (
  <Button
    variant="outlined"
    size="small"
    onClick={onRescanVocabulary}
    sx={{ mt: 1 }}
  >
    Rescan vocabulary
  </Button>
)}
```

> `Button` is from MUI — confirm it is already imported at the top of the file (it is used for other actions); if not, add it to the existing `@mui/material` import.

- [ ] **Step 5: Thread through SettingsDialog** — add `onRescanVocabulary?: () => void` to its Props and pass it to the server `ServerConfigPanel` instance (line 91, alongside `onSave={onServerConfigSave}`):

```tsx
            onRescanVocabulary={onRescanVocabulary}
```

- [ ] **Step 6: Wire App.tsx** —
  - Add state beside the other snacks (line ~195): `const [vocabSnack, setVocabSnack] = useState<string | null>(null);`
  - Add a send handler beside `handleServerConfigSave` (line ~801):
    ```tsx
    function handleRescanVocabulary() {
      send({ type: 'rescan_vocabulary' });
    }
    ```
  - Add an inbound case in the `switch (msg.type)` (after `verify_all_complete`, line ~632):
    ```tsx
      case 'vocabulary_rescanned':
        setVocabSnack(`Biasing ${msg.term_count} terms (${msg.callsign_count} callsigns).`);
        break;
    ```
  - Add a close handler beside `handleCloseErrorSnack` (line ~978): `function handleCloseVocabSnack() { setVocabSnack(null); }`
  - Pass `onRescanVocabulary={handleRescanVocabulary}` into `SettingsDialog` (find where `onServerConfigSave={handleServerConfigSave}` is passed, line ~1077) and pass `vocabSnack` + `onCloseVocabSnack={handleCloseVocabSnack}` into the DesktopApp/MobileApp render alongside the existing snack props.

> The inbound `msg` is loosely typed; if the message type union is declared, add `vocabulary_rescanned` with `term_count: number; callsign_count: number` to it. Otherwise cast as the file already does for other cases.

- [ ] **Step 7: Render the snackbar** — in BOTH `DesktopApp.tsx` and `MobileApp.tsx`, add `vocabSnack: string | null;` + `onCloseVocabSnack: () => void;` to Props, destructure them, and add a Snackbar block copied from the `journalSavedSnack` one (severity `success`, autoHide 4000):

```tsx
      <Snackbar
        open={vocabSnack !== null}
        autoHideDuration={4000}
        onClose={onCloseVocabSnack}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={onCloseVocabSnack} severity="success" sx={{ width: '100%' }} aria-live="polite" aria-atomic="true">
          {vocabSnack}
        </Alert>
      </Snackbar>
```

- [ ] **Step 8: Run the frontend tests + typecheck**

Run (from `frontend/`): `npx vitest run src/components/ServerConfigPanel/ && npx tsc --noEmit`
Expected: ServerConfigPanel tests PASS; no type errors.

- [ ] **Step 9: Commit**

```bash
git add frontend/src
git commit -m "feat(ui): rescan vocabulary button + biasing toast"
```

---

### Task 7: Full test sweep + manual eval note

**Files:** none (verification only)

- [ ] **Step 1: Backend suite**

Run: `python -m pytest backend/tests -q`
Expected: PASS (no regressions; new vocab/contacts/transcriber/config/server tests green).

- [ ] **Step 2: Frontend suite + typecheck**

Run (from `frontend/`): `npx vitest run && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 3: Manual eval note (not automated)**

Document in the PR description that WER validation of the biasing uses the existing harness: capture with `stt_debug_capture`, then `python -m backend.tools.eval_stt --audio <dir>`. Tune `_MAX_PROMPT_CHARS` / `stt_vocab_max_callsigns` only against a labelled corpus. Release docs (README / USER_MANUAL / index.html / version bump) are handled by the `/release` skill at release time — not in this plan.

---

## Notes for the implementer

- Run all `python -m pytest` from the repo root `/mnt/storage/Repos/Radio-TTY`; run `npx` commands from `frontend/`.
- `update_phrases()` (worker.py:235-243) sets `self.saved_phrases` and calls `update_prompt()` on the **fast** cache only. **Before relying on the final-pass model refreshing live:** read the final-pass loop in `worker.py` (~720-792) and confirm it rebuilds its prompt from `self.saved_phrases` per finalization. If it does NOT, add a guarded `self._model_cache.whisper_final.update_prompt(self.saved_phrases)` (matching the attribute name actually used for the final model) to `update_phrases()` so live contact/phrase changes reach both engines without a restart. Either way, worker construction now passes the assembled list, so both engines are correct at startup and after any restart.
- Do not add per-category toggles, usage tracking, or `hotwords` — explicitly out of scope per the spec.
