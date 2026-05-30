import re

# NATO phonetic alphabet (case insensitive)
NATO_PHONETIC = {
    "alpha": "A", "alfa": "A", "bravo": "B", "charlie": "C", "delta": "D",
    "echo": "E", "foxtrot": "F", "golf": "G", "hotel": "H", "india": "I",
    "juliet": "J", "juliett": "J", "kilo": "K", "lima": "L", "mike": "M",
    "november": "N", "oscar": "O", "papa": "P", "quebec": "Q", "romeo": "R",
    "sierra": "S", "tango": "T", "uniform": "U", "victor": "V", "whiskey": "W",
    "whisky": "W", "xray": "X", "yankee": "Y", "zulu": "Z",
}
NUMBER_WORDS = {
    "zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "fife": "5", "six": "6", "seven": "7", "eight": "8",
    "niner": "9", "nine": "9",
}

SINGLE_CHAR_RUN_RE = re.compile(r'\b(?:[A-Za-z0-9][\s\-.,]+){2,}[A-Za-z0-9]\b')


def convert_phonetics(text):
    """Replace NATO phonetic words and spelled-out digits with letters/digits."""
    # 'X-ray' is the only NATO word with an internal separator; normalize
    # 'X-ray' / 'X ray' to 'Xray' so the word-level regex treats it as a
    # single token instead of 'X' + 'ray'.
    text = re.sub(r'\bX[\s\-]ray\b', 'Xray', text, flags=re.IGNORECASE)

    def repl(m):
        w = m.group(0).lower()
        return NATO_PHONETIC.get(w, NUMBER_WORDS.get(w, m.group(0)))

    return re.sub(r'\b[A-Za-z]+\b', repl, text)


def collapse_single_char_runs(text):
    """Collapse runs of single-char tokens separated by whitespace, hyphens, periods, or commas.
    'W S L Z 2 3 3' -> 'WSLZ233', 'W.S.L.Z.2.3.3' -> 'WSLZ233', 'W, S, L, Z, 2, 3, 3' -> 'WSLZ233'."""
    return SINGLE_CHAR_RUN_RE.sub(
        lambda m: re.sub(r'[\s\-.,]+', '', m.group(0)), text
    )


def join_letters_and_digits(text):
    """Join a letter block to an adjacent digit block: 'WSLZ 233', 'WSLZ.233', 'WSLZ, 233' -> 'WSLZ233'."""
    return re.sub(r'([A-Za-z]{2,})[\s\-.,]+(\d{3,4})\b', r'\1\2', text)
