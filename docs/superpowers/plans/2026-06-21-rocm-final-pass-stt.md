# ROCm GPU Final-Pass STT Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run Hearthwave's whole-utterance STT final pass on the AMD Radeon 680M via ROCm, keeping the streaming tier on CPU, with automatic CPU fallback.

**Architecture:** The streaming path is untouched. A new `GpuWhisperTranscriber` (transformers Whisper, fp16, ROCm) is selected behind the existing `STTWorker._load_final_transcriber()` seam based on a `stt_final_device` config key and a runtime ROCm probe; any GPU failure falls back to today's CPU faster-whisper final pass, then to plain finals. Prompt-building and hallucination-drop logic is extracted into a shared module so both transcribers stay DRY.

**Tech Stack:** Python 3.13, faster-whisper (CPU, CTranslate2), transformers + torch (ROCm 6.4 wheels), Docker Compose, pytest.

## Global Constraints

- Streaming tier (faster-whisper `small.en`, CPU int8) MUST NOT change behavior.
- GPU final-pass model: `distil-whisper/distil-large-v3` (HF transformers format), fp16, `num_beams=5`.
- GPU long-form (>30s) MUST use native `model.generate(..., return_timestamps=True)` with `truncation=False` features — NOT the pipeline's experimental `chunk_length_s`.
- Final-pass `transcribe()` is always called with `vad_filter=False, drop_low_confidence=False`; per-segment confidence filtering is not required on the GPU path.
- Any GPU load/inference failure falls back to CPU faster-whisper, then to plain finals. Streaming is never affected by final-pass failures.
- ROCm host env: `HSA_OVERRIDE_GFX_VERSION=10.3.0`; container needs `/dev/kfd`, `/dev/dri`, and host `render` GID (992 on the dev box — verify per host).
- Existing public symbols `WhisperTranscriber._build_prompt` and `WhisperTranscriber._MAX_PROMPT_TOKENS` MUST remain importable (existing tests depend on them).
- TDD: write the failing test first; commit after each green task.
- Run unit tests with: `~/torch-rocm/bin/python -m pytest <path> -v` from `~/Hearthwave` (the venv has pytest-asyncio; the stt conftest stubs ML deps).

---

### Task 1: Extract shared prompt + hallucination logic into `backend/stt/_prompt.py`

**Files:**
- Create: `backend/stt/_prompt.py`
- Modify: `backend/stt/transcriber.py`
- Test: `backend/tests/unit/stt/test_prompt.py` (create), `backend/tests/unit/stt/test_transcriber.py` (must still pass unchanged)

**Interfaces:**
- Produces:
  - `MAX_PROMPT_TOKENS: int = 220`
  - `build_prompt(phrases, *, count_tokens) -> str`
  - `is_hallucination(text: str) -> bool` — True when `text` is empty or its normalized form is in `constants.HALLUCINATIONS`.

- [ ] **Step 1: Write the failing test** — `backend/tests/unit/stt/test_prompt.py`

```python
"""Unit tests for shared STT prompt + hallucination helpers."""
from backend.stt._prompt import build_prompt, is_hallucination, MAX_PROMPT_TOKENS


def _wordcount(s):  # fake tokenizer: 1 token per word
    return len(s.split())


def test_empty_returns_base():
    assert build_prompt([], count_tokens=_wordcount) == "GMRS radio."


def test_single_phrase_framed():
    assert build_prompt(["break break"], count_tokens=_wordcount) == (
        "GMRS radio. Phrases: break break."
    )


def test_token_trim_keeps_tail():
    phrases = [f"term{i}" for i in range(300)] + ["KE8ZZZ"]
    out = build_prompt(phrases, count_tokens=_wordcount)
    assert _wordcount(out) <= MAX_PROMPT_TOKENS
    assert out.endswith("KE8ZZZ.")
    assert "term0," not in out


def test_is_hallucination_empty():
    assert is_hallucination("") is True
    assert is_hallucination("   ") is True


def test_is_hallucination_known_phrase():
    # "you" is a canonical Whisper-on-silence hallucination in constants.HALLUCINATIONS
    assert is_hallucination("You.") is True


def test_is_hallucination_real_text():
    assert is_hallucination("unit seven en route") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `~/torch-rocm/bin/python -m pytest backend/tests/unit/stt/test_prompt.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.stt._prompt'`

- [ ] **Step 3: Create `backend/stt/_prompt.py`**

```python
"""Shared STT helpers: Whisper initial-prompt construction and the
hallucination/empty-output drop. Used by both the CPU (faster-whisper) and
GPU (transformers) transcribers so the logic lives in exactly one place.
"""
from backend.constants import HALLUCINATIONS

# Whisper keeps only ~223 prompt tokens (the tail). Callers order phrases
# lowest-priority-first, so trimming from the front drops generic vocab
# while callsigns/custom phrases survive. 220 leaves a small margin.
MAX_PROMPT_TOKENS = 220

_BASE = "GMRS radio."


def build_prompt(phrases, *, count_tokens) -> str:
    """Frame saved phrases into a Whisper initial_prompt within the token budget.
    Trims from the front (lowest priority) until it fits."""
    phrases = [p for p in (phrases or []) if p]
    if not phrases:
        return _BASE
    while phrases:
        prompt = f"{_BASE} Phrases: {', '.join(phrases)}."
        if count_tokens(prompt) <= MAX_PROMPT_TOKENS:
            return prompt
        phrases.pop(0)
    return _BASE


def is_hallucination(text: str) -> bool:
    """True when text is empty or matches a known Whisper-on-silence hallucination."""
    if not text:
        return True
    normalized = text.lower().strip(".,!?;: ")
    return not normalized or normalized in HALLUCINATIONS
```

- [ ] **Step 4: Refactor `backend/stt/transcriber.py` to use the shared module**

Replace the `_MAX_PROMPT_TOKENS` constant, `_build_prompt` staticmethod, and the hallucination check inside `transcribe()` with delegations. Keep the old names as aliases so existing tests/imports keep working.

In `transcriber.py`, add near the top imports:
```python
from backend.stt._prompt import build_prompt, is_hallucination, MAX_PROMPT_TOKENS
```

Replace the `_MAX_PROMPT_TOKENS = 220` class attribute and its comment with:
```python
    # Kept as a class attribute alias for backward compatibility (tests import it).
    _MAX_PROMPT_TOKENS = MAX_PROMPT_TOKENS
```

Replace the `_build_prompt` staticmethod body with a delegation:
```python
    @staticmethod
    def _build_prompt(phrases, *, count_tokens) -> str:
        return build_prompt(phrases, count_tokens=count_tokens)
```

In `transcribe()`, replace the final block:
```python
        text = " ".join(kept).strip()
        normalized = text.lower().strip(".,!?;: ")
        if not text or normalized in HALLUCINATIONS:
            return None
        return text
```
with:
```python
        text = " ".join(kept).strip()
        if is_hallucination(text):
            return None
        return text
```

If `from backend.constants import HALLUCINATIONS` is now unused in `transcriber.py`, remove that import.

- [ ] **Step 5: Run both test files to verify they pass**

Run: `~/torch-rocm/bin/python -m pytest backend/tests/unit/stt/test_prompt.py backend/tests/unit/stt/test_transcriber.py -v`
Expected: PASS (all tests, including the pre-existing `_build_prompt`/`_MAX_PROMPT_TOKENS` tests)

- [ ] **Step 6: Commit**

```bash
git add backend/stt/_prompt.py backend/stt/transcriber.py backend/tests/unit/stt/test_prompt.py
git commit -m "refactor: extract shared STT prompt + hallucination helpers"
```

---

### Task 2: ROCm device probe `backend/stt/_device.py`

**Files:**
- Create: `backend/stt/_device.py`
- Test: `backend/tests/unit/stt/test_device.py` (create)

**Interfaces:**
- Produces: `rocm_available() -> bool` — True only when torch is importable, built with HIP, and `torch.cuda.is_available()` is True. Never raises.

- [ ] **Step 1: Write the failing test** — `backend/tests/unit/stt/test_device.py`

```python
"""Unit tests for the ROCm device probe."""
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

from backend.stt import _device


def _fake_torch(hip, cuda_ok):
    t = MagicMock()
    t.version = SimpleNamespace(hip=hip)
    t.cuda.is_available.return_value = cuda_ok
    return t


def test_true_when_hip_and_cuda(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", _fake_torch("6.4", True))
    assert _device.rocm_available() is True


def test_false_when_no_hip(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", _fake_torch(None, True))
    assert _device.rocm_available() is False


def test_false_when_cuda_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", _fake_torch("6.4", False))
    assert _device.rocm_available() is False


def test_false_when_torch_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", None)  # import torch -> ImportError
    assert _device.rocm_available() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `~/torch-rocm/bin/python -m pytest backend/tests/unit/stt/test_device.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.stt._device'`

- [ ] **Step 3: Create `backend/stt/_device.py`**

```python
"""Runtime probe for an available ROCm/HIP GPU usable by torch.

Isolated so the worker's backend selection can be unit-tested by stubbing torch.
"""
import logging

logger = logging.getLogger(__name__)


def rocm_available() -> bool:
    """True when torch is importable, built with HIP, and a GPU is visible.
    Never raises — any failure means 'no usable ROCm GPU'."""
    try:
        import torch
        return bool(getattr(torch.version, "hip", None)) and torch.cuda.is_available()
    except Exception as exc:  # ImportError, driver errors, etc.
        logger.info("ROCm GPU not available: %s", exc)
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `~/torch-rocm/bin/python -m pytest backend/tests/unit/stt/test_device.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/stt/_device.py backend/tests/unit/stt/test_device.py
git commit -m "feat: add rocm_available() device probe"
```

---

### Task 3: Add `stt_final_device` config key

**Files:**
- Modify: `backend/config.py` (add property after `stt_final_max_s`, ~line 80)
- Test: `backend/tests/unit/test_config_final_device.py` (create)

**Interfaces:**
- Produces: `ServerConfig.stt_final_device -> str` — one of `"auto"`, `"gpu"`, `"cpu"`; default `"auto"`; unknown values coerced to `"auto"`.

- [ ] **Step 1: Write the failing test** — `backend/tests/unit/test_config_final_device.py`

```python
from backend.config import ServerConfig


def test_default_is_auto():
    assert ServerConfig().stt_final_device == "auto"


def test_explicit_gpu():
    assert ServerConfig({"stt_final_device": "gpu"}).stt_final_device == "gpu"


def test_explicit_cpu():
    assert ServerConfig({"stt_final_device": "cpu"}).stt_final_device == "cpu"


def test_unknown_coerced_to_auto():
    assert ServerConfig({"stt_final_device": "tpu"}).stt_final_device == "auto"


def test_case_insensitive():
    assert ServerConfig({"stt_final_device": "GPU"}).stt_final_device == "gpu"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `~/torch-rocm/bin/python -m pytest backend/tests/unit/test_config_final_device.py -v`
Expected: FAIL with `AttributeError: 'ServerConfig' object has no attribute 'stt_final_device'`

- [ ] **Step 3: Add the property** in `backend/config.py` immediately after the `stt_final_max_s` property (after line 80):

```python
    @property
    def stt_final_device(self) -> str:
        """Where the whole-utterance final pass runs:
        'auto' (GPU if a ROCm GPU is present, else CPU), 'gpu', or 'cpu'."""
        val = str(self.get("stt_final_device", "auto")).strip().lower()
        return val if val in ("auto", "gpu", "cpu") else "auto"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `~/torch-rocm/bin/python -m pytest backend/tests/unit/test_config_final_device.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/config.py backend/tests/unit/test_config_final_device.py
git commit -m "feat: add stt_final_device config key"
```

---

### Task 4: `GpuWhisperTranscriber` (transformers / ROCm)

**Files:**
- Create: `backend/stt/gpu_transcriber.py`
- Modify: `backend/tests/unit/stt/conftest.py` (stub `torch`, `transformers`)
- Test: `backend/tests/unit/stt/test_gpu_transcriber.py` (create)

**Interfaces:**
- Consumes: `backend.stt._prompt.build_prompt`, `is_hallucination`.
- Produces: class `GpuWhisperTranscriber`:
  - `__init__(self, model, processor, saved_phrases=())`
  - `classmethod load(cls, model, saved_phrases=(), *, cpu_threads=None) -> GpuWhisperTranscriber`
  - `transcribe(self, audio, *, vad_filter=False, drop_low_confidence=False) -> str | None`
  - `update_prompt(self, saved_phrases=()) -> None`
  - attribute `initial_prompt: str`

Note: `torch` and `transformers` are imported lazily inside methods so the module imports cleanly in CI. Tests inject fake `model`/`processor` and stub `torch`.

- [ ] **Step 1: Add stubs to `backend/tests/unit/stt/conftest.py`**

Change the stub loop line:
```python
for _name in ("sounddevice", "faster_whisper", "silero_vad", "piper"):
    sys.modules.setdefault(_name, MagicMock())
```
to:
```python
for _name in ("sounddevice", "faster_whisper", "silero_vad", "piper", "torch", "transformers"):
    sys.modules.setdefault(_name, MagicMock())
```

- [ ] **Step 2: Write the failing test** — `backend/tests/unit/stt/test_gpu_transcriber.py`

```python
"""Unit tests for GpuWhisperTranscriber logic (no real GPU/torch)."""
from unittest.mock import MagicMock

import numpy as np

from backend.stt.gpu_transcriber import GpuWhisperTranscriber


class _FakeProcessor:
    """Minimal stand-in for a transformers WhisperProcessor."""
    def __init__(self):
        self.tokenizer = MagicMock()
        self.tokenizer.side_effect = lambda s: MagicMock(input_ids=list(range(len(s.split()))))
        self.gen_calls = []
        self.decoded = "unit seven en route"

    def get_prompt_ids(self, text, return_tensors=None):
        return MagicMock(name="prompt_ids")

    def __call__(self, audio, sampling_rate=16000, **kw):
        feats = MagicMock()
        feats.input_features.to.return_value = "FEATS"
        return feats

    def batch_decode(self, ids, skip_special_tokens=True):
        return [self.decoded]


class _FakeModel:
    def __init__(self):
        self.generate_kwargs = None

    def generate(self, feats, **kwargs):
        self.generate_kwargs = kwargs
        return MagicMock(name="token_ids")


def _make(decoded="unit seven en route", phrases=()):
    proc = _FakeProcessor()
    proc.decoded = decoded
    return GpuWhisperTranscriber(model=_FakeModel(), processor=proc, saved_phrases=phrases), proc


def test_initial_prompt_built():
    t, _ = _make(phrases=["over", "QSL"])
    assert t.initial_prompt == "GMRS radio. Phrases: over, QSL."


def test_transcribe_returns_decoded_text():
    t, _ = _make(decoded="unit seven en route")
    assert t.transcribe(np.zeros(16000, dtype=np.float32)) == "unit seven en route"


def test_transcribe_drops_hallucination():
    t, _ = _make(decoded="You.")
    assert t.transcribe(np.zeros(16000, dtype=np.float32)) is None


def test_transcribe_uses_beam_and_timestamps():
    t, _ = _make()
    t.transcribe(np.zeros(16000, dtype=np.float32))
    kw = t.model.generate_kwargs
    assert kw["num_beams"] == 5
    assert kw["return_timestamps"] is True
    assert kw["language"] == "en"
    assert kw["task"] == "transcribe"


def test_update_prompt_rebuilds():
    t, _ = _make(phrases=["old"])
    t.update_prompt(["new"])
    assert t.initial_prompt == "GMRS radio. Phrases: new."
```

- [ ] **Step 3: Run test to verify it fails**

Run: `~/torch-rocm/bin/python -m pytest backend/tests/unit/stt/test_gpu_transcriber.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.stt.gpu_transcriber'`

- [ ] **Step 4: Create `backend/stt/gpu_transcriber.py`**

```python
"""GPU final-pass transcriber: transformers Whisper on ROCm (fp16).

Mirrors the public interface of WhisperTranscriber that the STTWorker final
pass uses (load / transcribe / update_prompt) so the worker can swap backends
behind one seam. Used only for the whole-utterance final pass, which always
calls transcribe(vad_filter=False, drop_low_confidence=False) — so per-segment
confidence filtering is not implemented here.

torch/transformers are imported lazily so this module imports without them
present (unit tests stub both).
"""
import logging

from backend.stt._prompt import build_prompt, is_hallucination

logger = logging.getLogger(__name__)

_SR = 16000


class GpuWhisperTranscriber:
    def __init__(self, model, processor, saved_phrases=()):
        self.model = model
        self.processor = processor
        self._count_tokens = self._make_token_counter(processor)
        self.initial_prompt = build_prompt(saved_phrases, count_tokens=self._count_tokens)
        self._prompt_ids = self._encode_prompt(self.initial_prompt)

    @staticmethod
    def _make_token_counter(processor):
        tok = getattr(processor, "tokenizer", None)
        if tok is not None:
            return lambda s: len(tok(s).input_ids)
        return lambda s: max(1, len(s) // 4)

    def _encode_prompt(self, prompt):
        try:
            return self.processor.get_prompt_ids(prompt, return_tensors="pt")
        except Exception as exc:
            logger.warning("Could not encode prompt_ids: %s", exc)
            return None

    @classmethod
    def load(cls, model, saved_phrases=(), *, cpu_threads=None):
        """Load an HF Whisper model onto the GPU in fp16 and pre-warm it.
        cpu_threads is accepted for interface parity and ignored."""
        import torch
        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

        processor = AutoProcessor.from_pretrained(model)
        m = AutoModelForSpeechSeq2Seq.from_pretrained(
            model, torch_dtype=torch.float16, low_cpu_mem_usage=True
        ).to("cuda")
        inst = cls(m, processor, saved_phrases=saved_phrases)
        inst._prewarm()
        return inst

    def _prewarm(self):
        """Absorb first-call kernel-compile latency with one silent generate."""
        import numpy as np
        try:
            self.transcribe(np.zeros(_SR, dtype=np.float32))
        except Exception as exc:
            logger.info("GPU pre-warm skipped: %s", exc)

    def update_prompt(self, saved_phrases=()) -> None:
        self.initial_prompt = build_prompt(saved_phrases, count_tokens=self._count_tokens)
        self._prompt_ids = self._encode_prompt(self.initial_prompt)

    def transcribe(self, audio, *, vad_filter=False, drop_low_confidence=False):
        """Transcribe a whole utterance. vad_filter/drop_low_confidence are
        accepted for interface parity (final pass passes both False)."""
        import torch

        # truncation=False -> full-length features so generate() uses Whisper's
        # native sequential long-form algorithm for utterances > 30s.
        inputs = self.processor(
            audio, sampling_rate=_SR, return_tensors="pt", truncation=False,
            padding="longest", return_attention_mask=True,
        )
        feats = inputs.input_features.to("cuda", torch.float16)
        attn = getattr(inputs, "attention_mask", None)
        gen_kw = dict(
            language="en", task="transcribe", num_beams=5, return_timestamps=True,
        )
        if attn is not None:
            gen_kw["attention_mask"] = attn.to("cuda")
        if self._prompt_ids is not None:
            gen_kw["prompt_ids"] = self._prompt_ids.to("cuda")
        with torch.no_grad():
            ids = self.model.generate(feats, **gen_kw)
        text = self.processor.batch_decode(ids, skip_special_tokens=True)[0].strip()
        if is_hallucination(text):
            return None
        return text
```

- [ ] **Step 5: Run test to verify it passes**

Run: `~/torch-rocm/bin/python -m pytest backend/tests/unit/stt/test_gpu_transcriber.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/stt/gpu_transcriber.py backend/tests/unit/stt/test_gpu_transcriber.py backend/tests/unit/stt/conftest.py
git commit -m "feat: add GpuWhisperTranscriber (transformers/ROCm final pass)"
```

---

### Task 5: Worker backend selection + fallback + server wiring

**Files:**
- Modify: `backend/stt/worker.py` (constructor ~line 105-166; `_load_final_transcriber` ~line 725-758)
- Modify: `backend/server.py` (`_make_stt_worker` ~line 481-496)
- Test: `backend/tests/unit/stt/test_final_backend_select.py` (create)

**Interfaces:**
- Consumes: `backend.stt._device.rocm_available`, `backend.stt.gpu_transcriber.GpuWhisperTranscriber`, `backend.stt.transcriber.WhisperTranscriber`.
- Produces: `STTWorker.__init__` gains `stt_final_device: str = "auto"`; stored as `self.stt_final_device`. `_load_final_transcriber()` selects GPU vs CPU and falls back to CPU on GPU failure, returning a transcriber or `None`.

- [ ] **Step 1: Write the failing test** — `backend/tests/unit/stt/test_final_backend_select.py`

```python
"""Selection + fallback logic for the final-pass transcriber backend."""
import asyncio
from unittest.mock import MagicMock

import backend.stt.worker as worker_mod
from backend.stt.worker import STTWorker


def _worker(tmp_path, device, monkeypatch):
    # Make both the CT2 and HF model dirs exist so path checks pass.
    models = tmp_path / "Models" / "STT"
    (models / "distil-large-v3").mkdir(parents=True)
    (models / "distil-large-v3-hf").mkdir(parents=True)
    monkeypatch.setattr(STTWorker, "_MODELS_DIR", models)
    w = STTWorker(
        out_queue=asyncio.Queue(),
        whisper_model_final="distil-large-v3",
        stt_final_device=device,
    )
    w._emit_status = lambda *a, **k: None
    w._emit_error = lambda *a, **k: None
    return w


def test_auto_uses_gpu_when_available(tmp_path, monkeypatch):
    monkeypatch.setattr(worker_mod, "rocm_available", lambda: True)
    gpu = MagicMock(name="gpu_inst")
    monkeypatch.setattr(worker_mod.GpuWhisperTranscriber, "load", lambda *a, **k: gpu)
    w = _worker(tmp_path, "auto", monkeypatch)
    assert w._load_final_transcriber() is gpu


def test_auto_uses_cpu_when_no_gpu(tmp_path, monkeypatch):
    monkeypatch.setattr(worker_mod, "rocm_available", lambda: False)
    cpu = MagicMock(name="cpu_inst")
    monkeypatch.setattr(worker_mod.WhisperTranscriber, "load", lambda *a, **k: cpu)
    w = _worker(tmp_path, "auto", monkeypatch)
    assert w._load_final_transcriber() is cpu


def test_gpu_failure_falls_back_to_cpu(tmp_path, monkeypatch):
    monkeypatch.setattr(worker_mod, "rocm_available", lambda: True)
    def boom(*a, **k):
        raise RuntimeError("hip error")
    monkeypatch.setattr(worker_mod.GpuWhisperTranscriber, "load", boom)
    cpu = MagicMock(name="cpu_inst")
    monkeypatch.setattr(worker_mod.WhisperTranscriber, "load", lambda *a, **k: cpu)
    w = _worker(tmp_path, "auto", monkeypatch)
    assert w._load_final_transcriber() is cpu


def test_forced_cpu_ignores_gpu(tmp_path, monkeypatch):
    monkeypatch.setattr(worker_mod, "rocm_available", lambda: True)
    cpu = MagicMock(name="cpu_inst")
    monkeypatch.setattr(worker_mod.WhisperTranscriber, "load", lambda *a, **k: cpu)
    # GpuWhisperTranscriber.load must NOT be called; make it explode if it is.
    monkeypatch.setattr(worker_mod.GpuWhisperTranscriber, "load",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("gpu used")))
    w = _worker(tmp_path, "cpu", monkeypatch)
    assert w._load_final_transcriber() is cpu
```

- [ ] **Step 2: Run test to verify it fails**

Run: `~/torch-rocm/bin/python -m pytest backend/tests/unit/stt/test_final_backend_select.py -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'stt_final_device'` (and `worker_mod` has no `rocm_available`/`GpuWhisperTranscriber`).

- [ ] **Step 3: Add imports + constructor param in `backend/stt/worker.py`**

Add to the imports block (near the other `from backend.stt...` imports, ~line 42):
```python
from backend.stt.gpu_transcriber import GpuWhisperTranscriber
from backend.stt._device import rocm_available
```

In `STTWorker.__init__`, add a parameter (alongside `whisper_model_final` / `final_max_s`, ~line 121):
```python
        stt_final_device: str = "auto",
```
and store it (near where `self.whisper_model_final` is set, ~line 162):
```python
        self.stt_final_device = stt_final_device
```

- [ ] **Step 4: Rewrite `_load_final_transcriber` in `backend/stt/worker.py`**

Replace the whole method (currently ~line 725-758) with:
```python
    def _resolve_final_backend(self) -> str:
        """'gpu' or 'cpu' — honoring config and GPU availability."""
        if self.stt_final_device == "cpu":
            return "cpu"
        if self.stt_final_device == "gpu":
            return "gpu"
        return "gpu" if rocm_available() else "cpu"

    def _final_model_path(self, backend: str) -> str:
        """CT2 dir for CPU, '<name>-hf' dir for the GPU transformers model."""
        name = self.whisper_model_final + ("-hf" if backend == "gpu" else "")
        return str(self._MODELS_DIR / name)

    def _load_one_final(self, backend: str):
        """Load a single backend's final transcriber, or None on missing dir."""
        path = self._final_model_path(backend)
        if not os.path.isdir(path):
            self._emit_error(
                f"Final-pass model not found at '{path}'. Run "
                f"'python bootstrap_models.py --final-model {self.whisper_model_final}' "
                f"(backend={backend}), then copy Models/ here. "
                f"Falling back to single-pass transcription."
            )
            return None
        self._emit_status(f"Loading final-pass model {self.whisper_model_final} ({backend})...")
        cores = os.cpu_count() or 2
        cls = GpuWhisperTranscriber if backend == "gpu" else WhisperTranscriber
        return cls.load(
            path, saved_phrases=self.saved_phrases, cpu_threads=max(1, cores // 2)
        )

    def _load_final_transcriber(self):
        """Lazy-load the final-pass model (cached across Listen toggles).
        Selects GPU vs CPU; any GPU failure falls back to CPU. Returns None
        only when no backend can load (caller then emits plain finals)."""
        cache = self._model_cache
        if (
            cache is not None
            and cache.whisper_final is not None
            and cache.final_model_name == self.whisper_model_final
        ):
            cache.whisper_final.update_prompt(self.saved_phrases)
            return cache.whisper_final

        backend = self._resolve_final_backend()
        transcriber = None
        if backend == "gpu":
            try:
                transcriber = self._load_one_final("gpu")
            except Exception as e:
                self._emit_error(f"GPU final-pass load failed ({e}); falling back to CPU.")
                transcriber = None
            if transcriber is None:
                backend = "cpu"
        if transcriber is None:
            try:
                transcriber = self._load_one_final("cpu")
            except Exception as e:
                self._emit_error(f"Failed to load final-pass model: {e}")
                return None

        if transcriber is not None and cache is not None:
            cache.whisper_final = transcriber
            cache.final_model_name = self.whisper_model_final
        return transcriber
```

- [ ] **Step 5: Wire config through `_make_stt_worker` in `backend/server.py`**

In the `STTWorker(...)` call (~line 481), add after `final_max_s=_config.stt_final_max_s,`:
```python
        stt_final_device=_config.stt_final_device,
```

- [ ] **Step 6: Run the new test + the existing worker final-pass tests**

Run: `~/torch-rocm/bin/python -m pytest backend/tests/unit/stt/test_final_backend_select.py backend/tests/unit/stt/test_worker_final_pass.py backend/tests/unit/stt/test_make_stt_worker.py -v`
Expected: PASS (selection/fallback green; existing final-pass + make-worker tests still pass — they stub `_load_final_transcriber` or pass through the new default `stt_final_device="auto"`).

- [ ] **Step 7: Commit**

```bash
git add backend/stt/worker.py backend/server.py backend/tests/unit/stt/test_final_backend_select.py
git commit -m "feat: select GPU/CPU final-pass backend with fallback"
```

---

### Task 6: Format-aware model staging

**Files:**
- Modify: `bootstrap_models.py`
- Modify: `setup.sh` (whisper fetch section ~line 155-166)
- Test: `backend/tests/unit/test_bootstrap_models.py` (create)

**Interfaces:**
- Produces in `bootstrap_models.py`:
  - `HF_FINAL_REPOS: dict[str, str]` mapping final-model name → HF transformers repo.
  - `final_target(name: str, backend: str) -> tuple[str, str]` returning `(repo_id, local_dir)` where `local_dir` is `Models/STT/<name>` for `cpu`/CT2 and `Models/STT/<name>-hf` for `gpu`/HF.
  - New CLI flag `--final-model NAME` and `--final-backend {cpu,gpu}` (default `cpu`).

- [ ] **Step 1: Write the failing test** — `backend/tests/unit/test_bootstrap_models.py`

```python
import bootstrap_models as bm


def test_cpu_final_uses_ct2_repo_and_plain_dir():
    repo, local = bm.final_target("distil-large-v3", "cpu")
    assert repo == "Systran/faster-distil-whisper-large-v3"
    assert local.replace("\\", "/").endswith("Models/STT/distil-large-v3")


def test_gpu_final_uses_hf_repo_and_hf_dir():
    repo, local = bm.final_target("distil-large-v3", "gpu")
    assert repo == "distil-whisper/distil-large-v3"
    assert local.replace("\\", "/").endswith("Models/STT/distil-large-v3-hf")


def test_unknown_final_model_raises():
    import pytest
    with pytest.raises(KeyError):
        bm.final_target("nope", "gpu")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `~/torch-rocm/bin/python -m pytest backend/tests/unit/test_bootstrap_models.py -v`
Expected: FAIL with `AttributeError: module 'bootstrap_models' has no attribute 'final_target'`

- [ ] **Step 3: Edit `bootstrap_models.py`**

Add after the existing `WHISPER_REPOS` dict:
```python
# HF transformers-format repos for the GPU final pass (distinct from the CT2
# faster-whisper repos above). Staged under Models/STT/<name>-hf/.
HF_FINAL_REPOS = {
    "distil-large-v3": "distil-whisper/distil-large-v3",
    "large-v3": "openai/whisper-large-v3",
    "large-v3-turbo": "openai/whisper-large-v3-turbo",
}


def final_target(name: str, backend: str):
    """Return (repo_id, local_dir) for a final-pass model and backend.
    backend 'cpu' -> CT2 faster-whisper repo, dir Models/STT/<name>.
    backend 'gpu' -> HF transformers repo, dir Models/STT/<name>-hf."""
    if backend == "gpu":
        return HF_FINAL_REPOS[name], os.path.join("Models", "STT", name + "-hf")
    return WHISPER_REPOS[name], os.path.join("Models", "STT", name)
```

Add CLI args in `main()` (after the existing `--model` argument):
```python
    parser.add_argument("--final-model", metavar="NAME", default=None,
                        help="Stage a final-pass model in the format for --final-backend.")
    parser.add_argument("--final-backend", choices=("cpu", "gpu"), default="cpu",
                        help="Format for --final-model: cpu (CT2) or gpu (HF transformers).")
```

Add staging logic in `main()` after the existing `for model in models:` loop (before `return 0`):
```python
    if args.final_model:
        repo_id, target = final_target(args.final_model, args.final_backend)
        os.makedirs(target, exist_ok=True)
        print(f"Final ({args.final_backend}): downloading {repo_id} -> {target}")
        snapshot_download(repo_id=repo_id, local_dir=target)
        print(f"Final: done. Loaded at runtime from {target}/")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `~/torch-rocm/bin/python -m pytest backend/tests/unit/test_bootstrap_models.py -v`
Expected: PASS

- [ ] **Step 5: Update `setup.sh`**

In `setup.sh`, the `repo_for_model()` helper and `fetch_whisper_model()` handle CT2 only. Add an HF-aware branch so `--final-model` stages the format matching `COMPUTE_BACKEND`. After the existing final-model fetch, add (adapt to the script's existing variable names `$FINAL_MODEL`, `$COMPUTE_BACKEND`):
```bash
# When COMPUTE_BACKEND=rocm, also stage the final model in HF transformers
# format (Models/STT/<name>-hf) for the GPU final pass.
if [[ -n "$FINAL_MODEL" && "${COMPUTE_BACKEND:-cpu}" == "rocm" ]]; then
  echo "==> Staging HF-format final model for GPU: ${FINAL_MODEL}"
  python3 bootstrap_models.py --final-model "$FINAL_MODEL" --final-backend gpu
fi
```

- [ ] **Step 6: Commit**

```bash
git add bootstrap_models.py setup.sh backend/tests/unit/test_bootstrap_models.py
git commit -m "feat: stage HF-format final model for GPU final pass"
```

---

### Task 7: Docker ROCm deployment wiring

**Files:**
- Modify: `backend/Dockerfile` (builder stage GPU-package branch ~line 17-22)
- Modify: `docker-compose.yml` (backend service)
- Modify: `.env.example`

**Interfaces:** None (deployment config). Verified by build + runtime probe, not unit tests.

- [ ] **Step 1: Add the `rocm` case to `backend/Dockerfile`**

In the builder stage, extend the conditional GPU-package install:
```dockerfile
RUN if [ "$COMPUTE_BACKEND" = "cuda" ]; then \
        pip install --no-cache-dir --prefix=/install onnxruntime-gpu; \
    elif [ "$COMPUTE_BACKEND" = "openvino" ]; then \
        pip install --no-cache-dir --prefix=/install openvino onnxruntime-openvino; \
    elif [ "$COMPUTE_BACKEND" = "rocm" ]; then \
        pip install --no-cache-dir --prefix=/install \
            --index-url https://download.pytorch.org/whl/rocm6.4 \
            torch torchaudio && \
        pip install --no-cache-dir --prefix=/install transformers accelerate; \
    fi
```

- [ ] **Step 2: Add GPU passthrough to `docker-compose.yml`**

Under `services.backend`, extend `devices` and add `group_add` + the HSA env var:
```yaml
    environment:
      - PULSE_SERVER=unix:/run/pulse/native
      - HSA_OVERRIDE_GFX_VERSION=${HSA_OVERRIDE_GFX_VERSION:-10.3.0}
    devices:
      - /dev/snd:/dev/snd
      - /dev/kfd:/dev/kfd
      - /dev/dri:/dev/dri
    group_add:
      - "${RENDER_GID:-992}"
```

(Keep the rest of the service unchanged. `/dev/kfd` and `/dev/dri` are harmless when unused on CPU-only hosts, but if you prefer strict separation, gate them via a `docker-compose.rocm.yml` override; the inline form above is simplest.)

- [ ] **Step 3: Document env vars in `.env.example`**

Update the `COMPUTE_BACKEND` comment and add the two new vars:
```bash
# Whisper hardware backend: cpu (default) | cuda | openvino | rocm
# 'rocm' runs the STT final pass on an AMD GPU (ROCm). Requires /dev/kfd +
# /dev/dri passthrough (configured in docker-compose.yml) and the host render group.
COMPUTE_BACKEND=cpu

# AMD ROCm only: gfx override so unsupported GPUs (e.g. Radeon 680M / gfx1035)
# present as a supported gfx1030. Leave default unless your GPU needs another.
HSA_OVERRIDE_GFX_VERSION=10.3.0

# AMD ROCm only: host 'render' group GID (run: getent group render). The
# container process joins this group to access /dev/kfd.
RENDER_GID=992
```

- [ ] **Step 4: Build the ROCm backend image**

Run:
```bash
cd ~/Hearthwave
COMPUTE_BACKEND=rocm docker compose build backend
```
Expected: build succeeds (note: pulls ~3-4 GB of torch ROCm wheels; first build is slow).

- [ ] **Step 5: Commit**

```bash
git add backend/Dockerfile docker-compose.yml .env.example
git commit -m "feat: ROCm (COMPUTE_BACKEND=rocm) Docker deployment for GPU final pass"
```

---

### Task 8: On-hardware validation (the contention bet)

**Files:**
- Create: `scripts/validate_final_pass.py` (a throwaway/utility validation script)

**Interfaces:** None. This task proves the design's core hypothesis before rollout; if it fails, the CPU fallback (`stt_final_device=cpu` or `COMPUTE_BACKEND=cpu`) keeps behavior unchanged.

- [ ] **Step 1: Stage the GPU final model**

Run:
```bash
cd ~/Hearthwave
~/torch-rocm/bin/python bootstrap_models.py --final-model distil-large-v3 --final-backend gpu
ls Models/STT/distil-large-v3-hf
```
Expected: HF model files present (`config.json`, `model.safetensors`, processor files).

- [ ] **Step 2: Write `scripts/validate_final_pass.py`**

```python
"""On-hardware validation for the GPU final pass.

Measures, for a long synthetic utterance:
  - GPU final-pass wall-time and WER vs the CPU baseline,
  - streaming-during-finalization stall: run small.en streaming repeatedly
    while a final pass runs on (a) CPU and (b) GPU, and compare streaming
    iteration latency. The GPU path should NOT inflate streaming latency.
Run with the ROCm env, e.g.:
  sg render -c 'HSA_OVERRIDE_GFX_VERSION=10.3.0 ~/torch-rocm/bin/python scripts/validate_final_pass.py'
"""
import os, time, threading, statistics
import numpy as np, librosa
from backend.stt.transcriber import WhisperTranscriber
from backend.stt.gpu_transcriber import GpuWhisperTranscriber

SR = 16000
LONG = librosa.load(os.path.expanduser(
    "/tmp/claude-1000/-home-wslz233/f29ecb82-b586-4e1d-aa1e-fc6d87003da1/scratchpad/stt-bench/xlong.wav"
), sr=SR, mono=True)[0].astype(np.float32)
SHORT = LONG[: int(4.0 * SR)]

stream = WhisperTranscriber.load(os.path.expanduser("~/Hearthwave/Models/STT/small.en"), cpu_threads=15)

def stream_latencies(n=8):
    out = []
    for _ in range(n):
        t = time.perf_counter(); stream.transcribe(SHORT, vad_filter=False); out.append(time.perf_counter()-t)
    return out

def run_with_final(final):
    done = threading.Event()
    def finalize():
        final.transcribe(LONG, vad_filter=False, drop_low_confidence=False); done.set()
    th = threading.Thread(target=finalize); th.start()
    lat = stream_latencies()
    th.join()
    return statistics.median(lat)

cpu_final = WhisperTranscriber.load(os.path.expanduser("~/Hearthwave/Models/STT/distil-large-v3"), cpu_threads=8)
gpu_final = GpuWhisperTranscriber.load(os.path.expanduser("~/Hearthwave/Models/STT/distil-large-v3-hf"))

base = statistics.median(stream_latencies())
cpu_lat = run_with_final(cpu_final)
gpu_lat = run_with_final(gpu_final)
print(f"streaming median latency (s): idle={base:.3f}  during-CPU-final={cpu_lat:.3f}  during-GPU-final={gpu_lat:.3f}")
print(f"GPU win = streaming stall reduced: {cpu_lat - gpu_lat:+.3f}s ({100*(cpu_lat-gpu_lat)/cpu_lat:+.1f}%)")
```

- [ ] **Step 3: Run the validation**

Run:
```bash
cd ~/Hearthwave
sg render -c 'HSA_OVERRIDE_GFX_VERSION=10.3.0 PYTORCH_HIP_ALLOC_CONF=expandable_segments:True ~/torch-rocm/bin/python scripts/validate_final_pass.py'
```
Expected/success: `during-GPU-final` streaming latency is materially lower than `during-CPU-final` (the contention relief). If it is NOT lower, the hypothesis fails — record the numbers and decide with the user whether to ship GPU final anyway (it's still ~no worse) or set `stt_final_device=cpu` as the default.

- [ ] **Step 4: Run the full STT unit suite**

Run: `~/torch-rocm/bin/python -m pytest backend/tests/unit/stt backend/tests/unit/test_config_final_device.py backend/tests/unit/test_bootstrap_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/validate_final_pass.py
git commit -m "test: on-hardware validation for GPU final-pass contention"
```

---

## Self-Review

**Spec coverage:**
- Streaming unchanged → enforced by Global Constraints + Task 5 only touching the final path. ✓
- New `GpuWhisperTranscriber` with interface parity → Task 4. ✓
- Shared `_prompt.py` → Task 1. ✓
- Backend selection + fallback + `stt_final_device` → Tasks 3, 5. ✓
- HF-format model staging (`-hf`) → Task 6. ✓
- Docker ROCm wiring (`/dev/kfd`, `/dev/dri`, `group_add`, HSA env) → Task 7. ✓
- Native long-form generate (not pipeline chunking) → Task 4 transcribe(), Global Constraints. ✓
- Validation gated on contention hypothesis → Task 8. ✓
- Rollback via config/build flag → preserved by fallback (Task 5) + `COMPUTE_BACKEND=cpu` (Task 7). ✓

**Placeholder scan:** No TBD/TODO; all code blocks complete; the only "adapt to existing variable names" note (Task 6 Step 5) references concrete vars (`$FINAL_MODEL`, `$COMPUTE_BACKEND`) the engineer will confirm in `setup.sh`. ✓

**Type consistency:** `build_prompt`/`is_hallucination`/`MAX_PROMPT_TOKENS` names consistent across Tasks 1/4. `rocm_available`, `GpuWhisperTranscriber.load(model, saved_phrases, cpu_threads=...)`, and `transcribe(audio, *, vad_filter, drop_low_confidence)` signatures consistent across Tasks 2/4/5. `final_target(name, backend)` consistent across Task 6. `stt_final_device` consistent across Tasks 3/5/7. ✓
