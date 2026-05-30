from backend.text.placeholders import find_placeholders, substitute_placeholders


class TestFindPlaceholders:
    def test_no_placeholders(self):
        assert find_placeholders("Radio check") == []

    def test_single_placeholder(self):
        assert find_placeholders("QSY to channel {N}") == ["N"]

    def test_multi_word_name(self):
        assert find_placeholders("QSY to channel {Channel Number}") == ["Channel Number"]

    def test_multiple_placeholders_preserve_order(self):
        assert find_placeholders("Meet at {Time} on {Channel}") == ["Time", "Channel"]

    def test_duplicate_placeholder_deduplicated(self):
        # A preset that mentions {N} twice should only prompt the operator once.
        assert find_placeholders("Channel {N}, repeating, channel {N}") == ["N"]

    def test_underscore_and_digit_names(self):
        assert find_placeholders("call_{Call_Sign_1}") == ["Call_Sign_1"]

    def test_empty_braces_ignored(self):
        # Bare `{}` is not a valid placeholder name.
        assert find_placeholders("nothing here {}") == []

    def test_leading_digit_or_space_skipped(self):
        # The token must start with a letter, digit, or underscore — leading
        # whitespace is treated as a literal brace pair, not a placeholder.
        assert find_placeholders("oops { Name}") == []

    def test_empty_input(self):
        assert find_placeholders("") == []

    def test_none_input(self):
        assert find_placeholders(None) == []


class TestSubstitutePlaceholders:
    def test_basic_substitution(self):
        assert substitute_placeholders("QSY to channel {N}", {"N": "22"}) == "QSY to channel 22"

    def test_multiple_placeholders(self):
        result = substitute_placeholders("Meet at {Time} on {Channel}", {"Time": "1900Z", "Channel": "22"})
        assert result == "Meet at 1900Z on 22"

    def test_duplicate_placeholder_uses_same_value(self):
        result = substitute_placeholders("Channel {N}, repeating, channel {N}", {"N": "22"})
        assert result == "Channel 22, repeating, channel 22"

    def test_missing_value_leaves_token_untouched(self):
        # Caller decides whether to abort or transmit literally.
        assert substitute_placeholders("QSY to channel {N}", {}) == "QSY to channel {N}"

    def test_extra_values_ignored(self):
        assert substitute_placeholders("Radio check", {"Unused": "value"}) == "Radio check"

    def test_non_string_value_coerced(self):
        assert substitute_placeholders("Channel {N}", {"N": 22}) == "Channel 22"

    def test_empty_value_substitutes_empty(self):
        assert substitute_placeholders("Channel {N}", {"N": ""}) == "Channel "

    def test_empty_input(self):
        assert substitute_placeholders("", {"N": "22"}) == ""

    def test_none_input(self):
        assert substitute_placeholders(None, {"N": "22"}) is None
