import pytest
import backend.ptt.factory as ptt_factory
from backend.ptt import ManualPTT, VoxPTT, make_ptt


class TestMakePttModeSelection:
    def test_default_mode_is_manual(self):
        assert isinstance(make_ptt({}), ManualPTT)

    def test_explicit_manual(self):
        assert isinstance(make_ptt({"ptt_mode": "manual"}), ManualPTT)

    def test_vox_mode(self):
        assert isinstance(make_ptt({"ptt_mode": "vox"}), VoxPTT)

    def test_unknown_mode_falls_through_to_manual(self):
        # Defensive: an unknown / future mode value shouldn't crash; it falls back.
        assert isinstance(make_ptt({"ptt_mode": "morse-code-bluetooth-magic"}), ManualPTT)


class TestUsbFtdiFallback:
    def test_missing_port_falls_back_to_manual(self, caplog):
        result = make_ptt({"ptt_mode": "usb_ftdi", "ptt_serial_port": ""})
        assert isinstance(result, ManualPTT)
        # Operators need to see *why* their configured PTT mode didn't engage.
        assert "no serial port configured" in caplog.text

    def test_whitespace_only_port_falls_back_to_manual(self, caplog):
        result = make_ptt({"ptt_mode": "usb_ftdi", "ptt_serial_port": "   "})
        assert isinstance(result, ManualPTT)
        assert "no serial port configured" in caplog.text

    def test_unopenable_port_falls_back_to_manual(self, caplog):
        # A path that definitely won't exist as a serial device. The Serial
        # constructor will raise; make_ptt catches and degrades to Manual.
        result = make_ptt(
            {"ptt_mode": "usb_ftdi", "ptt_serial_port": "/dev/this_serial_port_does_not_exist_12345"}
        )
        assert isinstance(result, ManualPTT)
        assert "failed to open serial port" in caplog.text


class TestFactoryRegistration:
    def test_new_mode_registered_without_modifying_make_ptt(self):
        """Registering a new factory in _FACTORIES is all that's needed."""
        sentinel = object()

        original = ptt_factory._FACTORIES.copy()
        try:
            ptt_factory._FACTORIES["test_mode"] = lambda _: sentinel
            assert make_ptt({"ptt_mode": "test_mode"}) is sentinel
        finally:
            ptt_factory._FACTORIES.clear()
            ptt_factory._FACTORIES.update(original)


class TestVoxTailSilence:
    # Pin the per-mode padding contract so callers (TX pipeline) keep getting
    # the right amount of silence. VOX needs trailing silence; serial needs both.
    def test_manual_has_no_padding(self):
        ptt = ManualPTT()
        assert ptt.lead_in_seconds == 0.0
        assert ptt.tail_seconds == 0.0

    def test_vox_has_tail_silence(self):
        ptt = VoxPTT()
        assert ptt.lead_in_seconds == pytest.approx(0.35)
        assert ptt.tail_seconds == 0.15
