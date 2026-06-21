# Hybrid STT: CPU streaming + GPU (ROCm) final pass

**Date:** 2026-06-21
**Status:** Design approved, pending spec review
**Target hardware (dev):** AMD Ryzen 9 6900HX + Radeon 680M iGPU (gfx1035), LMDE 7 / Debian 13

## Problem

Hearthwave's two-tier STT runs entirely on CPU. Users report both the streaming
partials and — especially — the whole-utterance final pass feeling slow,
particularly during back-to-back transmissions.

The current pipeline (`backend/stt/worker.py`):
- **Streaming tier:** faster-whisper `small.en`, int8 CPU, `cpu_threads = cores-1` (15).
- **Final tier:** faster-whisper `distil-large-v3`, int8 CPU, `cpu_threads = cores//2` (8),
  re-transcribing the whole utterance on a low-priority thread and broadcasting a
  replacing final.

On a 16-thread CPU, a running final pass (8 threads) contends with streaming
(15 threads) — oversubscription that stalls both. This contention is the most
likely cause of the reported slowness, more than raw per-model speed.

## Evidence (benchmarks on this hardware)

Synthetic Piper-TTS clips; `×realtime` = audio_len / processing_time; min of 3 runs.

**Streaming (small.en):**

| Device | short 4.7s | long 23.7s |
|---|---|---|
| CPU faster-whisper int8 | 3.4× | 8.3× |
| 680M transformers fp16 | 2.1× | 3.1× |

→ **CPU streaming is strictly faster.** Moving streaming to the GPU is a regression.
Streaming stays on CPU.

**Final pass — model shootout on the 680M (fp16, long-form):**

| Model | long 23.7s | xlong 38.7s | WER |
|---|---|---|---|
| distil-large-v3 | 5.3s (4.5×) | 10.6s (3.7×) | 7.3% / 6.9% |
| large-v3-turbo | 7.4s (3.2×) | 15.2s (2.5×) | 4.9% / 6.9% |

→ **distil-large-v3 chosen:** ~40% faster on the long utterances that hurt, accuracy a
wash (tied at 6.9% on the 39s clip), and it matches the current config.

Raw GPU-vs-CPU final-pass speed is roughly a tie (GPU ~10% faster at the app's
8-thread CPU cap). **The real bet is contention relief:** offloading the final pass
to the GPU frees CPU cores so streaming no longer stalls during finalization. The
validation plan must prove this; if it doesn't hold, the CPU fallback leaves behavior
unchanged from today.

## Goals

- Run the final pass on the Radeon 680M via ROCm; keep streaming on CPU.
- No regression to streaming latency or accuracy.
- Graceful, automatic fallback to the current CPU final pass when no ROCm GPU is
  present or GPU inference fails. Streaming is never affected by final-pass failures.
- Correct long-form handling for utterances up to `stt_final_max_s` (60s).

## Non-goals

- Changing the streaming engine/model.
- TTS / Piper / ONNX Runtime changes.
- NPU / OpenVINO paths.
- Supporting ROCm on officially-unsupported configs beyond this dev box (best-effort
  via `HSA_OVERRIDE_GFX_VERSION=10.3.0`).

## Architecture

Streaming path is untouched. Only the final-pass transcriber gains a GPU
implementation, selected at load time, behind the existing
`_load_final_transcriber()` seam in `worker.py`.

### Components

**1. `backend/stt/_prompt.py` (new) — shared logic**
Extract from `WhisperTranscriber` so both transcribers share one implementation:
- `build_prompt(phrases, *, count_tokens) -> str` (current `_build_prompt`)
- prompt token-budget trimming (`_MAX_PROMPT_TOKENS = 220`)
- `is_hallucination(text) -> bool` (the `HALLUCINATIONS` + empty/normalized check)

`WhisperTranscriber` (CPU) is refactored to call these; behavior identical.

**2. `backend/stt/gpu_transcriber.py` (new) — `GpuWhisperTranscriber`**
`transformers` Whisper on ROCm, exposing the exact interface the final pass calls:
- `load(model, saved_phrases=(), *, cpu_threads=None) -> GpuWhisperTranscriber`
  - `AutoProcessor` + `AutoModelForSpeechSeq2Seq`, `torch_dtype=float16`, `.to("cuda")`.
  - Builds prompt via `processor.get_prompt_ids()`; token counter from the HF tokenizer.
  - Pre-warms one short `generate()` to absorb first-call kernel-compile latency.
  - `cpu_threads` accepted and ignored (interface parity).
- `transcribe(audio, *, vad_filter=False, drop_low_confidence=False) -> str | None`
  - Uses `model.generate(..., return_timestamps=True, language="en", task="transcribe",
    num_beams=5, prompt_ids=...)` — Whisper's **native** long-form algorithm, not the
    pipeline's experimental `chunk_length_s` (per HF guidance), so >30s utterances are
    handled correctly.
  - `vad_filter` / `drop_low_confidence` are accepted for interface parity; the final
    pass calls both `False`, so per-segment `no_speech_prob`/`avg_logprob` filtering is
    not needed. Applies `is_hallucination()` drop and returns `None` on empty/hallucination.
- `update_prompt(saved_phrases=())` — rebuild prompt_ids.

**3. `backend/stt/worker.py` — backend selection + fallback**
In `_load_final_transcriber()`:
- Read new config `stt_final_device` (`"auto" | "gpu" | "cpu"`, default `"auto"`).
- Resolve: `auto` → GPU if `torch.version.hip` and `torch.cuda.is_available()`, else CPU.
- `gpu` → load `GpuWhisperTranscriber` from the HF-format model dir.
- `cpu` (or any GPU failure) → load CPU `WhisperTranscriber` (today's behavior); on a
  further failure, return `None` → plain finals. Wrap GPU load + pre-warm in try/except;
  log and fall back. Streaming is never touched by this path.
- `ModelCache.whisper_final` / `final_model_name` caching is preserved for both types;
  `update_prompt` works on both.

**4. Model staging — `bootstrap_models.py`, `setup.sh`**
The GPU path needs the HF-format repo `distil-whisper/distil-large-v3` (not the CT2
`Systran/faster-distil-whisper-large-v3`). Add format-aware fetch:
- CT2 final model → `Models/STT/<name>/` (unchanged).
- HF final model → `Models/STT/<name>-hf/` (new), so the two formats never collide.
- `worker.py` resolves the final-model path by selected device (`-hf` suffix for GPU).
- `setup.sh --final-model <name>` stages the format matching `COMPUTE_BACKEND`.

**5. Deployment — Docker ROCm (`COMPUTE_BACKEND=rocm`)**
- `backend/Dockerfile`: add a `rocm` branch installing `torch torchaudio` from
  `https://download.pytorch.org/whl/rocm6.4` plus `transformers accelerate`.
  **Image grows ~3–4 GB.** Keep CPU baseline default.
- `docker-compose.yml`: when rocm, add
  - `devices: ["/dev/kfd", "/dev/dri"]`
  - `group_add: ["992"]`  (host `render` GID — verify per host)
  - `environment: HSA_OVERRIDE_GFX_VERSION=10.3.0`
- `.env` / `.env.example`: document `COMPUTE_BACKEND=rocm`.
- `setup.sh` / `prereq.sh`: detect AMD GPU, ensure host user in `render`, stage HF model.

## Configuration

New key in `data/config.json` / `ServerConfig` (`backend/config.py`):
- `stt_final_device`: `"auto"` (default) | `"gpu"` | `"cpu"`.

Existing keys unchanged: `whisper_model`, `whisper_model_final`, `stt_final_max_s`.

## Error handling / fallback

- No ROCm GPU, or `stt_final_device="cpu"` → CPU faster-whisper final pass (today).
- GPU selected but load/pre-warm/inference throws → log error, fall back to CPU final
  transcriber; if that also fails, return `None` → plain finals.
- GPU OOM on a long utterance → caught per-job; that job falls back to a plain final
  (partials preserved), consistent with existing backlog/abandon handling.
- Streaming is fully independent and never affected by final-pass backend failures.

## Testing / validation

Unit:
- `_prompt.py` functions (prompt build, token-budget trim, hallucination drop) —
  port existing `WhisperTranscriber` tests; assert CPU transcriber behavior unchanged.
- `GpuWhisperTranscriber` with a CPU-mapped tiny model (skip/xfail if no GPU in CI):
  prompt biasing applied, hallucination/empty → `None`, long-form >30s returns full text.
- `_load_final_transcriber()` selection + fallback logic (mock torch/hw probes): auto→gpu,
  auto→cpu, gpu-failure→cpu, cpu-failure→None.

Integration / on-hardware (the decisive test):
- Concurrent load: stream a clip while a final pass runs; measure **streaming partial
  latency during finalization**, CPU-only-final vs GPU-final. Success = streaming
  partials no longer stall (the contention bet).
- Final-pass wall-time for ~24s and ~40s utterances ≤ current CPU times.
- Final-pass WER within ~1–2% of the CPU distil-large-v3 baseline.
- Fallback verified by forcing `stt_final_device="cpu"` and by hiding the GPU.

## Risks

- **Contention bet may not pay off:** GPU and CPU share the APU's power/memory budget;
  GPU finalization could throttle CPU streaming. Mitigation: the integration test gates
  the whole effort; CPU fallback preserves today's behavior.
- **Docker image size** grows ~3–4 GB; longer builds/pulls.
- **Unsupported GPU/distro:** relies on `HSA_OVERRIDE_GFX_VERSION=10.3.0`; treat as
  best-effort, with auto-fallback to CPU on any other host.
- **First-final latency:** kernel compile on first GPU `generate`; mitigated by pre-warm
  at load.

## Rollback

Set `COMPUTE_BACKEND=cpu` (rebuild) or `stt_final_device="cpu"` (no rebuild). Both restore
the current CPU-only pipeline with no code revert required.
