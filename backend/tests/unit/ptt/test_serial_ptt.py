"""Tests for backend.ptt.serial_ptt — SerialPTT PTT implementation."""
import sys
import pytest
from unittest.mock import MagicMock, patch

from backend.ptt.serial_ptt import SerialPTT


@pytest.fixture
def mock_serial():
    """Mock serial.Serial via sys.modules so pyserial need not be installed."""
    mock_port = MagicMock()
    mock_port.rts = False
    mock_port.dtr = False
    mock_module = MagicMock()
    mock_module.Serial.return_value = mock_port
    with patch.dict(sys.modules, {"serial": mock_module}):
        yield mock_port


class TestSerialPTTLeadIn:
    def test_default_lead_in_is_350ms(self, mock_serial):
        """Default lead-in must be 350 ms to protect slow radio TX chains."""
        ptt = SerialPTT("/dev/ttyUSB0")
        assert ptt.lead_in_seconds == pytest.approx(0.35)

    def test_custom_lead_in_ms(self, mock_serial):
        ptt = SerialPTT("/dev/ttyUSB0", lead_in_ms=500)
        assert ptt.lead_in_seconds == pytest.approx(0.5)

    def test_lead_in_zero_is_valid(self, mock_serial):
        ptt = SerialPTT("/dev/ttyUSB0", lead_in_ms=0)
        assert ptt.lead_in_seconds == pytest.approx(0.0)


class TestSerialPTTBasics:
    def test_line_defaults_to_rts(self, mock_serial):
        """Line should default to RTS."""
        ptt = SerialPTT("/dev/ttyUSB0")
        assert ptt.line == "RTS"

    def test_line_can_be_dtr(self, mock_serial):
        """Line can be set to DTR."""
        ptt = SerialPTT("/dev/ttyUSB0", line="DTR")
        assert ptt.line == "DTR"

    def test_line_is_uppercased(self, mock_serial):
        """Line should be uppercased."""
        ptt = SerialPTT("/dev/ttyUSB0", line="dtr")
        assert ptt.line == "DTR"

    def test_tail_is_50ms(self, mock_serial):
        """Tail should be 50 ms."""
        ptt = SerialPTT("/dev/ttyUSB0")
        assert ptt.tail_seconds == pytest.approx(0.05)


class TestSerialPTTKey:
    def test_key_sets_rts_true(self, mock_serial):
        """key() should set RTS high."""
        ptt = SerialPTT("/dev/ttyUSB0", line="RTS")
        ptt.key()
        assert mock_serial.rts is True

    def test_unkey_sets_rts_false(self, mock_serial):
        """unkey() should set RTS low."""
        ptt = SerialPTT("/dev/ttyUSB0", line="RTS")
        ptt.key()
        ptt.unkey()
        assert mock_serial.rts is False

    def test_key_sets_dtr_true_when_line_is_dtr(self, mock_serial):
        """key() should set DTR high when line is DTR."""
        ptt = SerialPTT("/dev/ttyUSB0", line="DTR")
        ptt.key()
        assert mock_serial.dtr is True

    def test_unkey_sets_dtr_false_when_line_is_dtr(self, mock_serial):
        """unkey() should set DTR low when line is DTR."""
        ptt = SerialPTT("/dev/ttyUSB0", line="DTR")
        ptt.key()
        ptt.unkey()
        assert mock_serial.dtr is False
