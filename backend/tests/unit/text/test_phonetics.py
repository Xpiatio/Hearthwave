from backend.text.phonetics import (
    collapse_single_char_runs,
    convert_phonetics,
    join_letters_and_digits,
)


class TestConvertPhonetics:
    def test_nato_letters_to_single_chars(self):
        assert convert_phonetics("Whiskey Sierra Lima Zulu") == "W S L Z"

    def test_numbers_to_digits(self):
        assert convert_phonetics("Two Three Three") == "2 3 3"

    def test_x_ray_hyphen_normalized(self):
        assert convert_phonetics("X-ray") == "X"

    def test_x_ray_space_normalized(self):
        assert convert_phonetics("X ray") == "X"

    def test_oh_means_zero(self):
        assert convert_phonetics("Oh") == "0"

    def test_niner_means_nine(self):
        assert convert_phonetics("niner") == "9"

    def test_alfa_alternate_spelling(self):
        # 'Alfa' is the international spelling; the table accepts both.
        assert convert_phonetics("Alfa") == "A"

    def test_unknown_words_preserved(self):
        assert convert_phonetics("Hello World") == "Hello World"

    def test_mixed_known_and_unknown(self):
        # Unknown 'Hello' kept; known 'Whiskey' converted.
        assert convert_phonetics("Hello Whiskey there") == "Hello W there"


class TestCollapseSingleCharRuns:
    def test_space_separated_letters_and_digits(self):
        assert collapse_single_char_runs("W S L Z 2 3 3") == "WSLZ233"

    def test_dot_separated(self):
        assert collapse_single_char_runs("W.S.L.Z.2.3.3") == "WSLZ233"

    def test_comma_separated(self):
        assert collapse_single_char_runs("W, S, L, Z, 2, 3, 3") == "WSLZ233"

    def test_hyphen_separated(self):
        assert collapse_single_char_runs("W-S-L-Z-2-3-3") == "WSLZ233"

    def test_single_token_left_alone(self):
        assert collapse_single_char_runs("WSLZ233") == "WSLZ233"

    def test_short_run_below_threshold_left_alone(self):
        # The regex requires at least 3 single-char tokens. Two-token runs
        # ('W S') are not collapsed because they're more often two real words.
        assert collapse_single_char_runs("W S") == "W S"


class TestJoinLettersAndDigits:
    def test_space_between_groups(self):
        assert join_letters_and_digits("WSLZ 233") == "WSLZ233"

    def test_dash_between_groups(self):
        assert join_letters_and_digits("WSLZ-233") == "WSLZ233"

    def test_dot_between_groups(self):
        assert join_letters_and_digits("WSLZ.233") == "WSLZ233"

    def test_comma_between_groups(self):
        assert join_letters_and_digits("WSLZ, 233") == "WSLZ233"

    def test_four_digit_legacy_suffix(self):
        assert join_letters_and_digits("KAE-1234") == "KAE1234"

    def test_letter_block_too_short_unchanged(self):
        # The regex requires ≥2 letters before the digit block. 'W 233' stays
        # as-is because a single-letter prefix is not enough to be a callsign-like
        # token under this normalization step.
        assert join_letters_and_digits("W 233") == "W 233"
