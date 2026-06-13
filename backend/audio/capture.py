from __future__ import annotations

import math
import shutil
import subprocess
import sys
import time
from typing import Protocol, runtime_checkable

import numpy as np
from scipy.signal import resample_poly


class _LazySounddevice:
    """Defer the sounddevice import until an audio device is actually used.

    PortAudio is a runtime-only dependency: the parec path and offline tools
    (backend.tools.eval_stt) never touch it, and importing it at module load
    breaks environments without libportaudio.
    """

    def __getattr__(self, name):
        import sounddevice
        return getattr(sounddevice, name)


sd = _LazySounddevice()


@runtime_checkable
class AudioInputSource(Protocol):
    """Structural interface for all audio capture sources."""

    def read(self) -> np.ndarray: ...
    def close(self) -> None: ...


def enumerate_monitor_sources() -> list[tuple[str, str]]:
    """Return (display_name, sink_id) pairs for available system audio outputs.

    sink_id="" means system default. On Linux the sink_id is a PulseAudio/
    PipeWire sink name; on Windows it is the output device index as a string.
    """
    sources: list[tuple[str, str]] = [("System Default", "")]
    if sys.platform == "linux":
        try:
            result = subprocess.run(
                ["pactl", "list", "sinks", "short"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.strip().splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    sources.append((parts[1], parts[1]))
        except Exception:
            pass
    elif sys.platform == "win32":
        try:
            for i, dev in enumerate(sd.query_devices()):
                if dev.get("max_output_channels", 0) > 0:
                    sources.append((dev["name"], str(i)))
        except Exception:
            pass
    return sources


class SystemMonitorSource:
    """Captures system audio output (loopback) as an input source.

    On Linux uses ``parec --device=<sink>.monitor`` via PipeWire/PulseAudio.
    On Windows uses sounddevice WASAPI loopback on the selected output device.
    Pass sink="" to capture the system default output.
    """

    def __init__(self, sample_rate: int, chunk_samples: int, sink: str = ""):
        self._sample_rate = sample_rate
        self._chunk_samples = chunk_samples
        self._bytes_per_chunk = chunk_samples * 2  # int16 little-endian
        self._proc = None
        self._stream = None

        if sys.platform == "linux":
            self._open_linux(sink)
        elif sys.platform == "win32":
            self._open_windows(sink)
        else:
            raise NotImplementedError(
                f"System monitor capture is not supported on {sys.platform}"
            )

    def _open_linux(self, sink: str) -> None:
        parec_bin = shutil.which("parec")
        if not parec_bin:
            raise FileNotFoundError("parec binary not on PATH")
        if not sink:
            try:
                r = subprocess.run(
                    ["pactl", "get-default-sink"],
                    capture_output=True, text=True, timeout=5,
                )
                sink = r.stdout.strip()
            except Exception:
                pass
        cmd = [
            parec_bin, "--raw", "--format=s16le",
            f"--rate={self._sample_rate}", "--channels=1",
        ]
        if sink:
            cmd.append(f"--device={sink}.monitor")
        self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        time.sleep(0.15)
        if self._proc.poll() is not None:
            self._proc = None
            raise IOError(
                "parec exited immediately — PulseAudio/PipeWire not reachable "
                "or sink not found. Is PULSE_SERVER set in the container?"
            )

    def _open_windows(self, sink: str) -> None:
        if not hasattr(sd, "WasapiSettings"):
            raise RuntimeError(
                "WASAPI loopback requires the Windows build of sounddevice"
            )
        device = int(sink) if sink else None
        self._stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=1,
            dtype="float32",
            device=device,
            extra_settings=sd.WasapiSettings(loopback=True),
        )
        self._stream.start()

    def read(self) -> np.ndarray:
        if self._proc is not None:
            buf = self._proc.stdout.read(self._bytes_per_chunk)
            while len(buf) < self._bytes_per_chunk:
                more = self._proc.stdout.read(self._bytes_per_chunk - len(buf))
                if not more:
                    raise IOError("parec monitor stream closed unexpectedly")
                buf += more
            return np.frombuffer(buf, dtype=np.int16).astype(np.float32) / 32768.0
        data, _ = self._stream.read(self._chunk_samples)
        return data[:, 0].copy()

    def close(self) -> None:
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=2)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None


class ParecSource:
    """PulseAudio/PipeWire `parec` capture.

    Reliable on PipeWire 1.4 where PortAudio's ALSA bridge can silently
    deliver flat-zero buffers — only the first stream after PortAudio init
    returns audio, and long-lived streams degenerate to silence with no
    error. parec speaks PipeWire's PulseAudio protocol directly and is
    stable across stream restarts.
    """

    def __init__(self, sample_rate, chunk_samples):
        parec_bin = shutil.which("parec")
        if not parec_bin:
            raise FileNotFoundError("parec binary not on PATH")
        self.sample_rate = sample_rate
        self.chunk_samples = chunk_samples
        self.bytes_per_chunk = chunk_samples * 2  # int16 little-endian
        self.proc = subprocess.Popen(
            [parec_bin, "--raw", "--format=s16le",
             f"--rate={sample_rate}", "--channels=1"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        # parec exits immediately when no PulseAudio/PipeWire server is
        # reachable (e.g. inside a Docker container without a PA socket
        # mounted). Detect this early so the caller can fall back.
        time.sleep(0.15)
        if self.proc.poll() is not None:
            raise IOError("parec exited — PulseAudio/PipeWire not reachable")

    def read(self) -> np.ndarray:
        buf = self.proc.stdout.read(self.bytes_per_chunk)
        if len(buf) < self.bytes_per_chunk:
            chunks = [buf]
            while len(buf) < self.bytes_per_chunk:
                more = self.proc.stdout.read(self.bytes_per_chunk - len(buf))
                if not more:
                    raise IOError("parec stdout closed unexpectedly")
                chunks.append(more)
                buf = b"".join(chunks)
        return np.frombuffer(buf, dtype=np.int16).astype(np.float32) / 32768.0

    def close(self) -> None:
        try:
            self.proc.terminate()
            self.proc.wait(timeout=2)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass


class PortAudioSource:
    """sounddevice/PortAudio capture for a specific input device.

    Used when the operator has selected an explicit input device (e.g., a
    USB sound card / Signalink / Digirig), or when parec isn't available
    on the host (Windows, headless Linux without PulseAudio/PipeWire).

    Captures at the device's native sample rate and resamples to the
    requested rate when they differ (e.g. 48 kHz hardware → 16 kHz STT).
    """

    def __init__(self, sample_rate: int, chunk_samples: int, device=None):
        self.sample_rate = sample_rate
        self.chunk_samples = chunk_samples

        # Discover the device's native rate.
        try:
            dev_idx = device if device is not None else sd.default.device[0]
            native_rate = int(sd.query_devices(dev_idx)["default_samplerate"])
        except Exception:
            native_rate = sample_rate

        gcd = math.gcd(sample_rate, native_rate)
        self._up = sample_rate // gcd
        self._down = native_rate // gcd
        self._do_resample = native_rate != sample_rate
        # How many native-rate frames we need to produce exactly chunk_samples
        # after resampling.  round() keeps the ratio exact for common pairs
        # (48000→16000 = 3:1, 44100→16000 rounds to 1411 native frames).
        self._native_chunks = round(chunk_samples * native_rate / sample_rate)

        self.stream = sd.InputStream(
            samplerate=native_rate,
            channels=1,
            dtype="float32",
            device=device,
        )
        self.stream.start()

    def read(self) -> np.ndarray:
        data, _ = self.stream.read(self._native_chunks)
        chunk = data[:, 0].copy()
        if self._do_resample:
            chunk = resample_poly(chunk, self._up, self._down).astype(np.float32)
            # Trim or zero-pad to guarantee exactly chunk_samples frames.
            if len(chunk) > self.chunk_samples:
                chunk = chunk[: self.chunk_samples]
            elif len(chunk) < self.chunk_samples:
                chunk = np.pad(chunk, (0, self.chunk_samples - len(chunk)))
        return chunk

    def close(self) -> None:
        try:
            self.stream.stop()
            self.stream.close()
        except Exception:
            pass


def open_input_source(
    sample_rate: int,
    chunk_samples: int,
    input_device: str | int | None = None,
    system_monitor_sink: str = "",
) -> AudioInputSource:
    """Open an InputSource for the active capture path.

    Prefers ``parec`` over PortAudio when the operator has not selected a
    specific input device — PortAudio's PipeWire-via-ALSA bridge can
    silently deliver flat-zero buffers on PipeWire 1.4. Falls back to
    PortAudio if parec isn't on PATH, or when a specific input device
    is configured.

    When input_device is ``"system_monitor"``, captures the system audio
    output (loopback) so the user can play any audio source and have it
    transcribed without a physical microphone.
    """
    if input_device == "system_monitor":
        return SystemMonitorSource(sample_rate, chunk_samples, sink=system_monitor_sink)
    if input_device is None:
        try:
            return ParecSource(sample_rate, chunk_samples)
        except (FileNotFoundError, IOError):
            pass
    return PortAudioSource(sample_rate, chunk_samples, device=input_device)
