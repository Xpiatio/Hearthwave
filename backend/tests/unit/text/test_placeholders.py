from backend.text.placeholders import find_placeholders, resolve_aac_placeholders, substitute_placeholders


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


class TestResolveAacPlaceholders:
    def test_fills_name_and_callsign_case_insensitive(self):
        out = resolve_aac_placeholders("this is {callsign} checking in, {Name}", "Sam", "WRXB123")
        assert out == "this is WRXB123 checking in, Sam"

    def test_strips_unknown_tokens_and_collapses_whitespace(self):
        assert resolve_aac_placeholders("hello {weird token} world", "Sam", "W1AW") == "hello world"

    def test_fallbacks_match_frontend(self):
        assert resolve_aac_placeholders("{Name} {callsign}", "", "") == "Operator my callsign"

    def test_backslash_group_ref_in_name_passes_through_literally(self):
        # A replacement value containing a regex backslash-group reference
        # (e.g. "\1") must not be interpreted by re.sub — it previously
        # raised re.error: invalid group reference and crashed the socket.
        out = resolve_aac_placeholders("hi {Name}", r"\1", "WRXB123")
        assert out == r"hi \1"

    def test_backslash_group_ref_in_callsign_passes_through_literally(self):
        out = resolve_aac_placeholders("this is {callsign}", "Sam", r"\1")
        assert out == r"this is \1"

    def test_dollar_amp_in_name_passes_through_literally(self):
        # "$&" has no special meaning in Python re.sub replacement strings,
        # but is included as a defensive regression check for replacement
        # metacharacter handling generally.
        out = resolve_aac_placeholders("hi {Name}", "$&", "WRXB123")
        assert out == "hi $&"
