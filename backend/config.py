"""Server configuration for Radio-TTY.

ServerConfig is a dict subclass (same pattern as GMRS-TTY's AppConfig) so it
can be passed as a plain dict anywhere and still offer typed property access
with centralised defaults.

Config file path is resolved from the RADIO_TTY_CONFIG environment variable,
falling back to /data/config.json.  save() writes atomically via a sibling
tempfile so a crash mid-write never corrupts the file.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

_log = logging.getLogger(__name__)

CONFIG_FILE = Path(os.environ.get("RADIO_TTY_CONFIG", "/data/config.json"))


class ServerConfig(dict):
    """Typed wrapper around the JSON config dict.

    Subclasses dict so it remains a drop-in for all existing code that passes
    config as a plain dict.  Properties provide typed access with centralised
    defaults so magic strings and inline defaults don't repeat at every call site.
    """

    # ---- station identity ------------------------------------------------

    @property
    def callsign(self) -> str:
        return self.get("callsign", "N0CALL")

    @property
    def name(self) -> str:
        return self.get("name", "")

    @property
    def location(self) -> str:
        return self.get("location", "")

    # ---- audio / STT -----------------------------------------------------

    @property
    def input_device(self):
        return self.get("input_device", -1)

    @property
    def output_device(self):
        return self.get("output_device", -1)

    @property
    def monitor_enabled(self) -> bool:
        return bool(self.get("monitor_enabled", False))

    @property
    def monitor_passthrough(self) -> bool:
        return bool(self.get("monitor_passthrough", False))

    @property
    def whisper_model(self) -> str:
        return self.get("whisper_model", "small.en")

    @property
    def vad_threshold(self) -> float:
        return float(self.get("vad_threshold", 0.5))

    @property
    def system_monitor_sink(self) -> str:
        return (self.get("system_monitor_sink") or "").strip()

    # ---- TTS -------------------------------------------------------------

    @property
    def voice(self) -> str:
        return self.get("voice", "")

    @property
    def tts_length_scale(self) -> float:
        return float(self.get("tts_length_scale", 1.0))

    # ---- text / content --------------------------------------------------

    @property
    def filter_profanity(self) -> bool:
        return bool(self.get("filter_profanity", True))

    @property
    def fuzzy_callsign(self) -> bool:
        return bool(self.get("fuzzy_callsign", False))

    # ---- radio / service -------------------------------------------------

    @property
    def radio_service(self) -> str:
        return self.get("radio_service", "")

    @property
    def listen_only(self) -> bool:
        return bool(self.get("listen_only", False))

    # ---- PTT -------------------------------------------------------------

    @property
    def ptt_mode(self) -> str:
        return self.get("ptt_mode", "manual")

    @property
    def ptt_serial_port(self) -> str:
        return (self.get("ptt_serial_port") or "").strip()

    @property
    def ptt_serial_line(self) -> str:
        return self.get("ptt_serial_line", "RTS")

    # ---- attendance ------------------------------------------------------

    @property
    def attendance_enabled(self) -> bool:
        return bool((self.get("attendance") or {}).get("enabled", False))

    @attendance_enabled.setter
    def attendance_enabled(self, value: bool) -> None:
        self["attendance"] = {"enabled": value}

    # ---- persistence (contacts) ------------------------------------------

    @property
    def contacts_file(self) -> Path:
        raw = self.get("contacts_file")
        return Path(raw) if raw else Path("/data/contacts.json")

    # ---- server ----------------------------------------------------------

    @property
    def host(self) -> str:
        return self.get("host", "0.0.0.0")

    @property
    def port(self) -> int:
        return int(self.get("port", 8765))

    # ---- persistence ---------------------------------------------------------

    @classmethod
    def load(cls, path: Path = CONFIG_FILE) -> "ServerConfig":
        """Load config from *path*, returning a ServerConfig with defaults if the
        file is absent or contains invalid JSON."""
        instance = cls()
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, dict):
                    instance.update(data)
                else:
                    _log.warning(
                        "Config file %s did not contain a JSON object; using defaults.", path
                    )
            except (json.JSONDecodeError, OSError) as exc:
                _log.warning("Could not load config %s: %s; using defaults.", path, exc)
        return instance

    def save(self, path: Path = CONFIG_FILE) -> None:
        """Persist this config to *path* atomically via a sibling tempfile."""
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(dict(self), fh, indent=4, ensure_ascii=False)
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
