"""Tests for backend.ptt.base — PTT abstract base class."""
import pytest

from backend.ptt.base import PTT


# ---------------------------------------------------------------------------
# Concretely implement PTT so we can exercise the non-abstract surface.
# ---------------------------------------------------------------------------

class ConcretePTT(PTT):
    """Minimal concrete implementation; tracks key/unkey calls."""

    def __init__(self):
        self.keyed = False
        self.key_calls = 0
        self.unkey_calls = 0

    def key(self) -> None:
        self.keyed = True
        self.key_calls += 1

    def unkey(self) -> None:
        self.keyed = False
        self.unkey_calls += 1


class TestPTTAbstract:
    def test_cannot_instantiate_directly(self):
        """PTT is ABC — direct instantiation must raise TypeError."""
        with pytest.raises(TypeError):
            PTT()  # type: ignore[abstract]

    def test_subclass_without_key_cannot_be_instantiated(self):
        class NoKey(PTT):
            def unkey(self): pass

        with pytest.raises(TypeError):
            NoKey()

    def test_subclass_without_unkey_cannot_be_instantiated(self):
        class NoUnkey(PTT):
            def key(self): pass

        with pytest.raises(TypeError):
            NoUnkey()

    def test_concrete_subclass_is_instantiable(self):
        ptt = ConcretePTT()
        assert isinstance(ptt, PTT)


class TestPTTDefaultPadding:
    """Pin the class-level defaults so subclasses don't silently drift."""

    def test_default_lead_in_is_zero(self):
        ptt = ConcretePTT()
        assert ptt.lead_in_seconds == 0.0

    def test_default_tail_is_zero(self):
        ptt = ConcretePTT()
        assert ptt.tail_seconds == 0.0


class TestPTTClose:
    def test_close_is_no_op_by_default(self):
        """close() must not raise on a subclass that doesn't override it."""
        ptt = ConcretePTT()
        ptt.close()  # should not raise

    def test_close_can_be_called_multiple_times(self):
        ptt = ConcretePTT()
        ptt.close()
        ptt.close()


class TestPTTKeyUnkey:
    def test_key_is_called(self):
        ptt = ConcretePTT()
        ptt.key()
        assert ptt.key_calls == 1

    def test_unkey_is_called(self):
        ptt = ConcretePTT()
        ptt.key()
        ptt.unkey()
        assert ptt.unkey_calls == 1

    def test_key_unkey_sequence(self):
        ptt = ConcretePTT()
        ptt.key()
        assert ptt.keyed is True
        ptt.unkey()
        assert ptt.keyed is False

    def test_padding_class_attrs_are_overridable(self):
        class PaddedPTT(PTT):
            lead_in_seconds = 0.5
            tail_seconds = 0.3

            def key(self): pass
            def unkey(self): pass

        ptt = PaddedPTT()
        assert ptt.lead_in_seconds == 0.5
        assert ptt.tail_seconds == 0.3
