"""Final-text resolution for the RX pump — replace vs accumulate semantics."""
from backend.server import _resolve_final_text


class TestResolveFinalText:
    def test_plain_final_prepends_accumulated_partials(self):
        assert _resolve_final_text("hello there", "over", replace=False) == "hello there over"

    def test_plain_final_without_partials_is_chunk_text(self):
        assert _resolve_final_text("", "over", replace=False) == "over"

    def test_replace_final_uses_chunk_text_alone(self):
        # The second-pass model re-transcribed the WHOLE utterance — the
        # accumulated partial text must not be prepended.
        assert _resolve_final_text("hello their", "hello there over", replace=True) == "hello there over"

    def test_replace_with_empty_text_falls_back_to_partials(self):
        # A failed/empty final pass must not erase the partial transcript.
        assert _resolve_final_text("hello there", "", replace=True) == "hello there"

    def test_empty_everything_is_empty(self):
        assert _resolve_final_text("", "", replace=False) == ""

    def test_truncated_replace_falls_back_to_partials(self):
        # The second pass returned only the first bit of a long utterance
        # (a known long-audio failure mode). It must not overwrite the
        # complete first-pass transcript with a fragment.
        prior = "alpha bravo charlie delta echo foxtrot golf hotel"
        assert _resolve_final_text(prior, "alpha", replace=True) == prior

    def test_replace_without_prior_uses_chunk_even_if_short(self):
        # No first-pass text to protect — take whatever the final pass gave.
        assert _resolve_final_text("", "alpha", replace=True) == "alpha"

    def test_slightly_shorter_replace_still_wins(self):
        # The better model is legitimately more concise; only a drastic drop
        # signals truncation. A modest reduction must still replace.
        assert (
            _resolve_final_text("hello there um over", "hello there over", replace=True)
            == "hello there over"
        )
