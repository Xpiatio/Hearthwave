# STT Vocabulary Biasing — Design

**Date:** 2026-06-20
**Status:** Approved (design)
**Project:** Hearthwave (Radio-TTY)

## Revision — post-build, 2026-06-20 (token-budget reality)

The final whole-branch review + tokenizer measurements (faster-whisper 1.2.1,
`small.en`) invalidated the original char-budget tuning. Hard facts:

- Whisper keeps only ~223 prompt tokens. The original 73-term curated set =
  **221 tokens by itself** — it consumed the entire budget.
- Callsigns cost **~6 tokens each** (alphanumerics tokenize near per-character),
  so `max_callsigns=100` was physically unreachable (~36 fit, alone).
- Result: with any contacts, callsigns-first + front-trim evicted ALL curated
  vocab. The headline curated biasing was effectively dead in real deployments.

Decisions (user-approved):

1. **Trim curated to a 40-term high-value core** — NATO (26) + 14 procedure
   words / Q-codes (over, out, roger, affirmative, negative, copy that, say
   again, standing by, break break, CQ, QSL, QSY, QRZ, seventy three) = 111
   tokens. CB slang and band-identifier extras dropped (operators add their own
   via saved phrases).
2. **Token-accurate budgeting** — `_build_prompt` trims by real token count via
   the model tokenizer (`WhisperModel.hf_tokenizer`), budget `_MAX_PROMPT_TOKENS
   = 220`, with a char-based heuristic fallback when no tokenizer (unit tests).
   Replaces the unreliable `_MAX_PROMPT_CHARS` proxy.
3. **`stt_vocab_max_callsigns` default 100 → 15** — core (111) + 15 callsigns
   (~94) ≈ 205 tokens, fits under 220 with both halves active. Documented that
   callsigns are token-expensive and only the newest ~15 bias the prompt.
4. **Final-pass engine live refresh (review Important #1)** —
   `STTWorker.update_phrases` now refreshes BOTH the fast and final Whisper
   caches, so live contact/phrase changes reach the authoritative replacing
   transcript without a worker restart.

## Goal

Bias both Whisper STT engines toward radio-domain vocabulary (CB, HAM, GMRS,
MURS, NATO phonetic alphabet) **and** toward known contact callsigns, and keep
that bias current as contacts and custom phrases are added over time.

## Background

The app already has the mechanism: both engines feed off a single phrase list
that becomes Whisper's `initial_prompt`.

- Fast/partial transcriber: `backend/stt/transcriber.py` — `_build_prompt()`
  (lines 51–55) builds the prompt; passed as `initial_prompt` at line 79.
- Final-pass transcriber: same class, invoked at `backend/stt/worker.py:783`.
- Live update path: `worker.py` `update_phrases()` (235–243) propagates to both
  engine caches via `update_prompt()` — no STT restart.
- Contacts: `backend/persistence/contacts.py` — `known_callsigns()` (54–66)
  returns the uppercase set across all three callsign fields (`callsign`,
  `gmrs_callsign`, `ham_callsign`).
- Current bias source: `saved_phrases` in `config.json`, defaulted in
  `config.py` (164–168).

So this work **populates, curates, prioritizes, and auto-refreshes** that bias
source rather than building new transcription infrastructure.

## Key constraints (these drive the design)

1. **Whisper `initial_prompt` is soft biasing with a ~224-token budget.** Only
   roughly the last 224 tokens survive; the rest is silently dropped. Over-biasing
   also makes Whisper *hallucinate* prompt words into static.
2. **The tail survives.** The prompt must be assembled lowest-priority-first so
   that, on truncation, generic vocab is dropped and callsigns + custom phrases
   (the tail) are kept.

## Decisions

- **Priority on overflow: callsigns first.** Contact callsigns + saved phrases
  always win; curated band vocab fills remaining budget. (Also the lowest
  hallucination risk — callsigns are words genuinely expected on-air.)
- **Refresh: both.** Auto-rebuild on any contact add/edit/delete or phrase
  change, plus a manual "Rescan vocabulary" button for bulk imports.
- **Curated sets: fixed, always-on.** All five baked in, not user-editable, no
  per-category toggles. "Always-on" = no toggle UI; the budget cap still trims
  curated vocab (never callsigns) when tight.
- **Mechanism stays `initial_prompt`** (not faster-whisper `hotwords`) — lower
  risk to a working path; revisit only if eval shows it underperforms.
- **Trim default `saved_phrases` to empty** — the curated sets now cover the old
  defaults (over, 10-4, QSL, QSY, QRZ, standing by); `saved_phrases` becomes
  purely the operator's custom additions.

## Components

### 1. `backend/stt/vocab.py` (new)

Module-level `frozenset`s for the five curated sets plus pure assembly logic.
No I/O — unit-testable and compatible with the `eval_stt` harness.

Representative contents (finalized at implementation):

- `NATO` — Alfa…Zulu (26).
- `CB` — breaker, what's your twenty, smokey, bear, handle, good buddy, back
  door, ratchet jaw, ears, negatory, come back, wall to wall, kojak with a
  kodak…
- `HAM` — Q-codes (QSL, QSY, QRZ, QRM, QRN, QTH, QSO, QRP, QRT, QSB), CQ, roger,
  affirmative, say again, monitoring…
- `GMRS` — GMRS, repeater, simplex, duplex, privacy code, PL tone, kerchunk,
  channel…
- `MURS` — MURS, blue dot, green dot…

Public function:

```python
assemble_phrases(callsigns, saved_phrases, *, max_callsigns) -> list[str]
```

- Concatenates in **priority order, lowest first**:
  `CURATED (NATO+CB+HAM+GMRS+MURS) → saved_phrases → callsigns`.
- Callsigns capped at `max_callsigns`. When over the cap, keep the **last
  `max_callsigns` in contacts-file insertion order** (most-recently-added win,
  since there is no created-at field). If any dropped, `log()` the dropped
  count — never silent.
- Case-insensitive dedup keeping the **highest-priority (latest) occurrence**, so
  a term shared between a curated set and a callsign survives as the callsign.
- Returns the ordered list. Framing + token-budget trim happen downstream in the
  transcriber (the engine boundary).

### 2. `backend/stt/transcriber.py` (modified)

`_build_prompt(phrases)` changes from "join everything" to "frame + trim":

- Assembles `"GMRS radio. " + ", ".join(phrases) + "."`.
- Trims **from the front** (low-priority curated vocab) until under a
  conservative char budget (`~700 chars` ≈ ~200 tokens, headroom under 224 —
  module constant with an explanatory comment; validated via eval). The tail
  (callsigns + saved phrases) always survives.
- `update_prompt()` (57–59) and the transcribe call (79) unchanged.

### 3. `backend/stt/worker.py` (modified semantics only)

`update_phrases()` (235–243) keeps its signature and dual-cache propagation.
Callers now pass the **fully assembled** list (vocab + phrases + callsigns)
instead of raw `saved_phrases`. Live update, no restart.

### 4. `backend/server.py` (orchestration — owns both data sources)

New helper:

```python
def _rebuild_stt_vocabulary():
    # Ordered, deduped callsigns in contacts-file insertion order (NOT the
    # unordered known_callsigns() set) so the insertion-order cap is meaningful.
    callsigns = ordered_callsigns(_contacts_store.get_all())
    phrases = vocab.assemble_phrases(
        callsigns, _config.saved_phrases,
        max_callsigns=_config.stt_vocab_max_callsigns,
    )
    _stt_worker.update_phrases(phrases)
```

`ordered_callsigns()` is a small helper (in `contacts.py`, beside
`known_callsigns`) that walks contacts in file order, emits each populated
callsign field (`callsign`, `gmrs_callsign`, `ham_callsign`) normalized and
uppercased, skips `"ALL"` and blanks, and dedups preserving first appearance.

Wired into:

- **Startup** — once after the worker/engines initialize (replaces passing raw
  `saved_phrases` at load).
- **`set_server_config`** handler (1651–1658) — replaces the direct
  `update_phrases(saved_phrases)` call.
- **`add_contact` / `update_contact` / `delete_contact`** handlers — auto-refresh.
- **New `rescan_vocabulary` WS message** — manual forced rebuild; returns the
  resulting phrase count (and callsign count) for a UI toast.

### 5. `backend/config.py` (modified)

- Add `stt_vocab_max_callsigns` (default `100`).
- Trim the hardcoded `saved_phrases` default (164–168) to empty.

### 6. Frontend (one button)

A **"Rescan vocabulary"** button in the settings dialog → sends
`rescan_vocabulary` → toast like "Biasing 142 terms (88 callsigns)." Auto-refresh
needs no UI.

## Data flow

```
contact add/edit/delete ─┐
phrase change ───────────┼─► _rebuild_stt_vocabulary()
rescan_vocabulary (WS) ──┘        │
startup ─────────────────────────┘
        │
        ├─ known_callsigns(contacts)        (contacts.py:54)
        ├─ config.saved_phrases
        ▼
   vocab.assemble_phrases()  ── ordered low→high priority, deduped, callsigns capped
        ▼
   worker.update_phrases()   ── both engine caches
        ▼
   transcriber._build_prompt() ── frame + front-trim to ~700 chars
        ▼
   Whisper initial_prompt (tail survives = callsigns + saved phrases)
```

## Error handling / edge cases

- **Empty contacts + empty saved_phrases** → prompt is curated vocab only.
- **Callsign overflow** → cap at `max_callsigns`, keep newest, `log()` dropped count.
- **Budget overflow** → front-trim drops curated vocab first; callsigns/phrases kept.
- **Rebuild before worker ready** → guard on `_stt_worker` existence; no-op if not up.
- **Term in multiple sets** → deduped, highest-priority position retained.

## Testing

- **Unit (`vocab.assemble_phrases`)**: priority ordering (callsigns last), dedup
  precedence, callsign cap + drop-logging.
- **Unit (`transcriber._build_prompt`)**: front-trim keeps the tail under budget.
- **Backend WS**: `rescan_vocabulary` triggers rebuild; contact add/delete triggers
  rebuild (mock worker, assert `update_phrases` called with expected tail).
- **Frontend**: button sends message + renders toast (in `ServerConfigPanel/__tests__`).
- **Manual/eval**: real WER validation uses the existing `eval_stt` harness against
  a labelled corpus — not automated in this work.

## Out of scope (YAGNI)

- Per-category toggles or editable curated lists.
- Frequency/recency usage tracking for ranking.
- Switching to faster-whisper `hotwords`.
- Storing curated sets in `config.json`.
