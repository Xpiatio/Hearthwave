"""Callsign recovery across the two STT passes.

A replacing second pass can drop or truncate a callsign the first pass
caught. _detected_callsigns unions the final-text spans with callsigns found
in the first-pass (prior) text so attendance/pending survive either pass.
"""
from backend.server import _detected_callsigns


class TestDetectedCallsigns:
    def test_spans_only(self):
        spans = [[0, 7, "WSLZ233"]]
        assert _detected_callsigns(spans, "", set(), fuzzy=False) == {"WSLZ233"}

    def test_recovers_callsign_dropped_by_second_pass(self):
        # The replacing final lost the callsign; the first-pass text kept it.
        prior = "whiskey sierra lima zulu two three three checking in"
        assert _detected_callsigns([], prior, set(), fuzzy=False) == {"WSLZ233"}

    def test_unions_both_sources(self):
        spans = [[0, 7, "KD9XYZ"]]
        prior = "whiskey sierra lima zulu two three three"
        assert _detected_callsigns(spans, prior, set(), fuzzy=False) == {"KD9XYZ", "WSLZ233"}

    def test_no_callsigns_anywhere(self):
        assert _detected_callsigns([], "just chatting over", set(), fuzzy=False) == set()

    def test_fuzzy_maps_prior_callsign_to_known(self):
        # First-pass misheard one digit; fuzzy correction lands it on the
        # known contact rather than registering a stray near-miss.
        prior = "WSLZ235 here"
        assert _detected_callsigns([], prior, {"WSLZ233"}, fuzzy=True) == {"WSLZ233"}
