"""City-centroid geocoding for FCC license locations.

The crossref API hands back a licensee's city and state, never a house
number, so the best a pin from a license can ever be is the middle of a
town. Everything here leans on that: one lookup per city serves every
station licensed there, results are cached for the life of the process
because town centres do not move, and a pin is scattered a few hundred
metres off the centroid so several stations in one city stay separately
clickable.

A miss is cached alongside a hit — a town Nominatim cannot resolve will
not resolve on the next check-in either. Transient failures are not
cached, so a flaky network re-tries.
"""
from __future__ import annotations

import hashlib
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from backend.net.online import is_online

_log = logging.getLogger(__name__)

API_BASE = "https://nominatim.openstreetmap.org/search"
REQUEST_TIMEOUT_SECONDS = 5.0

#: Nominatim's usage policy requires a User-Agent that identifies the app.
USER_AGENT = "Hearthwave/1.0 (+https://xpiatio.github.io/Hearthwave/)"

#: Half-width of the scatter box, in degrees — roughly 300 m of latitude.
#: Wide enough to keep two pins from overlapping at neighbourhood zoom,
#: far narrower than the city the centroid already generalises to.
SCATTER_DEG = 0.0027

#: US cities number in the tens of thousands; a net sees a handful. The cap
#: is only there so a malformed run of location strings can't grow the cache
#: for the life of the process.
MAX_CACHE_ENTRIES = 2048

_MISS = object()
_cache: dict[str, object] = {}


def clear_cache() -> None:
    _cache.clear()


def _remember(key: str, value: object) -> None:
    if len(_cache) >= MAX_CACHE_ENTRIES:
        _cache.clear()
    _cache[key] = value


def geocode_city(location: str) -> tuple[float, float] | None:
    """Resolve a "City, ST" string to a centroid, or None if it can't be.

    Skips the HTTP call when offline for the same reason verify_callsign
    does: a check-in must never sit on a network timeout.
    """
    key = " ".join((location or "").split()).lower()
    if not key:
        return None

    cached = _cache.get(key, None)
    if cached is _MISS:
        return None
    if cached is not None:
        return cached  # type: ignore[return-value]

    if not is_online():
        return None

    query = urllib.parse.urlencode({"q": location, "format": "json", "limit": 1})
    request = urllib.request.Request(
        f"{API_BASE}?{query}", headers={"User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
            body = resp.read(256 * 1024)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        _log.debug("geocode failed for %r: %s", location, exc)
        return None

    try:
        results = json.loads(body)
        lat = float(results[0]["lat"])
        lon = float(results[0]["lon"])
    except (json.JSONDecodeError, ValueError, TypeError, KeyError, IndexError):
        _remember(key, _MISS)
        return None

    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        _remember(key, _MISS)
        return None

    _remember(key, (lat, lon))
    return lat, lon


def scatter(lat: float, lon: float, seed: str) -> tuple[float, float]:
    """Nudge a shared centroid deterministically so pins don't stack.

    Deterministic in `seed` (a callsign) so a station's pin lands in the
    same spot every net rather than jumping around the town square.
    """
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    lat_frac = int.from_bytes(digest[:4], "big") / 0xFFFFFFFF
    lon_frac = int.from_bytes(digest[4:8], "big") / 0xFFFFFFFF
    return (
        lat + (lat_frac * 2 - 1) * SCATTER_DEG,
        lon + (lon_frac * 2 - 1) * SCATTER_DEG,
    )
