# Selectable STT gain stage (Dynamic AGC / Simple RMS / Off)

**Date:** 2026-06-23
**Status:** Approved design, pending implementation plan

## Problem

The per-segment DSP chain that feeds Whisper always applies `dynamic_agc` as its
gain stage. There is no way for an admin to change or disable it without editing
code. A dynamic AGC with a fast (10 ms) attack can "pump" — over-amplifying quiet
tails and breathing across pauses — which may inject artifacts that hurt
transcription. The sibling project GMRS-TTY uses a gentler one-shot RMS
normalize instead and is reported to transcribe more cleanly.

We want an admin-settable control to switch the gain stage between Dynamic AGC,
Simple RMS normalize, and Off, so the gain stage can be isolated during
troubleshooting and compared with the eval harness.

## Goals

- Admin can choose the gain stage from the System config panel: Dynamic AGC,
  Simple RMS, or Off.
- Default behavior is unchanged (Dynamic AGC) for existing and new installs.
- The choice applies to both the streaming tier and the final pass, consistently.
- The choice is measurable offline via the STT eval harness.

## Non-goals (out of scope)

- Changing the default away from Dynamic AGC.
- Exposing AGC's attack / release / target-dBFS knobs in the UI.
- Per-tier independent gain modes (streaming vs final).

## Design

### Config layer — `backend/config.py`

Add a property `stt_gain_mode` returning one of `"agc" | "rms" | "off"`,
default `"agc"`. Unknown or malformed values normalize to `"agc"`, following the
existing defensive pattern used by `stt_final_device` (config.py:83-87):

```python
@property
def stt_gain_mode(self) -> str:
    """Gain stage applied after bandpass/denoise: 'agc', 'rms', or 'off'."""
    val = str(self.get("stt_gain_mode", "agc")).strip().lower()
    return val if val in ("agc", "rms", "off") else "agc"
```

### DSP chain — `backend/stt/preprocess.py`

Replace the boolean `agc_enabled: bool = True` parameter with
`gain_mode: str = "agc"`. The chain stays bandpass → optional denoise → gain
branch:

```python
def preprocess_segment(
    audio, sample_rate, bandpass_sos, *,
    denoise_enabled: bool = True,
    prop_decrease: float = 0.7,
    gain_mode: str = "agc",
) -> np.ndarray:
    out = bandpass(audio, bandpass_sos)
    if denoise_enabled:
        out = denoise(out, sample_rate, prop_decrease=prop_decrease)
    if gain_mode == "agc":
        out = dynamic_agc(out, sample_rate)
    elif gain_mode == "rms":
        out = normalize_rms(out)
    # "off" → no gain stage
    return out
```

- Bandpass and denoise are untouched.
- `normalize_rms` (dsp.py:37) already exists and is GMRS-TTY's exact approach
  (one-shot RMS to −20 dBFS, near-silence guard, clip to [-1, 1]). It mutates in
  place, but receives the fresh array returned by `bandpass`/`denoise`, so it
  does not mutate the caller's buffer.
- Import `normalize_rms` alongside `bandpass, denoise, dynamic_agc`.

### Call sites — `backend/stt/worker.py`

Both `preprocess_segment` calls (worker.py:656 streaming, worker.py:820 final
pass) pass `gain_mode=self.config.stt_gain_mode`, keeping the two passes
consistent with each other as they are today.

### Eval harness — `backend/tools/eval_stt.py`

- `EvalConfig.agc_enabled: bool` → `gain_mode: str = "agc"`.
- The `preprocess_segment` call (eval_stt.py:102-106) passes `gain_mode=cfg.gain_mode`.
- CLI: replace `--no-agc` with `--gain-mode {agc,rms,off}` (default `agc`). Keep
  `--no-agc` as a deprecated alias that maps to `--gain-mode off`, so existing
  notes keep working.
- Update `docs/stt-eval.md` flag reference accordingly.

This makes the toggle measurable: an admin can A/B all three modes against
labelled WER on the same captures.

### Admin UI — `frontend/src/components/ServerConfigPanel/ServerConfigPanel.tsx`

- Add a "Gain control" `<select>` near the other STT/squelch fields with options:
  Dynamic AGC (`agc`), Simple RMS (`rms`), Off (`off`).
- Bind to a new `stt_gain_mode` config field; save through the existing config
  save flow (no new endpoint).
- Add `stt_gain_mode` to the config type in `frontend/src/types/ws.ts`.

## Data flow

```
admin selects Gain control  → config save (existing WS flow)
        → config.stt_gain_mode persisted in data/config.json
STT worker reads config.stt_gain_mode at each segment
        → preprocess_segment(..., gain_mode=...) branches to
           dynamic_agc | normalize_rms | (none)
```

## Error handling

- Invalid/missing config value → normalized to `"agc"` in the config property
  (no crash, current behavior preserved).
- `normalize_rms` already guards near-silent buffers and clips output; no new
  failure modes introduced. `"off"` is a no-op.

## Testing

- **preprocess** (`backend` tests): with a non-trivial buffer, assert
  `gain_mode="agc"` invokes `dynamic_agc`, `"rms"` invokes `normalize_rms`, and
  `"off"` applies neither (output equals bandpass[/denoise] output). Use spies or
  compare against the individual DSP functions.
- **config**: `stt_gain_mode` defaults to `"agc"`; an unknown value falls back to
  `"agc"`; valid values pass through.
- **ServerConfigPanel** (`frontend` tests): the select renders the three options
  and emits `stt_gain_mode` on change through the save flow.

## Files touched

- `backend/config.py` — new `stt_gain_mode` property
- `backend/stt/preprocess.py` — `gain_mode` param + branch, import `normalize_rms`
- `backend/stt/worker.py` — pass `gain_mode` at both call sites
- `backend/tools/eval_stt.py` — `gain_mode` field + `--gain-mode` flag (+`--no-agc` alias)
- `docs/stt-eval.md` — flag reference update
- `frontend/src/components/ServerConfigPanel/ServerConfigPanel.tsx` — select control
- `frontend/src/types/ws.ts` — `stt_gain_mode` field
- Tests: preprocess, config, ServerConfigPanel
