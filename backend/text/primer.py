"""Spoken VOX priming word: prefix a keyword to TX text so a VOX-keyed radio
hears a clear word (e.g. "transmit") before the actual message."""


def prepend_primer_word(text: str, word: str) -> str:
    """Return *text* with *word* spoken first, separated by a period so TTS
    pauses between them.  Returns *text* unchanged when *word* is empty or
    whitespace-only."""
    w = (word or "").strip()
    if not w:
        return text
    return f"{w}. {text}"
