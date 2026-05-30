from __future__ import annotations

import shutil
import subprocess
import sys
from typing import Protocol, runtime_checkable

import numpy as np
import sounddevice as sd


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

    def read(self) -> np.ndarray:
        buf = self.proc.stdout.read(self.bytes_per_chunk)
        while len(buf) < self.bytes_per_chunk:
            more = self.proc.stdout.read(self.bytes_per_chunk - len(buf))
            if not more:
                raise IOError("parec stdout closed unexpectedly")
            buf = buf + more
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
    """

    def __init__(self, sample_rate, chunk_samples, device=None):
        self.sample_rate = sample_rate
        self.chunk_samples = chunk_samples
        self.stream = sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            device=device,
        )
        self.stream.start()

    def read(self) -> np.ndarray:
        data, _ = self.stream.read(self.chunk_samples)
        return data[:, 0].copy()

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
        except FileNotFoundError:
            pass
    return PortAudioSource(sample_rate, chunk_samples, device=input_device)
