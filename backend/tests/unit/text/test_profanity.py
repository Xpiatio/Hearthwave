from backend.text.profanity import mask_profanity


class TestMaskingFormat:
    def test_four_letter_word(self):
        # First letter preserved, remainder asterisked; length preserved.
        assert mask_profanity("oh shit") == "oh s***"

    def test_seven_letter_word(self):
        assert mask_profanity("you asshole") == "you a******"

    def test_first_letter_case_preserved(self):
        assert mask_profanity("Shit happens") == "S*** happens"
        assert mask_profanity("FUCK off") == "F*** off"

    def test_multiple_words_in_one_message(self):
        result = mask_profanity("shit and fuck")
        assert result == "s*** and f***"

    def test_no_profanity_unchanged(self):
        msg = "Radio check, copy that, going QSY to channel 5."
        assert mask_profanity(msg) == msg

    def test_empty_string(self):
        assert mask_profanity("") == ""


class TestCaseInsensitivity:
    def test_lowercase_match(self):
        assert mask_profanity("fuck") == "f***"

    def test_uppercase_match(self):
        assert mask_profanity("FUCK") == "F***"

    def test_mixed_case_match(self):
        assert mask_profanity("FuCk") == "F***"


class TestWordBoundaries:
    def test_class_unchanged(self):
        # 'class' contains 'ass' but bare 'ass' isn't in the list anyway;
        # this just guards against accidental broader matching.
        assert mask_profanity("classroom") == "classroom"

    def test_assassin_unchanged(self):
        # 'assassin' contains 'ass' substring; word-boundary regex must not
        # match either 'ass' or 'asshole' inside it.
        assert mask_profanity("assassin") == "assassin"

    def test_scunthorpe_unchanged(self):
        # The classic substring-match false positive — 'cunt' inside a place name.
        assert mask_profanity("Scunthorpe") == "Scunthorpe"

    def test_shitake_unchanged(self):
        # 'shit' substring inside an unrelated word.
        assert mask_profanity("shitake mushrooms") == "shitake mushrooms"

    def test_passing_unchanged(self):
        # 'ass' inside 'passing' is fine since bare ass isn't filtered, but
        # also guards against future regressions if someone adds it.
        assert mask_profanity("passing through") == "passing through"


class TestVariants:
    def test_plural_form(self):
        assert mask_profanity("you assholes") == "you a*******"

    def test_ing_form(self):
        assert mask_profanity("fucking radio") == "f****** radio"

    def test_motherfucker(self):
        assert mask_profanity("motherfucker") == "m***********"

    def test_compound_bullshit(self):
        assert mask_profanity("total bullshit") == "total b*******"


class TestPunctuation:
    def test_trailing_punctuation(self):
        # 'shit!' — punctuation acts as a word boundary, mask applies.
        assert mask_profanity("oh shit!") == "oh s***!"

    def test_quoted(self):
        assert mask_profanity('he said "shit"') == 'he said "s***"'

    def test_apostrophe_trailing(self):
        # "fuckin'" — apostrophe is a non-word char, so 'fuckin' word-matches
        # and the apostrophe is left in place untouched.
        assert mask_profanity("fuckin' radio") == "f*****' radio"


class TestMildPg13Allowed:
    """PG-13 explicitly allows mild language. These should pass through unmasked
    so legitimate radio speech ('damn it', 'go to hell', 'kick ass') survives."""

    def test_damn_unchanged(self):
        assert mask_profanity("damn it") == "damn it"

    def test_hell_unchanged(self):
        assert mask_profanity("what the hell") == "what the hell"

    def test_ass_alone_unchanged(self):
        assert mask_profanity("kick ass") == "kick ass"

    def test_crap_unchanged(self):
        assert mask_profanity("oh crap") == "oh crap"
