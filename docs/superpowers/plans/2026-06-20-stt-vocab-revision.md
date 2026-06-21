# STT Vocabulary Biasing — Revision Plan (token-budget reality)

Follows the implemented 6-task plan. Driven by tokenizer measurements
(faster-whisper 1.2.1, `small.en`): full curated set = 221 tokens (the whole
~223 budget); callsigns ≈ 6 tokens each. See the spec's "Revision" section.

**Global constraints:**
- Whisper initial_prompt ceiling ≈ 223 tokens; use `_MAX_PROMPT_TOKENS = 220`.
- Curated core = 40 terms (26 NATO + 14 procedure/Q) = 111 tokens.
- `stt_vocab_max_callsigns` default = 15.
- No Co-Authored-By trailers.
- Measured baselines: core-only ≈ 111 tokens; core + 15 callsigns ≈ 205 tokens.

---

### Task 8: Trim curated set to high-value core + lower callsign cap

**Files:**
- Modify: `backend/stt/vocab.py` (the curated tuples + `CURATED`)
- Modify: `backend/config.py` (`stt_vocab_max_callsigns` default)
- Test: `backend/tests/unit/stt/test_vocab.py`, `backend/tests/unit/test_config.py`

- [ ] **Step 1: Update the failing tests first.**

In `test_vocab.py`, replace `test_curated_sets_present` with one asserting the
new core and the removal of the dropped sets:

```python
def test_curated_core_is_nato_plus_procedure():
    # NATO fully present
    assert "Alfa" in vocab.CURATED and "Zulu" in vocab.CURATED
    # key procedure words / Q-codes present
    for t in ("over", "roger", "say again", "standing by", "QSL", "CQ"):
        assert t in vocab.CURATED
    # CB slang and band-identifier extras were dropped from the core
    for t in ("breaker", "kerchunk", "MURS", "good buddy", "ratchet jaw"):
        assert t not in vocab.CURATED
    assert len(vocab.CURATED) == 40
```

The other vocab tests (`test_callsigns_come_last...`, `test_dedup...`,
`test_callsign_cap...`) use synthetic phrases/callsigns, not curated membership,
and stay as-is — confirm they still pass after the trim. (The dedup test uses
`"QSL"`, which remains in the core, so it is unaffected.)

In `test_config.py`, change the default assertion:

```python
def test_stt_vocab_max_callsigns_default():
    assert ServerConfig().stt_vocab_max_callsigns == 15
```

Run `python -m pytest backend/tests/unit/stt/test_vocab.py backend/tests/unit/test_config.py -v` — confirm the two changed tests FAIL.

- [ ] **Step 2: Implement.** In `vocab.py`, replace the five set tuples + `CURATED` with the trimmed core (keep the ordered-tuple structure and module docstring):

```python
NATO: tuple[str, ...] = (
    "Alfa", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf", "Hotel",
    "India", "Juliett", "Kilo", "Lima", "Mike", "November", "Oscar", "Papa",
    "Quebec", "Romeo", "Sierra", "Tango", "Uniform", "Victor", "Whiskey",
    "X-ray", "Yankee", "Zulu",
)

# High-value procedure words and Q-codes. Kept deliberately small: the full
# curated set consumed Whisper's entire ~223-token initial_prompt budget,
# leaving no room for contact callsigns (~6 tokens each). See spec revision.
PROCEDURE: tuple[str, ...] = (
    "over", "out", "roger", "affirmative", "negative", "copy that",
    "say again", "standing by", "break break", "CQ", "QSL", "QSY", "QRZ",
    "seventy three",
)

CURATED: tuple[str, ...] = NATO + PROCEDURE
```

Delete the old `CB`, `HAM`, `GMRS`, `MURS` tuples. In `config.py`, change the
default: `return int(self.get("stt_vocab_max_callsigns", 15))` and update its
comment to note callsigns are ~6 tokens each.

- [ ] **Step 3:** Re-run the two test files; confirm all pass (including the unchanged synthetic vocab tests).

- [ ] **Step 4: Commit** `feat(stt): trim curated vocab to NATO+procedure core; cap callsigns at 15`.

---

### Task 9: Token-accurate prompt budgeting in transcriber

**Files:**
- Modify: `backend/stt/transcriber.py`
- Test: `backend/tests/unit/stt/test_transcriber.py`

**Interfaces:**
- `_build_prompt(phrases, *, count_tokens) -> str` — staticmethod, pure; trims
  from the FRONT while `count_tokens(prompt) > _MAX_PROMPT_TOKENS`.
- `__init__`/`update_prompt` pass `self._count_tokens`, built from the model.

- [ ] **Step 1: Update tests first.** Replace the three `build_prompt` tests
(which assert the old `_MAX_PROMPT_CHARS` char behavior) with token-aware ones
using an injected fake counter (1 token per whitespace-split word, so tests are
deterministic and need no model):

```python
def _wordcount(s):  # fake tokenizer: 1 token per word
    return len(s.split())


def test_build_prompt_empty_returns_base():
    from backend.stt.transcriber import WhisperTranscriber
    assert WhisperTranscriber._build_prompt([], count_tokens=_wordcount) == "GMRS radio."


def test_build_prompt_frames_phrases():
    from backend.stt.transcriber import WhisperTranscriber
    out = WhisperTranscriber._build_prompt(["over", "KE8AAA"], count_tokens=_wordcount)
    assert out == "GMRS radio. Phrases: over, KE8AAA."


def test_build_prompt_token_trims_keeping_tail():
    from backend.stt.transcriber import WhisperTranscriber
    # Force a tiny budget by using a counter that overcounts, proving the
    # front is dropped and the high-priority tail token survives.
    phrases = [f"term{i}" for i in range(300)] + ["KE8ZZZ"]
    out = WhisperTranscriber._build_prompt(phrases, count_tokens=_wordcount)
    assert _wordcount(out) <= WhisperTranscriber._MAX_PROMPT_TOKENS
    assert out.endswith("KE8ZZZ.")
    assert "term0," not in out
```

Run `python -m pytest backend/tests/unit/stt/test_transcriber.py -k build_prompt -v` — confirm FAIL.

- [ ] **Step 2: Implement.** Replace the `_MAX_PROMPT_CHARS` constant with
`_MAX_PROMPT_TOKENS = 220` (comment: ~223-token Whisper ceiling, margin). Rewrite
`_build_prompt` as a pure staticmethod taking `count_tokens`:

```python
    # Whisper keeps only ~223 prompt tokens (the tail). Callers order phrases
    # lowest-priority-first, so trimming from the front drops generic vocab
    # while callsigns/custom phrases survive. 220 leaves a small margin.
    _MAX_PROMPT_TOKENS = 220

    @staticmethod
    def _build_prompt(phrases, *, count_tokens) -> str:
        base = "GMRS radio."
        phrases = [p for p in (phrases or []) if p]
        if not phrases:
            return base
        while phrases:
            prompt = f"{base} Phrases: {', '.join(phrases)}."
            if count_tokens(prompt) <= WhisperTranscriber._MAX_PROMPT_TOKENS:
                return prompt
            phrases.pop(0)
        return base
```

Add a token-counter factory and wire `__init__`/`update_prompt` to it:

```python
    @staticmethod
    def _make_token_counter(model):
        """Return a callable(str)->int. Uses the model's Whisper tokenizer when
        available; falls back to a coarse char/4 heuristic (e.g. in unit tests
        with no model)."""
        tok = getattr(model, "hf_tokenizer", None)
        if tok is not None:
            return lambda s: len(tok.encode(s).ids)
        return lambda s: max(1, len(s) // 4)
```

In `__init__`, after `self.model = model`:
```python
        self._count_tokens = self._make_token_counter(model)
        self.initial_prompt = self._build_prompt(saved_phrases, count_tokens=self._count_tokens)
```
In `update_prompt`:
```python
        self.initial_prompt = self._build_prompt(saved_phrases, count_tokens=self._count_tokens)
```

- [ ] **Step 3:** Re-run the build_prompt tests; confirm pass. Then run the full
`python -m pytest backend/tests/unit/stt/ -q` to confirm no regressions (the
`WhisperTranscriber` is constructed with real/fake models elsewhere — if any
test constructs it with a bare object lacking `hf_tokenizer`, the heuristic
fallback covers it).

- [ ] **Step 4: Commit** `feat(stt): token-accurate prompt budget via model tokenizer`.

---

### Task 10: Final-pass engine live refresh (review Important #1)

**Files:**
- Modify: `backend/stt/worker.py` (`update_phrases`, ~235-243)
- Test: `backend/tests/unit/stt/` (add a worker-level test)

- [ ] **Step 1:** First READ `worker.py` to confirm the model-cache attribute
name for the final-pass transcriber (the review identified `whisper_final` on
the cache object; verify against the actual `_model_cache` structure and the
`_load_final_transcriber`/`_final_pass_loop` code, ~700-792). Use the real
attribute name.

- [ ] **Step 2: Write the failing test.** Construct an `STTWorker`, set its
`_model_cache` to a fake object exposing `.whisper` and the final attr (both
with an `update_prompt` mock recording calls), call `update_phrases([...])`, and
assert BOTH caches' `update_prompt` were called with the new list. Match the
existing worker-test construction pattern in the repo (see how other
`backend/tests/unit/stt/` tests build a worker / fake cache). Confirm it FAILS
(current code refreshes only `.whisper`).

- [ ] **Step 3: Implement.** In `update_phrases`, after refreshing the fast
cache, refresh the final cache when present:

```python
        self.saved_phrases = list(phrases)
        if self._model_cache is not None:
            self._model_cache.whisper.update_prompt(self.saved_phrases)
            final = getattr(self._model_cache, "<FINAL_ATTR>", None)
            if final is not None:
                final.update_prompt(self.saved_phrases)
```

(Replace `<FINAL_ATTR>` with the confirmed attribute name from Step 1.)

- [ ] **Step 4:** Re-run the new test + `python -m pytest backend/tests/unit/stt/ -q`; confirm pass.

- [ ] **Step 5: Commit** `fix(stt): refresh final-pass engine on live phrase update`.
