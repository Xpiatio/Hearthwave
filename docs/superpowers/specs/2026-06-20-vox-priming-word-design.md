# Spoken VOX priming word — Design

**Date:** 2026-06-20
**Status:** Approved (pending spec review)

## Summary

When enabled, every server-synthesized transmission speaks a configurable
priming word (default `"transmit"`) **after** the existing VOX primer tone and
**before** the actual message. The word is adjustable per deployment because
different VOX-keyed radios respond differently to a priming utterance.

This extends the existing `vox_primer_*` feature family (shipped v2.5.1). It adds
**no** multi-radio infrastructure — Hearthwave runs one radio per server, so a
single per-deployment setting is sufficient.

## On-the-wire sequence

When both the tone primer and word primer are enabled:

```
lead-in silence → 1 kHz tone → 80 ms gap → "transmit." → message
```

The word primer is **independent** of the tone primer (separate enable flag), so
an admin can run any combination: word-only, tone-only, both, or neither.

## Config

Two new keys in `backend/config.py`, mirroring the existing tone keys
(`vox_primer_enabled` / `vox_primer_ms`):

| Key | Type | Default | Notes |
|-----|------|---------|-------|
| `vox_primer_word_enabled` | bool | `False` | Off by default |
| `vox_primer_word` | str | `"transmit"` | The spoken word(s) |

Sanitizing in the `set_server_config` handler: coerce to `str`, `strip()`, cap
length at 64 characters. If the word is empty/whitespace after stripping, treat
the word primer as disabled for that transmission (no-op) even if the enable
flag is on.

## Injection point

In `_tx_pump()` (`backend/server.py`), immediately before the synthesis call,
prepend the word to the message text when enabled and non-empty:

```python
text = f"{word}. {text}"
```

Prepending as **text** (not spliced audio) means the word automatically inherits
the same voice, length-scale, and TX conditioning as the message — consistent
and simple. The existing tone splice inside the synthesizer then naturally lands
in front of the combined text, producing the tone → word → message order without
any change to the synthesizer.

The word applies to **all** transmissions when enabled — it is not gated to VOX
PTT mode, matching the existing tone primer's behavior and the "all TTS
transmissions" requirement.

Tradeoff accepted: the word is re-synthesized on each transmission rather than
cached. Cost is negligible relative to message synthesis.

## Plumbing (follows the documented 8-step config pattern)

1. `backend/config.py` — two `@property` accessors with defaults.
2. `backend/server.py` `_ws_handle_set_server_config()` — validate/sanitize and
   assign both keys.
3. `backend/server.py` `_build_status()` — broadcast both keys.
4. `frontend/src/types/ws.ts` — add optional `vox_primer_word_enabled` /
   `vox_primer_word` fields.
5. `frontend/src/components/ServerConfigPanel/ServerConfigPanel.tsx` — switch +
   text field in the System tab, directly under the existing VOX primer tone
   controls; state var, useEffect init, include in `handleSave()`.
6. `frontend/src/App.tsx` — capture both fields from the status broadcast.
7. Persistence is automatic via `_config.save()`.
8. Tests (below).

## Testing

- **Backend unit:** config defaults; word sanitizing (strip, length cap, empty
  handling).
- **Backend integration:** with the word primer enabled, the text handed to the
  synthesizer is prefixed with `"<word>. "`; disabled leaves the text untouched;
  enabled-but-empty word is a no-op.
- **Frontend:** component test that the switch and text field render and that a
  change round-trips through `handleSave()`.

## Out of scope

- Multi-radio / per-radio configuration (no such concept exists; not needed).
- Caching synthesized primer audio.
- Replacing or removing the existing tone primer.
