# VOX Primer Tone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a server-level toggle that prepends a short tone to server-synthesized TX audio so a VOX-keyed radio is fully keyed before the message begins.

**Architecture:** A pure tone generator (`make_vox_primer`) produces a 1000 Hz tone + short silence gap. `TTSSynthesizer._synthesize_blocking` splices it between the lead-in silence and the speech, gated by a new `vox_primer_ms` argument that defaults off (so the preview/audition path is unchanged). `_tx_pump` passes the configured duration only on the real-TX synth call. Two config keys (`vox_primer_enabled`, `vox_primer_ms`) flow through `set_server_config` / status / the System tab of the Settings dialog, mirroring the existing `tx_conditioning` toggle.

**Tech Stack:** Python (FastAPI backend, numpy, Piper TTS), pytest; React + TypeScript + MUI frontend, vitest.

**Spec:** `docs/superpowers/specs/2026-06-13-vox-primer-tone-design.md`

---

### Task 1: `make_vox_primer` tone generator (backend, pure)

**Files:**
- Modify: `backend/tts/synthesizer.py` (add module-level function near top, after imports)
- Test: `backend/tests/integration/test_vox_primer.py` (new)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/integration/test_vox_primer.py`:

```python
"""VOX primer tone generator + splicing into the TX buffer."""
import asyncio
from unittest.mock import MagicMock

import numpy as np

from backend.tts.synthesizer import TTSSynthesizer, make_vox_primer

SR = 22050


def _fake_voice(amp=0.8, seconds=0.5):
    t = np.arange(int(seconds * SR)) / SR
    pcm = (amp * np.sin(2 * np.pi * 800 * t) * 32767).astype(np.int16)
    chunk = MagicMock()
    chunk.audio_int16_array = pcm
    voice = MagicMock()
    voice.config.sample_rate = SR
    voice.config.num_speakers = 1
    voice.synthesize.return_value = [chunk]
    return voice, pcm


class TestMakeVoxPrimer:
    def test_length_is_tone_plus_gap(self):
        primer = make_vox_primer(SR, ms=300, gap_ms=80)
        assert len(primer) == int(0.300 * SR) + int(0.080 * SR)

    def test_dtype_is_int16(self):
        assert make_vox_primer(SR, ms=300).dtype == np.int16

    def test_tone_region_is_non_silent(self):
        primer = make_vox_primer(SR, ms=300, gap_ms=80)
        tone_n = int(0.300 * SR)
        assert np.max(np.abs(primer[:tone_n])) > 0

    def test_gap_region_is_silent(self):
        primer = make_vox_primer(SR, ms=300, gap_ms=80)
        tone_n = int(0.300 * SR)
        assert np.all(primer[tone_n:] == 0)

    def test_amplitude_within_int16_and_level(self):
        primer = make_vox_primer(SR, ms=300, level=0.3)
        peak = np.max(np.abs(primer))
        assert peak <= 32767
        assert peak >= int(0.25 * 32767)  # ~level, allowing for sine peak/rounding
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/integration/test_vox_primer.py::TestMakeVoxPrimer -q -p no:cacheprovider`
Expected: FAIL — `ImportError: cannot import name 'make_vox_primer'`

- [ ] **Step 3: Write minimal implementation**

In `backend/tts/synthesizer.py`, add this module-level function (after the imports, before the class):

```python
def make_vox_primer(
    sample_rate: int,
    ms: float,
    freq: int = 1000,
    level: float = 0.3,
    gap_ms: float = 80.0,
) -> "np.ndarray":
    """Build a VOX-priming burst: ``ms`` of a ``freq`` Hz sine at ``level`` of
    full scale, followed by ``gap_ms`` of silence. The tone keys a VOX radio;
    the gap lets it settle before speech so the first word isn't clipped.
    Returns int16 PCM at ``sample_rate``."""
    import numpy as np

    tone_n = int(ms / 1000.0 * sample_rate)
    gap_n = int(gap_ms / 1000.0 * sample_rate)
    t = np.arange(tone_n) / sample_rate
    tone = (level * np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
    return np.concatenate([tone, np.zeros(gap_n, dtype=np.int16)])
```

Note: `import numpy as np` is module-scoped in tests but `synthesizer.py` may lazy-import numpy. Check the top of the file — if numpy is already imported at module scope, drop the local `import numpy as np`. Otherwise keep it local.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/integration/test_vox_primer.py::TestMakeVoxPrimer -q -p no:cacheprovider`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/tts/synthesizer.py backend/tests/integration/test_vox_primer.py
git commit -m "feat(tts): add make_vox_primer tone generator"
```

---

### Task 2: Config keys `vox_primer_enabled` / `vox_primer_ms`

**Files:**
- Modify: `backend/config.py` (add two properties after `tx_conditioning`, ~line 124)
- Test: `backend/tests/unit/test_config.py` (append a test class)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/unit/test_config.py`:

```python
class TestVoxPrimer:
    def test_enabled_default_false(self):
        assert ServerConfig().vox_primer_enabled is False

    def test_enabled_override(self):
        assert make_config(vox_primer_enabled=True).vox_primer_enabled is True

    def test_ms_default_300(self):
        assert ServerConfig().vox_primer_ms == 300

    def test_ms_override(self):
        assert make_config(vox_primer_ms=500).vox_primer_ms == 500
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/unit/test_config.py::TestVoxPrimer -q -p no:cacheprovider`
Expected: FAIL — `AttributeError: 'ServerConfig' object has no attribute 'vox_primer_enabled'`

- [ ] **Step 3: Write minimal implementation**

In `backend/config.py`, after the `tx_conditioning` property (ends ~line 124), add:

```python
    @property
    def vox_primer_enabled(self) -> bool:
        """Prepend a short tone to server-synthesized TX audio so a VOX-keyed
        radio is fully keyed before the message starts."""
        return bool(self.get("vox_primer_enabled", False))

    @property
    def vox_primer_ms(self) -> int:
        """Duration of the VOX primer tone in milliseconds."""
        return int(self.get("vox_primer_ms", 300))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/unit/test_config.py::TestVoxPrimer -q -p no:cacheprovider`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/config.py backend/tests/unit/test_config.py
git commit -m "feat(config): add vox_primer_enabled / vox_primer_ms keys"
```

---

### Task 3: Splice the primer into the TX buffer

**Files:**
- Modify: `backend/tts/synthesizer.py` — `_synthesize_blocking` (~line 115-159) and `synthesize_to_buffer` (~line 55-71)
- Test: `backend/tests/integration/test_vox_primer.py` (append a class)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/integration/test_vox_primer.py`:

```python
class TestPrimerSplicing:
    def test_primer_prepended_before_speech(self):
        voice, pcm = _fake_voice()
        synth = TTSSynthesizer(out_queue=asyncio.Queue())
        audio, sr = synth._synthesize_blocking(
            voice, "hi", 0.1, 0.05, 1.0, condition=False, vox_primer_ms=300,
        )
        lead_n = int(0.1 * SR)
        tail_n = int(0.05 * SR)
        primer_n = len(make_vox_primer(SR, ms=300))
        assert audio.size == lead_n + primer_n + pcm.size + tail_n
        # lead is silence; primer region is non-silent; speech follows
        assert np.all(audio[:lead_n] == 0)
        assert np.max(np.abs(audio[lead_n:lead_n + primer_n])) > 0
        speech_start = lead_n + primer_n
        assert np.array_equal(audio[speech_start:speech_start + pcm.size], pcm)

    def test_disabled_is_unchanged(self):
        voice, pcm = _fake_voice()
        synth = TTSSynthesizer(out_queue=asyncio.Queue())
        audio, sr = synth._synthesize_blocking(
            voice, "hi", 0.1, 0.05, 1.0, condition=False, vox_primer_ms=0,
        )
        lead_n, tail_n = int(0.1 * SR), int(0.05 * SR)
        assert audio.size == lead_n + pcm.size + tail_n  # no primer samples

    def test_buffer_path_defaults_to_no_primer(self):
        voice, pcm = _fake_voice()
        synth = TTSSynthesizer(out_queue=asyncio.Queue())
        audio, sr = asyncio.run(synth.synthesize_to_buffer(voice, "hi"))
        assert np.array_equal(audio, pcm)  # preview path unchanged

    def test_buffer_path_forwards_primer(self):
        voice, pcm = _fake_voice()
        synth = TTSSynthesizer(out_queue=asyncio.Queue())
        audio, sr = asyncio.run(
            synth.synthesize_to_buffer(voice, "hi", vox_primer_ms=300)
        )
        primer_n = len(make_vox_primer(SR, ms=300))
        assert audio.size == primer_n + pcm.size
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/integration/test_vox_primer.py::TestPrimerSplicing -q -p no:cacheprovider`
Expected: FAIL — `TypeError: _synthesize_blocking() got an unexpected keyword argument 'vox_primer_ms'`

- [ ] **Step 3: Write minimal implementation**

In `backend/tts/synthesizer.py`, change the `_synthesize_blocking` signature to add the parameter (after `condition: bool = False`):

```python
    def _synthesize_blocking(
        self,
        voice,
        text: str,
        lead_in_seconds: float,
        tail_seconds: float,
        length_scale: float,
        condition: bool = False,
        vox_primer_ms: float = 0.0,
    ) -> tuple[np.ndarray | None, int]:
```

Then replace the buffer-assembly block (currently):

```python
        lead_samples = int(lead_in_seconds * sample_rate)
        tail_samples = int(tail_seconds * sample_rate)
        total = lead_samples + len(speech) + tail_samples
        # np.zeros so lead and tail regions are already silence; no
        # extra concatenations needed to splice them in.
        audio = np.zeros(total, dtype=np.int16)
        audio[lead_samples:lead_samples + len(speech)] = speech

        return audio, sample_rate
```

with:

```python
        lead_samples = int(lead_in_seconds * sample_rate)
        tail_samples = int(tail_seconds * sample_rate)
        primer = make_vox_primer(sample_rate, vox_primer_ms) if vox_primer_ms > 0 else None
        primer_samples = len(primer) if primer is not None else 0
        total = lead_samples + primer_samples + len(speech) + tail_samples
        # np.zeros so lead and tail regions are already silence; no
        # extra concatenations needed to splice them in.
        audio = np.zeros(total, dtype=np.int16)
        if primer is not None:
            audio[lead_samples:lead_samples + primer_samples] = primer
        speech_start = lead_samples + primer_samples
        audio[speech_start:speech_start + len(speech)] = speech

        return audio, sample_rate
```

Then add the parameter to `synthesize_to_buffer` and forward it. Change its signature:

```python
    async def synthesize_to_buffer(
        self,
        voice,
        text: str,
        length_scale: float = 1.0,
        lead_in_seconds: float = 0.0,
        tail_seconds: float = 0.0,
        vox_primer_ms: float = 0.0,
    ) -> tuple["np.ndarray | None", int]:
```

and its body:

```python
        return await asyncio.to_thread(
            self._synthesize_blocking, voice, text, lead_in_seconds, tail_seconds, length_scale,
            condition=False, vox_primer_ms=vox_primer_ms,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/integration/test_vox_primer.py -q -p no:cacheprovider`
Expected: PASS (all tests in the file)

Also run the conditioning regression suite to confirm nothing broke:
Run: `python -m pytest backend/tests/integration/test_tts_conditioning.py -q -p no:cacheprovider`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tts/synthesizer.py backend/tests/integration/test_vox_primer.py
git commit -m "feat(tts): splice VOX primer tone into the TX buffer"
```

---

### Task 4: Wire config → real-TX synth, set_server_config, status

**Files:**
- Modify: `backend/server.py` — `_tx_pump` real-TX synth call (~line 731-738), `_ws_handle_set_server_config` (~line 1407, after the `tx_conditioning` block), `_build_status` (~line 1023, after `tx_conditioning`)
- Test: manual (covered by integration in Task 6); no new unit test — these are wiring lines that mirror `tx_conditioning`.

- [ ] **Step 1: Pass the primer duration on the real-TX synth call**

In `backend/server.py` `_tx_pump`, the real-TX branch calls `synthesize_to_buffer` with `lead_in_seconds`/`tail_seconds`. Add the primer argument:

```python
                    audio, sample_rate = await asyncio.wait_for(
                        _synthesizer.synthesize_to_buffer(
                            voice, text, length_scale=length_scale,
                            lead_in_seconds=ptt.lead_in_seconds,
                            tail_seconds=ptt.tail_seconds,
                            vox_primer_ms=(_config.vox_primer_ms if _config.vox_primer_enabled else 0),
                        ),
                        timeout=synth_timeout,
                    )
```

Leave the **preview** call (the `is_preview` branch, `synthesize_to_buffer(voice, text, length_scale=length_scale)`) unchanged — preview must never emit the tone.

- [ ] **Step 2: Accept the keys in set_server_config**

In `_ws_handle_set_server_config`, immediately after the `tx_conditioning` block (ends ~line 1411), add:

```python
    if "vox_primer_enabled" in data:
        _config["vox_primer_enabled"] = bool(data["vox_primer_enabled"])

    if "vox_primer_ms" in data:
        try:
            ms = int(data["vox_primer_ms"])
            _config["vox_primer_ms"] = max(0, min(2000, ms))
        except (TypeError, ValueError):
            pass
```

- [ ] **Step 3: Report the keys in status**

In `_build_status`, after the `"tx_conditioning": ...` line (~1023), add:

```python
        "vox_primer_enabled": bool(_config.vox_primer_enabled) if _config else False,
        "vox_primer_ms": int(_config.vox_primer_ms) if _config else 300,
```

- [ ] **Step 4: Verify backend still imports and tests pass**

Run: `python -m pytest backend/tests/ -q -p no:cacheprovider`
Expected: PASS (full suite green)

- [ ] **Step 5: Commit**

```bash
git add backend/server.py
git commit -m "feat(server): wire VOX primer through TX, set_server_config, status"
```

---

### Task 5: Frontend toggle + duration field

**Files:**
- Modify: `frontend/src/types/ws.ts` — `StatusMsg` (~line 34-79, after `tx_conditioning?`)
- Modify: `frontend/src/components/ServerConfigPanel/ServerConfigPanel.tsx` — `ServerConfig`, `ServerConfigSaveValues`, state, init effect, `handleSave`, and the form body (after the `tx_conditioning` Switch ~line 246)
- Modify: `frontend/src/App.tsx` — `serverConfig` initial state (~line 104), status mapping (~line 333)
- Test: `frontend/src/components/ServerConfigPanel/__tests__/ServerConfigPanel.test.tsx` (append)

- [ ] **Step 1: Write the failing test**

Append to `frontend/src/components/ServerConfigPanel/__tests__/ServerConfigPanel.test.tsx` (follow the existing render/save helpers in that file — reuse its `renderPanel`/`baseConfig` if present; the snippet below assumes a `renderPanel(configOverrides)` helper and MUI Testing Library queries already used in the file):

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ServerConfigPanel, type ServerConfig } from '../ServerConfigPanel';

const baseConfig: ServerConfig = {
  vadThreshold: 0.5,
  whisperModel: 'small.en',
  whisperModelFinal: '',
  squelchAdaptive: false,
  sttDebugCapture: false,
  txConditioning: false,
  voxPrimerEnabled: false,
  voxPrimerMs: 300,
  pttMode: 'manual',
  pttSerialPort: '',
  pttSerialLine: 'RTS',
  monitorPassthrough: false,
  attendanceEnabled: false,
  savedPhrases: [],
};

describe('ServerConfigPanel VOX primer', () => {
  it('saves vox_primer_enabled when toggled on', () => {
    const onSave = vi.fn();
    render(
      <ServerConfigPanel open onClose={() => {}} config={baseConfig} onSave={onSave} embedded />,
    );
    fireEvent.click(screen.getByLabelText('VOX primer tone'));
    fireEvent.click(screen.getByRole('button', { name: /save/i }));
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ vox_primer_enabled: true, vox_primer_ms: 300 }),
    );
  });
});
```

If the existing test file uses a different render helper or the Save button has a different accessible name, adapt the two queries to match that file's conventions (read it first).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && rm -rf node_modules/.vite-temp && npx vitest run src/components/ServerConfigPanel`
Expected: FAIL — type error on `voxPrimerEnabled`/`voxPrimerMs` not in `ServerConfig`, or "Unable to find a label 'VOX primer tone'".

- [ ] **Step 3: Write minimal implementation**

**`frontend/src/types/ws.ts`** — in `StatusMsg`, after `tx_conditioning?: boolean;` (~line 66):

```ts
  vox_primer_enabled?: boolean;
  vox_primer_ms?: number;
```

**`ServerConfigPanel.tsx`** — add to `interface ServerConfig` (after `txConditioning: boolean;`):

```ts
  voxPrimerEnabled: boolean;
  voxPrimerMs: number;
```

add to `interface ServerConfigSaveValues` (after `tx_conditioning: boolean;`):

```ts
  vox_primer_enabled: boolean;
  vox_primer_ms: number;
```

add state (after `const [txConditioning, setTxConditioning] = useState(false);`):

```ts
  const [voxPrimerEnabled, setVoxPrimerEnabled] = useState(false);
  const [voxPrimerMs, setVoxPrimerMs] = useState(300);
```

add to the `useEffect` init block (after `setTxConditioning(config.txConditioning);`):

```ts
    setVoxPrimerEnabled(config.voxPrimerEnabled);
    setVoxPrimerMs(config.voxPrimerMs);
```

add to `handleSave`'s `onSave({...})` object (after `tx_conditioning: txConditioning,`):

```ts
      vox_primer_enabled: voxPrimerEnabled,
      vox_primer_ms: voxPrimerMs,
```

add the controls in the form body, right after the `tx_conditioning` `<FormControlLabel>`/caption block (~line 246):

```tsx
          <FormControlLabel
            control={
              <Switch
                checked={voxPrimerEnabled}
                onChange={(e) => setVoxPrimerEnabled(e.target.checked)}
                size="small"
              />
            }
            label="VOX primer tone"
          />
          <Typography variant="caption" sx={{ color: 'text.secondary', mt: -1.5 }}>
            Prepend a short tone to each transmission so a VOX-keyed radio is fully
            keyed before the message starts (silence won't trip VOX).
          </Typography>
          <TextField
            label="Primer duration (ms)"
            type="number"
            size="small"
            value={voxPrimerMs}
            disabled={!voxPrimerEnabled}
            onChange={(e) => setVoxPrimerMs(Math.max(0, Math.min(2000, Number(e.target.value) || 0)))}
            slotProps={{ htmlInput: { min: 0, max: 2000, step: 50 } }}
            sx={{ maxWidth: 200 }}
          />
```

**`App.tsx`** — add to `serverConfig` initial state (after `txConditioning: false,`):

```ts
    voxPrimerEnabled: false,
    voxPrimerMs: 300,
```

add to the status mapping `setServerConfig((prev) => ({...}))` (after `txConditioning: msg.tx_conditioning ?? prev.txConditioning,`):

```ts
          voxPrimerEnabled: msg.vox_primer_enabled ?? prev.voxPrimerEnabled,
          voxPrimerMs: msg.vox_primer_ms ?? prev.voxPrimerMs,
```

- [ ] **Step 4: Run test + typecheck to verify pass**

Run: `cd frontend && npx vitest run src/components/ServerConfigPanel`
Expected: PASS

Run: `cd frontend && npx tsc -p tsconfig.build.json --noEmit`
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/ws.ts frontend/src/components/ServerConfigPanel/ServerConfigPanel.tsx frontend/src/App.tsx frontend/src/components/ServerConfigPanel/__tests__/ServerConfigPanel.test.tsx
git commit -m "feat(frontend): VOX primer toggle + duration in Settings"
```

---

### Task 6: Build, deploy, verify on the rig

**Files:** none (deployment + manual verification)

- [ ] **Step 1: Run the full suites**

Run: `python -m pytest backend/tests/ -q -p no:cacheprovider` → all pass
Run: `cd frontend && rm -rf node_modules/.vite-temp && npx vitest run` → all pass
Run: `cd frontend && npx tsc -p tsconfig.build.json --noEmit` → no errors

- [ ] **Step 2: Build and deploy**

```bash
docker compose build backend frontend && docker compose up -d
```
Wait for health: `docker inspect -f '{{.State.Health.Status}}' radio-tty-backend-1` == `healthy`

- [ ] **Step 3: Manual verification**

In the app: open Admin Settings → System tab → enable "VOX primer tone", set duration (e.g. 300 ms), Save. Transmit a message. Confirm:
- The radio keys via VOX with no clipped first word.
- The primer tone is NOT in the chat echo.
- Disable the toggle, transmit again, confirm the tone is gone.

- [ ] **Step 4: Commit any doc updates** (if README/USER_MANUAL mention TX settings — out of scope unless cutting a release; if releasing, use the `/release` skill per CLAUDE.md).

---

## Notes for the implementer

- The class is `TTSSynthesizer` (not `Synthesizer`); config class is `ServerConfig` (dict-like: `.get`, `.update`, `cfg["key"] = v`).
- The frontend stack runs from **built** docker images, not bind mounts — source edits require `docker compose build` to take effect.
- `rm -rf frontend/node_modules/.vite-temp` before vitest (root-owned dir from a prior docker run blocks vitest config bundling).
- Do NOT commit `docs/index.html`, `docs/GMRS-SkyWarn.html`, or `specification/*.docx` — left for the user.
