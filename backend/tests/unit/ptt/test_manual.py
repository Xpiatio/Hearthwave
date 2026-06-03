"""Tests for backend.ptt.manual — ManualPTT."""
from backend.ptt.base import PTT
from backend.ptt.manual import ManualPTT


class TestManualPTTInheritance:
    def test_is_ptt_subclass(self):
        assert issubclass(ManualPTT, PTT)

    def test_is_instantiable(self):
        assert isinstance(ManualPTT(), PTT)


class TestManualPTTPadding:
    """ManualPTT must not add any lead-in or tail silence."""

    def test_lead_in_seconds_is_zero(self):
        ptt = ManualPTT()
        assert ptt.lead_in_seconds == 0.0

    def test_tail_seconds_is_zero(self):
        ptt = ManualPTT()
        assert ptt.tail_seconds == 0.0


class TestManualPTTOperations:
    """key/unkey/close are intentional no-ops — they must not raise."""

    def test_key_does_not_raise(self):
        ManualPTT().key()

    def test_unkey_does_not_raise(self):
        ManualPTT().unkey()

    def test_key_then_unkey_does_not_raise(self):
        ptt = ManualPTT()
        ptt.key()
        ptt.unkey()

    def test_multiple_key_calls_do_not_raise(self):
        ptt = ManualPTT()
        ptt.key()
        ptt.key()

    def test_multiple_unkey_calls_do_not_raise(self):
        ptt = ManualPTT()
        ptt.unkey()
        ptt.unkey()

    def test_close_does_not_raise(self):
        ManualPTT().close()

    def test_key_returns_none(self):
        assert ManualPTT().key() is None

    def test_unkey_returns_none(self):
        assert ManualPTT().unkey() is None

    def test_close_returns_none(self):
        assert ManualPTT().close() is None


class TestManualPTTIndependentInstances:
    """Instances must be independent — no class-level mutable state."""

    def test_two_instances_are_independent(self):
        a = ManualPTT()
        b = ManualPTT()
        a.key()
        b.unkey()
        # Still no side-effects on each other; main assertion is no exception.
        assert a is not b
