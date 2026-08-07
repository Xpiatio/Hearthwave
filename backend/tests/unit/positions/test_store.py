"""Unit tests for backend.positions.store.

Covers the parts that decide whether a bad or hostile input can hurt us:
range validation, the null-island reject, the entry cap, TTL expiry, and the
persistence round-trip. Time is injected everywhere so nothing sleeps.
"""
from __future__ import annotations

import json

import pytest

from backend.positions.store import (
    MAX_EXTRA_KEYS,
    MAX_LABEL_LEN,
    InvalidPosition,
    PositionStore,
    validate_coords,
)

T0 = 1_700_000_000.0


@pytest.fixture
def store(tmp_path):
    return PositionStore(tmp_path / "positions.json", ttl_minutes=60, max_entries=5)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_validate_coords_accepts_ordinary_fix():
    assert validate_coords(42.9, -85.8) == (42.9, -85.8)


def test_validate_coords_accepts_strings():
    assert validate_coords("42.9", "-85.8") == (42.9, -85.8)


@pytest.mark.parametrize("lat,lon", [(91.0, 0.0), (-91.0, 0.0), (0.0, 181.0), (0.0, -181.0)])
def test_validate_coords_rejects_out_of_range(lat, lon):
    with pytest.raises(InvalidPosition):
        validate_coords(lat, lon)


def test_validate_coords_rejects_null_island():
    with pytest.raises(InvalidPosition):
        validate_coords(0.0, 0.0)


def test_validate_coords_allows_a_zero_on_one_axis_only():
    assert validate_coords(0.0, -85.8) == (0.0, -85.8)


@pytest.mark.parametrize("lat,lon", [("north", 0.0), (None, 1.0), (1.0, object())])
def test_validate_coords_rejects_non_numeric(lat, lon):
    with pytest.raises(InvalidPosition):
        validate_coords(lat, lon)


def test_upsert_requires_source_and_node_id(store):
    with pytest.raises(InvalidPosition):
        store.upsert("", "node", 42.9, -85.8)
    with pytest.raises(InvalidPosition):
        store.upsert("aprs", "  ", 42.9, -85.8)


# ---------------------------------------------------------------------------
# Upsert semantics
# ---------------------------------------------------------------------------

def test_upsert_keys_on_source_and_node(store):
    store.upsert("aprs", "W8ABC-9", 42.9, -85.8, now=T0)
    store.upsert("meshtastic", "W8ABC-9", 43.0, -85.7, now=T0)
    assert len(store) == 2


def test_upsert_replaces_same_key(store):
    store.upsert("aprs", "W8ABC-9", 42.9, -85.8, now=T0)
    record = store.upsert("aprs", "W8ABC-9", 43.0, -85.7, now=T0 + 10)
    assert len(store) == 1
    assert (record.lat, record.lon) == (43.0, -85.7)


def test_update_without_label_keeps_the_known_one(store):
    store.upsert("meshtastic", "!abcd", 42.9, -85.8, label="Barn", now=T0)
    record = store.upsert("meshtastic", "!abcd", 42.91, -85.81, now=T0 + 10)
    assert record.label == "Barn"


def test_label_is_clamped(store):
    record = store.upsert("aprs", "n1", 42.9, -85.8, label="x" * 500, now=T0)
    assert len(record.label) == MAX_LABEL_LEN


def test_extra_metadata_is_bounded(store):
    record = store.upsert(
        "aprs", "n1", 42.9, -85.8,
        extra={f"k{i}": "v" * 400 for i in range(50)},
        now=T0,
    )
    assert len(record.extra) == MAX_EXTRA_KEYS
    assert all(len(v) <= 120 for v in record.extra.values())


def test_altitude_is_optional_and_tolerant(store):
    assert store.upsert("aprs", "n1", 42.9, -85.8, now=T0).alt_m is None
    assert store.upsert("aprs", "n2", 42.9, -85.8, alt_m="240", now=T0).alt_m == 240.0
    assert store.upsert("aprs", "n3", 42.9, -85.8, alt_m="high", now=T0).alt_m is None


# ---------------------------------------------------------------------------
# Cap + TTL
# ---------------------------------------------------------------------------

def test_cap_evicts_the_stalest_entries(store):
    for i in range(8):
        store.upsert("aprs", f"n{i}", 42.9, -85.8, now=T0 + i)
    assert len(store) == 5
    remaining = {r.node_id for r in store.active(T0 + 100)}
    assert remaining == {"n3", "n4", "n5", "n6", "n7"}


def test_active_excludes_expired(store):
    store.upsert("aprs", "old", 42.9, -85.8, now=T0)
    store.upsert("aprs", "new", 43.0, -85.7, now=T0 + 3500)
    live = store.active(now=T0 + 3601)
    assert [r.node_id for r in live] == ["new"]


def test_active_does_not_mutate(store):
    store.upsert("aprs", "old", 42.9, -85.8, now=T0)
    store.active(now=T0 + 999_999)
    assert len(store) == 1


def test_purge_expired_removes_and_counts(store):
    store.upsert("aprs", "old", 42.9, -85.8, now=T0)
    store.upsert("aprs", "new", 43.0, -85.7, now=T0 + 3500)
    assert store.purge_expired(now=T0 + 3601) == 1
    assert len(store) == 1


def test_set_ttl_minutes_has_a_floor(store):
    store.set_ttl_minutes(0)
    assert store.ttl_minutes == 1


def test_active_is_freshest_first(store):
    store.upsert("aprs", "a", 42.9, -85.8, now=T0)
    store.upsert("aprs", "b", 42.9, -85.8, now=T0 + 5)
    assert [r.node_id for r in store.active(T0 + 6)] == ["b", "a"]


# ---------------------------------------------------------------------------
# Snapshot payload
# ---------------------------------------------------------------------------

def test_snapshot_without_origin_has_no_distance(store):
    store.upsert("aprs", "n1", 42.9, -85.8, now=T0)
    row = store.snapshot(origin=None, now=T0)[0]
    assert row["distance_km"] is None
    assert row["bearing_deg"] is None
    assert row["compass"] is None


def test_snapshot_with_origin_resolves_distance_and_bearing(store):
    store.upsert("aprs", "north", 43.9, -85.8, now=T0)
    row = store.snapshot(origin=(42.9, -85.8), now=T0)[0]
    assert row["distance_km"] == pytest.approx(111.2, rel=0.01)
    assert row["compass"] == "N"


def test_snapshot_sorts_nearest_first_when_origin_known(store):
    store.upsert("aprs", "far", 45.0, -85.8, now=T0)
    store.upsert("aprs", "near", 42.95, -85.8, now=T0)
    assert [r["node_id"] for r in store.snapshot(origin=(42.9, -85.8), now=T0)] == ["near", "far"]


def test_snapshot_age_is_server_resolved_and_never_negative(store):
    store.upsert("aprs", "n1", 42.9, -85.8, now=T0)
    assert store.snapshot(now=T0 + 90)[0]["age_s"] == 90
    # A node whose clock ran ahead of ours must not render as "-4 s ago".
    assert store.snapshot(now=T0 - 4)[0]["age_s"] == 0


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def test_flush_is_a_no_op_when_clean(tmp_path):
    store = PositionStore(tmp_path / "p.json")
    assert store.flush() is False
    assert not (tmp_path / "p.json").exists()


def test_round_trip(tmp_path):
    path = tmp_path / "p.json"
    first = PositionStore(path, ttl_minutes=60)
    first.upsert("aprs", "W8ABC-9", 42.9, -85.8, label="Truck", alt_m=240.0,
                 extra={"comment": "mobile"}, now=T0)
    assert first.flush() is True

    second = PositionStore(path, ttl_minutes=60)
    record = second.active(now=T0)[0]
    assert (record.source, record.node_id, record.label) == ("aprs", "W8ABC-9", "Truck")
    assert (record.lat, record.lon, record.alt_m) == (42.9, -85.8, 240.0)
    assert record.extra == {"comment": "mobile"}


def test_load_skips_corrupt_rows(tmp_path):
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"positions": [
        {"source": "aprs", "node_id": "good", "lat": 42.9, "lon": -85.8, "heard_at": T0},
        {"source": "aprs", "node_id": "no-coords", "heard_at": T0},
        {"lat": 1.0, "lon": 2.0, "heard_at": T0},
        "not-a-dict-at-all",
    ]}), encoding="utf-8")
    store = PositionStore(path, ttl_minutes=60)
    assert [r.node_id for r in store.active(T0)] == ["good"]


def test_load_tolerates_garbage_file(tmp_path):
    path = tmp_path / "p.json"
    path.write_text("{not json", encoding="utf-8")
    assert len(PositionStore(path)) == 0


def test_remove_and_clear(store):
    store.upsert("aprs", "n1", 42.9, -85.8, now=T0)
    assert store.remove("aprs", "nope") is False
    assert store.remove("aprs", "n1") is True
    store.upsert("aprs", "n2", 42.9, -85.8, now=T0)
    store.clear()
    assert len(store) == 0


def test_flush_survives_an_unwritable_path(tmp_path):
    # /data going read-only must not take the radio down.
    store = PositionStore(tmp_path / "missing-dir" / "p.json", ttl_minutes=60)
    store.upsert("aprs", "n1", 42.9, -85.8, now=T0)
    (tmp_path / "missing-dir").write_text("I am a file, not a directory", encoding="utf-8")
    assert store.flush() is False
    assert len(store) == 1


def test_take_pending_snapshots_so_the_write_can_go_off_thread(tmp_path):
    # The server builds the payload on the event loop and writes it in a
    # worker; the snapshot must not alias the live dict, or a position
    # arriving mid-write would change size during iteration.
    store = PositionStore(tmp_path / "p.json", ttl_minutes=60)
    store.upsert("aprs", "n1", 42.9, -85.8, now=T0)
    pending = store.take_pending()
    assert pending is not None and len(pending["positions"]) == 1

    store.upsert("aprs", "n2", 43.0, -85.9, now=T0)
    assert len(pending["positions"]) == 1  # unaffected by the later upsert
    assert store.write(pending) is True

    reloaded = PositionStore(tmp_path / "p.json", ttl_minutes=60)
    assert [r.node_id for r in reloaded.active(T0)] == ["n1"]


def test_take_pending_returns_none_when_clean(tmp_path):
    store = PositionStore(tmp_path / "p.json", ttl_minutes=60)
    assert store.take_pending() is None
    store.upsert("aprs", "n1", 42.9, -85.8, now=T0)
    assert store.take_pending() is not None
    assert store.take_pending() is None  # dirty flag cleared by the first call


def test_a_failed_write_re_arms_the_dirty_flag(tmp_path):
    # Otherwise a transient full disk would silently drop the positions until
    # the next station happened to be heard.
    store = PositionStore(tmp_path / "missing-dir" / "p.json", ttl_minutes=60)
    store.upsert("aprs", "n1", 42.9, -85.8, now=T0)
    (tmp_path / "missing-dir").write_text("I am a file, not a directory", encoding="utf-8")
    pending = store.take_pending()
    assert pending is not None
    assert store.write(pending) is False
    assert store.take_pending() is not None  # retried on the next pass
