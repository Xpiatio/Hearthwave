from backend.text.locations import expand_trailing_state


class TestExpandTrailingStateKnownAbbreviations:
    def test_city_comma_two_letter_state(self):
        assert expand_trailing_state("Jenison, MI") == "Jenison, Michigan"

    def test_city_space_two_letter_state(self):
        assert expand_trailing_state("Home Base TX") == "Home Base Texas"

    def test_three_word_city_with_state(self):
        assert expand_trailing_state("Grand Rapids, MI") == "Grand Rapids, Michigan"

    def test_state_only(self):
        assert expand_trailing_state("MI") == "Michigan"

    def test_all_50_states_spot_check(self):
        cases = {
            "AK": "Alaska",
            "CA": "California",
            "FL": "Florida",
            "NY": "New York",
            "WA": "Washington",
            "WV": "West Virginia",
        }
        for abbr, full in cases.items():
            assert expand_trailing_state(abbr) == full, f"Failed for {abbr}"

    def test_dc(self):
        assert expand_trailing_state("Washington, DC") == "Washington, Washington D.C."

    def test_territory_pr(self):
        assert expand_trailing_state("San Juan, PR") == "San Juan, Puerto Rico"

    def test_territory_gu(self):
        assert expand_trailing_state("Hagatna, GU") == "Hagatna, Guam"

    def test_territory_vi(self):
        assert expand_trailing_state("Charlotte Amalie, VI") == "Charlotte Amalie, U.S. Virgin Islands"

    def test_territory_as(self):
        assert expand_trailing_state("Pago Pago, AS") == "Pago Pago, American Samoa"

    def test_territory_mp(self):
        assert expand_trailing_state("Saipan, MP") == "Saipan, Northern Mariana Islands"


class TestExpandTrailingStateNoChange:
    def test_no_trailing_abbreviation_unchanged(self):
        assert expand_trailing_state("Jenison, Michigan") == "Jenison, Michigan"

    def test_plain_text_unchanged(self):
        assert expand_trailing_state("Home Base") == "Home Base"

    def test_empty_string_unchanged(self):
        assert expand_trailing_state("") == ""

    def test_unknown_two_letter_code_unchanged(self):
        # 'ZZ' is not a valid US state/territory
        assert expand_trailing_state("Somewhere, ZZ") == "Somewhere, ZZ"

    def test_lowercase_abbreviation_not_matched(self):
        # The regex requires uppercase; lowercase 'mi' should not be expanded
        assert expand_trailing_state("Jenison, mi") == "Jenison, mi"

    def test_abbreviation_not_at_end_unchanged(self):
        # 'MI' in the middle is not trailing
        assert expand_trailing_state("MI city here") == "MI city here"

    def test_trailing_three_letter_code_unchanged(self):
        # Three-letter suffix should not trigger the two-letter pattern
        assert expand_trailing_state("Somewhere, USA") == "Somewhere, USA"

    def test_single_lowercase_word_unchanged(self):
        assert expand_trailing_state("michigan") == "michigan"
