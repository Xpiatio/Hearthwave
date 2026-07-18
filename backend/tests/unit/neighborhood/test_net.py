"""Unit tests for backend.neighborhood.net.NeighborhoodNet (pure state machine)."""
from __future__ import annotations

from backend.neighborhood.net import NeighborhoodNet


def test_starts_inactive_with_no_current_call():
    n = NeighborhoodNet()
    assert n.active is False
    assert n.current_call is None
    assert n.roster() == []


def test_start_activates_and_clears_prior_roster():
    n = NeighborhoodNet()
    n.start()
    n.checkin("u1", "A", "Ann", "5th St")
    n.end()
    n.start()
    assert n.active is True
    assert n.current_call is None
    assert n.roster() == []


def test_end_returns_roster_snapshot_and_deactivates():
    n = NeighborhoodNet()
    n.start()
    n.checkin("u1", "A", "Ann", "5th St")
    summary = n.end()
    assert n.active is False
    assert summary["roster"][0]["callsign"] == "A"
    assert "duration_seconds" in summary


def test_checkin_idempotent_updates():
    n = NeighborhoodNet()
    n.start()
    n.checkin("u1", "WRXB123", "Ben", "5th St")
    n.checkin("u1", "WRXB123", "Ben", "Oak Ave")
    assert len(n.roster()) == 1 and n.roster()[0]["location"] == "Oak Ave"


def test_checkin_defaults_to_checked_in_status():
    n = NeighborhoodNet()
    n.start()
    row = n.checkin("u1", "A", "Ann", "")
    assert row["status"] == "checked_in"
    assert row["called"] is False


def test_call_next_round():
    n = NeighborhoodNet()
    n.start()
    n.checkin("u1", "A", "Ann", "")
    n.checkin("u2", "B", "Bob", "")
    first = n.call_next()
    second = n.call_next()
    assert (first["user_id"], second["user_id"]) == ("u1", "u2")
    assert n.current_call == "u2"
    assert n.call_next() is None  # round complete
    n.call_reset()
    assert n.call_next()["user_id"] == "u1"


def test_call_reset_clears_called_and_current():
    n = NeighborhoodNet()
    n.start()
    n.checkin("u1", "A", "Ann", "")
    n.call_next()
    assert n.current_call == "u1"
    n.call_reset()
    assert n.current_call is None
    assert n.roster()[0]["called"] is False


def test_standby_skipped():
    n = NeighborhoodNet()
    n.start()
    n.checkin("u1", "A", "Ann", "")
    n.set_status("u1", "standby")
    assert n.call_next() is None


def test_set_status_back_to_checked_in_makes_eligible_again():
    n = NeighborhoodNet()
    n.start()
    n.checkin("u1", "A", "Ann", "")
    n.set_status("u1", "standby")
    n.set_status("u1", "checked_in")
    row = n.call_next()
    assert row is not None and row["user_id"] == "u1"


def test_set_status_unknown_user_is_noop():
    n = NeighborhoodNet()
    n.start()
    n.set_status("nobody", "standby")  # must not raise
    assert n.roster() == []
