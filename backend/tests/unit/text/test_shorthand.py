from backend.text.shorthand import expand_tty_abbreviations


class TestUniversalTerms:
    def test_ga(self):
        assert expand_tty_abbreviations("GA Bob") == "Go ahead Bob"

    def test_sk(self):
        assert expand_tty_abbreviations("SK now") == "Stop keying now"

    def test_sksk_takes_precedence_over_sk(self):
        # Longest-key-first ordering: SKSK must match before SK.
        assert expand_tty_abbreviations("SKSK") == "Hanging up"

    def test_ga_to_sk_takes_precedence_over_ga_and_sk(self):
        assert (
            expand_tty_abbreviations("GA TO SK")
            == "Completing messages and getting ready to hang up"
        )

    def test_q_question_mark(self):
        assert expand_tty_abbreviations("Bob Q") == "Bob Question mark"

    def test_xxxx_erasing_error(self):
        assert expand_tty_abbreviations("oops XXXX done") == "oops Erasing the error done"


class TestCommonTerms:
    def test_asap(self):
        assert expand_tty_abbreviations("Call ASAP") == "Call As soon as possible"

    def test_ily(self):
        assert expand_tty_abbreviations("ILY mom") == "I love you mom"

    def test_cul(self):
        assert expand_tty_abbreviations("CUL friend") == "See you later friend"

    def test_msg(self):
        assert expand_tty_abbreviations("got your MSG") == "got your Message"


class TestCaseInsensitivity:
    def test_lowercase_matches(self):
        assert expand_tty_abbreviations("ga lowercase") == "Go ahead lowercase"

    def test_mixed_case_matches(self):
        assert expand_tty_abbreviations("Asap") == "As soon as possible"


class TestRadioVernacular:
    def test_73_sign_off(self):
        assert expand_tty_abbreviations("73 Bob") == "best regards Bob"

    def test_88(self):
        assert expand_tty_abbreviations("88 from K1ABC") == "love and kisses from K1ABC"

    def test_qsl(self):
        assert expand_tty_abbreviations("QSL on the last") == "received and acknowledged on the last"

    def test_qso(self):
        assert expand_tty_abbreviations("nice QSO") == "nice radio contact"

    def test_qth(self):
        assert expand_tty_abbreviations("my QTH is Ohio") == "my location is Ohio"

    def test_qrz(self):
        assert expand_tty_abbreviations("QRZ?") == "who is calling me?"

    def test_qrm(self):
        assert expand_tty_abbreviations("heavy QRM") == "heavy interference"

    def test_qrn(self):
        assert expand_tty_abbreviations("QRN tonight") == "static tonight"

    def test_qrt(self):
        assert expand_tty_abbreviations("going QRT") == "going stopping transmission"

    def test_hw(self):
        assert expand_tty_abbreviations("HW?") == "how copy?"

    def test_om(self):
        assert expand_tty_abbreviations("tnx OM") == "thanks old man"

    def test_xyl(self):
        assert expand_tty_abbreviations("XYL says hi") == "wife says hi"

    def test_wx(self):
        assert expand_tty_abbreviations("WX is clear") == "weather is clear"

    def test_tnx(self):
        assert expand_tty_abbreviations("TNX for the call") == "thanks for the call"

    def test_rst(self):
        assert expand_tty_abbreviations("your RST is 599") == "your readability strength tone is 599"

    def test_es(self):
        assert expand_tty_abbreviations("rig ES antenna") == "rig and antenna"

    def test_fb(self):
        assert expand_tty_abbreviations("FB signal") == "fine business signal"

    def test_agn(self):
        assert expand_tty_abbreviations("say AGN") == "say again"

    def test_b4(self):
        assert expand_tty_abbreviations("worked you B4") == "worked you before"


class TestWordBoundaries:
    def test_q_inside_qso_expands_qso_not_q(self):
        # Longest-key-first ordering: QSO must match before Q so we get
        # "radio contact", not "Question mark SO".
        assert expand_tty_abbreviations("QSO traffic") == "radio contact traffic"

    def test_q_inside_word_not_expanded(self):
        # Standalone Q expands to "Question mark"; Q inside 'Quick' must not.
        assert expand_tty_abbreviations("Quick Q") == "Quick Question mark"

    def test_73_inside_year_not_expanded(self):
        # Bare 73 expands; embedded in '1973' it must not.
        assert expand_tty_abbreviations("1973 was a year") == "1973 was a year"

    def test_dr_inside_doctor_not_expanded(self):
        # 'Doctor' must survive unchanged even though 'DR' is in the table.
        assert expand_tty_abbreviations("Doctor uses DR shorthand") == "Doctor uses Doctor shorthand"

    def test_msg_inside_messaging_not_expanded(self):
        assert expand_tty_abbreviations("messaging system") == "messaging system"

    def test_no_match_unchanged(self):
        assert expand_tty_abbreviations("plain prose with no shorthand") == (
            "plain prose with no shorthand"
        )

    def test_empty_string(self):
        assert expand_tty_abbreviations("") == ""
