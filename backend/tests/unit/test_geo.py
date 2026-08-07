"""Unit tests for backend.geo — great-circle distance, bearing, compass.

Reference values are the standard worked examples for the haversine and
initial-bearing formulae, checked to a tolerance far tighter than any GPS fix
this app will ever see.
"""
from __future__ import annotations

import pytest

from backend.geo import bearing_deg, compass_point, haversine_km, km_to_miles


def test_zero_distance_to_self():
    assert haversine_km(42.9, -85.8, 42.9, -85.8) == pytest.approx(0.0, abs=1e-9)


def test_known_distance_jfk_to_lax():
    # JFK (40.6413, -73.7781) to LAX (33.9416, -118.4085): ~3974 km great circle.
    km = haversine_km(40.6413, -73.7781, 33.9416, -118.4085)
    assert km == pytest.approx(3974, rel=0.002)


def test_one_degree_of_latitude_is_about_111_km():
    assert haversine_km(0.0, 0.0, 1.0, 0.0) == pytest.approx(111.19, rel=0.001)


def test_antipodal_is_half_the_circumference():
    km = haversine_km(0.0, 0.0, 0.0, 180.0)
    assert km == pytest.approx(20015, rel=0.001)


def test_distance_is_symmetric():
    a = haversine_km(42.9, -85.8, 43.1, -85.5)
    b = haversine_km(43.1, -85.5, 42.9, -85.8)
    assert a == pytest.approx(b)


@pytest.mark.parametrize(
    "lat2,lon2,expected",
    [
        (43.9, -85.8, 0.0),    # due north
        (42.9, -84.8, 90.0),   # due east (short hop, so convergence is negligible)
        (41.9, -85.8, 180.0),  # due south
        (42.9, -86.8, 270.0),  # due west
    ],
)
def test_cardinal_bearings(lat2, lon2, expected):
    assert bearing_deg(42.9, -85.8, lat2, lon2) == pytest.approx(expected, abs=0.5)


def test_bearing_is_always_in_range():
    for lon in range(-180, 181, 15):
        assert 0.0 <= bearing_deg(42.9, -85.8, 10.0, float(lon)) < 360.0


@pytest.mark.parametrize(
    "deg,expected",
    [
        (0, "N"), (11, "N"), (12, "NNE"), (45, "NE"), (90, "E"),
        (180, "S"), (270, "W"), (348, "NNW"), (349, "N"), (359.9, "N"),
    ],
)
def test_compass_point(deg, expected):
    assert compass_point(deg) == expected


def test_compass_point_wraps_past_360():
    assert compass_point(360.0) == "N"
    assert compass_point(405.0) == "NE"


def test_km_to_miles():
    assert km_to_miles(1.609344) == pytest.approx(1.0)
