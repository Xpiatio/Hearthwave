"""TNC2 text -> normalised position, via aprslib.

APRS encodes coordinates three different ways (uncompressed, Base-91
compressed, and Mic-E, which hides half the latitude in the destination
callsign). `aprslib` already implements all three, so this module only maps its
output onto what `ctx.report_position` wants and drops everything that carries
no fix — status, messages, telemetry, bulletins.

aprslib is imported lazily so the plugin still loads (and reports a clear error
when enabled) on installs that never pip-installed it.
"""
from __future__ import annotations

_aprslib = None


def load_aprslib():
    """Import aprslib, raising a message an operator can act on."""
    global _aprslib
    if _aprslib is None:
        try:
            import aprslib  # optional dependency
        except ImportError as exc:  # pragma: no cover - env-dependent
            raise RuntimeError(
                "aprslib not installed — `pip install aprslib` to enable the APRS RF plugin"
            ) from exc
        _aprslib = aprslib
    return _aprslib


def parse_position(tnc2: str) -> dict | None:
    """Return ``{node_id, lat, lon, alt_m, extra}``, or None if there's no fix.

    Never raises for bad input: a shared RF channel carries plenty of packets
    that aren't positions, and one malformed beacon must not end the read loop.
    """
    aprslib = load_aprslib()
    try:
        packet = aprslib.parse(tnc2)
    except aprslib.exceptions.GenericError:
        return None
    except Exception:
        # aprslib is strict about well-formed input but not exhaustively
        # defensive; RF gives it bytes no sender intended.
        return None

    source = str(packet.get("from") or "").strip()
    lat, lon = packet.get("latitude"), packet.get("longitude")
    if not source or lat is None or lon is None:
        return None
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return None

    return {
        "node_id": source,
        "lat": lat,
        "lon": lon,
        "alt_m": _as_float(packet.get("altitude")),
        "extra": _extra(packet),
    }


def _extra(packet: dict) -> dict:
    """The handful of fields worth showing in a marker popup. The store clamps
    key count and value length, so this only has to pick, not police."""
    extra: dict[str, str] = {}
    comment = str(packet.get("comment") or "").strip()
    if comment:
        extra["comment"] = comment
    symbol = f"{packet.get('symbol_table') or ''}{packet.get('symbol') or ''}".strip()
    if symbol:
        extra["symbol"] = symbol
    speed = _as_float(packet.get("speed"))
    if speed is not None and speed > 0:
        extra["speed"] = f"{speed:.0f} km/h"
    course = _as_float(packet.get("course"))
    if course is not None:
        extra["course"] = f"{course:.0f}°"
    path = packet.get("path")
    if isinstance(path, (list, tuple)) and path:
        extra["path"] = ",".join(str(hop) for hop in path)
    return extra


def _as_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
