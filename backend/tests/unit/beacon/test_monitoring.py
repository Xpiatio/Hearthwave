from backend.beacon.monitoring import format_monitoring_call, should_emit_beacon


# ---------------------------------------------------------------------------
# format_monitoring_call
# ---------------------------------------------------------------------------

class TestFormatMonitoringCall:
    def test_substitutes_callsign(self):
        result = format_monitoring_call(
            "{callsign} Hearthwave base, monitoring.", "WSLZ233"
        )
        assert result.startswith("WSLZ")
        assert "Hearthwave base, monitoring." in result

    def test_digits_in_callsign_are_spelled(self):
        result = format_monitoring_call(
            "{callsign} Hearthwave base, monitoring.", "WSLZ233"
        )
        assert "WSLZ 2 3 3" in result

    def test_custom_template(self):
        result = format_monitoring_call("CQ from {callsign}.", "WSLZ233")
        assert "CQ from WSLZ 2 3 3." == result

    def test_stray_brace_is_not_an_error(self):
        # {weird} is not {callsign}; it must be left untouched, no exception.
        result = format_monitoring_call("{callsign} {weird}.", "WSLZ233")
        assert "{weird}." in result


# ---------------------------------------------------------------------------
# should_emit_beacon
# ---------------------------------------------------------------------------

class TestShouldEmitBeacon:
    def _kwargs(self, **over):
        base = dict(
            enabled=True, ncs_active=False, channel_clear=True,
            elapsed=1000.0, interval=900.0,
        )
        base.update(over)
        return base

    def test_fires_when_all_conditions_met(self):
        assert should_emit_beacon(**self._kwargs()) is True

    def test_skips_when_disabled(self):
        assert should_emit_beacon(**self._kwargs(enabled=False)) is False

    def test_skips_when_ncs_active(self):
        assert should_emit_beacon(**self._kwargs(ncs_active=True)) is False

    def test_skips_when_channel_busy(self):
        assert should_emit_beacon(**self._kwargs(channel_clear=False)) is False

    def test_skips_when_interval_not_elapsed(self):
        assert should_emit_beacon(**self._kwargs(elapsed=10.0, interval=900.0)) is False

    def test_fires_exactly_at_interval(self):
        assert should_emit_beacon(**self._kwargs(elapsed=900.0, interval=900.0)) is True
