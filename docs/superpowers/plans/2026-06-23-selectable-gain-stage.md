# Selectable STT Gain Stage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an admin choose the STT gain stage — Dynamic AGC (default), Simple RMS normalize, or Off — from the System config panel, and make the choice A/B-testable in the eval harness.

**Architecture:** A new `stt_gain_mode` config key (`"agc" | "rms" | "off"`) flows: config → `STTWorker(gain_mode=...)` → `preprocess_segment(gain_mode=...)`, which branches the gain stage between `dynamic_agc`, the existing `normalize_rms`, or no-op. The same key surfaces in the admin UI (`ServerConfigPanel`) and the offline eval CLI.

**Tech Stack:** Python 3 (FastAPI backend, pytest), React + TypeScript (MUI, vitest).

## Global Constraints

- `stt_gain_mode` valid values: `"agc"`, `"rms"`, `"off"` — verbatim, lowercase.
- Default is `"agc"` everywhere (config property, worker, eval, frontend) — **no behavior change on upgrade**.
- Unknown/malformed values normalize to `"agc"` (never raise).
- The gain mode applies to **both** the streaming tier and the final pass.
- Bandpass and denoise stages are untouched.
- Do **not** add a `Co-Authored-By` trailer or any Claude/PR footer to commits (project preference).
- Commit messages use Conventional Commits (`feat:`, `test:`, `docs:`).

---

### Task 1: `stt_gain_mode` config property

**Files:**
- Modify: `backend/config.py` (insert after `stt_final_device`, config.py:87)
- Test: `backend/tests/unit/test_config_gain_mode.py` (create)

**Interfaces:**
- Produces: `ServerConfig.stt_gain_mode -> str` returning one of `"agc" | "rms" | "off"`, default `"agc"`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_config_gain_mode.py`:

```python
from backend.config import ServerConfig


def test_default_is_agc():
    assert ServerConfig().stt_gain_mode == "agc"


def test_explicit_rms():
    assert ServerConfig({"stt_gain_mode": "rms"}).stt_gain_mode == "rms"


def test_explicit_off():
    assert ServerConfig({"stt_gain_mode": "off"}).stt_gain_mode == "off"


def test_unknown_coerced_to_agc():
    assert ServerConfig({"stt_gain_mode": "loud"}).stt_gain_mode == "agc"


def test_case_insensitive():
    assert ServerConfig({"stt_gain_mode": "RMS"}).stt_gain_mode == "rms"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/unit/test_config_gain_mode.py -v`
Expected: FAIL — `AttributeError: 'ServerConfig' object has no attribute 'stt_gain_mode'`

- [ ] **Step 3: Write minimal implementation**

In `backend/config.py`, insert after the `stt_final_device` property (after line 87):

```python
    @property
    def stt_gain_mode(self) -> str:
        """Gain stage applied after bandpass/denoise, before transcription:
        'agc' (dynamic attack/release AGC), 'rms' (one-shot RMS normalize),
        or 'off' (no gain)."""
        val = str(self.get("stt_gain_mode", "agc")).strip().lower()
        return val if val in ("agc", "rms", "off") else "agc"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/unit/test_config_gain_mode.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/config.py backend/tests/unit/test_config_gain_mode.py
git commit -m "feat(config): add stt_gain_mode (agc/rms/off, default agc)"
```

---

### Task 2: `preprocess_segment` gain-mode branch

**Files:**
- Modify: `backend/stt/preprocess.py`
- Test: `backend/tests/unit/stt/test_preprocess.py` (modify)

**Interfaces:**
- Consumes: `normalize_rms`, `dynamic_agc` from `backend.audio.dsp` (both already exist).
- Produces: `preprocess_segment(audio, sample_rate, bandpass_sos, *, denoise_enabled=True, prop_decrease=0.7, gain_mode="agc") -> np.ndarray`. The `agc_enabled` parameter is **removed** (replaced by `gain_mode`).

- [ ] **Step 1: Update the failing tests**

In `backend/tests/unit/stt/test_preprocess.py`, replace the existing `test_agc_disabled_skips_agc` (lines 39-45) with these three tests, and update the two `agc_enabled=False` call sites in `test_bandpass_attenuates_out_of_band_tone` (lines 65-66) and `test_all_stages_disabled_still_bandpasses` (line 72) to `gain_mode="off"`:

```python
def test_gain_mode_off_skips_gain(sos, monkeypatch):
    agc_calls, rms_calls = [], []
    import backend.stt.preprocess as mod
    monkeypatch.setattr(mod, "dynamic_agc", lambda *a, **k: agc_calls.append(a) or a[0])
    monkeypatch.setattr(mod, "normalize_rms", lambda *a, **k: rms_calls.append(a) or a[0])
    preprocess_segment(_tone_with_noise(), SAMPLE_RATE, sos, gain_mode="off")
    assert agc_calls == [] and rms_calls == []


def test_gain_mode_agc_uses_dynamic_agc(sos, monkeypatch):
    agc_calls, rms_calls = [], []
    import backend.stt.preprocess as mod
    monkeypatch.setattr(mod, "dynamic_agc", lambda *a, **k: agc_calls.append(a) or a[0])
    monkeypatch.setattr(mod, "normalize_rms", lambda *a, **k: rms_calls.append(a) or a[0])
    preprocess_segment(_tone_with_noise(), SAMPLE_RATE, sos, gain_mode="agc")
    assert len(agc_calls) == 1 and rms_calls == []


def test_gain_mode_rms_uses_normalize_rms(sos, monkeypatch):
    agc_calls, rms_calls = [], []
    import backend.stt.preprocess as mod
    monkeypatch.setattr(mod, "dynamic_agc", lambda *a, **k: agc_calls.append(a) or a[0])
    monkeypatch.setattr(mod, "normalize_rms", lambda *a, **k: rms_calls.append(a) or a[0])
    preprocess_segment(_tone_with_noise(), SAMPLE_RATE, sos, gain_mode="rms")
    assert len(rms_calls) == 1 and agc_calls == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest backend/tests/unit/stt/test_preprocess.py -v`
Expected: FAIL — `TypeError: preprocess_segment() got an unexpected keyword argument 'gain_mode'` (and `normalize_rms` not importable in `mod`).

- [ ] **Step 3: Write minimal implementation**

Replace `backend/stt/preprocess.py` lines 8 and 11-30 so the file reads:

```python
from backend.audio.dsp import bandpass, denoise, dynamic_agc, normalize_rms


def preprocess_segment(
    audio: np.ndarray,
    sample_rate: int,
    bandpass_sos,
    *,
    denoise_enabled: bool = True,
    prop_decrease: float = 0.7,
    gain_mode: str = "agc",
) -> np.ndarray:
    """Bandpass → spectral-gating denoise → gain stage, each stage optional.

    The bandpass always runs: Whisper sees narrowband-FM voice (300–3000 Hz)
    and everything outside that band is noise by definition. The gain stage is
    selected by ``gain_mode``: "agc" (dynamic attack/release), "rms" (one-shot
    RMS normalize), or "off" (no gain).
    """
    out = bandpass(audio, bandpass_sos)
    if denoise_enabled:
        out = denoise(out, sample_rate, prop_decrease=prop_decrease)
    if gain_mode == "agc":
        out = dynamic_agc(out, sample_rate)
    elif gain_mode == "rms":
        out = normalize_rms(out)
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest backend/tests/unit/stt/test_preprocess.py -v`
Expected: PASS (all tests, including the unchanged bandpass/denoise/float32 ones)

- [ ] **Step 5: Commit**

```bash
git add backend/stt/preprocess.py backend/tests/unit/stt/test_preprocess.py
git commit -m "feat(stt): select gain stage via gain_mode in preprocess_segment"
```

---

### Task 3: Wire gain_mode through worker and server

**Files:**
- Modify: `backend/stt/worker.py` (constructor ~110-167; call sites worker.py:656 and worker.py:820)
- Modify: `backend/server.py` (`_make_stt_worker` kwargs near server.py:490-504; config snapshot near server.py:1211; `set_config` handler near server.py:1810)
- Test: `backend/tests/unit/stt/test_make_stt_worker.py` (modify)

**Interfaces:**
- Consumes: `ServerConfig.stt_gain_mode` (Task 1); `preprocess_segment(..., gain_mode=...)` (Task 2).
- Produces: `STTWorker(..., gain_mode="agc")` constructor kwarg stored as `self.gain_mode`.

- [ ] **Step 1: Write the failing test**

In `backend/tests/unit/stt/test_make_stt_worker.py`, add `"stt_gain_mode": "rms"` to the config dict in `test_passes_stt_accuracy_config_keys` (after line 33) and assert it reaches the worker; also assert the default in `test_defaults_when_keys_absent`:

```python
# add inside test_passes_stt_accuracy_config_keys, with the other asserts:
    assert kw["gain_mode"] == "rms"

# add inside test_defaults_when_keys_absent, with the other asserts:
    assert kw["gain_mode"] == "agc"
```

(Also add `"stt_gain_mode": "rms",` to the `ServerConfig({...})` dict literal in `test_passes_stt_accuracy_config_keys`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/unit/stt/test_make_stt_worker.py -v`
Expected: FAIL — `KeyError: 'gain_mode'` (worker not constructed with the kwarg yet)

- [ ] **Step 3: Add the worker constructor parameter**

In `backend/stt/worker.py`, add a parameter after `stt_final_device: str = "auto",` (worker.py:125):

```python
        gain_mode: str = "agc",
```

And store it (after `self.stt_final_device = stt_final_device`, worker.py:167):

```python
        self.gain_mode = gain_mode if gain_mode in ("agc", "rms", "off") else "agc"
```

- [ ] **Step 4: Pass gain_mode at both preprocess call sites**

In `backend/stt/worker.py`, update the streaming call (worker.py:656):

```python
                processed = preprocess_segment(
                    audio, self.SAMPLE_RATE, bandpass_sos, gain_mode=self.gain_mode
                )
```

And the final-pass call (worker.py:820):

```python
                    processed = preprocess_segment(
                        audio, self.SAMPLE_RATE, bandpass_sos, gain_mode=self.gain_mode
                    )
```

- [ ] **Step 5: Pass gain_mode from config in `_make_stt_worker`**

In `backend/server.py`, add to the `STTWorker(...)` kwargs (after `stt_final_device=_config.stt_final_device,`, server.py:504):

```python
        gain_mode=_config.stt_gain_mode,
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest backend/tests/unit/stt/test_make_stt_worker.py -v`
Expected: PASS

- [ ] **Step 7: Add gain_mode to the config snapshot and set_config handler**

In `backend/server.py` config snapshot dict, after `"whisper_model": ...` (server.py:1210):

```python
        "stt_gain_mode": (_config.stt_gain_mode if _config else "agc"),
```

In the `set_config` handler, after the `whisper_model_final` block (after server.py:1810):

```python
    if "stt_gain_mode" in data:
        mode = str(data["stt_gain_mode"]).strip().lower()
        if mode in ("agc", "rms", "off") and mode != _config.stt_gain_mode:
            _config["stt_gain_mode"] = mode
            stt_restart_needed = True
```

- [ ] **Step 8: Run the STT unit + server suites to verify no regressions**

Run: `python -m pytest backend/tests/unit/stt/ backend/tests/unit/test_config_gain_mode.py -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add backend/stt/worker.py backend/server.py backend/tests/unit/stt/test_make_stt_worker.py
git commit -m "feat(stt): plumb gain_mode from config through worker and set_config"
```

---

### Task 4: Eval-harness `--gain-mode` flag

**Files:**
- Modify: `backend/tools/eval_stt.py` (`EvalPipelineConfig` field eval_stt.py:45; `preprocess_segment` call eval_stt.py:102-107; argparse eval_stt.py:190 and cfg build eval_stt.py:200-208)
- Modify: `docs/stt-eval.md` (flag reference)
- Test: `backend/tests/unit/stt/test_eval_pipeline.py` (modify — add a dataclass-default assertion)

**Interfaces:**
- Consumes: `preprocess_segment(..., gain_mode=...)` (Task 2).
- Produces: `EvalPipelineConfig.gain_mode: str = "agc"`; CLI `--gain-mode {agc,rms,off}` with `--no-agc` as a deprecated alias for `--gain-mode off`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/unit/stt/test_eval_pipeline.py`:

```python
def test_eval_config_gain_mode_defaults_to_agc():
    from backend.tools.eval_stt import EvalPipelineConfig
    assert EvalPipelineConfig().gain_mode == "agc"
    assert EvalPipelineConfig(gain_mode="rms").gain_mode == "rms"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/unit/stt/test_eval_pipeline.py::test_eval_config_gain_mode_defaults_to_agc -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'gain_mode'`

- [ ] **Step 3: Replace the dataclass field**

In `backend/tools/eval_stt.py`, replace `agc_enabled: bool = True` (eval_stt.py:45) with:

```python
    gain_mode: str = "agc"
```

- [ ] **Step 4: Update the `preprocess_segment` call**

Replace `agc_enabled=cfg.agc_enabled,` (eval_stt.py:106) with:

```python
                gain_mode=cfg.gain_mode,
```

- [ ] **Step 5: Update the CLI**

In `backend/tools/eval_stt.py`, replace the `--no-agc` argument (eval_stt.py:190) with:

```python
    ap.add_argument("--gain-mode", choices=["agc", "rms", "off"], default="agc",
                    help="gain stage after bandpass/denoise")
    ap.add_argument("--no-agc", action="store_true",
                    help="deprecated alias for --gain-mode off")
```

Replace `agc_enabled=not args.no_agc,` in the `EvalPipelineConfig(...)` build (eval_stt.py:203) with:

```python
        gain_mode="off" if args.no_agc else args.gain_mode,
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest backend/tests/unit/stt/test_eval_pipeline.py -v`
Expected: PASS

- [ ] **Step 7: Update the docs**

In `docs/stt-eval.md`, find the `--no-agc` flag row/line in the flag reference and replace it with an entry for `--gain-mode {agc,rms,off}` (default `agc`), noting `--no-agc` is a deprecated alias for `--gain-mode off`. Add a one-line A/B example:

```bash
python -m backend.tools.eval_stt --audio /data/debug/stt --gain-mode rms --json > rms.json
python -m backend.tools.eval_stt --audio /data/debug/stt --gain-mode off --json > nogain.json
```

- [ ] **Step 8: Smoke-test the CLI parses all three modes**

Run: `python -m backend.tools.eval_stt --help`
Expected: help text lists `--gain-mode {agc,rms,off}` and `--no-agc`.

- [ ] **Step 9: Commit**

```bash
git add backend/tools/eval_stt.py backend/tests/unit/stt/test_eval_pipeline.py docs/stt-eval.md
git commit -m "feat(eval): add --gain-mode {agc,rms,off} to STT eval harness"
```

---

### Task 5: Admin UI gain-mode select

**Files:**
- Modify: `frontend/src/types/ws.ts` (ServerConfig message type, ws.ts:63)
- Modify: `frontend/src/App.tsx` (default config App.tsx:150; live mapping App.tsx:385)
- Modify: `frontend/src/components/ServerConfigPanel/ServerConfigPanel.tsx`
- Test: `frontend/src/components/ServerConfigPanel/__tests__/ServerConfigPanel.test.tsx` (modify)

**Interfaces:**
- Consumes: backend `stt_gain_mode` config key (Tasks 1, 3).
- Produces: `ServerConfig.gainMode: string` (camelCase) ↔ `ServerConfigSaveValues.stt_gain_mode: string` (snake_case).

- [ ] **Step 1: Write the failing test**

In `frontend/src/components/ServerConfigPanel/__tests__/ServerConfigPanel.test.tsx`, add a test that the gain-mode select renders and emits `stt_gain_mode` on save. Mirror the existing render/save helpers in that file (use the same render wrapper and `onSave` spy the other tests use). The assertion core:

```tsx
it('saves the selected gain mode', async () => {
  const onSave = vi.fn();
  // render the panel with onSave and a config whose gainMode is 'agc'
  // (reuse the file's existing renderPanel/baseConfig helper)
  renderPanel({ onSave, config: { ...baseConfig, gainMode: 'agc' } });

  // open the "Gain control" select and choose "Simple RMS"
  fireEvent.mouseDown(screen.getByLabelText('Gain control'));
  fireEvent.click(await screen.findByText(/Simple RMS/));
  fireEvent.click(screen.getByRole('button', { name: /save/i }));

  expect(onSave).toHaveBeenCalledWith(
    expect.objectContaining({ stt_gain_mode: 'rms' }),
  );
});
```

If the test file has no shared `renderPanel`/`baseConfig`, copy the setup from the nearest existing test in the same file (e.g. the `whisper_model_final` save test) and adapt it.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/ServerConfigPanel/__tests__/ServerConfigPanel.test.tsx`
Expected: FAIL — no element labelled "Gain control".

- [ ] **Step 3: Add the type fields**

In `frontend/src/types/ws.ts`, add to the ServerConfig message type (after ws.ts:63, alongside `whisper_model_final?`):

```ts
  stt_gain_mode?: string;
```

In `frontend/src/components/ServerConfigPanel/ServerConfigPanel.tsx`:

- Add the options constant after `FINAL_WHISPER_MODELS` (after ServerConfigPanel.tsx:50):

```tsx
const GAIN_MODES = [
  { value: 'agc', label: 'Dynamic AGC — attack/release (default)' },
  { value: 'rms', label: 'Simple RMS normalize' },
  { value: 'off', label: 'Off — no gain' },
];
```

- Add `gainMode: string;` to `interface ServerConfig` (after ServerConfigPanel.tsx:55).
- Add `stt_gain_mode: string;` to `interface ServerConfigSaveValues` (after ServerConfigPanel.tsx:74).
- Add `stt_gain_mode: c.gainMode,` to `valuesFromConfig` (after ServerConfigPanel.tsx:115).

- [ ] **Step 4: Add state, seeding, and save wiring**

In `ServerConfigPanel.tsx`:

- Add state after `whisperModelFinal` (after ServerConfigPanel.tsx:139):

```tsx
  const [gainMode, setGainMode] = useState('agc');
```

- Seed it in the open effect (after ServerConfigPanel.tsx:163):

```tsx
    setGainMode(config.gainMode);
```

- Add to `buildValues()` (after ServerConfigPanel.tsx:207):

```tsx
      stt_gain_mode: gainMode,
```

- [ ] **Step 5: Render the select**

In `ServerConfigPanel.tsx`, add this block right after the Final-pass Model `<FormControl>` (after the closing tag near ServerConfigPanel.tsx:275), following the same MUI pattern:

```tsx
          <FormControl fullWidth size="small" sx={{ mt: 2 }}>
            <InputLabel id="gain-mode-label">Gain control</InputLabel>
            <Select
              labelId="gain-mode-label"
              label="Gain control"
              value={gainMode}
              onChange={(e) => setGainMode(e.target.value)}
            >
              {GAIN_MODES.map((m) => (
                <MenuItem key={m.value} value={m.value}>{m.label}</MenuItem>
              ))}
            </Select>
          </FormControl>
```

- [ ] **Step 6: Wire the parent config in App.tsx**

In `frontend/src/App.tsx`:

- Add to the default ServerConfig object (after `whisperModelFinal: '',`, App.tsx:150):

```tsx
    gainMode: 'agc',
```

- Add to the live WS update mapping (after `whisperModelFinal: msg.whisper_model_final ?? prev.whisperModelFinal,`, App.tsx:385):

```tsx
          gainMode: msg.stt_gain_mode ?? prev.gainMode,
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/components/ServerConfigPanel/__tests__/ServerConfigPanel.test.tsx`
Expected: PASS

- [ ] **Step 8: Typecheck and run the full frontend suite**

Run: `cd frontend && npx tsc --noEmit && npx vitest run`
Expected: no type errors; all tests pass.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/types/ws.ts frontend/src/App.tsx \
  frontend/src/components/ServerConfigPanel/ServerConfigPanel.tsx \
  frontend/src/components/ServerConfigPanel/__tests__/ServerConfigPanel.test.tsx
git commit -m "feat(ui): add gain-control selector to server config panel"
```

---

## Final verification

- [ ] Run the full backend STT + config suites:
  `python -m pytest backend/tests/unit/stt/ backend/tests/unit/test_config_gain_mode.py backend/tests/unit/test_config.py -v`
- [ ] Run the full frontend suite: `cd frontend && npx vitest run`
- [ ] Confirm default behavior unchanged: a config with no `stt_gain_mode` still runs Dynamic AGC (covered by Task 1 `test_default_is_agc`, Task 3 `test_defaults_when_keys_absent`, Task 4 dataclass default).

## Notes for the implementer

- Changing the gain mode in the admin UI triggers `stt_restart_needed` (the listener restarts to rebuild the worker with the new `self.gain_mode`) — same lifecycle as changing the Whisper model. There is no live, mid-utterance switch.
- `normalize_rms` (backend/audio/dsp.py:37) mutates its input in place but is fed the fresh array returned by `bandpass`/`denoise`, so it never mutates the caller's buffer.
- This is **not** a release; no version bump or `/release` skill needed unless the user later decides to ship it.
