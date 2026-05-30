
from backend.text.callsigns import (
    callsign_to_nato,
    detect_callsigns,
    find_callsign_spans,
    fuzzy_match_callsign,
    spell_digits_in_callsigns,
)


class TestDetectCallsignsEmptyInputs:
    def test_none_returns_empty(self):
        assert detect_callsigns(None) == []

    def test_empty_string_returns_empty(self):
        assert detect_callsigns("") == []

    def test_no_callsign_returns_empty(self):
        assert detect_callsigns("just text, nothing radio-shaped here") == []


class TestDetectCallsignsCompactForms:
    def test_gmrs_modern(self):
        assert detect_callsigns("WSLZ233 here") == ["WSLZ233"]

    def test_gmrs_legacy_three_digit(self):
        assert detect_callsigns("KAE123 calling") == ["KAE123"]

    def test_gmrs_legacy_four_digit(self):
        assert detect_callsigns("KAE1234 calling") == ["KAE1234"]

    def test_us_amateur_one_by_three(self):
        assert detect_callsigns("K1ABC here") == ["K1ABC"]

    def test_us_amateur_two_by_three(self):
        assert detect_callsigns("KD9XYZ here") == ["KD9XYZ"]

    def test_us_amateur_one_by_two(self):
        assert detect_callsigns("W1AW broadcasting") == ["W1AW"]

    def test_lowercase_input_is_normalized_to_upper(self):
        assert detect_callsigns("wslz233 over") == ["WSLZ233"]

    def test_multiple_distinct_callsigns_sorted(self):
        # Output is sorted alphabetically (set internally, sorted on return).
        assert detect_callsigns("WSLZ233 and KAE1234") == ["KAE1234", "WSLZ233"]


class TestDetectCallsignsSpacedAndSeparated:
    def test_space_separated_chars(self):
        assert detect_callsigns("W S L Z 2 3 3") == ["WSLZ233"]

    def test_dot_separated_chars(self):
        assert detect_callsigns("W.S.L.Z.2.3.3") == ["WSLZ233"]

    def test_comma_separated_chars(self):
        assert detect_callsigns("W, S, L, Z, 2, 3, 3") == ["WSLZ233"]

    def test_letter_block_dash_digits(self):
        assert detect_callsigns("WSLZ-233") == ["WSLZ233"]

    def test_letter_block_dot_digits(self):
        assert detect_callsigns("WSLZ.233") == ["WSLZ233"]

    def test_letter_block_comma_digits(self):
        assert detect_callsigns("WSLZ, 233") == ["WSLZ233"]

    def test_letter_block_space_digits(self):
        assert detect_callsigns("WSLZ 233") == ["WSLZ233"]


class TestDetectCallsignsPhonetic:
    def test_nato_phonetic_titlecase(self):
        assert detect_callsigns("Whiskey Sierra Lima Zulu Two Three Three") == ["WSLZ233"]

    def test_nato_phonetic_lowercase(self):
        assert detect_callsigns("whiskey sierra lima zulu two three three") == ["WSLZ233"]

    def test_nato_phonetic_with_xray_hyphen(self):
        # 'X-ray' is normalized to 'Xray' so it becomes a single 'X' letter.
        # Whiskey X-ray Sierra Zulu = WXSZ, which fits W[A-Z]{3}\d{3}.
        assert detect_callsigns("Whiskey X-ray Sierra Zulu Two Three Three") == ["WXSZ233"]

    def test_nato_phonetic_with_xray_space(self):
        assert detect_callsigns("Whiskey X ray Sierra Zulu Two Three Three") == ["WXSZ233"]

    def test_juliet_variant_juliett(self):
        # The phonetic alphabet table accepts both 'Juliet' and 'Juliett'.
        assert detect_callsigns("Whiskey Juliett Lima Zulu Two Three Three") == ["WJLZ233"]


class TestCallsignToNato:
    def test_modern_gmrs(self):
        assert callsign_to_nato("WSLZ233") == "Whiskey Sierra Lima Zulu 2 3 3"

    def test_amateur_with_interior_digit(self):
        assert callsign_to_nato("K1ABC") == "Kilo 1 Alpha Bravo Charlie"

    def test_lowercase_input_is_upper_cased(self):
        assert callsign_to_nato("wslz233") == "Whiskey Sierra Lima Zulu 2 3 3"

    def test_empty(self):
        assert callsign_to_nato("") == ""

    def test_x_uses_x_ray_token(self):
        # X is the only letter whose NATO form contains a hyphen — preserve it.
        assert callsign_to_nato("WXSZ233") == "Whiskey X-ray Sierra Zulu 2 3 3"


class TestSpellDigitsInCallsigns:
    def test_gmrs_modern(self):
        assert spell_digits_in_callsigns("Hello WSLZ233") == "Hello WSLZ 2 3 3"

    def test_amateur_with_interior_digit(self):
        assert spell_digits_in_callsigns("K1ABC says hi") == "K 1 ABC says hi"

    def test_legacy_four_digit(self):
        assert spell_digits_in_callsigns("KAE1234 calling") == "KAE 1 2 3 4 calling"

    def test_multiple_callsigns_spelled_independently(self):
        assert (
            spell_digits_in_callsigns("two WSLZ233 in row KAE1234")
            == "two WSLZ 2 3 3 in row KAE 1 2 3 4"
        )

    def test_non_callsign_text_left_alone(self):
        assert spell_digits_in_callsigns("just plain text 100") == "just plain text 100"


class TestFindCallsignSpansEmptyInputs:
    def test_none_returns_empty(self):
        assert find_callsign_spans(None) == []

    def test_empty_string_returns_empty(self):
        assert find_callsign_spans("") == []

    def test_plain_text_returns_empty(self):
        assert find_callsign_spans("Hello, world.") == []

    def test_too_few_digits_returns_empty(self):
        # GMRS modern needs 3 digits; with only 2 we shouldn't match.
        assert find_callsign_spans("WSLZ 23 over") == []


class TestFindCallsignSpansCompact:
    def test_raw_gmrs_modern_offsets(self):
        # 'hello ' is 6 characters; 'WSLZ233' is 7. Span should be (6, 13).
        assert find_callsign_spans("hello WSLZ233 over") == [(6, 13, "WSLZ233")]

    def test_raw_amateur(self):
        assert find_callsign_spans("K1ABC here") == [(0, 5, "K1ABC")]

    def test_raw_gmrs_legacy_four_digit(self):
        assert find_callsign_spans("KAE1234 calling") == [(0, 7, "KAE1234")]

    def test_lowercase_normalized(self):
        spans = find_callsign_spans("wslz233 over")
        assert spans == [(0, 7, "WSLZ233")]

    def test_multiple_callsigns_left_to_right(self):
        text = "WSLZ233 to KAE1234"
        spans = find_callsign_spans(text)
        assert [cs for _, _, cs in spans] == ["WSLZ233", "KAE1234"]
        # Each returned span should cover the source substring.
        for start, end, cs in spans:
            assert text[start:end].replace(" ", "").upper() == cs


class TestFindCallsignSpansSpaced:
    def test_all_chars_space_separated(self):
        text = "W S L Z 2 3 3 ack"
        spans = find_callsign_spans(text)
        assert spans == [(0, 13, "WSLZ233")]

    def test_letter_block_space_digits(self):
        text = "WSLZ 233 here"
        spans = find_callsign_spans(text)
        assert spans == [(0, 8, "WSLZ233")]

    def test_period_separated(self):
        text = "W.S.L.Z.2.3.3 over"
        spans = find_callsign_spans(text)
        assert spans == [(0, 13, "WSLZ233")]

    def test_letter_block_period_digits(self):
        text = "WSLZ.233 over"
        spans = find_callsign_spans(text)
        assert spans == [(0, 8, "WSLZ233")]

    def test_hyphen_separated(self):
        text = "WSLZ-233 here"
        spans = find_callsign_spans(text)
        assert spans == [(0, 8, "WSLZ233")]

    def test_comma_separated(self):
        text = "W, S, L, Z, 2, 3, 3 out"
        spans = find_callsign_spans(text)
        assert len(spans) == 1
        start, end, cs = spans[0]
        assert cs == "WSLZ233"
        assert text[start:end] == "W, S, L, Z, 2, 3, 3"


class TestFindCallsignSpansPhonetic:
    def test_full_nato(self):
        text = "calling Whiskey Sierra Lima Zulu Two Three Three out"
        spans = find_callsign_spans(text)
        assert len(spans) == 1
        start, end, cs = spans[0]
        assert cs == "WSLZ233"
        assert text[start:end] == "Whiskey Sierra Lima Zulu Two Three Three"

    def test_nato_lowercase(self):
        text = "whiskey sierra lima zulu two three three"
        spans = find_callsign_spans(text)
        assert spans[0][2] == "WSLZ233"

    def test_nato_with_xray_hyphen(self):
        text = "Whiskey X-ray Sierra Zulu Two Three Three"
        spans = find_callsign_spans(text)
        assert len(spans) == 1
        assert spans[0][2] == "WXSZ233"
        s, e, _ = spans[0]
        assert text[s:e] == text  # the whole input is the callsign

    def test_nato_with_xray_space(self):
        text = "Whiskey X ray Sierra Zulu Two Three Three"
        spans = find_callsign_spans(text)
        assert spans[0][2] == "WXSZ233"

    def test_juliett_variant(self):
        text = "Whiskey Juliett Lima Zulu Two Three Three"
        spans = find_callsign_spans(text)
        assert spans[0][2] == "WJLZ233"

    def test_whisky_variant(self):
        # 'Whisky' (no e) is an accepted spelling of the NATO 'W'.
        text = "Whisky Sierra Lima Zulu Two Three Three"
        spans = find_callsign_spans(text)
        assert spans[0][2] == "WSLZ233"

    def test_alfa_variant(self):
        # 'Alfa' (instead of Alpha) is an accepted spelling of the NATO 'A'.
        text = "Kilo Alfa Echo One Two Three"
        spans = find_callsign_spans(text)
        assert spans[0][2] == "KAE123"

    def test_amateur_phonetic(self):
        text = "Kilo One Alpha Bravo Charlie clear"
        spans = find_callsign_spans(text)
        assert spans[0][2] == "K1ABC"

    def test_legacy_phonetic(self):
        text = "Kilo Alpha Echo One Two Three Four out"
        spans = find_callsign_spans(text)
        assert spans[0][2] == "KAE1234"

    def test_mixed_nato_and_raw(self):
        text = "Whiskey Sierra Lima Zulu 233 hello"
        spans = find_callsign_spans(text)
        assert spans[0][2] == "WSLZ233"

    def test_nato_not_in_word_boundary(self):
        # 'Sierraleone' should not contribute a callsign — the NATO branch
        # requires the word to stand alone.
        assert find_callsign_spans("Whiskey Sierraleone Lima Zulu Two Three Three") == []


class TestFuzzyMatchCallsign:
    def test_exact_match_returns_input(self):
        assert fuzzy_match_callsign("WSLZ233", {"WSLZ233"}) == "WSLZ233"

    def test_off_by_one_letter_matches(self):
        # Common Whisper miss: 'L' vs 'I' look identical and sound similar.
        assert fuzzy_match_callsign("WSIZ233", {"WSLZ233"}) == "WSLZ233"

    def test_off_by_one_digit_matches(self):
        # STT regularly swaps adjacent digits — 'two' / 'three' / 'four'.
        assert fuzzy_match_callsign("WSLZ234", {"WSLZ233"}) == "WSLZ233"

    def test_case_insensitive(self):
        assert fuzzy_match_callsign("wslz234", {"wslz233"}) == "WSLZ233"

    def test_two_or_more_diffs_rejected(self):
        # Two characters off is not "off by one"; it's a different call.
        assert fuzzy_match_callsign("WSLZ244", {"WSLZ233"}) is None

    def test_different_length_rejected(self):
        # Edit distance via deletion/insertion is not a one-character swap;
        # an extra/missing char usually means STT split a digit-word wrong.
        assert fuzzy_match_callsign("WSLZ2333", {"WSLZ233"}) is None
        assert fuzzy_match_callsign("WSLZ23", {"WSLZ233"}) is None

    def test_letter_in_digit_slot_rejected(self):
        # 'WSLZ23A' would technically be one char off from 'WSLZ233', but the
        # diff is letter-vs-digit — that's not a single-character mishear, it's
        # a different callsign shape. Reject.
        assert fuzzy_match_callsign("WSLZ23A", {"WSLZ233"}) is None

    def test_digit_in_letter_slot_rejected(self):
        assert fuzzy_match_callsign("WSL3233", {"WSLZ233"}) is None

    def test_ambiguous_match_returns_none(self):
        # Two known callsigns both one edit away — picking either silently
        # would be wrong as often as it is right.
        assert fuzzy_match_callsign(
            "WSLZ234", {"WSLZ233", "WSLZ235"}
        ) is None

    def test_unrelated_known_callsigns_dont_interfere(self):
        assert fuzzy_match_callsign(
            "WSLZ234", {"WSLZ233", "KAE1234", "K1ABC"}
        ) == "WSLZ233"

    def test_empty_detected_returns_none(self):
        assert fuzzy_match_callsign("", {"WSLZ233"}) is None

    def test_empty_known_returns_none(self):
        assert fuzzy_match_callsign("WSLZ233", set()) is None

    def test_none_inputs_return_none(self):
        assert fuzzy_match_callsign(None, {"WSLZ233"}) is None
        assert fuzzy_match_callsign("WSLZ233", None) is None
