"""Name-based audio device lookup.

PortAudio builds its device list once, at Pa_Initialize(), and identifies
devices by position in that list.  Both properties bite us:

* A card that is busy when the scan runs is dropped from the list entirely,
  which shifts every device after it down one slot — so a stored index
  silently starts addressing different hardware.
* The list is never rebuilt, so a device that was busy at process start stays
  invisible for the life of the process (see refresh()).

Storing the device *name* and resolving it against the current list at use
time makes the selection stable across both.
"""
from __future__ import annotations

import logging

_log = logging.getLogger(__name__)

# "System Default" — let PortAudio pick.
DEFAULT = -1

_CHANNEL_KEY = {"input": "max_input_channels", "output": "max_output_channels"}

_cache: list[dict] | None = None


def _query() -> list[dict]:
    """Raw PortAudio enumeration.  Patched out in tests."""
    import sounddevice as sd

    return list(sd.query_devices())


def _reinit() -> None:
    """Tear PortAudio down and bring it back up so it re-scans the hardware.

    Unsafe while any stream is open — callers must close theirs first.
    """
    import sounddevice as sd

    sd._terminate()
    sd._initialize()


def invalidate_cache() -> None:
    """Drop the memoised enumeration so the next call re-reads PortAudio."""
    global _cache
    _cache = None


def refresh() -> None:
    """Re-scan audio hardware, picking up devices that were busy at startup.

    Invalidating our own cache is not sufficient: PortAudio itself builds the
    device list once at Pa_Initialize() and never revisits it, so a device
    that was unavailable then stays missing until it is re-initialised.
    """
    try:
        _reinit()
    except Exception as exc:
        # A failed re-init leaves the previous PortAudio state usable; a stale
        # list beats propagating the error into the settings dialog.
        _log.warning("PortAudio re-initialisation failed: %s", exc)
    invalidate_cache()


def _all_devices() -> list[dict]:
    global _cache
    if _cache is None:
        try:
            _cache = _query()
        except Exception as exc:
            _log.warning("Audio device enumeration failed: %s", exc)
            return []
    return _cache


def list_devices(kind: str) -> list[dict]:
    """Devices usable for *kind* ('input'/'output') as {"label", "id", "name"}.

    The id is the device name: it survives the index shuffling described above.
    """
    channel_key = _CHANNEL_KEY[kind]
    return [
        {"label": d["name"], "id": d["name"], "name": d["name"]}
        for d in _all_devices()
        if d.get(channel_key, 0) > 0
    ]


def name_at_index(index: int, kind: str) -> str | None:
    """Name of the device currently at *index*, if it is usable for *kind*.

    Used to migrate legacy index-based settings; returns None when the index
    is out of range or names a device with no channels of that kind.
    """
    channel_key = _CHANNEL_KEY[kind]
    all_devices = _all_devices()
    if 0 <= index < len(all_devices):
        candidate = all_devices[index]
        if candidate.get(channel_key, 0) > 0:
            return candidate["name"]
    return None


def resolve(stored: str | int | None, kind: str) -> int:
    """Map a stored device name to its current PortAudio index.

    Returns DEFAULT when *stored* is the default sentinel or names a device
    that is not currently present — falling back to the system default beats
    addressing whatever hardware happens to occupy that slot now.
    """
    if stored is None or stored == DEFAULT or stored == "":
        return DEFAULT

    channel_key = _CHANNEL_KEY[kind]
    for i, d in enumerate(_all_devices()):
        if d["name"] == stored and d.get(channel_key, 0) > 0:
            return i

    _log.info("Audio device %r not present for %s — using system default", stored, kind)
    return DEFAULT
