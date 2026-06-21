# Spoken VOX Priming Word Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When enabled, speak a configurable priming word (default `"transmit"`) at the front of every server-synthesized radio transmission, after the existing VOX primer tone and before the message.

**Architecture:** Extend the existing `vox_primer_*` config family with two keys (`vox_primer_word_enabled`, `vox_primer_word`). A pure helper prepends the word to the message *text* just before synthesis in `_tx_pump`, so the word inherits the same voice/length-scale/conditioning as the message and the existing tone splice naturally lands in front of it. No multi-radio infrastructure — one word setting per deployment.

**Tech Stack:** Python 3 / asyncio / Starlette (backend), pytest; React + TypeScript + MUI (frontend), vitest + Testing Library.

## Global Constraints

- Spoken-word primer is **independent** of the tone primer: admin can run word-only, tone-only, both, or neither.
- Word applies to **all** radio transmissions when enabled (not gated to VOX PTT mode); it is **not** applied to voice previews (local audition).
- On-the-wire order when both enabled: `lead-in silence → tone → gap → "<word>." → message`.
- Config keys mirror the existing `vox_primer_enabled` / `vox_primer_ms` naming and plumbing pattern exactly.
- Word is sanitized at the config boundary: coerce to `str`, `strip()`, cap at 64 chars. An empty/whitespace word is a no-op even if the enable flag is on.
- Default word: `"transmit"`. Default enabled: `False`.
- No new dependencies. Follow existing file/test patterns.

---

### Task 1: Config properties + unit tests

**Files:**
- Modify: `backend/config.py` (after the `vox_primer_ms` property, ~line 135)
- Test: `backend/tests/unit/test_config.py`

**Interfaces:**
- Produces: `ServerConfig.vox_primer_word_enabled -> bool` (default `False`); `ServerConfig.vox_primer_word -> str` (default `"transmit"`)

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/unit/test_config.py` (the file already defines the `make_config(**kwargs)` helper near the top):

```python
# ---------------------------------------------------------------------------
# VOX priming word
# ---------------------------------------------------------------------------

class TestVoxPrimerWordDefaults:
    def test_enabled_default_false(self):
        assert ServerConfig().vox_primer_word_enabled is False

    def test_word_default_transmit(self):
        assert ServerConfig().vox_primer_word == "transmit"


class TestVoxPrimerWordOverrides:
    def test_enabled_override(self):
        assert make_config(vox_primer_word_enabled=True).vox_primer_word_enabled is True

    def test_word_override(self):
        assert make_config(vox_primer_word="break").vox_primer_word == "break"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/unit/test_config.py -k VoxPrimerWord -v`
Expected: FAIL with `AttributeError: 'ServerConfig' object has no attribute 'vox_primer_word_enabled'`

- [ ] **Step 3: Add the properties**

In `backend/config.py`, immediately after the `vox_primer_ms` property (line 135), add:

```python
    @property
    def vox_primer_word_enabled(self) -> bool:
        """Speak a configurable priming word (e.g. "transmit") after the VOX
        primer tone and before the message, so a VOX-keyed radio is keyed on a
        clear spoken keyword.  Different radios may need different words."""
        return bool(self.get("vox_primer_word_enabled", False))

    @property
    def vox_primer_word(self) -> str:
        """The spoken VOX priming word."""
        return str(self.get("vox_primer_word", "transmit"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/unit/test_config.py -k VoxPrimerWord -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/config.py backend/tests/unit/test_config.py
git commit -m "feat(config): add vox_primer_word_enabled / vox_primer_word keys"
```

---

### Task 2: Pure primer-word text helper + unit tests

**Files:**
- Create: `backend/text/primer.py`
- Test: `backend/tests/unit/text/test_primer.py`

**Interfaces:**
- Produces: `prepend_primer_word(text: str, word: str) -> str` — returns `f"{word.strip()}. {text}"`; returns `text` unchanged when `word` is empty/whitespace.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/text/test_primer.py`:

```python
from backend.text.primer import prepend_primer_word


class TestPrependPrimerWord:
    def test_prepends_word_with_period_and_space(self):
        assert prepend_primer_word("hello world", "transmit") == "transmit. hello world"

    def test_custom_word(self):
        assert prepend_primer_word("go ahead", "break") == "break. go ahead"

    def test_empty_word_is_noop(self):
        assert prepend_primer_word("hello", "") == "hello"

    def test_whitespace_word_is_noop(self):
        assert prepend_primer_word("hello", "   ") == "hello"

    def test_word_is_stripped(self):
        assert prepend_primer_word("hello", "  transmit  ") == "transmit. hello"
```

> Note: `backend/tests/unit/text/` may not exist yet. If pytest reports collection issues, create an empty `backend/tests/unit/text/__init__.py` (mirror the existing `backend/tests/unit/__init__.py`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/unit/text/test_primer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.text.primer'`

- [ ] **Step 3: Create the helper**

Create `backend/text/primer.py`:

```python
"""Spoken VOX priming word: prefix a keyword to TX text so a VOX-keyed radio
hears a clear word (e.g. "transmit") before the actual message."""


def prepend_primer_word(text: str, word: str) -> str:
    """Return *text* with *word* spoken first, separated by a period so TTS
    pauses between them.  Returns *text* unchanged when *word* is empty or
    whitespace-only."""
    w = (word or "").strip()
    if not w:
        return text
    return f"{w}. {text}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/unit/text/test_primer.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/text/primer.py backend/tests/unit/text/
git commit -m "feat(text): add prepend_primer_word helper"
```

---

### Task 3: set_server_config sanitizing + status broadcast

**Files:**
- Modify: `backend/server.py` — `_ws_handle_set_server_config()` (after the `vox_primer_ms` block, ~line 1615) and `_build_status()` (after the `vox_primer_ms` line, ~1176)
- Test: `backend/tests/integration/test_server_ws.py`

**Interfaces:**
- Consumes: `ServerConfig.vox_primer_word_enabled`, `ServerConfig.vox_primer_word` (Task 1)
- Produces: status frames now carry `vox_primer_word_enabled: bool` and `vox_primer_word: str`; `set_server_config` accepts the same two keys.

- [ ] **Step 1: Write the failing integration tests**

Append to `backend/tests/integration/test_server_ws.py` (mirrors the existing `TestSetServerConfigSavedPhrases` class, which patches `ServerConfig.save` and uses the `client` fixture + `_drain_initial`):

```python
# ---------------------------------------------------------------------------
# set_server_config — vox priming word
# ---------------------------------------------------------------------------

class TestSetServerConfigVoxPrimerWord:
    def _send_and_get_status(self, ws, data):
        with patch("backend.config.ServerConfig.save"):
            ws.send_json({"type": "set_server_config", **data})
            return ws.receive_json()

    def test_word_and_enabled_reflected_in_status(self, client):
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            msg = self._send_and_get_status(
                ws, {"vox_primer_word_enabled": True, "vox_primer_word": "break"}
            )
            assert msg["type"] == "status"
            assert msg["vox_primer_word_enabled"] is True
            assert msg["vox_primer_word"] == "break"

    def test_word_is_trimmed(self, client):
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            msg = self._send_and_get_status(ws, {"vox_primer_word": "  transmit  "})
            assert msg["vox_primer_word"] == "transmit"

    def test_word_capped_at_64_chars(self, client):
        with client.websocket_connect(WS_URL) as ws:
            _drain_initial(ws)
            msg = self._send_and_get_status(ws, {"vox_primer_word": "x" * 100})
            assert msg["vox_primer_word"] == "x" * 64

    def test_status_default_word_is_transmit(self, client):
        with client.websocket_connect(WS_URL) as ws:
            frames = _drain_initial(ws)
            status = next(f for f in frames if f["type"] == "status")
            assert status["vox_primer_word"] == "transmit"
            assert status["vox_primer_word_enabled"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/integration/test_server_ws.py -k VoxPrimerWord -v`
Expected: FAIL — `KeyError: 'vox_primer_word'` (status does not yet carry the keys)

- [ ] **Step 3: Add the status broadcast keys**

In `backend/server.py` `_build_status()`, immediately after the `"vox_primer_ms": ...` line (~1176), add:

```python
        "vox_primer_word_enabled": bool(_config.vox_primer_word_enabled) if _config else False,
        "vox_primer_word": (_config.vox_primer_word if _config else "transmit"),
```

- [ ] **Step 4: Add the set_server_config handler block**

In `backend/server.py` `_ws_handle_set_server_config()`, immediately after the `vox_primer_ms` block (the `try/except` ending ~line 1615), add:

```python
    if "vox_primer_word_enabled" in data:
        _config["vox_primer_word_enabled"] = bool(data["vox_primer_word_enabled"])

    if "vox_primer_word" in data:
        _config["vox_primer_word"] = str(data["vox_primer_word"]).strip()[:64]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/integration/test_server_ws.py -k VoxPrimerWord -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add backend/server.py backend/tests/integration/test_server_ws.py
git commit -m "feat(server): accept + broadcast vox_primer_word config"
```

---

### Task 4: Wire the primer word into the TX pump

**Files:**
- Modify: `backend/server.py` — imports (near line 147, with the other `backend.text.*` imports) and `_tx_pump()` non-preview branch (~line 868, just before `ptt = make_ptt(_config)`)
- Test: `backend/tests/integration/test_server_ws.py`

**Interfaces:**
- Consumes: `prepend_primer_word` (Task 2); `ServerConfig.vox_primer_word_enabled` / `vox_primer_word` (Task 1)
- Produces: when the word primer is enabled, the `text` passed to `_synthesizer.synthesize_to_buffer(...)` is prefixed with `"<word>. "`.

- [ ] **Step 1: Write the failing integration test**

Append to `backend/tests/integration/test_server_ws.py`. This mirrors `test_stt_worker_paused_during_tx_and_resumed_after` (line ~302) — a self-contained server with a synth mock whose `side_effect` records the text it receives:

```python
class TestTxAppliesPrimerWord:
    def test_enabled_prepends_word_to_synth_text(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)
        cfg["vox_primer_word_enabled"] = True
        cfg["vox_primer_word"] = "transmit"
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()
        captured: dict[str, str] = {}
        synth_done = threading.Event()

        async def _capture_synth(_voice, text, *_args, **_kwargs):
            captured["text"] = text
            synth_done.set()
            return None, None

        mock_tts.synthesize_to_buffer = _capture_synth

        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
            patch("backend.server.make_ptt", return_value=MagicMock()),
            patch("piper.PiperVoice"),
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    ws.send_json({"type": "tx_message", "callsign": "W5TST", "text": "hello"})
                    _drain_until_idle(ws)
                synth_done.wait(timeout=2.0)

        assert "text" in captured, "synthesize_to_buffer was never called"
        assert captured["text"].startswith("transmit. "), captured["text"]

    def test_disabled_does_not_prepend(self, tmp_path):
        cfg = _minimal_cfg(tmp_path)  # word primer off by default
        mock_stt, mock_tts = _make_mocks()
        mock_users, mock_tokens = _make_auth_mocks()
        captured: dict[str, str] = {}
        synth_done = threading.Event()

        async def _capture_synth(_voice, text, *_args, **_kwargs):
            captured["text"] = text
            synth_done.set()
            return None, None

        mock_tts.synthesize_to_buffer = _capture_synth

        with (
            patch("backend.server.ServerConfig.load", return_value=cfg),
            patch("backend.server.STTWorker", return_value=mock_stt),
            patch("backend.server.TTSSynthesizer", return_value=mock_tts),
            patch("backend.server.UsersStore", return_value=mock_users),
            patch("backend.server.TokenStore", return_value=mock_tokens),
            patch("backend.auth_routes.init"),
            patch("backend.server.make_ptt", return_value=MagicMock()),
            patch("piper.PiperVoice"),
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect(WS_URL) as ws:
                    _drain_initial(ws)
                    ws.send_json({"type": "tx_message", "callsign": "W5TST", "text": "hello"})
                    _drain_until_idle(ws)
                synth_done.wait(timeout=2.0)

        assert "text" in captured, "synthesize_to_buffer was never called"
        assert not captured["text"].startswith("transmit. "), captured["text"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/integration/test_server_ws.py -k TxAppliesPrimerWord -v`
Expected: FAIL — `test_enabled_prepends_word_to_synth_text` fails its `startswith` assert (text is not yet prefixed). `test_disabled_does_not_prepend` should already pass.

- [ ] **Step 3: Add the import**

In `backend/server.py`, with the other `from backend.text.* import ...` lines (~line 145), add:

```python
from backend.text.primer import prepend_primer_word
```

- [ ] **Step 4: Wire the prepend into the non-preview TX branch**

In `_tx_pump()`, inside the `else:` (non-preview) branch, immediately before `ptt = make_ptt(_config)` (~line 868), add:

```python
                if _config.vox_primer_word_enabled:
                    text = prepend_primer_word(text, _config.vox_primer_word)
```

(Indentation: this sits inside the `else:` block at the same level as `ptt = make_ptt(_config)`.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/integration/test_server_ws.py -k TxAppliesPrimerWord -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Run the full backend suite to confirm no regressions**

Run: `cd /mnt/storage/Repos/Radio-TTY && python -m pytest backend/tests/ -q`
Expected: all pass (no regressions in the existing TX / VOX primer tests).

- [ ] **Step 7: Commit**

```bash
git add backend/server.py backend/tests/integration/test_server_ws.py
git commit -m "feat(server): speak configurable VOX priming word before TX"
```

---

### Task 5: Frontend — types, state, and Settings UI

**Files:**
- Modify: `frontend/src/types/ws.ts` (~line 68, after `vox_primer_ms?`)
- Modify: `frontend/src/App.tsx` (config defaults ~line 154; status reducer ~line 385)
- Modify: `frontend/src/components/ServerConfigPanel/ServerConfigPanel.tsx` (interfaces, state, useEffect, handleSave, UI)
- Test: `frontend/src/components/ServerConfigPanel/__tests__/ServerConfigPanel.test.tsx`

**Interfaces:**
- Consumes: status keys `vox_primer_word_enabled` / `vox_primer_word` (Task 3)
- Produces: `handleSave()` emits `vox_primer_word_enabled: boolean` and `vox_primer_word: string` in its `ServerConfigSaveValues` payload.

- [ ] **Step 1: Add the WS status types**

In `frontend/src/types/ws.ts`, after `vox_primer_ms?: number;` (line 68):

```typescript
  vox_primer_word_enabled?: boolean;
  vox_primer_word?: string;
```

- [ ] **Step 2: Add App.tsx defaults and reducer mapping**

In `frontend/src/App.tsx`, after `voxPrimerMs: 300,` (~line 154) in the initial config object:

```typescript
    voxPrimerWordEnabled: false,
    voxPrimerWord: 'transmit',
```

And after `voxPrimerMs: msg.vox_primer_ms ?? prev.voxPrimerMs,` (~line 385) in the status reducer:

```typescript
          voxPrimerWordEnabled: msg.vox_primer_word_enabled ?? prev.voxPrimerWordEnabled,
          voxPrimerWord: msg.vox_primer_word ?? prev.voxPrimerWord,
```

- [ ] **Step 3: Extend the ServerConfigPanel interfaces**

In `frontend/src/components/ServerConfigPanel/ServerConfigPanel.tsx`:

In `interface ServerConfig`, after `voxPrimerMs: number;` (line 60):

```typescript
  voxPrimerWordEnabled: boolean;
  voxPrimerWord: string;
```

In `interface ServerConfigSaveValues`, after `vox_primer_ms: number;` (line 77):

```typescript
  vox_primer_word_enabled: boolean;
  vox_primer_word: string;
```

- [ ] **Step 4: Add component state + init + save**

In `ServerConfigPanel`, after `const [voxPrimerMs, setVoxPrimerMs] = useState(300);` (line 104):

```typescript
  const [voxPrimerWordEnabled, setVoxPrimerWordEnabled] = useState(false);
  const [voxPrimerWord, setVoxPrimerWord] = useState('transmit');
```

In the `useEffect` init block, after `setVoxPrimerMs(config.voxPrimerMs);` (line 124):

```typescript
    setVoxPrimerWordEnabled(config.voxPrimerWordEnabled);
    setVoxPrimerWord(config.voxPrimerWord);
```

In `handleSave()`, after `vox_primer_ms: voxPrimerMs,` (line 155):

```typescript
      vox_primer_word_enabled: voxPrimerWordEnabled,
      vox_primer_word: voxPrimerWord.trim(),
```

- [ ] **Step 5: Add the UI controls**

In the JSX, immediately after the existing VOX primer tone `TextField` (the "Primer duration (ms)" field, closing `/>` at line 281):

```tsx
          <FormControlLabel
            control={
              <Switch
                checked={voxPrimerWordEnabled}
                onChange={(e) => setVoxPrimerWordEnabled(e.target.checked)}
                size="small"
              />
            }
            label="VOX priming word"
          />
          <Typography variant="caption" sx={{ color: 'text.secondary', mt: -1.5 }}>
            Speak a word (e.g. "transmit") right after the primer tone and before
            the message, so a VOX-keyed radio is keyed on a clear spoken keyword.
            Different radios may need different words.
          </Typography>
          <TextField
            label="Priming word"
            size="small"
            value={voxPrimerWord}
            disabled={!voxPrimerWordEnabled}
            onChange={(e) => setVoxPrimerWord(e.target.value.slice(0, 64))}
            sx={{ maxWidth: 200 }}
          />
```

- [ ] **Step 6: Update existing test fixtures + the save-roundtrip assertion**

The existing exact-match save test (`'calls onSave and onClose with correct values when Save is clicked'`, ~line 197) and `makeConfig` helper (~line 15) will break once `handleSave` emits the new keys. Update both.

In `makeConfig` (after `voxPrimerMs: 300,`):

```typescript
    voxPrimerWordEnabled: false,
    voxPrimerWord: 'transmit',
```

In the exact-match `toHaveBeenCalledWith({ ... })` object (after `vox_primer_ms: 300,`):

```typescript
      vox_primer_word_enabled: false,
      vox_primer_word: 'transmit',
```

- [ ] **Step 7: Add a new component test for the priming-word controls**

Append inside the `describe('ServerConfigPanel', ...)` block:

```tsx
  it('toggles the VOX priming word and passes word + flag to onSave', async () => {
    const user = userEvent.setup()
    const props = makeDefaultProps({ voxPrimerWordEnabled: true, voxPrimerWord: 'transmit' })
    render(<ServerConfigPanel {...props} />)

    const field = screen.getByLabelText(/priming word/i)
    await user.clear(field)
    await user.type(field, 'break')
    await user.click(screen.getByRole('button', { name: /save/i }))

    expect(props.onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        vox_primer_word_enabled: true,
        vox_primer_word: 'break',
      })
    )
  })
```

- [ ] **Step 8: Run the frontend tests**

Run: `cd /mnt/storage/Repos/Radio-TTY/frontend && npx vitest run src/components/ServerConfigPanel/__tests__/ServerConfigPanel.test.tsx`
Expected: PASS, including the updated exact-match test and the new priming-word test.

- [ ] **Step 9: Type-check / build the frontend**

Run: `cd /mnt/storage/Repos/Radio-TTY/frontend && npx tsc --noEmit`
Expected: no type errors.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/types/ws.ts frontend/src/App.tsx frontend/src/components/ServerConfigPanel/
git commit -m "feat(frontend): VOX priming word toggle + word field in Settings"
```

---

## Self-Review

**Spec coverage:**
- Configurable word, default "transmit" → Tasks 1, 3, 5. ✓
- Word after tone, before message → Task 4 (text prepend lands behind the synthesizer's tone splice). ✓
- Per-deployment single setting (no multi-radio) → only global config keys added. ✓
- All TX when enabled, not previews → Task 4 wires the non-preview branch only. ✓
- Independent of tone primer → separate enable flag throughout. ✓
- Sanitizing (strip, 64-char cap, empty no-op) → Task 3 (boundary) + Task 2 (helper guards empty). ✓
- Testing: backend unit (helper + config), backend integration (config round-trip + TX wiring), frontend component → Tasks 1–5. ✓

**Placeholder scan:** none — every code/test step has full content and exact commands.

**Type consistency:** `prepend_primer_word(text, word)` defined in Task 2, consumed identically in Task 4. Config keys `vox_primer_word_enabled` / `vox_primer_word` and frontend `voxPrimerWordEnabled` / `voxPrimerWord` used consistently across Tasks 1, 3, 5. `handleSave` payload keys match `ServerConfigSaveValues` and the backend handler.

> Release note: this is a user-facing feature. Per CLAUDE.md, run the `/release` skill when cutting the next version so README / USER_MANUAL / docs/index.html are updated.
