import logging

from backend.ptt.manual import ManualPTT
from backend.ptt.serial_ptt import SerialPTT
from backend.ptt.vox import VoxPTT

_log = logging.getLogger(__name__)


def _lead_in_ms(config) -> int:
    raw = int(config.get("ptt_lead_in_ms", 350))
    if raw > 1000:
        _log.warning("ptt_lead_in_ms=%d exceeds 1000 ms; clamping to 1000.", raw)
        return 1000
    return raw


def _make_manual(config) -> ManualPTT:
    return ManualPTT()


def _make_vox(config) -> VoxPTT:
    return VoxPTT(lead_in_ms=_lead_in_ms(config))


def _make_serial(config) -> ManualPTT | SerialPTT:
    port = (config.get("ptt_serial_port") or "").strip()
    line = config.get("ptt_serial_line", "RTS")
    lead_in_ms = _lead_in_ms(config)
    if not port:
        _log.warning("PTT: USB FTDI selected but no serial port configured; falling back to manual.")
        return ManualPTT()
    try:
        return SerialPTT(port, line, lead_in_ms=lead_in_ms)
    except Exception as e:
        _log.error("PTT: failed to open serial port %s: %s; falling back to manual.", port, e)
        return ManualPTT()


# Maps mode strings to factory callables that accept the config dict.
# Register new PTT types here — make_ptt never needs to change.
_FACTORIES = {
    "manual": _make_manual,
    "vox": _make_vox,
    "usb_ftdi": _make_serial,
}


def make_ptt(config):
    mode = config.get("ptt_mode", "manual")
    factory = _FACTORIES.get(mode, _make_manual)
    return factory(config)
