import re

from backend.text.phonetics import (
    NATO_PHONETIC,
    NUMBER_WORDS,
    collapse_single_char_runs,
    convert_phonetics,
    join_letters_and_digits,
)

# Callsign formats we detect:
#   - GMRS modern:  W + 3 letters + 3 digits         (WSLZ233)
#   - GMRS legacy:  KA + 1 letter + 3-4 digits       (KAE1234)
#   - US amateur:   1-2 letters (A/K/N/W prefix) +
#                   1 digit + 1-3 letters            (K1ABC, KD9XYZ, W1AW)
CALLSIGN_RE = re.compile(
    r'\b(W[A-Z]{3}\d{3}|KA[A-Z]\d{3,4}|[AKNW][A-Z]?\d[A-Z]{1,3})\b',
    re.IGNORECASE,
)


def _letter_token(letters):
    """Sub-pattern matching one letter (constrained to `letters`) either as a
    single character or as a NATO phonetic word for that letter. NATO words
    are \\b-anchored so 'Sierra-Leone' won't false-match 'Sierra'; single
    chars are not anchored so adjacent-letter runs like 'WSLZ' chain."""
    upper = set(letters.upper())
    words = [w for w, c in NATO_PHONETIC.items() if c in upper]
    if "X" in upper:
        # NATO_PHONETIC stores X as the collapsed 'xray'; also accept the
        # hyphenated/spaced renderings the FCC ID rule emits.
        words.extend(["X-ray", "X ray"])
    # Longest-first so 'Whiskey' wins over single-char 'W' at the same start.
    words.sort(key=len, reverse=True)
    chars = "[" + "".join(sorted(upper)) + "]"
    if not words:
        return chars
    return r"(?:\b(?:" + "|".join(re.escape(w) for w in words) + r")\b|" + chars + r")"


def _digit_token():
    words = sorted(NUMBER_WORDS.keys(), key=len, reverse=True)
    return r"(?:\b(?:" + "|".join(re.escape(w) for w in words) + r")\b|\d)"


_SEP = r"[\s.,\-]*"  # optional separator (space, period, comma, hyphen)
_ANY_LETTER = _letter_token("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
_W_LETTER = _letter_token("W")
_K_LETTER = _letter_token("K")
_A_LETTER = _letter_token("A")
_AKNW_LETTER = _letter_token("AKNW")
_ANY_DIGIT = _digit_token()


def _seq(*parts):
    return _SEP.join(parts)


_GMRS_MODERN = _seq(
    _W_LETTER, _ANY_LETTER, _ANY_LETTER, _ANY_LETTER,
    _ANY_DIGIT, _ANY_DIGIT, _ANY_DIGIT,
)
_GMRS_LEGACY = _seq(
    _K_LETTER, _A_LETTER, _ANY_LETTER,
    _ANY_DIGIT, _ANY_DIGIT, _ANY_DIGIT,
) + f"(?:{_SEP}{_ANY_DIGIT})?"
_US_AMATEUR = (
    _AKNW_LETTER
    + f"(?:{_SEP}{_ANY_LETTER})?"
    + _SEP + _ANY_DIGIT
    + _SEP + _ANY_LETTER
    + f"(?:{_SEP}{_ANY_LETTER})?"
    + f"(?:{_SEP}{_ANY_LETTER})?"
)

# Matches a callsign in its raw, spaced, hyphenated, period/comma-separated,
# or NATO-phonetic form. The match span covers the original characters, so
# callers can use the offsets to style the rendered text.
EXPANDED_CALLSIGN_RE = re.compile(
    r"\b(?:" + _GMRS_MODERN + r"|" + _GMRS_LEGACY + r"|" + _US_AMATEUR + r")\b",
    re.IGNORECASE,
)

# Derived from NATO_PHONETIC (word→letter); first occurrence wins so
# canonical spellings (Alpha, Juliet, Whiskey) take priority over aliases
# (Alfa, Juliett, Whisky). X-ray is patched because NATO_PHONETIC stores it
# as "xray" (the hyphen is stripped during normalisation).
LETTER_TO_NATO: dict[str, str] = {}
for _word, _letter in NATO_PHONETIC.items():
    LETTER_TO_NATO.setdefault(_letter.upper(), _word.capitalize())
LETTER_TO_NATO["X"] = "X-ray"


def detect_callsigns(text):
    """Return uppercased GMRS callsigns found in raw or phonetic/spaced forms.
    Handles separators: whitespace, hyphens, and periods between letters/digits."""
    if not text:
        return []
    found = set()
    phonetic = convert_phonetics(text)
    variants = [
        text,
        join_letters_and_digits(text),
        collapse_single_char_runs(text),
        join_letters_and_digits(collapse_single_char_runs(text)),
        collapse_single_char_runs(phonetic),
        join_letters_and_digits(phonetic),
        join_letters_and_digits(collapse_single_char_runs(phonetic)),
    ]
    for variant in variants:
        for m in CALLSIGN_RE.finditer(variant):
            found.add(m.group(1).upper())
    return sorted(found)


def callsign_to_nato(callsign):
    """'WSLZ233' -> 'Whiskey Sierra Lima Zulu 2 3 3'. Letters become NATO words,
    digits stay individual."""
    parts = []
    for ch in callsign.upper():
        if ch in LETTER_TO_NATO:
            parts.append(LETTER_TO_NATO[ch])
        elif ch.isdigit():
            parts.append(ch)
    return ' '.join(parts)


def find_callsign_spans(text):
    """Locate callsigns at their ORIGINAL character positions in `text`,
    including NATO-phonetic, spaced, hyphenated, period- and comma-separated
    forms. Returns a list of (start, end, callsign_upper) tuples sorted by
    start position. Callers use the offsets to style the rendered text."""
    if not text:
        return []
    spans = []
    for m in EXPANDED_CALLSIGN_RE.finditer(text):
        canonical = detect_callsigns(m.group(0))
        if canonical:
            spans.append((m.start(), m.end(), canonical[0]))
    return spans


def fuzzy_match_callsign(detected, known_callsigns):
    """Return the single known callsign that differs from ``detected`` in
    exactly one character (same length, same letter-vs-digit shape at the
    differing position), or ``None`` when there is no candidate or when two
    or more known callsigns are equally close.

    Used by the "fuzzy callsign logic" toggle: STT sometimes mishears a
    single letter or digit (``WSLZ233`` → ``WSLZ235``). When the toggle is
    on, an off-by-one detection is treated as a hit on the known call so
    the chat shows the corrected token rather than a stray near-miss.

    Ambiguity is disqualifying on purpose: when two known calls both sit
    one edit away, picking either silently would be wrong as often as it
    was right, so the caller falls back to its non-fuzzy behavior."""
    if not detected or not known_callsigns:
        return None
    detected = detected.upper()
    if detected in known_callsigns:
        return detected
    best = None
    for known in known_callsigns:
        known = known.upper()
        if len(known) != len(detected):
            continue
        diff_index = -1
        for i, (a, b) in enumerate(zip(detected, known)):
            if a != b:
                if diff_index != -1:
                    diff_index = -2
                    break
                diff_index = i
        if diff_index < 0:
            continue
        a, b = detected[diff_index], known[diff_index]
        # Only swap like-for-like — a letter STT'd as a letter, or a digit
        # STT'd as a digit. A digit-in-letter-slot is usually a different
        # callsign shape, not a one-character typo.
        if a.isalpha() != b.isalpha() or a.isdigit() != b.isdigit():
            continue
        if best is not None and best != known:
            return None
        best = known
    return best


def spell_digits_in_callsigns(text):
    """Insert spaces around every digit in any detected callsign so TTS reads
    them one at a time. 'WSLZ233' -> 'WSLZ 2 3 3', 'K1ABC' -> 'K 1 ABC'.
    Amateur callsigns have a digit between letter groups, so we tokenize on
    letter-runs vs. individual digits rather than assuming a single prefix."""
    def repl(m):
        cs = m.group(1)
        tokens = re.findall(r'[A-Za-z]+|\d', cs)
        return ' '.join(tokens)

    return CALLSIGN_RE.sub(repl, text)
