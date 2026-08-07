"""Great-circle helpers for position display.

Pure functions, no dependencies. Distances are small enough here (a
neighbourhood net, a mesh, an APRS receive footprint) that the spherical
earth model is well inside the error of a consumer GPS fix.
"""
from __future__ import annotations

import math

EARTH_RADIUS_KM = 6371.0088  # IUGG mean radius

KM_PER_MILE = 1.609344

#: 16-point compass, indexed by round(bearing / 22.5) % 16.
COMPASS_POINTS: tuple[str, ...] = (
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points, in kilometres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, a)))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial great-circle bearing from point 1 to point 2, in degrees true.

    Returned in [0, 360). This is the *initial* bearing; over the distances
    this app deals with it does not measurably diverge from the rhumb line.
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_lambda = math.radians(lon2 - lon1)
    y = math.sin(d_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lambda)
    return math.degrees(math.atan2(y, x)) % 360.0


def compass_point(deg: float) -> str:
    """Nearest 16-point compass abbreviation for a bearing in degrees."""
    return COMPASS_POINTS[int(round(deg / 22.5)) % 16]


def km_to_miles(km: float) -> float:
    return km / KM_PER_MILE
