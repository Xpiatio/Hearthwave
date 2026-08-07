"""Store of positions heard from other stations.

Positions arrive from plugins (a mesh radio's node database, an APRS TNC) and
are held keyed by ``(source, node_id)`` — the same callsign heard on two
different bearers is two rows, because they are two different radios telling
us two different things.

Everything here is best-effort, ephemeral data: a position is only as good as
its age, so reads expire anything older than the configured TTL and the file
on disk exists purely so a restart does not blank the map. That is why writes
are deliberately not durable-per-update; the server flushes on a timer (see
``flush``), and losing the last few seconds of positions costs nothing.

The entry cap is the same reasoning as ``_OUTBOUND_QUEUE_MAX`` in
``plugins/mesh_forwarder.py``: a busy APRS band is an unbounded input, and an
unbounded input needs a bound somewhere.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from backend.geo import bearing_deg, compass_point, haversine_km
from backend.persistence._utils import atomic_json_write

_log = logging.getLogger(__name__)

_DEFAULT_PATH = Path(os.environ.get("RADIO_TTY_POSITIONS", "/data/positions.json"))

MAX_LABEL_LEN = 64
MAX_SOURCE_LEN = 32
MAX_NODE_ID_LEN = 64
MAX_EXTRA_KEYS = 12
MAX_EXTRA_VALUE_LEN = 120

#: Hard ceiling on stored stations. Well above any plausible neighbourhood
#: net or mesh; low enough that a chatty APRS band cannot grow the file
#: without limit. Eviction is oldest-heard-first.
MAX_ENTRIES = 500

DEFAULT_TTL_MINUTES = 1440


class InvalidPosition(ValueError):
    """A reported position failed validation and was not stored."""


@dataclass(frozen=True)
class PositionRecord:
    source: str
    node_id: str
    label: str
    lat: float
    lon: float
    heard_at: float          # epoch seconds
    alt_m: float | None = None
    extra: dict = field(default_factory=dict)

    def to_payload(self, now: float, origin: tuple[float, float] | None) -> dict:
        """Wire form for the WS/state payload.

        Age is resolved server-side rather than shipping a timestamp because a
        wall kiosk's clock is not to be trusted, and distance/bearing likewise
        because the e-ink list has no way to compute them.
        """
        payload = {
            "source": self.source,
            "node_id": self.node_id,
            "label": self.label,
            "lat": self.lat,
            "lon": self.lon,
            "alt_m": self.alt_m,
            "age_s": max(0, int(now - self.heard_at)),
            "extra": self.extra,
            "distance_km": None,
            "bearing_deg": None,
            "compass": None,
        }
        if origin is not None:
            o_lat, o_lon = origin
            bearing = bearing_deg(o_lat, o_lon, self.lat, self.lon)
            payload["distance_km"] = round(haversine_km(o_lat, o_lon, self.lat, self.lon), 3)
            payload["bearing_deg"] = round(bearing, 1)
            payload["compass"] = compass_point(bearing)
        return payload


def _clamp(text: object, limit: int) -> str:
    return str(text or "").strip()[:limit]


def validate_coords(lat: object, lon: object) -> tuple[float, float]:
    """Coerce and range-check a coordinate pair.

    Rejects exactly (0, 0) — "null island" is what a GPS-less node reports far
    more often than it is a real fix in the Gulf of Guinea.
    """
    try:
        lat_f, lon_f = float(lat), float(lon)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise InvalidPosition(f"Non-numeric coordinates: {lat!r}, {lon!r}") from exc
    if not (-90.0 <= lat_f <= 90.0) or not (-180.0 <= lon_f <= 180.0):
        raise InvalidPosition(f"Coordinates out of range: {lat_f}, {lon_f}")
    if lat_f == 0.0 and lon_f == 0.0:
        raise InvalidPosition("Null-island coordinates (0, 0) rejected")
    return lat_f, lon_f


class PositionStore:
    def __init__(
        self,
        path: Path | None = None,
        *,
        ttl_minutes: int = DEFAULT_TTL_MINUTES,
        max_entries: int = MAX_ENTRIES,
    ) -> None:
        self._path = path or _DEFAULT_PATH
        self._max_entries = max(1, int(max_entries))
        self._ttl_s = max(60, int(ttl_minutes) * 60)
        self._records: dict[tuple[str, str], PositionRecord] = {}
        self._dirty = False
        self._load()

    # ---- configuration ---------------------------------------------------

    @property
    def ttl_minutes(self) -> int:
        return self._ttl_s // 60

    def set_ttl_minutes(self, minutes: int) -> None:
        self._ttl_s = max(60, int(minutes) * 60)

    # ---- persistence -----------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            _log.warning("Could not load %s: %s; starting empty", self._path, exc)
            return
        if not isinstance(data, dict):
            return
        for raw in data.get("positions", []):
            try:
                record = PositionRecord(
                    source=_clamp(raw["source"], MAX_SOURCE_LEN),
                    node_id=_clamp(raw["node_id"], MAX_NODE_ID_LEN),
                    label=_clamp(raw.get("label"), MAX_LABEL_LEN),
                    lat=float(raw["lat"]),
                    lon=float(raw["lon"]),
                    heard_at=float(raw["heard_at"]),
                    alt_m=None if raw.get("alt_m") is None else float(raw["alt_m"]),
                    extra=dict(raw.get("extra") or {}),
                )
            except (KeyError, TypeError, ValueError):
                continue
            if record.source and record.node_id:
                self._records[(record.source, record.node_id)] = record

    def take_pending(self) -> dict | None:
        """Snapshot for disk, or None if nothing changed. Clears the dirty flag.

        Split from :meth:`write` so the caller can build the snapshot on the
        event loop and do the file I/O in a worker thread: iterating
        ``_records`` off-thread while a plugin reports a new fix would raise
        "dictionary changed size during iteration".
        """
        if not self._dirty:
            return None
        self._dirty = False
        return {
            "positions": [
                {
                    "source": r.source,
                    "node_id": r.node_id,
                    "label": r.label,
                    "lat": r.lat,
                    "lon": r.lon,
                    "heard_at": r.heard_at,
                    "alt_m": r.alt_m,
                    "extra": r.extra,
                }
                for r in self._records.values()
            ]
        }

    def write(self, payload: dict) -> bool:
        """Write a snapshot from :meth:`take_pending`. Safe to call off-thread."""
        try:
            atomic_json_write(self._path, payload)
        except OSError as exc:
            # A read-only or full /data must not take the radio down; the
            # positions themselves are still live in memory. Re-arm the dirty
            # flag so the next pass retries instead of dropping the write.
            _log.warning("Could not persist positions to %s: %s", self._path, exc)
            self._dirty = True
            return False
        return True

    def flush(self) -> bool:
        """Persist if anything changed since the last flush. Returns True if written."""
        payload = self.take_pending()
        if payload is None:
            return False
        return self.write(payload)

    # ---- mutation --------------------------------------------------------

    def upsert(
        self,
        source: str,
        node_id: str,
        lat: float,
        lon: float,
        *,
        label: str = "",
        alt_m: float | None = None,
        extra: dict | None = None,
        now: float | None = None,
    ) -> PositionRecord:
        """Record a heard position. Raises InvalidPosition on bad input."""
        source = _clamp(source, MAX_SOURCE_LEN)
        node_id = _clamp(node_id, MAX_NODE_ID_LEN)
        if not source or not node_id:
            raise InvalidPosition("source and node_id are required")
        lat_f, lon_f = validate_coords(lat, lon)

        alt: float | None = None
        if alt_m is not None:
            try:
                alt = float(alt_m)
            except (TypeError, ValueError):
                alt = None

        key = (source, node_id)
        previous = self._records.get(key)
        # An update that omits the label keeps the one we already knew: mesh
        # node databases routinely hand back a position before the node's name.
        resolved_label = _clamp(label, MAX_LABEL_LEN) or (previous.label if previous else "")

        record = PositionRecord(
            source=source,
            node_id=node_id,
            label=resolved_label,
            lat=lat_f,
            lon=lon_f,
            heard_at=float(now if now is not None else time.time()),
            alt_m=alt,
            extra=self._clean_extra(extra),
        )
        self._records[key] = record
        self._dirty = True
        self._enforce_cap()
        return record

    @staticmethod
    def _clean_extra(extra: dict | None) -> dict:
        if not isinstance(extra, dict):
            return {}
        cleaned: dict[str, str] = {}
        for name, value in extra.items():
            if len(cleaned) >= MAX_EXTRA_KEYS:
                break
            key = _clamp(name, MAX_LABEL_LEN)
            if key:
                cleaned[key] = _clamp(value, MAX_EXTRA_VALUE_LEN)
        return cleaned

    def _enforce_cap(self) -> None:
        overflow = len(self._records) - self._max_entries
        if overflow <= 0:
            return
        stalest = sorted(self._records.items(), key=lambda kv: kv[1].heard_at)[:overflow]
        for key, _ in stalest:
            del self._records[key]
        _log.info("Position store over cap; evicted %d stalest entries", overflow)

    def remove(self, source: str, node_id: str) -> bool:
        if self._records.pop((source, node_id), None) is None:
            return False
        self._dirty = True
        return True

    def clear(self) -> None:
        if self._records:
            self._records.clear()
            self._dirty = True

    # ---- reads -----------------------------------------------------------

    def purge_expired(self, now: float | None = None) -> int:
        """Drop records older than the TTL. Returns the number removed."""
        cutoff = (now if now is not None else time.time()) - self._ttl_s
        expired = [key for key, rec in self._records.items() if rec.heard_at < cutoff]
        for key in expired:
            del self._records[key]
        if expired:
            self._dirty = True
        return len(expired)

    def active(self, now: float | None = None) -> list[PositionRecord]:
        """Non-expired records, freshest first. Does not mutate the store."""
        moment = now if now is not None else time.time()
        cutoff = moment - self._ttl_s
        live = [rec for rec in self._records.values() if rec.heard_at >= cutoff]
        live.sort(key=lambda rec: rec.heard_at, reverse=True)
        return live

    def snapshot(
        self,
        origin: tuple[float, float] | None = None,
        now: float | None = None,
    ) -> list[dict]:
        """Wire payload for the state/display messages.

        Sorted nearest-first when we know where we are, freshest-first when we
        do not — the distance-sorted e-ink list depends on this ordering, and
        doing it here keeps the two renderers from disagreeing.
        """
        moment = now if now is not None else time.time()
        payloads = [rec.to_payload(moment, origin) for rec in self.active(moment)]
        if origin is not None:
            payloads.sort(key=lambda p: p["distance_km"])
        return payloads

    def __len__(self) -> int:
        return len(self._records)
