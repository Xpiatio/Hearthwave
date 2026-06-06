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

    @property
    def voices_dir(self) -> Path:
        raw = self.get("voices_dir")
        if raw:
            return Path(raw)
        if self.voice:
            # Only derive the directory from `voice` when it is a real path.
            # A bare stem like "ryan-high" has parent "." which would collapse
            # the voices directory to the CWD and hide every installed voice
            # (a chicken-and-egg lockout: the picker is empty so no valid voice
            # can ever be selected). Fall through to the default in that case.
            parent = Path(self.voice).parent
            if str(parent) not in ("", "."):
                return parent
        return Path("/app/Voices")

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

    @property
    def tx_max_duration_seconds(self) -> int:
        """Hard cap on how long PTT may remain keyed for any single transmission."""
        return int(self.get("tx_max_duration_seconds", 60))

    @property
    def tx_synthesis_timeout_seconds(self) -> int:
        """Max time to wait for TTS synthesis before aborting without keying PTT."""
        return int(self.get("tx_synthesis_timeout_seconds", 30))

    @property
    def ptt_lead_in_ms(self) -> int:
        """Silence to prepend after PTT key before TTS audio plays (ms)."""
        return int(self.get("ptt_lead_in_ms", 350))

    # ---- receive mode ----------------------------------------------------

    @property
    def rx_mode(self) -> str:
        """Receive mode: 'voice' (Whisper STT) or 'cw' (morse decoder)."""
        return self.get("rx_mode", "voice")

    # ---- attendance ------------------------------------------------------

    @property
    def attendance_enabled(self) -> bool:
        return bool((self.get("attendance") or {}).get("enabled", False))

    @attendance_enabled.setter
    def attendance_enabled(self, value: bool) -> None:
        existing = dict(self.get("attendance") or {})
        existing["enabled"] = value
        self["attendance"] = existing

    # ---- AI / journals ---------------------------------------------------

    @property
    def gemini_api_key(self) -> str:
        return self.get("gemini_api_key", "")

    @property
    def journals_dir(self) -> Path:
        raw = self.get("journals_dir")
        return Path(raw) if raw else Path("/data/journals")

    # ---- spectrogram -----------------------------------------------------

    @property
    def spectro_colormap(self) -> str:
        return self.get("spectro_colormap", "viridis")

    @property
    def spectro_freq_range(self) -> str:
        return self.get("spectro_freq_range", "full")

    @property
    def spectro_time_window_s(self) -> int:
        return int(self.get("spectro_time_window_s", 30))

    # ---- persistence ---------------------------------------------------------

    @property
    def contacts_file(self) -> Path:
        raw = self.get("contacts_file")
        return Path(raw) if raw else Path("/data/contacts.json")

    @property
    def users_file(self) -> Path:
        raw = self.get("users_file")
        return Path(raw) if raw else Path("/data/users.json")

    @property
    def tokens_file(self) -> Path:
        raw = self.get("tokens_file")
        return Path(raw) if raw else Path("/data/tokens.json")

    # ---- NCS / Net Control Station --------------------------------------

    @property
    def ncs_zone(self) -> str:
        """NWS county zone code for SKYWARN alerts (e.g. 'MIZ025'). Empty = disabled."""
        return (self.get("ncs_zone") or "").strip().upper()

    @property
    def ncs_announcement_interval(self) -> int:
        """Seconds between automated net announcements while NCS is active (default 600)."""
        return int(self.get("ncs_announcement_interval", 600))

    # ---- server ----------------------------------------------------------

    @property
    def host(self) -> str:
        return self.get("host", "0.0.0.0")

    @property
    def port(self) -> int:
        return int(self.get("port", 8765))

    # ---- serialization ---------------------------------------------------------

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
