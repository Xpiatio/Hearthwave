"""Tests for backend.ptt.vox — VoxPTT."""
from backend.ptt.base import PTT
from backend.ptt.manual import ManualPTT
from backend.ptt.vox import VoxPTT


class TestVoxPTTInheritance:
    def test_is_ptt_subclass(self):
        assert issubclass(VoxPTT, PTT)

    def test_is_instantiable(self):
        assert isinstance(VoxPTT(), PTT)

    def test_is_not_manual_ptt(self):
        assert not isinstance(VoxPTT(), ManualPTT)


class TestVoxPTTPadding:
    """VOX relies on trailing silence to keep the radio's VOX circuit engaged
    long enough that the last syllable isn't clipped on dropout.
    Pin the contract so the TX pipeline keeps getting the right value."""

    def test_tail_seconds_is_0_15(self):
        ptt = VoxPTT()
        assert ptt.tail_seconds == 0.15

    def test_lead_in_seconds_is_zero(self):
        """VOX detects audio itself; no software lead-in needed."""
        ptt = VoxPTT()
        assert ptt.lead_in_seconds == 0.0

    def test_tail_seconds_is_class_attribute(self):
        """Attribute must be on the class so subclasses can read it without
        instantiation (factory introspection pattern)."""
        assert VoxPTT.tail_seconds == 0.15

    def test_lead_in_is_class_attribute(self):
        assert VoxPTT.lead_in_seconds == 0.0


class TestVoxPTTOperations:
    """key/unkey/close are no-ops under VOX — the radio handles keying."""

    def test_key_does_not_raise(self):
        VoxPTT().key()

    def test_unkey_does_not_raise(self):
        VoxPTT().unkey()

    def test_key_then_unkey_does_not_raise(self):
        ptt = VoxPTT()
        ptt.key()
        ptt.unkey()

    def test_multiple_key_calls_do_not_raise(self):
        ptt = VoxPTT()
        ptt.key()
        ptt.key()

    def test_multiple_unkey_calls_do_not_raise(self):
        ptt = VoxPTT()
        ptt.unkey()
        ptt.unkey()

    def test_close_does_not_raise(self):
        VoxPTT().close()

    def test_key_returns_none(self):
        assert VoxPTT().key() is None

    def test_unkey_returns_none(self):
        assert VoxPTT().unkey() is None

    def test_close_returns_none(self):
        assert VoxPTT().close() is None


class TestVoxVsManualPadding:
    """Explicitly contrast VoxPTT vs ManualPTT so any accidental merging is caught."""

    def test_vox_tail_differs_from_manual(self):
        assert VoxPTT().tail_seconds != ManualPTT().tail_seconds

    def test_both_lead_in_are_zero(self):
        assert VoxPTT().lead_in_seconds == ManualPTT().lead_in_seconds == 0.0


class TestVoxPTTIndependentInstances:
    def test_two_instances_are_independent(self):
        a = VoxPTT()
        b = VoxPTT()
        a.key()
        b.unkey()
        assert a is not b
