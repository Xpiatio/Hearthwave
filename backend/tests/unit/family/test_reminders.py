"""Unit tests for backend.family.reminders.is_checkin_missed (pure logic)."""
from __future__ import annotations

from datetime import datetime

from backend.family.reminders import is_checkin_missed

R = {"time": "09:00", "enabled": True}


def dt(h, m=0):
    return datetime(2026, 7, 17, h, m)


def test_not_missed_before_deadline():
    assert is_checkin_missed(R, None, dt(8, 59)) is False


def test_missed_after_deadline_no_ok():
    assert is_checkin_missed(R, None, dt(9, 1)) is True


def test_ok_today_before_deadline_counts():
    assert is_checkin_missed(R, "2026-07-17T07:30:00", dt(10)) is False


def test_ok_yesterday_does_not_count():
    assert is_checkin_missed(R, "2026-07-16T09:30:00", dt(10)) is True


def test_ok_today_after_deadline_clears():
    assert is_checkin_missed(R, "2026-07-17T09:30:00", dt(10)) is False


def test_disabled_never_missed():
    assert is_checkin_missed({"time": "09:00", "enabled": False}, None, dt(12)) is False


def test_bad_time_never_missed():
    assert is_checkin_missed({"time": "9am", "enabled": True}, None, dt(12)) is False


def test_missed_exactly_at_deadline():
    assert is_checkin_missed(R, None, dt(9, 0)) is True


def test_missing_time_key_never_missed():
    assert is_checkin_missed({"enabled": True}, None, dt(12)) is False


def test_missing_enabled_key_never_missed():
    assert is_checkin_missed({"time": "09:00"}, None, dt(12)) is False


def test_aware_now_converts_naive_last_ok_via_utc_assumption():
    """last_ok stored as UTC ISO (Z-suffixed); aware now_local in a different
    zone must convert last_ok before the date comparison — a check-in that
    was today in UTC but yesterday locally (or vice versa) is handled by the
    astimezone conversion, not a naive date() compare."""
    from datetime import timedelta, timezone

    tz = timezone(timedelta(hours=-5))
    now_local = datetime(2026, 7, 17, 10, 0, tzinfo=tz)  # 15:00 UTC
    last_ok_iso = "2026-07-17T23:30:00Z"  # 18:30 local same day -> still today
    assert is_checkin_missed(R, last_ok_iso, now_local) is False


def test_bad_last_ok_iso_counts_as_missed():
    assert is_checkin_missed(R, "not-a-timestamp", dt(10)) is True
