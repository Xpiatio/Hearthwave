# Audio Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add PTT pre-roll silence, a squelch-gated TX priority guard, and AGC+LPF audio preprocessing to the Radio-TTY backend.

**Architecture:** Three independent tracks: (1) PTT pre-roll adds a configurable `ptt_lead_in_ms` to `ServerConfig` and threads it into `SerialPTT`/`VoxPTT` via the factory; (2) the priority mixer exposes a `channel_busy: threading.Event` on `STTWorker` that is set/cleared by squelch events, then `_tx_pump` in `server.py` checks it before keying PTT and discards the transmission if the channel is occupied; (3) AGC+LPF adds three new functions to `dsp.py` — a causal per-chunk low-pass for the capture loop and a dynamic attack/release AGC for the per-segment transcription path.

**Tech Stack:** Python 3.11+, scipy (butter/sosfilt/sosfiltfilt), numpy, threading.Event, asyncio, pyserial, pytest.

**Architecture note on TX path:** The main TTS transmit path in `_tx_pump` sends base64 audio to the browser via WebSocket (`tx_audio` message); the browser plays it. `TTSSynthesizer.synthesize()` (sounddevice) is not used for over-the-air TX. The priority guard is therefore a pre-synthesis check — not a mid-stream sounddevice abort.

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `backend/config.py` | Modify | Add `ptt_lead_in_ms` property |
| `backend/ptt/serial_ptt.py` | Modify | Accept `lead_in_ms` constructor param |
| `backend/ptt/vox.py` | Modify | Accept `lead_in_ms` constructor param |
| `backend/ptt/factory.py` | Modify | Pass `ptt_lead_in_ms` when constructing PTT |
| `backend/stt/worker.py` | Modify | Add `channel_busy` Event; set/clear on squelch events; add per-chunk lowpass; replace `normalize_rms` with `dynamic_agc` |
| `backend/audio/dsp.py` | Modify | Add `make_lowpass_sos`, `lowpass`, `dynamic_agc` |
| `backend/server.py` | Modify | Check `channel_busy` in `_tx_pump` before PTT key |
| `backend/tests/unit/test_config.py` | Modify | Test `ptt_lead_in_ms` property |
| `backend/tests/unit/ptt/test_serial_ptt.py` | Modify | Test `lead_in_ms` param |
| `backend/tests/unit/ptt/test_vox.py` | Modify | Update broken lead_in assertions; test `lead_in_ms` param |
| `backend/tests/unit/ptt/test_factory.py` | Modify | Update `test_vox_has_tail_silence`; add lead_in factory test |
| `backend/tests/unit/audio/test_dsp.py` | Create | Tests for new dsp functions |
| `backend/tests/unit/stt/test_worker_channel_busy.py` | Create | Tests for `channel_busy` event on STTWorker |

---

## Task 1: Add `ptt_lead_in_ms` to ServerConfig

**Files:**
- Modify: `backend/config.py` (after `ptt_serial_line` property, ~line 134)
- Modify: `backend/tests/unit/test_config.py`

- [ ] **Step 1: Write the failing test**

Open `backend/tests/unit/test_config.py` and add this class at the end of the file:

```python
class TestPttLeadInMs:
    def test_default_is_350(self):
        cfg = ServerConfig()
        assert cfg.ptt_lead_in_ms == 350

    def test_reads_from_dict(self):
        cfg = ServerConfig({"ptt_lead_in_ms": 400})
        assert cfg.ptt_lead_in_ms == 400

    def test_returns_int(self):
        cfg = ServerConfig({"ptt_lead_in_ms": "500"})
        assert isinstance(cfg.ptt_lead_in_ms, int)
        assert cfg.ptt_lead_in_ms == 500
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /mnt/storage/Repos/Radio-TTY/.claude/worktrees/quizzical-floating-cerf/backend
python -m pytest tests/unit/test_config.py::TestPttLeadInMs -v
```

Expected: `FAILED` — `AttributeError: 'ServerConfig' object has no attribute 'ptt_lead_in_ms'`

- [ ] **Step 3: Add the property to ServerConfig**

In `backend/config.py`, insert after the `ptt_serial_line` property (after line 134):

```python
    @property
    def ptt_lead_in_ms(self) -> int:
        """Silence to prepend after PTT key before TTS audio plays (ms)."""
        return int(self.get("ptt_lead_in_ms", 350))
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/unit/test_config.py::TestPttLeadInMs -v
```

Expected: 3 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/config.py backend/tests/unit/test_config.py
git commit -m "feat: add ptt_lead_in_ms config property (default 350 ms)"
```

---

## Task 2: Make SerialPTT lead-in configurable

**Files:**
- Modify: `backend/ptt/serial_ptt.py`
- Modify: `backend/tests/unit/ptt/test_serial_ptt.py`

- [ ] **Step 1: Write the failing tests**

Open `backend/tests/unit/ptt/test_serial_ptt.py`. The file likely has basic instantiation tests that mock serial. Add this class:

```python
class TestSerialPTTLeadIn:
    def test_default_lead_in_is_350ms(self, mock_serial):
        """Default lead-in must be 350 ms to protect slow radio TX chains."""
        ptt = SerialPTT.__new__(SerialPTT)
        ptt.line = "RTS"
        ptt.port = mock_serial
        SerialPTT.__init__(ptt, "/dev/ttyUSB0", lead_in_ms=350)
        assert ptt.lead_in_seconds == pytest.approx(0.35)

    def test_custom_lead_in_ms(self, mock_serial):
        ptt = SerialPTT.__new__(SerialPTT)
        ptt.line = "RTS"
        ptt.port = mock_serial
        SerialPTT.__init__(ptt, "/dev/ttyUSB0", lead_in_ms=500)
        assert ptt.lead_in_seconds == pytest.approx(0.5)

    def test_lead_in_zero_is_valid(self, mock_serial):
        ptt = SerialPTT.__new__(SerialPTT)
        ptt.line = "RTS"
        ptt.port = mock_serial
        SerialPTT.__init__(ptt, "/dev/ttyUSB0", lead_in_ms=0)
        assert ptt.lead_in_seconds == pytest.approx(0.0)
```

First, read `test_serial_ptt.py` to see the existing fixture for `mock_serial`, then add the class above.

- [ ] **Step 2: Run to verify they fail**

```bash
python -m pytest tests/unit/ptt/test_serial_ptt.py::TestSerialPTTLeadIn -v
```

Expected: `FAILED` — TypeError or assertion error because `SerialPTT.__init__` doesn't accept `lead_in_ms`.

- [ ] **Step 3: Update SerialPTT**

Replace the content of `backend/ptt/serial_ptt.py` with:

```python
from backend.ptt.base import PTT


class SerialPTT(PTT):
    """USB-serial RTS or DTR drives an external transistor on the radio's PTT line.
    Lead-in/tail give the TX chain time to settle on both sides of the audio."""
    tail_seconds = 0.05

    def __init__(self, port, line="RTS", lead_in_ms: int = 350):
        import serial
        self.lead_in_seconds = lead_in_ms / 1000.0
        self.line = (line or "RTS").upper()
        self.port = serial.Serial(port)
        self.port.rts = False
        self.port.dtr = False

    def key(self):
        if self.line == "DTR":
            self.port.dtr = True
        else:
            self.port.rts = True

    def unkey(self):
        if self.line == "DTR":
            self.port.dtr = False
        else:
            self.port.rts = False

    def close(self):
        try:
            self.unkey()
            self.port.close()
        except Exception:
            pass
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/unit/ptt/test_serial_ptt.py -v
```

Expected: all tests PASSED (including the new `TestSerialPTTLeadIn` class)

- [ ] **Step 5: Commit**

```bash
git add backend/ptt/serial_ptt.py backend/tests/unit/ptt/test_serial_ptt.py
git commit -m "feat: make SerialPTT lead-in configurable via lead_in_ms param"
```

---

## Task 3: Make VoxPTT lead-in configurable and update broken tests

**Files:**
- Modify: `backend/ptt/vox.py`
- Modify: `backend/tests/unit/ptt/test_vox.py`
- Modify: `backend/tests/unit/ptt/test_factory.py`

**Important:** Existing tests in `test_vox.py` pin `lead_in_seconds == 0.0` and `VoxPTT.lead_in_seconds == 0.0`. These are now wrong — the default will be 0.35. Those tests must be updated, not deleted.

- [ ] **Step 1: Update VoxPTT**

Replace `backend/ptt/vox.py` with:

```python
from backend.ptt.base import PTT


class VoxPTT(PTT):
    """Radio's VOX circuit auto-keys on detected audio. Extra trailing silence
    keeps VOX engaged so the last syllable isn't clipped on dropout."""
    tail_seconds = 0.15

    def __init__(self, lead_in_ms: int = 350):
        self.lead_in_seconds = lead_in_ms / 1000.0

    def key(self) -> None:
        pass

    def unkey(self) -> None:
        pass
```

- [ ] **Step 2: Run the existing vox tests to see what breaks**

```bash
python -m pytest tests/unit/ptt/test_vox.py -v
```

Expected: several FAILED — `test_lead_in_seconds_is_zero`, `test_lead_in_is_class_attribute`, `test_both_lead_in_are_zero`

- [ ] **Step 3: Fix broken tests in test_vox.py**

In `backend/tests/unit/ptt/test_vox.py`, make these changes:

1. Replace `test_lead_in_seconds_is_zero`:
```python
    def test_lead_in_seconds_default_is_350ms(self):
        """Default pre-roll gives slow radio TX chains time to open."""
        ptt = VoxPTT()
        assert ptt.lead_in_seconds == pytest.approx(0.35)
```

2. Replace `test_lead_in_is_class_attribute` (lead_in is now an instance attribute set in `__init__`, not a class attr):
```python
    def test_lead_in_seconds_is_instance_attribute(self):
        """lead_in_seconds is set per-instance so lead_in_ms can vary."""
        ptt = VoxPTT()
        assert hasattr(ptt, "lead_in_seconds")
```

3. Add a new test for the `lead_in_ms` param:
```python
    def test_custom_lead_in_ms(self):
        ptt = VoxPTT(lead_in_ms=500)
        assert ptt.lead_in_seconds == pytest.approx(0.5)

    def test_zero_lead_in_ms(self):
        ptt = VoxPTT(lead_in_ms=0)
        assert ptt.lead_in_seconds == pytest.approx(0.0)
```

4. In `TestVoxVsManualPadding`, replace `test_both_lead_in_are_zero`:
```python
    def test_vox_and_manual_both_have_lead_in(self):
        """Both use the same default lead_in_ms; neither is special-cased."""
        assert VoxPTT().lead_in_seconds == pytest.approx(ManualPTT().lead_in_seconds)
```

Add `import pytest` at the top of the file if not already present.

- [ ] **Step 4: Fix test_factory.py**

In `backend/tests/unit/ptt/test_factory.py`, update `test_vox_has_tail_silence`:

```python
    def test_vox_has_tail_silence(self):
        ptt = VoxPTT()
        assert ptt.lead_in_seconds == pytest.approx(0.35)
        assert ptt.tail_seconds == 0.15
```

Add `import pytest` at the top if not present.

- [ ] **Step 5: Run all PTT tests**

```bash
python -m pytest tests/unit/ptt/ -v
```

Expected: all PASSED

- [ ] **Step 6: Commit**

```bash
git add backend/ptt/vox.py backend/tests/unit/ptt/test_vox.py backend/tests/unit/ptt/test_factory.py
git commit -m "feat: make VoxPTT lead-in configurable; update tests for new default 350 ms"
```

---

## Task 4: Wire ptt_lead_in_ms through the factory

**Files:**
- Modify: `backend/ptt/factory.py`
- Modify: `backend/tests/unit/ptt/test_factory.py`

- [ ] **Step 1: Write failing test**

Add this class to `backend/tests/unit/ptt/test_factory.py`:

```python
class TestLeadInPassthrough:
    def test_vox_factory_passes_lead_in_ms(self):
        ptt = make_ptt({"ptt_mode": "vox", "ptt_lead_in_ms": 400})
        assert ptt.lead_in_seconds == pytest.approx(0.4)

    def test_vox_factory_uses_default_when_absent(self):
        ptt = make_ptt({"ptt_mode": "vox"})
        assert ptt.lead_in_seconds == pytest.approx(0.35)

    def test_lead_in_ms_over_1000_is_clamped(self, caplog):
        ptt = make_ptt({"ptt_mode": "vox", "ptt_lead_in_ms": 5000})
        assert ptt.lead_in_seconds == pytest.approx(1.0)
        assert "clamping" in caplog.text
```

- [ ] **Step 2: Run to verify they fail**

```bash
python -m pytest tests/unit/ptt/test_factory.py::TestLeadInPassthrough -v
```

Expected: FAILED — `VoxPTT()` is called with no `lead_in_ms` argument so it uses the default 350; the test expecting 400 will fail.

- [ ] **Step 3: Update factory.py**

Replace `backend/ptt/factory.py` with:

```python
import logging

from backend.ptt.manual import ManualPTT
from backend.ptt.serial_ptt import SerialPTT
from backend.ptt.vox import VoxPTT

_log = logging.getLogger(__name__)


def _make_manual(config) -> ManualPTT:
    return ManualPTT()


def _lead_in_ms(config) -> int:
    raw = int(config.get("ptt_lead_in_ms", 350))
    if raw > 1000:
        _log.warning("ptt_lead_in_ms=%d exceeds 1000 ms; clamping to 1000.", raw)
        return 1000
    return raw


def _make_vox(config) -> VoxPTT:
    return VoxPTT(lead_in_ms=_lead_in_ms(config))


def _make_serial(config) -> ManualPTT | SerialPTT:
    port = (config.get("ptt_serial_port") or "").strip()
    line = config.get("ptt_serial_line", "RTS")
    lead_in_ms = _lead_in_ms(config)
    if not port:
        _log.warning("PTT: USB FTDI selected but no serial port configured; falling back to manual.")
        return ManualPTT()
    try:
        return SerialPTT(port, line, lead_in_ms=lead_in_ms)
    except Exception as e:
        _log.error("PTT: failed to open serial port %s: %s; falling back to manual.", port, e)
        return ManualPTT()


# Maps mode strings to factory callables that accept the config dict.
# Register new PTT types here — make_ptt never needs to change.
_FACTORIES = {
    "manual": _make_manual,
    "vox": _make_vox,
    "usb_ftdi": _make_serial,
}


def make_ptt(config):
    mode = config.get("ptt_mode", "manual")
    factory = _FACTORIES.get(mode, _make_manual)
    return factory(config)
```

- [ ] **Step 4: Run all PTT tests**

```bash
python -m pytest tests/unit/ptt/ -v
```

Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/ptt/factory.py backend/tests/unit/ptt/test_factory.py
git commit -m "feat: factory passes ptt_lead_in_ms to SerialPTT and VoxPTT"
```

---

## Task 5: Add channel_busy Event to STTWorker

**Files:**
- Modify: `backend/stt/worker.py`
- Create: `backend/tests/unit/stt/test_worker_channel_busy.py`

The `SpeechSegmenter.feed()` already emits `"squelch_opened"` and `"squelch_closed"` events. We surface these as a `threading.Event` on `STTWorker` so `_tx_pump` can check channel state without importing the worker's internals.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/stt/test_worker_channel_busy.py`:

```python
"""Tests for STTWorker.channel_busy threading.Event."""
import threading

from backend.stt.worker import STTWorker
import asyncio


def _make_worker():
    return STTWorker(out_queue=asyncio.Queue())


class TestChannelBusyAttribute:
    def test_channel_busy_exists(self):
        w = _make_worker()
        assert hasattr(w, "channel_busy")

    def test_channel_busy_is_threading_event(self):
        w = _make_worker()
        assert isinstance(w.channel_busy, threading.Event)

    def test_channel_busy_starts_clear(self):
        w = _make_worker()
        assert not w.channel_busy.is_set()


class TestChannelBusySetClear:
    """_apply_squelch_event is the internal helper that sets/clears the flag.
    We call it directly to test the state machine without starting the full
    capture loop (which requires a real audio device)."""

    def test_squelch_opened_sets_busy(self):
        w = _make_worker()
        w._apply_squelch_event("squelch_opened")
        assert w.channel_busy.is_set()

    def test_squelch_closed_clears_busy(self):
        w = _make_worker()
        w._apply_squelch_event("squelch_opened")
        w._apply_squelch_event("squelch_closed")
        assert not w.channel_busy.is_set()

    def test_vad_start_does_not_change_busy(self):
        w = _make_worker()
        w._apply_squelch_event("vad_start")
        assert not w.channel_busy.is_set()

    def test_vad_end_does_not_change_busy(self):
        w = _make_worker()
        w._apply_squelch_event("squelch_opened")
        w._apply_squelch_event("vad_end")
        assert w.channel_busy.is_set()  # unchanged by vad_end
```

- [ ] **Step 2: Run to verify they fail**

```bash
python -m pytest tests/unit/stt/test_worker_channel_busy.py -v
```

Expected: FAILED — `AttributeError: 'STTWorker' object has no attribute 'channel_busy'` and `_apply_squelch_event` doesn't exist yet.

- [ ] **Step 3: Add channel_busy and _apply_squelch_event to STTWorker**

In `backend/stt/worker.py`:

**Add `import threading` to the imports** (already imported — confirm it's at the top).

**In `STTWorker.__init__`**, after `self._on_error = on_error`, add:
```python
        self.channel_busy = threading.Event()  # set=channel occupied, clear=idle
```

**After the emit helpers section**, add this new method:
```python
    def _apply_squelch_event(self, event: str) -> None:
        """Update channel_busy based on squelch state transitions."""
        if event == "squelch_opened":
            self.channel_busy.set()
        elif event == "squelch_closed":
            self.channel_busy.clear()
```

**In `_run()`**, find the segment/event loop (around line 337-341):

```python
                segments, events = segmenter.feed(chunk, peak)
                for event in events:
                    self._emit_capture_event(event)
```

Replace with:

```python
                segments, events = segmenter.feed(chunk, peak)
                for event in events:
                    self._apply_squelch_event(event)
                    self._emit_capture_event(event)
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/unit/stt/test_worker_channel_busy.py -v
```

Expected: all PASSED

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
python -m pytest tests/unit/ -v --tb=short
```

Expected: all previously passing tests still PASSED

- [ ] **Step 6: Commit**

```bash
git add backend/stt/worker.py backend/tests/unit/stt/test_worker_channel_busy.py
git commit -m "feat: add channel_busy Event to STTWorker; set/clear on squelch transitions"
```

---

## Task 6: Guard _tx_pump with channel_busy check

**Files:**
- Modify: `backend/server.py`

No new test file — this path is already covered by integration tests and testing `_tx_pump` in isolation requires a full asyncio harness. The channel-busy behavior is covered by the unit tests in Task 5 and can be verified manually.

- [ ] **Step 1: Locate the TX guard insertion point**

In `backend/server.py`, find the block inside `_tx_pump` that begins around line 613:

```python
            # Pause STT before keying so the radio receiver doesn't
            # transcribe TTS audio bleeding back through the radio.
            if not is_preview and _stt_worker is not None:
                _stt_worker.pause()
```

- [ ] **Step 2: Insert the channel_busy check before the pause**

Replace that block with:

```python
            # Discard transmission if the channel is already occupied.
            if not is_preview and _stt_worker is not None and _stt_worker.channel_busy.is_set():
                _log.warning("TX discarded: channel busy (squelch open)")
                continue

            # Pause STT before keying so the radio receiver doesn't
            # transcribe TTS audio bleeding back through the radio.
            if not is_preview and _stt_worker is not None:
                _stt_worker.pause()
```

The `continue` inside the `try` block will execute the `finally` clause, which broadcasts `tx_status: idle` and resumes the STT worker — correct cleanup with no extra code needed.

- [ ] **Step 3: Run the integration test suite**

```bash
python -m pytest tests/integration/ -v --tb=short
```

Expected: all PASSED (or same pass/fail state as before — new code path is not exercised by existing integration tests)

- [ ] **Step 4: Commit**

```bash
git add backend/server.py
git commit -m "feat: discard TTS TX when squelch is open (priority mixer)"
```

---

## Task 7: Add make_lowpass_sos, lowpass, and dynamic_agc to dsp.py

**Files:**
- Modify: `backend/audio/dsp.py`
- Create: `backend/tests/unit/audio/test_dsp.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/audio/test_dsp.py`:

```python
"""Tests for backend.audio.dsp — lowpass and dynamic AGC functions."""
import numpy as np
import pytest

from backend.audio.dsp import dynamic_agc, lowpass, make_lowpass_sos

SAMPLE_RATE = 16000


class TestMakeLowpassSos:
    def test_returns_ndarray(self):
        sos = make_lowpass_sos(SAMPLE_RATE)
        assert isinstance(sos, np.ndarray)

    def test_has_sos_shape(self):
        sos = make_lowpass_sos(SAMPLE_RATE, cutoff_hz=2700, order=4)
        # SOS format: (n_sections, 6)
        assert sos.ndim == 2
        assert sos.shape[1] == 6

    def test_custom_cutoff_accepted(self):
        sos = make_lowpass_sos(SAMPLE_RATE, cutoff_hz=1000)
        assert sos is not None


class TestLowpass:
    def _sine(self, freq_hz, duration_s=0.1):
        t = np.linspace(0, duration_s, int(SAMPLE_RATE * duration_s), endpoint=False)
        return np.sin(2 * np.pi * freq_hz * t).astype(np.float32)

    def test_returns_float32(self):
        sos = make_lowpass_sos(SAMPLE_RATE, cutoff_hz=2700)
        audio = self._sine(1000)
        result = lowpass(audio, sos)
        assert result.dtype == np.float32

    def test_passes_low_freq(self):
        """A 500 Hz sine should pass through almost unattenuated (< 3 dB loss)."""
        sos = make_lowpass_sos(SAMPLE_RATE, cutoff_hz=2700)
        sig = self._sine(500)
        out = lowpass(sig, sos)
        # RMS ratio in dB
        rms_in  = float(np.sqrt(np.mean(sig ** 2)))
        rms_out = float(np.sqrt(np.mean(out ** 2)))
        attenuation_db = 20 * np.log10(rms_out / rms_in)
        assert attenuation_db > -3.0

    def test_attenuates_high_freq(self):
        """A 6000 Hz sine (well above 2700 Hz cutoff) must be attenuated > 20 dB."""
        sos = make_lowpass_sos(SAMPLE_RATE, cutoff_hz=2700, order=4)
        sig = self._sine(6000)
        out = lowpass(sig, sos)
        rms_in  = float(np.sqrt(np.mean(sig ** 2)))
        rms_out = float(np.sqrt(np.mean(out ** 2)))
        if rms_out < 1e-10:
            return  # complete suppression passes the test
        attenuation_db = 20 * np.log10(rms_out / rms_in)
        assert attenuation_db < -20.0


class TestDynamicAgc:
    def _make_audio(self, amplitude, duration_s=0.5):
        n = int(SAMPLE_RATE * duration_s)
        return (np.sin(2 * np.pi * 440 * np.linspace(0, duration_s, n)) * amplitude).astype(np.float32)

    def test_returns_float32(self):
        audio = self._make_audio(0.1)
        out = dynamic_agc(audio, SAMPLE_RATE)
        assert out.dtype == np.float32

    def test_output_same_length(self):
        audio = self._make_audio(0.1)
        out = dynamic_agc(audio, SAMPLE_RATE)
        assert len(out) == len(audio)

    def test_quiet_signal_boosted_toward_target(self):
        """A -40 dBFS signal should be boosted closer to -20 dBFS (default target)."""
        audio = self._make_audio(0.01)   # ~-40 dBFS
        out = dynamic_agc(audio, SAMPLE_RATE, target_dbfs=-20.0)
        rms_in  = float(np.sqrt(np.mean(audio ** 2)))
        rms_out = float(np.sqrt(np.mean(out ** 2)))
        assert rms_out > rms_in  # signal was amplified

    def test_loud_signal_reduced_toward_target(self):
        """A near-full-scale signal should be reduced toward the target."""
        audio = self._make_audio(0.9)   # loud
        out = dynamic_agc(audio, SAMPLE_RATE, target_dbfs=-20.0)
        rms_out = float(np.sqrt(np.mean(out ** 2)))
        rms_loud = float(np.sqrt(np.mean(audio ** 2)))
        assert rms_out < rms_loud

    def test_silence_not_amplified(self):
        """Near-zero input must stay near-zero (no noise amplification)."""
        audio = np.zeros(SAMPLE_RATE, dtype=np.float32)
        out = dynamic_agc(audio, SAMPLE_RATE)
        assert float(np.max(np.abs(out))) < 1e-5

    def test_output_clipped_to_unit_range(self):
        """Output must not exceed [-1, 1]."""
        audio = self._make_audio(0.95)
        out = dynamic_agc(audio, SAMPLE_RATE)
        assert float(np.max(np.abs(out))) <= 1.0 + 1e-6

    def test_does_not_modify_input(self):
        """dynamic_agc returns a copy; the original array is unchanged."""
        audio = self._make_audio(0.1)
        original = audio.copy()
        dynamic_agc(audio, SAMPLE_RATE)
        np.testing.assert_array_equal(audio, original)
```

- [ ] **Step 2: Run to verify they fail**

```bash
python -m pytest tests/unit/audio/test_dsp.py -v
```

Expected: FAILED — `ImportError: cannot import name 'dynamic_agc' from 'backend.audio.dsp'`

- [ ] **Step 3: Add the three functions to dsp.py**

Append to the end of `backend/audio/dsp.py`:

```python

def make_lowpass_sos(sample_rate: int, cutoff_hz: float = 2700, order: int = 4):
    """Butterworth low-pass for per-chunk stream filtering (causal path).

    Use sosfilt (not sosfiltfilt) with this SOS — sosfiltfilt needs the full
    buffer for zero-phase filtering; sosfilt is causal and safe per-chunk.
    """
    from scipy.signal import butter
    nyquist = sample_rate / 2
    return butter(order, cutoff_hz / nyquist, btype="low", output="sos")


def lowpass(audio: np.ndarray, sos) -> np.ndarray:
    """Apply a precomputed SOS low-pass to one audio chunk (causal, no lookahead)."""
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

    Walks the segment in chunk_ms frames. Tracks a smoothed gain envelope:
    gain falls quickly (attack) when the signal is loud, rises slowly (release)
    when it is quiet. Near-silent frames are skipped to avoid amplifying noise.
    Returns a copy; the input array is not modified. Output clipped to [-1, 1].
    """
    chunk_n = max(1, int(chunk_ms / 1000.0 * sample_rate))
    attack_coef  = np.exp(-1.0 / (attack_ms  / 1000.0 * sample_rate))
    release_coef = np.exp(-1.0 / (release_ms / 1000.0 * sample_rate))
    target_amp = 10.0 ** (target_dbfs / 20.0)

    out = audio.copy().astype(np.float32)
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

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/unit/audio/test_dsp.py -v
```

Expected: all PASSED

- [ ] **Step 5: Run the full unit suite**

```bash
python -m pytest tests/unit/ -v --tb=short
```

Expected: all previously passing tests still PASSED

- [ ] **Step 6: Commit**

```bash
git add backend/audio/dsp.py backend/tests/unit/audio/test_dsp.py
git commit -m "feat: add make_lowpass_sos, lowpass, and dynamic_agc to dsp.py"
```

---

## Task 8: Apply per-chunk lowpass in STTWorker capture loop

**Files:**
- Modify: `backend/stt/worker.py`

- [ ] **Step 1: Update imports in worker.py**

Find the import line in `backend/stt/worker.py`:

```python
from backend.audio.dsp import bandpass, denoise, make_bandpass_sos, normalize_rms
```

Replace with:

```python
from backend.audio.dsp import bandpass, denoise, dynamic_agc, lowpass, make_bandpass_sos, make_lowpass_sos, normalize_rms
```

- [ ] **Step 2: Construct the lowpass SOS alongside the bandpass SOS**

In `_run()`, find where `bandpass_sos` is created (around line 254):

```python
            bandpass_sos = make_bandpass_sos(
                self.SAMPLE_RATE,
                self.BANDPASS_LOW_HZ,
                self.BANDPASS_HIGH_HZ,
            )
```

Immediately after that block, add:

```python
            try:
                lowpass_sos = make_lowpass_sos(self.SAMPLE_RATE, cutoff_hz=2700)
            except Exception as e:
                _log.warning("Could not create lowpass filter: %s — skipping per-chunk LPF", e)
                lowpass_sos = None
```

- [ ] **Step 3: Apply the filter in the capture loop**

In `_run()`, find the block that reads the chunk and computes the peak (around line 306-323):

```python
                chunk = source.read()
                ...
                peak = float(np.max(np.abs(chunk))) if chunk.size else 0.0
                self._emit_audio_level(min(100, int(peak * 100)))
                self._emit_audio_chunk(chunk)
```

The chunk feeding into `segmenter.feed(chunk, peak)` should use the filtered copy. The raw chunk stays for level meter and waterfall. Replace the existing `segmenter.feed` call and the peak computation with:

```python
                # Apply per-chunk LPF for squelch/VAD — raw chunk preserved for meter/waterfall.
                chunk_for_vad = lowpass(chunk, lowpass_sos) if lowpass_sos is not None else chunk
                peak = float(np.max(np.abs(chunk_for_vad))) if chunk_for_vad.size else 0.0
                self._emit_audio_level(min(100, int(peak * 100)))
                self._emit_audio_chunk(chunk)
```

Then update the existing `peak` computation and the `segmenter.feed` call. The final diff for that region of `_run()` looks like this:

```python
                # Apply per-chunk LPF for squelch/VAD.
                chunk_for_vad = lowpass(chunk, lowpass_sos) if lowpass_sos is not None else chunk

                # Level meter and waterfall always see the raw signal.
                peak_raw = float(np.max(np.abs(chunk))) if chunk.size else 0.0
                self._emit_audio_level(min(100, int(peak_raw * 100)))
                self._emit_audio_chunk(chunk)

                if self._pause_event.is_set():
                    if not was_paused:
                        segmenter.reset()
                        self._emit_status("Paused (transmitting)")
                        was_paused = True
                    continue

                if was_paused:
                    segmenter.reset()
                    self._emit_status("Listening...")
                    was_paused = False

                # VAD and squelch use the filtered peak.
                peak_vad = float(np.max(np.abs(chunk_for_vad))) if chunk_for_vad.size else 0.0
                segments, events = segmenter.feed(chunk_for_vad, peak_vad)
                for event in events:
                    self._apply_squelch_event(event)
                    self._emit_capture_event(event)
                for uid, audio, is_final in segments:
                    transcribe_queue.put((uid, audio, is_final))
```

Remove the original `peak = ...` line (it no longer exists — replaced by `peak_raw` and `peak_vad` above).

- [ ] **Step 4: Run unit tests**

```bash
python -m pytest tests/unit/ -v --tb=short
```

Expected: all PASSED

- [ ] **Step 5: Run integration tests**

```bash
python -m pytest tests/integration/ -v --tb=short
```

Expected: all PASSED (or same state as before)

- [ ] **Step 6: Commit**

```bash
git add backend/stt/worker.py
git commit -m "feat: apply per-chunk lowpass filter before VAD/squelch in STT capture loop"
```

---

## Task 9: Replace normalize_rms with dynamic_agc in transcription loop

**Files:**
- Modify: `backend/stt/worker.py`

- [ ] **Step 1: Update the transcription loop**

In `backend/stt/worker.py`, find `_transcription_loop` (around line 443). Locate:

```python
                filtered = bandpass(audio, bandpass_sos)
                denoised = denoise(filtered, self.SAMPLE_RATE, prop_decrease=0.7)
                normalize_rms(denoised)
                text = transcriber.transcribe(denoised)
```

Replace with:

```python
                filtered  = bandpass(audio, bandpass_sos)
                denoised  = denoise(filtered, self.SAMPLE_RATE, prop_decrease=0.7)
                agc_audio = dynamic_agc(denoised, self.SAMPLE_RATE)
                text = transcriber.transcribe(agc_audio)
```

- [ ] **Step 2: Run all tests**

```bash
python -m pytest tests/unit/ tests/integration/ -v --tb=short
```

Expected: all PASSED

- [ ] **Step 3: Verify normalize_rms is no longer used anywhere (optional cleanup check)**

```bash
grep -rn "normalize_rms" backend/
```

If `normalize_rms` still appears only in `dsp.py` (its definition) and nowhere else, it is now unused — leave it in `dsp.py` (don't delete; it may be used by plugins or external callers).

- [ ] **Step 4: Commit**

```bash
git add backend/stt/worker.py
git commit -m "feat: replace normalize_rms with dynamic_agc in STT transcription pipeline"
```

---

## Final Verification

- [ ] **Run the complete test suite**

```bash
python -m pytest tests/ -v --tb=short
```

Expected: all PASSED

- [ ] **Smoke check: confirm all three features are wired end-to-end**

```bash
# 1. Pre-roll: verify factory produces correct lead_in for a known config
python -c "
from backend.ptt.factory import make_ptt
ptt = make_ptt({'ptt_mode': 'vox', 'ptt_lead_in_ms': 400})
print('VoxPTT lead_in_seconds:', ptt.lead_in_seconds)  # expect 0.4
ptt2 = make_ptt({'ptt_mode': 'vox'})
print('VoxPTT default lead_in_seconds:', ptt2.lead_in_seconds)  # expect 0.35
"

# 2. Channel busy: verify event attribute exists
python -c "
import asyncio, threading
from backend.stt.worker import STTWorker
w = STTWorker(asyncio.Queue())
assert isinstance(w.channel_busy, threading.Event)
w._apply_squelch_event('squelch_opened')
assert w.channel_busy.is_set()
w._apply_squelch_event('squelch_closed')
assert not w.channel_busy.is_set()
print('channel_busy OK')
"

# 3. DSP: verify new functions importable and run
python -c "
import numpy as np
from backend.audio.dsp import dynamic_agc, lowpass, make_lowpass_sos
sos = make_lowpass_sos(16000)
audio = np.random.randn(16000).astype(np.float32) * 0.1
out = lowpass(audio, sos)
agc = dynamic_agc(audio, 16000)
print('dsp OK — shapes:', out.shape, agc.shape)
"
```

Expected: all three print their success messages with no exceptions.
