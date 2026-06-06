# Audio Pipeline Design: Pre-roll Silence, Priority Mixer, AGC+LPF

**Date:** 2026-06-06
**Status:** Approved

---

## Overview

Three independent backend features that improve Radio-TTY's transmit reliability
and receive transcription accuracy:

1. **PTT Pre-roll Silence** — 300–500 ms of silence baked into the audio buffer
   after PTT is asserted, before the first TTS syllable plays.
2. **Priority Mixer** — audio-squelch-gated TX gate that discards outbound TTS
   if the channel is occupied when transmission starts or becomes occupied
   mid-playback.
3. **AGC + LPF** — lightweight low-pass filter applied per-chunk before
   squelch/VAD, plus dynamic attack/release AGC applied per-segment before
   Whisper.

---

## Architecture

Three feature tracks, each isolated to a clear layer of the stack:

```
Feature 1 ─ PTT Pre-roll
  config.py          ← new ptt_lead_in_ms property (default 350)
  ptt/serial_ptt.py  ← read lead_in_seconds from config at construction
  ptt/vox.py         ← same

Feature 2 ─ Priority Mixer
  stt/worker.py      ← expose channel_busy: threading.Event
                        set on squelch open, clear on squelch close
  tts/tx_mixer.py    ← new; wraps TTSSynthesizer
                        pre-check → chunked playback → mid-stream abort + discard
  server.py          ← wire channel_busy from STTWorker into TXMixer
                        call mixer.transmit() instead of synthesizer.synthesize()

Feature 3 ─ AGC + LPF
  audio/dsp.py       ← new make_lowpass_sos(), lowpass(), dynamic_agc()
  stt/worker.py      ← apply lowpass per-chunk (before squelch/VAD feed)
                        apply dynamic_agc in _transcription_loop (before Whisper)
```

No circular imports. `TXMixer` depends on `TTSSynthesizer` and
`threading.Event` only — it does not import `STTWorker`. The event is passed at
construction, keeping the two workers decoupled.

---

## Feature 1: PTT Pre-roll Silence

### Motivation

Radio hardware (especially VOX-activated rigs and relay-switched PTT) takes
10–200 ms to fully open the TX chain after the PTT line goes low. Without a
silence buffer, the first syllable of TTS audio is transmitted before the
transmitter is at full power, causing it to be cut off or distorted.

### Design

The existing architecture already supports lead-in silence: `PTT.lead_in_seconds`
is read by `TTSSynthesizer._synthesize_blocking()` and used to prepend a
zero-padded region to the int16 PCM buffer. The buffer is synthesized first,
then `ptt.key()` fires, then the whole buffer (silence + speech + tail) plays as
a single `sd.play()` call.

The only change needed is to make the lead-in duration configurable and raise the
default.

**`config.py`**

```python
@property
def ptt_lead_in_ms(self) -> int:
    """Silence to prepend after PTT key before TTS audio plays (ms)."""
    return int(self.get("ptt_lead_in_ms", 350))
```

**`ptt/serial_ptt.py`**

```python
class SerialPTT(PTT):
    tail_seconds = 0.05

    def __init__(self, port, line="RTS", lead_in_ms=350):
        self.lead_in_seconds = lead_in_ms / 1000.0
        ...
```

**`ptt/vox.py`**

```python
class VoxPTT(PTT):
    tail_seconds = 0.15

    def __init__(self, lead_in_ms=350):
        self.lead_in_seconds = lead_in_ms / 1000.0
```

**`ptt/factory.py`** — pass `config.ptt_lead_in_ms` when constructing either
class.

### Constraints

- `ManualPTT` is unchanged — the user keys and unkeys manually; pre-roll is their
  responsibility.
- `ptt_lead_in_ms` must be ≥ 0. Values above 1000 are silently clamped in the
  factory to prevent accidentally synthesizing multi-second silence buffers.

---

## Feature 2: Priority Mixer

### Motivation

When a family member transmits over the air, the hub's audio-squelch detector
opens. If the backend is simultaneously playing outbound TTS, it will transmit
over the incoming voice. The priority mixer discards outbound TTS when the channel
is occupied.

### Signal source

The existing `SquelchDetector` in `STTWorker._run()` already emits
`"squelch_opened"` / `"squelch_closed"` events via `segmenter.feed()`. These
events are used to set/clear a new `threading.Event` (`channel_busy`) exposed on
`STTWorker`.

### Design

**`stt/worker.py`** — new public attribute, set/cleared in the capture loop:

```python
class STTWorker:
    def __init__(self, ...):
        ...
        self.channel_busy = threading.Event()  # set=busy, clear=idle

    # Inside _run() capture loop, after segmenter.feed():
    for event in events:
        if event == "squelch_opened":
            self.channel_busy.set()
        elif event == "squelch_closed":
            self.channel_busy.clear()
        self._emit_capture_event(event)
```

**`tts/tx_mixer.py`** — new file:

```python
class TXMixer:
    """Priority gate around TTSSynthesizer.

    Discards outbound TTS if channel_busy is set before or during playback.
    Never requeues — callers treat a False return as a dropped transmission.
    """
    CHUNK_SAMPLES = 1024  # ~23 ms at 44.1 kHz; poll granularity during playback

    def __init__(self, synthesizer: TTSSynthesizer, channel_busy: threading.Event):
        self._synth = synthesizer
        self._busy = channel_busy

    async def transmit(self, voice, text, ptt, length_scale=1.0) -> bool:
        """Synthesize and play. Returns True if played, False if discarded."""
        if self._busy.is_set():
            await self._synth.out_queue.put({"event": "finished"})
            return False

        audio, sample_rate = await self._synth.synthesize_to_buffer(
            voice, text, ptt.lead_in_seconds, ptt.tail_seconds, length_scale
        )
        if audio is None:
            await self._synth.out_queue.put({"event": "finished"})
            return False

        await self._synth.out_queue.put({"event": "started"})
        try:
            ptt.key()
            aborted = await asyncio.to_thread(
                self._play_interruptible, audio, sample_rate
            )
        finally:
            ptt.unkey()
            await self._synth.out_queue.put({"event": "finished"})

        return not aborted

    def _play_interruptible(self, audio: np.ndarray, sample_rate: int) -> bool:
        """Chunked playback; returns True (aborted) if channel goes busy."""
        import sounddevice as sd
        pos = 0
        while pos < len(audio):
            if self._busy.is_set():
                sd.stop()
                return True
            chunk = audio[pos:pos + self.CHUNK_SAMPLES]
            sd.play(chunk, samplerate=sample_rate, blocking=True)
            pos += self.CHUNK_SAMPLES
        return False
```

**`server.py`** — at startup, construct `TXMixer` with the worker's
`channel_busy` event. Replace all `synthesizer.synthesize()` call sites with
`await mixer.transmit(...)`.

### Invariants

- `ptt.unkey()` always fires, even on abort — the TX chain is never left keyed.
- `"finished"` event is always emitted — downstream consumers (UI status) never
  hang waiting for it.
- Mid-stream abort latency ≤ `CHUNK_SAMPLES / sample_rate` ≈ 23 ms.
- If `channel_busy` is never cleared (squelch stuck open), every outbound
  transmission is discarded. This is logged at WARNING level.

---

## Feature 3: AGC + LPF

### Motivation

The existing pipeline applies a 300–3000 Hz bandpass + one-shot RMS
normalization to each audio segment before Whisper. Two gaps:

1. The squelch detector and VAD model see the raw, unfiltered audio — high-
   frequency noise above 3 kHz can cause the squelch threshold to react to
   noise bursts rather than voice.
2. RMS normalization is applied once per segment using the full-segment mean.
   A segment where someone starts quiet and gets louder (or vice versa) is
   under-normalized at one end.

### Design

**`audio/dsp.py`** — three new functions:

```python
def make_lowpass_sos(sample_rate: int, cutoff_hz: float = 2700, order: int = 4):
    """Butterworth low-pass for per-chunk stream filtering (causal path)."""
    from scipy.signal import butter
    nyquist = sample_rate / 2
    return butter(order, cutoff_hz / nyquist, btype="low", output="sos")


def lowpass(audio: np.ndarray, sos) -> np.ndarray:
    """Causal (sosfilt) low-pass. Used per-chunk; no look-ahead latency."""
    from scipy.signal import sosfilt
    return sosfilt(sos, audio).astype(np.float32)


def dynamic_agc(
    audio: np.ndarray,
    sample_rate: int,
    target_dbfs: float = -20.0,
    attack_ms: float = 10.0,
    release_ms: float = 100.0,
    chunk_ms: float = 20.0,
) -> np.ndarray:
    """Per-chunk attack/release AGC applied to a full segment buffer.

    Walks the segment in chunk_ms frames, tracks a smoothed gain envelope
    (fast attack, slow release), applies it sample-by-sample, clips to [-1, 1].
    Skips near-silent frames to avoid amplifying pure noise.
    """
    chunk_n = int(chunk_ms / 1000.0 * sample_rate)
    attack_coef  = np.exp(-1.0 / (attack_ms  / 1000.0 * sample_rate))
    release_coef = np.exp(-1.0 / (release_ms / 1000.0 * sample_rate))
    target_amp = 10.0 ** (target_dbfs / 20.0)

    out = audio.copy()
    gain = 1.0
    for start in range(0, len(out), chunk_n):
        frame = out[start:start + chunk_n]
        rms = float(np.sqrt(np.mean(frame ** 2)))
        if rms > 1e-6:
            desired = target_amp / rms
            coef = attack_coef if desired < gain else release_coef
            gain = gain * coef + desired * (1.0 - coef)
        frame *= gain
    np.clip(out, -1.0, 1.0, out=out)
    return out
```

Note: the existing bandpass uses `sosfiltfilt` (zero-phase, full-buffer). The
new per-chunk lowpass uses `sosfilt` (causal, no latency), which is correct for
a streaming path.

**`stt/worker.py`** — two integration points:

**Per-chunk (in `_run()`):**
```python
# Constructed once, alongside bandpass_sos:
lowpass_sos = make_lowpass_sos(self.SAMPLE_RATE, cutoff_hz=2700)

# In the capture loop, after reading chunk:
# source.read() returns float32 in [-1, 1]; no int16 conversion needed.
chunk_filtered = lowpass(chunk.astype(np.float32), lowpass_sos)
# Feed filtered copy to squelch/VAD; keep raw for level meter + waterfall
peak = float(np.max(np.abs(chunk_filtered))) if chunk_filtered.size else 0.0
self._emit_audio_level(min(100, int(peak * 100)))
self._emit_audio_chunk(chunk)          # raw — waterfall sees true signal
segments, events = segmenter.feed(chunk_filtered, peak)
```

**Per-segment (in `_transcription_loop()`):**
```python
filtered  = bandpass(audio, bandpass_sos)
denoised  = denoise(filtered, self.SAMPLE_RATE, prop_decrease=0.7)
agc_audio = dynamic_agc(denoised, self.SAMPLE_RATE)   # replaces normalize_rms
text = transcriber.transcribe(agc_audio)
```

### Invariants

- Raw int16 chunks are emitted to the level meter and waterfall unchanged.
- If `make_lowpass_sos` fails at construction, the worker logs an error and
  falls back to the unfiltered path (no lowpass applied to chunks).
- `dynamic_agc` is a pure function (no side effects, no global state).

---

## Error Handling

| Scenario | Behavior |
|---|---|
| `ptt_lead_in_ms` absent from config | Property returns 350 (default) |
| `ptt_lead_in_ms` > 1000 | Factory clamps to 1000 and logs a warning |
| `channel_busy` set before key | `transmit()` emits `finished`, returns False |
| Squelch opens mid-playback | `sd.stop()`, `ptt.unkey()`, `finished` emitted |
| Squelch stuck open | Every TX discarded; logged at WARNING |
| `synthesize_to_buffer` raises | `finished` still emitted from `except` branch |
| `make_lowpass_sos` raises | Worker logs error, continues without per-chunk LPF |
| `dynamic_agc` frame RMS < 1e-6 | Frame skipped (gain unchanged); no noise amplification |

---

## Tests

| Test | File | What it covers |
|---|---|---|
| `test_serial_ptt_lead_in` | `tests/unit/ptt/test_serial_ptt.py` | Constructor reads `lead_in_ms`, `lead_in_seconds` correct |
| `test_vox_lead_in` | `tests/unit/ptt/test_vox.py` | Same for VoxPTT |
| `test_tx_mixer_discards_when_busy` | `tests/unit/tts/test_tx_mixer.py` | `channel_busy` set → returns False, `ptt.key()` never called |
| `test_tx_mixer_aborts_mid_playback` | `tests/unit/tts/test_tx_mixer.py` | Event fires during `_play_interruptible` → `sd.stop()` called |
| `test_tx_mixer_plays_clean_channel` | `tests/unit/tts/test_tx_mixer.py` | Event clear → returns True, full audio plays |
| `test_tx_mixer_always_unkeys` | `tests/unit/tts/test_tx_mixer.py` | `ptt.unkey()` called even when aborted |
| `test_tx_mixer_always_emits_finished` | `tests/unit/tts/test_tx_mixer.py` | `finished` event always in out_queue |
| `test_lowpass_attenuates_high_freq` | `tests/unit/audio/test_dsp.py` | Sine above cutoff attenuated > 20 dB |
| `test_dynamic_agc_normalizes_quiet` | `tests/unit/audio/test_dsp.py` | Quiet signal brought up to near target dBFS |
| `test_dynamic_agc_skips_silence` | `tests/unit/audio/test_dsp.py` | Near-zero input stays near-zero |
| `test_channel_busy_set_on_squelch` | `tests/unit/stt/` | STTWorker sets `channel_busy` on `squelch_opened` |
| `test_channel_busy_clear_on_close` | `tests/unit/stt/` | STTWorker clears `channel_busy` on `squelch_closed` |
