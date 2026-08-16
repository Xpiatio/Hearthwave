import json
from unittest.mock import patch

import pytest

from backend.fcc import geocode


class FakeResponse:
    """urlopen stand-in: same shape as the one in test_crossref."""

    def __init__(self, payload):
        self._payload = payload

    def read(self, size=-1):
        return self._payload.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _hit(lat="42.9053", lon="-85.7936"):
    return json.dumps([{"lat": lat, "lon": lon, "display_name": "Jenison, Michigan"}])


@pytest.fixture(autouse=True)
def _clear_cache():
    geocode.clear_cache()
    geocode._last_request_at = 0.0
    yield
    geocode.clear_cache()


@pytest.fixture(autouse=True)
def sleeps():
    """No test waits on the real throttle; the ones about it read the mock."""
    with patch.object(geocode.time, "sleep") as mock_sleep:
        yield mock_sleep


class TestGeocodeCity:
    def test_returns_coordinates_from_api(self):
        with patch.object(geocode, "is_online", return_value=True), \
             patch("urllib.request.urlopen", return_value=FakeResponse(_hit())):
            assert geocode.geocode_city("Jenison, MI") == (42.9053, -85.7936)

    def test_blank_location_does_not_call_api(self):
        with patch("urllib.request.urlopen") as urlopen:
            assert geocode.geocode_city("  ") is None
        urlopen.assert_not_called()

    def test_offline_does_not_call_api(self):
        with patch.object(geocode, "is_online", return_value=False), \
             patch("urllib.request.urlopen") as urlopen:
            assert geocode.geocode_city("Jenison, MI") is None
        urlopen.assert_not_called()

    def test_second_lookup_is_served_from_cache(self):
        with patch.object(geocode, "is_online", return_value=True), \
             patch("urllib.request.urlopen", return_value=FakeResponse(_hit())) as urlopen:
            geocode.geocode_city("Jenison, MI")
            geocode.geocode_city("jenison, mi")
        assert urlopen.call_count == 1

    def test_empty_result_is_cached_as_a_miss(self):
        with patch.object(geocode, "is_online", return_value=True), \
             patch("urllib.request.urlopen", return_value=FakeResponse("[]")) as urlopen:
            assert geocode.geocode_city("Nowhere, ZZ") is None
            assert geocode.geocode_city("Nowhere, ZZ") is None
        assert urlopen.call_count == 1

    def test_network_error_is_not_cached(self):
        with patch.object(geocode, "is_online", return_value=True), \
             patch("urllib.request.urlopen", side_effect=OSError("boom")) as urlopen:
            assert geocode.geocode_city("Jenison, MI") is None
            assert geocode.geocode_city("Jenison, MI") is None
        assert urlopen.call_count == 2

    def test_out_of_range_coordinates_are_rejected(self):
        with patch.object(geocode, "is_online", return_value=True), \
             patch("urllib.request.urlopen", return_value=FakeResponse(_hit(lat="120.0"))):
            assert geocode.geocode_city("Jenison, MI") is None

    def test_request_identifies_the_app(self):
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["ua"] = req.get_header("User-agent")
            return FakeResponse(_hit())

        with patch.object(geocode, "is_online", return_value=True), \
             patch("urllib.request.urlopen", side_effect=fake_urlopen):
            geocode.geocode_city("Jenison, MI")
        assert "Hearthwave" in (captured["ua"] or "")

    def test_consecutive_lookups_are_spaced_out(self, sleeps):
        # Nominatim's usage policy allows about one request a second. A net
        # roll-call can start a dozen check-ins at once, so the throttle is
        # what keeps the app from getting its User-Agent blocked.
        with patch.object(geocode, "is_online", return_value=True), \
             patch("urllib.request.urlopen", return_value=FakeResponse(_hit())):
            geocode.geocode_city("Jenison, MI")
            geocode.geocode_city("Hudsonville, MI")
        waits = [call.args[0] for call in sleeps.call_args_list]
        assert waits and waits[0] > 0
        assert waits[0] <= geocode.MIN_REQUEST_INTERVAL_SECONDS

    def test_a_cached_answer_does_not_wait_on_the_throttle(self, sleeps):
        with patch.object(geocode, "is_online", return_value=True), \
             patch("urllib.request.urlopen", return_value=FakeResponse(_hit())):
            geocode.geocode_city("Jenison, MI")
            sleeps.reset_mock()
            geocode.geocode_city("Jenison, MI")
        assert sleeps.call_args_list == []

    def test_cache_does_not_grow_without_bound(self):
        with patch.object(geocode, "is_online", return_value=True), \
             patch("urllib.request.urlopen", return_value=FakeResponse(_hit())):
            for n in range(geocode.MAX_CACHE_ENTRIES + 10):
                geocode.geocode_city(f"Town {n}, MI")
        assert len(geocode._cache) <= geocode.MAX_CACHE_ENTRIES

    def test_the_oldest_entry_is_the_one_evicted(self):
        with patch.object(geocode, "is_online", return_value=True), \
             patch("urllib.request.urlopen", return_value=FakeResponse(_hit())):
            geocode.geocode_city("First, MI")
            for n in range(geocode.MAX_CACHE_ENTRIES):
                geocode.geocode_city(f"Town {n}, MI")
            # Only the oldest goes: wiping the whole cache would make every
            # town re-fetch, which is what the throttle makes expensive.
            assert "first, mi" not in geocode._cache
            assert "town 0, mi" in geocode._cache
            assert f"town {geocode.MAX_CACHE_ENTRIES - 1}, mi" in geocode._cache


class TestScatter:
    def test_is_deterministic_for_one_seed(self):
        assert geocode.scatter(42.9, -85.8, "WSLZ233") == geocode.scatter(42.9, -85.8, "WSLZ233")

    def test_separates_two_stations_in_one_city(self):
        a = geocode.scatter(42.9, -85.8, "WSLZ233")
        b = geocode.scatter(42.9, -85.8, "WRZM714")
        assert a != b

    def test_stays_within_the_city(self):
        lat, lon = geocode.scatter(42.9, -85.8, "WSLZ233")
        assert abs(lat - 42.9) <= geocode.SCATTER_DEG
        assert abs(lon - (-85.8)) <= geocode.SCATTER_DEG
