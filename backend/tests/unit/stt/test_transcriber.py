"""Unit tests for WhisperTranscriber prompt building and update logic."""
from unittest.mock import MagicMock

from backend.stt.transcriber import WhisperTranscriber


def _make(phrases=()):
    return WhisperTranscriber(model=MagicMock(), saved_phrases=phrases)


# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    def test_empty_list_returns_base(self):
        assert WhisperTranscriber._build_prompt([]) == "GMRS radio."

    def test_empty_tuple_returns_base(self):
        assert WhisperTranscriber._build_prompt(()) == "GMRS radio."

    def test_single_phrase(self):
        assert WhisperTranscriber._build_prompt(["break break"]) == (
            "GMRS radio. Phrases: break break."
        )

    def test_multiple_phrases_joined(self):
        assert WhisperTranscriber._build_prompt(["over", "10-4", "QSL"]) == (
            "GMRS radio. Phrases: over, 10-4, QSL."
        )

    def test_phrases_containing_commas_pass_through(self):
        result = WhisperTranscriber._build_prompt(["break, break"])
        assert result == "GMRS radio. Phrases: break, break."


# ---------------------------------------------------------------------------
# __init__ sets initial_prompt
# ---------------------------------------------------------------------------

class TestInit:
    def test_no_phrases_gives_base_prompt(self):
        assert _make().initial_prompt == "GMRS radio."

    def test_phrases_included_in_prompt(self):
        assert _make(["roger that"]).initial_prompt == "GMRS radio. Phrases: roger that."

    def test_multiple_phrases_at_init(self):
        t = _make(["over", "QSL"])
        assert t.initial_prompt == "GMRS radio. Phrases: over, QSL."


# ---------------------------------------------------------------------------
# update_prompt
# ---------------------------------------------------------------------------

class TestUpdatePrompt:
    def test_replaces_existing_phrases(self):
        t = _make(["old"])
        t.update_prompt(["new"])
        assert t.initial_prompt == "GMRS radio. Phrases: new."

    def test_empty_list_resets_to_base(self):
        t = _make(["break break"])
        t.update_prompt([])
        assert t.initial_prompt == "GMRS radio."

    def test_default_arg_resets_to_base(self):
        t = _make(["break break"])
        t.update_prompt()
        assert t.initial_prompt == "GMRS radio."

    def test_multiple_updates_are_independent(self):
        t = _make()
        t.update_prompt(["first"])
        t.update_prompt(["second"])
        assert t.initial_prompt == "GMRS radio. Phrases: second."
