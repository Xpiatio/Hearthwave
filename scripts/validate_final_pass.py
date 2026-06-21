"""On-hardware validation for the GPU final pass (the contention hypothesis).

Measures whether running the whole-utterance final pass concurrently with the
CPU streaming pass inflates streaming latency, and whether offloading the final
pass to the GPU relieves that contention vs running it on CPU.

Run with the ROCm env, e.g.:
  sg render -c 'HSA_OVERRIDE_GFX_VERSION=10.3.0 ~/torch-rocm/bin/python scripts/validate_final_pass.py'
"""
import os, time, threading, statistics
import numpy as np, librosa
from backend.stt.transcriber import WhisperTranscriber
from backend.stt.gpu_transcriber import GpuWhisperTranscriber

SR = 16000
XLONG = os.environ.get(
    "XLONG_WAV",
    "/tmp/claude-1000/-home-wslz233/f29ecb82-b586-4e1d-aa1e-fc6d87003da1/scratchpad/stt-bench/xlong.wav",
)
LONG = librosa.load(XLONG, sr=SR, mono=True)[0].astype(np.float32)
SHORT = LONG[: int(4.0 * SR)]
M = os.path.expanduser("~/Hearthwave/Models/STT")

stream = WhisperTranscriber.load(os.path.join(M, "small.en"), cpu_threads=15)

def stream_latencies(n=8):
    out = []
    for _ in range(n):
        t = time.perf_counter(); stream.transcribe(SHORT, vad_filter=False); out.append(time.perf_counter() - t)
    return out

def run_with_final(final):
    def finalize():
        final.transcribe(LONG, vad_filter=False, drop_low_confidence=False)
    th = threading.Thread(target=finalize); th.start()
    lat = stream_latencies()
    th.join()
    return statistics.median(lat)

cpu_final = WhisperTranscriber.load(os.path.join(M, "distil-large-v3"), cpu_threads=8)
gpu_final = GpuWhisperTranscriber.load(os.path.join(M, "distil-large-v3-hf"))

base = statistics.median(stream_latencies())
cpu_lat = run_with_final(cpu_final)
gpu_lat = run_with_final(gpu_final)

print(f"\nstreaming median latency (s):")
print(f"  idle (no final)      : {base:.3f}")
print(f"  during CPU final pass: {cpu_lat:.3f}  (+{100*(cpu_lat-base)/base:.0f}% vs idle)")
print(f"  during GPU final pass: {gpu_lat:.3f}  (+{100*(gpu_lat-base)/base:.0f}% vs idle)")
print(f"\nGPU contention relief vs CPU final: {cpu_lat-gpu_lat:+.3f}s ({100*(cpu_lat-gpu_lat)/cpu_lat:+.1f}%)")
print("VERDICT:", "GPU helps (streaming stalls less)" if gpu_lat < cpu_lat * 0.95 else "no meaningful contention relief")
