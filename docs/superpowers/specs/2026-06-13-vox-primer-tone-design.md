# VOX Primer Tone — Design

**Date:** 2026-06-13
**Branch:** `feat/server-side-tx-audio`
**Status:** Approved, pending implementation plan

## Problem

The radio is keyed by **VOX** (voice-operated transmit): it starts transmitting
when it detects audio at its mic input. The TX synthesis path currently prepends
a *silence* lead-in (`synthesizer._synthesize_blocking`, `lead_in_seconds`),
which is correct for serial-PTT keying but useless for VOX — silence never trips
the VOX circuit, so the radio keys up only once speech begins and clips the first
syllables of the message.

## Goal

Add a server-level toggle that prepends a short **tone** to server-synthesized
TX audio. The tone keys VOX before the message starts; it is a throwaway that
absorbs the VOX ramp-up so the spoken message arrives intact.

## Scope

**In scope:** all server-synthesized transmits — operator text transmits, the
"THIS IS" standalone ID, and auto station-ID tails. These all flow through
`Synthesizer.synthesize_to_buffer`.

**Out of scope:**
- Mic/voice transmits (`_handle_voice_tx`) — raw recorded audio, not synthesized.
- The voice **preview/audition** path — local-only, must stay byte-identical.

## Audio layout

`_synthesize_blocking` builds, in order:

```
[lead-in silence] → [PRIMER TONE] → [primer gap] → [speech] → [tail silence]
```

- The tone keys VOX.
- The gap lets VOX stabilize so the first word of speech is not clipped.
- The primer is inserted into the PCM buffer only — it never enters the text
  pipeline, so it is invisible to the chat echo by construction (satisfies
  "hide it from chat").
- The primer is **not** run through `tx_conditioning` (that conditions `speech`
  only); the tone is already clean and in-band.

## Configuration

Two new keys in `backend/config.py` (persisted to `config.json`):

| Key | Type | Default | Meaning |
|-----|------|---------|---------|
| `vox_primer_enabled` | bool | `false` | Master on/off for the primer tone |
| `vox_primer_ms` | int | `300` | Tone duration in milliseconds |

Fixed internal constants (not exposed, can be promoted to config later if tuning
is needed):

- Frequency: **1000 Hz** (solidly in the voice band VOX listens to)
- Amplitude: **~0.3** of int16 full scale
- Gap after tone: **~80 ms** of silence

Defaults keep the feature **off**; when off, behaviour is unchanged.

## Backend changes

- `backend/tts/synthesizer.py`
  - New pure helper `make_vox_primer(sample_rate, ms)` → `np.ndarray` (int16):
    `ms` of 1000 Hz sine at ~0.3 FS followed by ~80 ms of silence (gap).
  - `synthesize_to_buffer` / `_synthesize_blocking` gain a `vox_primer_ms`
    argument, default `0.0` / disabled. When >0,
    the primer block is spliced between the lead-in silence and the speech.
    Default-off path produces a buffer identical to today.
- `backend/server.py`
  - `_tx_pump`: on the **real-TX** `synthesize_to_buffer` call (not the preview
    call), pass the primer duration from `_config` when `vox_primer_enabled`.
  - `_ws_handle_set_server_config`: accept `vox_primer_enabled` (bool) and
    `vox_primer_ms` (int, clamped to a sane range, e.g. 0–2000), admin-gated,
    no STT restart required (mirrors `tx_conditioning`).
  - `_build_status()`: include both keys so the client can render current state.

## Frontend changes

- `frontend/src/components/ServerConfigPanel/…` (System tab of the Settings
  dialog): a "VOX primer tone" toggle and a "Primer duration (ms)" numeric field
  that is enabled only when the toggle is on. Sends `set_server_config` on
  change, following the existing `tx_conditioning` pattern.
- `frontend/src/types/ws.ts`: status message type gains `vox_primer_enabled` and
  `vox_primer_ms`.

## Testing

**Backend (pytest):**
- `make_vox_primer`: returns the expected sample count for a given ms+rate,
  output is non-silent in the tone region and silent in the gap region, and all
  samples are within int16 range.
- `_synthesize_blocking` with primer enabled prepends exactly
  `lead + tone + gap` samples before the speech region; with primer disabled the
  buffer is unchanged (regression guard for the preview path).
- `_ws_handle_set_server_config` stores and clamps the new keys.

**Frontend (vitest):**
- ServerConfigPanel renders the toggle + duration field, disables duration when
  off, and emits `set_server_config` with the new keys on change.

## Interaction with the TX-tail guard

The primer plays at the **start** of TX, entirely within the window where STT is
paused, so it cannot be self-transcribed. The recently added TX-tail guard
operates at the **end** of TX. The two features are independent and do not
conflict.
