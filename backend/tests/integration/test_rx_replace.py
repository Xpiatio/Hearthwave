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
