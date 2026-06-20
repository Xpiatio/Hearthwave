"""Monitoring beacon — periodic presence announcement.

Pure helpers only (no I/O). The async pump that drives these lives in
server.py as _monitoring_beacon_pump.
"""
from __future__ import annotations

from backend.text.callsigns import spell_digits_in_callsigns


def format_monitoring_call(template: str, callsign: str) -> str:
    """Build the spoken monitoring-beacon phrase.

    Substitutes {callsign} into *template*, then spells out digits in the
    callsign for radio intelligibility (the same treatment the FCC ID pump
    applies). Uses str.replace, not str.format, so stray braces in a custom
    template do not raise.
    """
    phrase = template.replace("{callsign}", callsign)
    return spell_digits_in_callsigns(phrase)


def should_emit_beacon(
    *,
    enabled: bool,
    ncs_active: bool,
    channel_clear: bool,
    elapsed: float,
    interval: float,
) -> bool:
    """Pure gating decision: True only when the beacon should transmit now.

    Order matters for clarity, not correctness: disabled and NCS-active are
    hard stops; a busy channel defers; otherwise fire once the interval has
    elapsed.
    """
    if not enabled:
        return False
    if ncs_active:
        return False
    if not channel_clear:
        return False
    return elapsed >= interval
