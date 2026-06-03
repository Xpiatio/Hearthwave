import pytest
from backend.text.metadata import extract_name_location


class TestExtractNameBasic:
    def test_name_after_callsign(self):
        name, _ = extract_name_location("WSLZ233 Bob from Jenison", "WSLZ233")
        assert name == "Bob"

    def test_name_case_sensitive_start(self):
        # Name regex matches capitalized word after callsign
        name, _ = extract_name_location("KD9XYZ Alice here", "KD9XYZ")
        assert name == "Alice"

    def test_no_name_after_callsign_returns_empty(self):
        # Callsign at end of string
        name, _ = extract_name_location("from KD9XYZ", "KD9XYZ")
        assert name == ""

    def test_callsign_not_found_returns_empty_name(self):
        name, _ = extract_name_location("just some text", "WSLZ233")
        assert name == ""

    def test_name_with_punctuation_stripped(self):
        # After callsign: ", Bob" — the lstrip handles leading punct
        name, _ = extract_name_location("WSLZ233, Bob from here", "WSLZ233")
        assert name == "Bob"

    def test_lowercase_word_after_callsign_not_captured(self):
        # "from" is lowercase; name regex requires leading capital
        name, _ = extract_name_location("WSLZ233 from Grand Rapids", "WSLZ233")
        assert name == ""

    def test_callsign_case_insensitive_search(self):
        # Callsign lookup uses .upper() on text so lowercase text still matches
        name, _ = extract_name_location("wslz233 Carol from here", "WSLZ233")
        assert name == "Carol"


class TestExtractLocationBasic:
    def test_in_keyword(self):
        _, location = extract_name_location("I am in Grand Rapids", "WSLZ233")
        assert location == "Grand Rapids"

    def test_from_keyword(self):
        _, location = extract_name_location("calling from Jenison", "WSLZ233")
        assert location == "Jenison"

    def test_near_keyword(self):
        _, location = extract_name_location("located near Holland", "WSLZ233")
        assert location == "Holland"

    def test_at_keyword(self):
        _, location = extract_name_location("stationed at Kalamazoo", "WSLZ233")
        assert location == "Kalamazoo"

    def test_multi_word_location(self):
        _, location = extract_name_location("WSLZ233 from Grand Rapids Michigan", "WSLZ233")
        # Up to 3 additional capitalised words are captured
        assert "Grand Rapids" in location

    def test_no_location_keyword_returns_empty(self):
        _, location = extract_name_location("WSLZ233 Bob", "WSLZ233")
        assert location == ""

    def test_lowercase_location_not_captured(self):
        # LOCATION_RE requires capitalised first letter after keyword
        _, location = extract_name_location("from some place", "WSLZ233")
        assert location == ""


class TestExtractNameAndLocationTogether:
    def test_both_present(self):
        name, location = extract_name_location(
            "WSLZ233 Carol from Grand Rapids", "WSLZ233"
        )
        assert name == "Carol"
        assert "Grand" in location

    def test_neither_present(self):
        name, location = extract_name_location("just noise", "WSLZ233")
        assert name == ""
        assert location == ""

    def test_location_with_comma_stripped(self):
        # strip(" ,") on the match group removes trailing comma/space
        _, location = extract_name_location("in Jenison, over", "WSLZ233")
        # Should not end with comma
        assert not location.endswith(",")
