from backend.text.primer import prepend_primer_word


class TestPrependPrimerWord:
    def test_prepends_word_with_period_and_space(self):
        assert prepend_primer_word("hello world", "transmit") == "transmit. hello world"

    def test_custom_word(self):
        assert prepend_primer_word("go ahead", "break") == "break. go ahead"

    def test_empty_word_is_noop(self):
        assert prepend_primer_word("hello", "") == "hello"

    def test_whitespace_word_is_noop(self):
        assert prepend_primer_word("hello", "   ") == "hello"

    def test_word_is_stripped(self):
        assert prepend_primer_word("hello", "  transmit  ") == "transmit. hello"
