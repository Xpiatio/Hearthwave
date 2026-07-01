"""Unit tests for shared STT prompt + hallucination helpers."""
from backend.stt._prompt import build_prompt, is_hallucination, MAX_PROMPT_TOKENS


def _wordcount(s):  # fake tokenizer: 1 token per word
    return len(s.split())


def test_empty_returns_base():
    assert build_prompt([], count_tokens=_wordcount) == "GMRS radio."


def test_single_phrase_framed():
    assert build_prompt(["break break"], count_tokens=_wordcount) == (
        "GMRS radio. Phrases: break break."
    )


def test_token_trim_keeps_tail():
    phrases = [f"term{i}" for i in range(300)] + ["KE8ZZZ"]
    out = build_prompt(phrases, count_tokens=_wordcount)
    assert _wordcount(out) <= MAX_PROMPT_TOKENS
    assert out.endswith("KE8ZZZ.")
    assert "term0," not in out


def test_is_hallucination_empty():
    assert is_hallucination("") is True
    assert is_hallucination("   ") is True


def test_is_hallucination_known_phrase():
    # "you" is a canonical Whisper-on-silence hallucination in constants.HALLUCINATIONS
    assert is_hallucination("You.") is True


def test_is_hallucination_real_text():
    assert is_hallucination("unit seven en route") is False


# ---------------------------------------------------------------------------
# style="transcript" — terse on-air log line rendering
# ---------------------------------------------------------------------------

def test_transcript_style_renders_template():
    out = build_prompt(
        ["Whiskey Sierra Lima Zulu two three three", "Radio check"],
        count_tokens=_wordcount,
        style="transcript",
    )
    assert out == (
        "GMRS radio. Whiskey Sierra Lima Zulu two three three. Radio check. Over."
    )


def test_transcript_style_no_double_dot_on_trailing_period():
    out = build_prompt(["over."], count_tokens=_wordcount, style="transcript")
    assert out == "GMRS radio. over. Over."


def test_transcript_style_empty_returns_base():
    assert build_prompt([], count_tokens=_wordcount, style="transcript") == "GMRS radio."


def test_transcript_style_trims_from_front_keeps_tail():
    phrases = [f"term{i}" for i in range(300)] + ["KE8ZZZ"]
    out = build_prompt(phrases, count_tokens=_wordcount, style="transcript")
    assert _wordcount(out) <= MAX_PROMPT_TOKENS
    assert out.endswith("KE8ZZZ. Over.")
    assert "term0." not in out


def test_transcript_style_falls_back_to_base_when_nothing_fits():
    def never_fits(_s):
        return MAX_PROMPT_TOKENS + 1
    out = build_prompt(["anything"], count_tokens=never_fits, style="transcript")
    assert out == "GMRS radio."


def test_unknown_style_falls_back_to_list_output():
    phrases = ["over", "QSL"]
    assert build_prompt(phrases, count_tokens=_wordcount, style="bogus") == build_prompt(
        phrases, count_tokens=_wordcount
    )


def test_default_style_is_list():
    assert build_prompt(["over"], count_tokens=_wordcount) == "GMRS radio. Phrases: over."
