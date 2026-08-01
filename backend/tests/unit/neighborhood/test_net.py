"""Unit tests for backend.neighborhood.net.NeighborhoodNet (pure state machine)."""
from __future__ import annotations

from unittest.mock import patch

from backend.neighborhood.net import NeighborhoodNet


def test_starts_inactive_with_no_current_call():
    n = NeighborhoodNet()
    assert n.active is False
    assert n.current_call is None
    assert n.roster() == []


def test_start_activates_and_does_not_clear_roster():
    n = NeighborhoodNet()
    n.start()
    n.checkin("u1", "A", "Ann", "5th St")
    n.start()  # a re-start while active must not wipe existing check-ins
    assert n.active is True
    assert n.current_call is None
    assert len(n.roster()) == 1
    assert n.roster()[0]["user_id"] == "u1"


def test_checkin_while_inactive_survives_into_started_net():
    """An early check-in (before start()) is a 'tap' that reserves a spot;
    starting the net must not wipe it."""
    n = NeighborhoodNet()
    n.checkin("u1", "A", "Ann", "5th St")
    assert n.active is False
    n.start()
    assert n.active is True
    assert len(n.roster()) == 1
    row = n.roster()[0]
    assert row["user_id"] == "u1"
    assert row["called"] is False


def test_end_clears_roster():
    n = NeighborhoodNet()
    n.start()
    n.checkin("u1", "A", "Ann", "5th St")
    n.end()
    assert n.roster() == []


def test_end_summary_still_contains_pre_clear_roster():
    n = NeighborhoodNet()
    n.start()
    n.checkin("u1", "A", "Ann", "5th St")
    summary = n.end()
    assert len(summary["roster"]) == 1
    assert summary["roster"][0]["callsign"] == "A"
    assert n.roster() == []  # live roster is empty even though summary kept it


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
    assert row["checkin_time"]  # non-empty ISO timestamp


def test_checkin_time_updates_on_idempotent_re_checkin():
    """Re-checking in updates checkin_time to the latest check-in — the
    honest presence signal — rather than preserving the original."""
    n = NeighborhoodNet()
    n.start()
    first = n.checkin("u1", "A", "Ann", "5th St")
    first_time = first["checkin_time"]
    with patch("backend.neighborhood.net.utc_now_iso", return_value="2099-01-01T00:00:00Z"):
        second = n.checkin("u1", "A", "Ann", "Oak Ave")
    assert second["checkin_time"] == "2099-01-01T00:00:00Z"
    assert second["checkin_time"] != first_time


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


def test_remove_deletes_roster_row():
    n = NeighborhoodNet()
    n.start()
    n.checkin("u1", "A", "Ann", "")
    n.checkin("u2", "B", "Bob", "")
    assert n.remove("u1") is True
    assert [r["user_id"] for r in n.roster()] == ["u2"]


def test_remove_unknown_user_is_noop_and_returns_false():
    n = NeighborhoodNet()
    n.start()
    n.checkin("u1", "A", "Ann", "")
    assert n.remove("nobody") is False
    assert len(n.roster()) == 1


def test_remove_clears_current_call_when_it_pointed_at_removed_user():
    n = NeighborhoodNet()
    n.start()
    n.checkin("u1", "A", "Ann", "")
    n.call_next()
    assert n.current_call == "u1"
    n.remove("u1")
    assert n.current_call is None


def test_remove_leaves_current_call_alone_when_it_points_elsewhere():
    n = NeighborhoodNet()
    n.start()
    n.checkin("u1", "A", "Ann", "")
    n.checkin("u2", "B", "Bob", "")
    n.call_next()
    assert n.current_call == "u1"
    n.remove("u2")
    assert n.current_call == "u1"


def test_clear_checkins_empties_the_roster_and_reports_the_count():
    n = NeighborhoodNet()
    n.start()
    n.checkin("u1", "A", "Ann", "")
    n.checkin("u2", "B", "Bob", "")
    assert n.clear_checkins() == 2
    assert n.roster() == []


def test_clear_checkins_on_an_empty_roster_is_a_noop_returning_zero():
    n = NeighborhoodNet()
    assert n.clear_checkins() == 0
    assert n.roster() == []


def test_clear_checkins_drops_current_call_with_the_rows():
    n = NeighborhoodNet()
    n.start()
    n.checkin("u1", "A", "Ann", "")
    n.call_next()
    assert n.current_call == "u1"
    n.clear_checkins()
    assert n.current_call is None


def test_clear_checkins_leaves_a_running_net_running():
    # Unlike end(), clearing the board is not a way to close the net.
    n = NeighborhoodNet()
    n.start()
    n.checkin("u1", "A", "Ann", "")
    n.clear_checkins()
    assert n.active is True


class TestEndTimestamps:
    def test_end_reports_start_and_end_times(self):
        net = NeighborhoodNet()
        net.checkin("u1", "WRAB123", "Sam", "Zeeland")
        net.start()
        summary = net.end()
        assert summary["started_at"].endswith("Z")
        assert summary["ended_at"].endswith("Z")
        assert summary["ended_at"] >= summary["started_at"]

    def test_end_without_start_has_blank_started_at(self):
        net = NeighborhoodNet()
        net.checkin("u1", "WRAB123", "Sam", "Zeeland")
        summary = net.end()
        assert summary["started_at"] == ""
        assert summary["duration_seconds"] == 0


def test_checkin_radio_creates_a_marked_row_with_a_deterministic_key():
    net = NeighborhoodNet()
    row = net.checkin_radio("wrab123", "Maria", "Maple St")
    assert row["user_id"] == "radio:WRAB123:maria"
    assert row["callsign"] == "WRAB123"
    assert row["name"] == "Maria"
    assert row["location"] == "Maple St"
    assert row["via"] == "radio"
    assert row["status"] == "checked_in"
    assert row["called"] is False


def test_checkin_radio_is_idempotent_per_station():
    net = NeighborhoodNet()
    net.checkin_radio("WRAB123", "Maria", "Maple St")
    net.checkin_radio("wrab123", "  maria ", "Oak St")
    roster = net.roster()
    assert len(roster) == 1
    # Latest check-in wins on the mutable fields, key stays stable.
    assert roster[0]["location"] == "Oak St"


def test_checkin_radio_stores_the_name_the_key_was_built_from():
    # The station key collapses internal whitespace, so the stored name must
    # too. Attendance history keys on (callsign, name.strip().casefold())
    # WITHOUT collapsing internal runs (backend/persistence/net_stats.py), so a
    # stored "Maria  Lopez" would be a different person from last week's
    # "Maria Lopez" — exactly the streak fragmentation Decision 2 exists to
    # prevent.
    net = NeighborhoodNet()
    row = net.checkin_radio("wrab123", "  Maria   Lopez ", "Maple St")
    assert row["name"] == "Maria Lopez"
    assert row["user_id"] == "radio:WRAB123:maria lopez"
    assert net.roster()[0]["name"] == "Maria Lopez"


def test_same_callsign_different_names_are_two_stations():
    # A GMRS family shares one licensed callsign — two people on it are two
    # stations, not one row overwriting the other.
    net = NeighborhoodNet()
    net.checkin_radio("WRAB123", "Maria", "Maple St")
    net.checkin_radio("WRAB123", "Diego", "Maple St")
    assert len(net.roster()) == 2


def test_roster_interleaves_radio_and_account_rows_in_checkin_order():
    net = NeighborhoodNet()
    net.checkin("u1", "WRAA111", "Ann", "1st St")
    net.checkin_radio("WRAB123", "Maria", "Maple St")
    net.checkin("u2", "WRAC333", "Cy", "3rd St")
    assert [r["name"] for r in net.roster()] == ["Ann", "Maria", "Cy"]


def test_re_checkin_does_not_reorder_the_roster():
    net = NeighborhoodNet()
    net.checkin("u1", "WRAA111", "Ann", "1st St")
    net.checkin_radio("WRAB123", "Maria", "Maple St")
    net.checkin("u1", "WRAA111", "Ann", "1st St")
    assert [r["name"] for r in net.roster()] == ["Ann", "Maria"]


def test_call_next_walks_radio_and_account_rows_in_the_same_order():
    net = NeighborhoodNet()
    net.checkin("u1", "WRAA111", "Ann", "1st St")
    net.checkin_radio("WRAB123", "Maria", "Maple St")
    net.start()
    assert net.call_next()["name"] == "Ann"
    second = net.call_next()
    assert second["name"] == "Maria"
    assert net.current_call == "radio:WRAB123:maria"
    assert net.call_next() is None


def test_set_status_reaches_a_radio_row():
    net = NeighborhoodNet()
    key = net.checkin_radio("WRAB123", "Maria", "Maple St")["user_id"]
    net.set_status(key, "checked_out")
    assert net.roster()[0]["status"] == "checked_out"
    # And a checked-out radio row is skipped by the round table.
    net.start()
    assert net.call_next() is None


def test_call_reset_clears_called_on_radio_rows():
    net = NeighborhoodNet()
    net.checkin_radio("WRAB123", "Maria", "Maple St")
    net.start()
    net.call_next()
    net.call_reset()
    assert net.roster()[0]["called"] is False
    assert net.current_call is None


def test_start_resets_called_on_radio_rows():
    net = NeighborhoodNet()
    net.checkin_radio("WRAB123", "Maria", "Maple St")
    net.start()
    net.call_next()
    net.start()
    assert net.roster()[0]["called"] is False


def test_remove_station_removes_only_radio_rows():
    net = NeighborhoodNet()
    net.checkin("u1", "WRAA111", "Ann", "1st St")
    key = net.checkin_radio("WRAB123", "Maria", "Maple St")["user_id"]
    assert net.remove_station("u1") is False
    assert net.remove_station("radio:NOPE:nobody") is False
    assert net.remove_station(key) is True
    assert [r["name"] for r in net.roster()] == ["Ann"]


def test_remove_station_clears_a_current_call_that_pointed_at_it():
    net = NeighborhoodNet()
    key = net.checkin_radio("WRAB123", "Maria", "Maple St")["user_id"]
    net.start()
    net.call_next()
    assert net.current_call == key
    net.remove_station(key)
    assert net.current_call is None


def test_remove_leaves_radio_rows_alone():
    # remove() is the account-deletion path; a radio key is not an account.
    net = NeighborhoodNet()
    key = net.checkin_radio("WRAB123", "Maria", "Maple St")["user_id"]
    assert net.remove(key) is False
    assert len(net.roster()) == 1


def test_end_includes_radio_rows_then_clears_both_stores():
    net = NeighborhoodNet()
    net.checkin("u1", "WRAA111", "Ann", "1st St")
    net.checkin_radio("WRAB123", "Maria", "Maple St")
    net.start()
    summary = net.end()
    assert [r["name"] for r in summary["roster"]] == ["Ann", "Maria"]
    assert net.roster() == []


def test_clear_checkins_clears_both_stores():
    net = NeighborhoodNet()
    net.checkin("u1", "WRAA111", "Ann", "1st St")
    net.checkin_radio("WRAB123", "Maria", "Maple St")
    assert net.clear_checkins() == 2
    assert net.roster() == []


def test_roster_rows_do_not_leak_the_internal_sequence_field():
    net = NeighborhoodNet()
    net.checkin_radio("WRAB123", "Maria", "Maple St")
    assert "seq" not in net.roster()[0]
