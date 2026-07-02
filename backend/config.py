"""Server configuration for Hearthwave.

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

from backend.constants import GAIN_MODES

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
    def whisper_model_final(self) -> str:
        """Second-pass model that re-transcribes the full utterance on
        finalization. Empty string disables the second pass."""
        return self.get("whisper_model_final", "")

    @property
    def stt_final_max_s(self) -> float:
        return float(self.get("stt_final_max_s", 60.0))

    @property
    def stt_final_device(self) -> str:
        """Where the whole-utterance final pass runs:
        'auto' (GPU if a ROCm GPU is present, else CPU), 'gpu', or 'cpu'."""
        val = str(self.get("stt_final_device", "auto")).strip().lower()
        return val if val in ("auto", "gpu", "cpu") else "auto"

    @property
    def stt_gain_mode(self) -> str:
        """Gain stage applied after bandpass/denoise, before transcription:
        'agc' (dynamic attack/release AGC), 'rms' (one-shot RMS normalize),
        or 'off' (no gain)."""
        val = str(self.get("stt_gain_mode", "agc")).strip().lower()
        return val if val in GAIN_MODES else "agc"

    @property
    def stt_noise_profile(self) -> bool:
        """Feed squelch-closed noise-floor audio to the denoise stage as a
        stationary noise estimate instead of letting it self-estimate from
        the speech-bearing segment. Off until WER-proven on a real corpus."""
        return bool(self.get("stt_noise_profile", False))

    @property
    def squelch_open_threshold(self) -> float:
        return float(self.get("squelch_open_threshold", 0.05))

    @property
    def squelch_adaptive(self) -> bool:
        return bool(self.get("squelch_adaptive", False))

    @property
    def stt_pre_roll_s(self) -> float:
        return float(self.get("stt_pre_roll_s", 1.0))

    @property
    def stt_min_speech_s(self) -> float:
        return float(self.get("stt_min_speech_s", 0.4))

    @property
    def stt_debug_capture(self) -> bool:
        return bool(self.get("stt_debug_capture", False))

    @property
    def stt_debug_dir(self) -> str:
        return self.get("stt_debug_dir", "/data/debug/stt")

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
    def tx_conditioning(self) -> bool:
        """Band-limit, compress, and level-normalize synthesized speech before
        it drives the radio's mic input."""
        return bool(self.get("tx_conditioning", False))

    @property
    def vox_primer_enabled(self) -> bool:
        """Prepend a short tone to server-synthesized TX audio so a VOX-keyed
        radio is fully keyed before the message starts."""
        return bool(self.get("vox_primer_enabled", False))

    @property
    def vox_primer_ms(self) -> int:
        """Duration of the VOX primer tone in milliseconds."""
        return int(self.get("vox_primer_ms", 300))

    @property
    def vox_primer_word_enabled(self) -> bool:
        """Speak a configurable priming word (e.g. "transmit") after the VOX
        primer tone and before the message, so a VOX-keyed radio is keyed on a
        clear spoken keyword.  Different radios may need different words."""
        return bool(self.get("vox_primer_word_enabled", False))

    @property
    def vox_primer_word(self) -> str:
        """The spoken VOX priming word."""
        return str(self.get("vox_primer_word", "transmit"))

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

    @property
    def fuzzy_callsign_rewrite(self) -> bool:
        """Rewrite misheard callsigns in final transcripts to the roster's
        canonical call (visibly marked). Only active when fuzzy_callsign is
        also on — this extends the span labeling into the text itself."""
        return bool(self.get("fuzzy_callsign_rewrite", False))

    @property
    def saved_phrases(self) -> list:
        # Default empty: curated radio vocabulary now lives in backend/stt/vocab.py
        # and is assembled server-side. saved_phrases holds only the operator's
        # custom additions.
        return list(self.get("saved_phrases", []))

    @property
    def stt_vocab_max_callsigns(self) -> int:
        """Max number of contact callsigns to include in Whisper initial_prompt.
        Callsigns are ~6 tokens each; smaller limit leaves room for procedure
        vocabulary and custom phrases within the ~223-token budget."""
        return int(self.get("stt_vocab_max_callsigns", 15))

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
    # NCS is a built-in plugin (id "ncs"); its master toggle lives in the plugin
    # namespace (see plugin_* helpers below). These are Station-tab settings it reads.

    @property
    def ncs_zone(self) -> str:
        """NWS county zone code for SKYWARN alerts (e.g. 'MIZ025'). Empty = disabled."""
        return (self.get("ncs_zone") or "").strip().upper()

    @property
    def ncs_announcement_interval(self) -> int:
        """Seconds between automated net announcements while NCS is active (default 600)."""
        return int(self.get("ncs_announcement_interval", 600))

    @property
    def ncs_preamble_text(self) -> str:
        """Opening net preamble template; placeholders substituted before TTS.
        Supports {callsign} {name} {location} {date} {time}. Empty = none."""
        return self.get("ncs_preamble_text", "") or ""

    @property
    def ncs_closing_text(self) -> str:
        """Closing net sign-off template; placeholders substituted before TTS.
        Supports {callsign} {name} {location} {date} {time}. Empty = none."""
        return self.get("ncs_closing_text", "") or ""

    # ---- plugins (namespaced config for installed plugins) --------------
    # Each plugin's state lives under config["plugins"][id]: the master toggle at
    # "enabled" plus one key per ConfigField. Built-in and 3rd-party plugins alike
    # read/write through these helpers; nothing else in core knows plugin keys.

    def plugin_config(self, plugin_id: str) -> dict:
        """This plugin's stored config namespace (empty dict if none yet)."""
        return (self.get("plugins") or {}).get(plugin_id) or {}

    def set_plugin_config(self, plugin_id: str, values: dict) -> None:
        """Merge *values* into config["plugins"][plugin_id] (in place)."""
        plugins = self.setdefault("plugins", {})
        plugins.setdefault(plugin_id, {}).update(values)

    def plugin_enabled(self, plugin_id: str, default: bool = False) -> bool:
        """Master toggle for *plugin_id*."""
        return bool(self.plugin_config(plugin_id).get("enabled", default))

    def set_plugin_enabled(self, plugin_id: str, enabled: bool) -> None:
        self.set_plugin_config(plugin_id, {"enabled": bool(enabled)})

    # ---- monitoring beacon ----------------------------------------------

    @property
    def monitoring_beacon_enabled(self) -> bool:
        """Emit a periodic presence beacon over the air (default off)."""
        return bool(self.get("monitoring_beacon_enabled", False))

    @property
    def monitoring_beacon_interval(self) -> int:
        """Seconds between monitoring beacons (default 900)."""
        return int(self.get("monitoring_beacon_interval", 900))

    @property
    def monitoring_beacon_text(self) -> str:
        """Beacon phrase template; {callsign} is substituted before TTS."""
        return self.get("monitoring_beacon_text", "{callsign} Hearthwave base, monitoring.")

    # ---- server ----------------------------------------------------------

    @property
    def host(self) -> str:
        return self.get("host", "0.0.0.0")

    @property
    def port(self) -> int:
        return int(self.get("port", 8765))

    # ---- serialization ---------------------------------------------------------

    #: One-time migration of pre-namespace flat plugin keys (released in v2.9.0 for
    #: MeshCore) into config["plugins"][id]. Maps legacy flat key -> namespaced key.
    _LEGACY_PLUGIN_KEYS = {
        "meshcore": {
            "meshcore_enabled": "enabled",
            "meshcore_serial_port": "serial_port",
            "meshcore_baud": "baud",
            "meshcore_max_packet_length": "max_packet_length",
            "meshcore_prefix_separator": "prefix_separator",
            "meshcore_channel_idx": "channel_idx",
        },
        "meshtastic": {
            "meshtastic_enabled": "enabled",
            "meshtastic_serial_port": "serial_port",
            "meshtastic_max_packet_length": "max_packet_length",
            "meshtastic_prefix_separator": "prefix_separator",
            "meshtastic_channel_idx": "channel_idx",
        },
        "ncs": {"ncs_enabled": "enabled"},
    }

    def _migrate_legacy_plugin_keys(self) -> None:
        """Fold legacy flat plugin keys into the plugins namespace, in place.
        A pre-existing namespaced value always wins; legacy keys are then removed."""
        for plugin_id, mapping in self._LEGACY_PLUGIN_KEYS.items():
            for legacy_key, new_key in mapping.items():
                if legacy_key not in self:
                    continue
                section = self.setdefault("plugins", {}).setdefault(plugin_id, {})
                section.setdefault(new_key, self[legacy_key])
                del self[legacy_key]

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
        instance._migrate_legacy_plugin_keys()
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
