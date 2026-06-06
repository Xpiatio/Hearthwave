import datetime

import pytest

from backend.constants import SERVICE_FRS
from backend.fcc.id_rule import (
    format_outgoing_message,
    format_standalone_id,
    format_tail_id,
)


@pytest.fixture
def now():
    return datetime.datetime(2026, 5, 15, 12, 0, 0)


@pytest.fixture
def me():
    return {"call": "WSLZ233", "name": "Bob"}


class TestFormatTailId:
    def test_returns_call_with_period(self):
        assert format_tail_id("WQXX123") == "WQXX123."

    def test_blank_call_returns_period_only(self):
        assert format_tail_id("") == "."


class TestUntargetedAlwaysAppendsTail:
    def test_appends_tail_to_non_empty_text(self, now, me):
        text, new_last = format_outgoing_message(
            "Hello channel",
            target_call="ALL",
            target_name="Everyone",
            my_call=me["call"],
            my_name=me["name"],
            now=now,
        )
        assert text == "Hello channel. WSLZ233."
        assert new_last == now

    def test_target_empty_string_treated_as_untargeted(self, now, me):
        text, new_last = format_outgoing_message(
            "Open call",
            target_call="",
            target_name="",
            my_call=me["call"],
            my_name=me["name"],
            now=now,
        )
        assert text == "Open call. WSLZ233."
        assert new_last == now

    def test_all_lowercase_still_treated_as_untargeted(self, now, me):
        text, new_last = format_outgoing_message(
            "msg",
            target_call="all",
            target_name="Everyone",
            my_call=me["call"],
            my_name=me["name"],
            now=now,
        )
        assert text == "msg. WSLZ233."
        assert new_last == now

    def test_empty_body_returns_tail_only(self, now, me):
        text, new_last = format_outgoing_message(
            "",
            target_call="ALL",
            target_name="",
            my_call=me["call"],
            my_name=me["name"],
            now=now,
        )
        assert text == "WSLZ233."
        assert new_last == now

    def test_always_resets_timer(self, now, me):
        # No timer gate — every untargeted TX resets the ID clock.
        _, new_last = format_outgoing_message(
            "checking in",
            target_call="ALL",
            target_name="",
            my_call=me["call"],
            my_name=me["name"],
            now=now,
        )
        assert new_last == now


class TestTargetedPreface:
    def test_with_target_name(self, now, me):
        text, new_last = format_outgoing_message(
            "you copy?",
            target_call="KAE1234",
            target_name="Alice",
            my_call=me["call"],
            my_name=me["name"],
            now=now,
        )
        assert text == "WSLZ233 Bob calling KAE1234 Alice. you copy?"
        assert new_last == now

    def test_without_target_name(self, now, me):
        text, new_last = format_outgoing_message(
            "you copy?",
            target_call="KAE1234",
            target_name="",
            my_call=me["call"],
            my_name=me["name"],
            now=now,
        )
        assert text == "WSLZ233 Bob calling KAE1234. you copy?"
        assert new_last == now

    def test_empty_body_text_yields_preface_only(self, now, me):
        text, _ = format_outgoing_message(
            "",
            target_call="KAE1234",
            target_name="Alice",
            my_call=me["call"],
            my_name=me["name"],
            now=now,
        )
        assert text == "WSLZ233 Bob calling KAE1234 Alice."

    def test_targeted_resets_timer(self, now, me):
        _, new_last = format_outgoing_message(
            "ping",
            target_call="KAE1234",
            target_name="Alice",
            my_call=me["call"],
            my_name=me["name"],
            now=now,
        )
        assert new_last == now

    def test_target_call_lowercase_still_treated_as_targeted(self, now, me):
        text, _ = format_outgoing_message(
            "msg",
            target_call="kae1234",
            target_name="alice",
            my_call=me["call"],
            my_name=me["name"],
            now=now,
        )
        assert text == "WSLZ233 Bob calling kae1234 alice. msg"

    def test_no_tail_appended_to_targeted_tx(self, now, me):
        # Preface already IDs the station — no tail should be added.
        text, _ = format_outgoing_message(
            "hello",
            target_call="KAE1234",
            target_name="Alice",
            my_call=me["call"],
            my_name=me["name"],
            now=now,
        )
        assert text == "WSLZ233 Bob calling KAE1234 Alice. hello"


class TestFrsModeSkipsCallsignFraming:
    """FRS doesn't require station ID. Text passes through unchanged and
    format_outgoing_message returns None for new_last_id_time so server.py
    can preserve the existing GMRS timer (FRS mode must not reset it)."""

    def test_untargeted_text_passes_through_unchanged(self, now, me):
        text, new_last = format_outgoing_message(
            "Just a quick check-in",
            target_call="ALL",
            target_name="Everyone",
            my_call=me["call"],
            my_name=me["name"],
            now=now,
            service=SERVICE_FRS,
        )
        assert text == "Just a quick check-in"
        assert new_last is None

    def test_targeted_send_does_not_inject_preface(self, now, me):
        text, new_last = format_outgoing_message(
            "you copy?",
            target_call="WSAC909",
            target_name="Tim",
            my_call=me["call"],
            my_name=me["name"],
            now=now,
            service=SERVICE_FRS,
        )
        assert text == "you copy?"
        assert new_last is None

    def test_default_service_is_gmrs(self, now, me):
        text, _ = format_outgoing_message(
            "Hello channel",
            target_call="ALL",
            target_name="Everyone",
            my_call=me["call"],
            my_name=me["name"],
            now=now,
        )
        assert text == "Hello channel. WSLZ233."


class TestStandaloneId:
    def test_with_location(self, now, me):
        text, new_last = format_standalone_id(
            my_call=me["call"],
            my_name=me["name"],
            my_location="Boston",
            now=now,
        )
        assert text == "This is WSLZ233, Whiskey Sierra Lima Zulu 2 3 3. Bob from Boston."
        assert new_last == now

    def test_without_location(self, now, me):
        text, new_last = format_standalone_id(
            my_call=me["call"],
            my_name=me["name"],
            my_location="",
            now=now,
        )
        assert text == "This is WSLZ233, Whiskey Sierra Lima Zulu 2 3 3. Bob."
        assert new_last == now

    def test_whitespace_only_location_treated_as_empty(self, now, me):
        text, _ = format_standalone_id(
            my_call=me["call"],
            my_name=me["name"],
            my_location="   ",
            now=now,
        )
        assert text == "This is WSLZ233, Whiskey Sierra Lima Zulu 2 3 3. Bob."

    def test_amateur_callsign_uses_correct_nato_form(self, now):
        text, _ = format_standalone_id(
            my_call="K1ABC",
            my_name="Carol",
            my_location="Denver",
            now=now,
        )
        assert text == "This is K1ABC, Kilo 1 Alpha Bravo Charlie. Carol from Denver."
