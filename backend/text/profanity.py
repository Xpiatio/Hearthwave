import re

# Curated PG-13 profanity list for GMRS use. Keeps the channel within FCC
# Part 95 obscenity expectations and avoids the words that push an MPAA
# rating from PG-13 to R (strong sexual profanity, slurs). Milder words
# tolerated in PG-13 ("damn", "hell", "ass" alone, "crap") are deliberately
# omitted so legitimate radio speech isn't over-masked.
#
# Add entries in lowercase; matching is case-insensitive and word-bounded.
PROFANITY_WORDS = frozenset({
    # F-word family
    "fuck", "fucks", "fucked", "fucking", "fucker", "fuckers", "fuckin",
    "motherfucker", "motherfuckers", "motherfucking",
    # S-word family
    "shit", "shits", "shitted", "shitting", "shitty", "shitter", "shitters",
    "bullshit", "bullshitter", "dipshit", "horseshit",
    # B-words
    "bitch", "bitches", "bitched", "bitching", "bitchy",
    "bastard", "bastards",
    # Anatomy used as profanity (compound forms — bare "ass" stays PG-13)
    "asshole", "assholes", "asshat", "asshats", "jackass", "jackasses",
    "dickhead", "dickheads", "cocksucker", "cocksuckers",
    "prick", "pricks",
    # C-words
    "cunt", "cunts",
    # Other strong words
    "piss", "pissed", "pisser", "pissing",
    "twat", "twats", "wanker", "wankers",
    "douche", "douchebag", "douchebags",
    # Slurs — always filtered regardless of register
    "nigger", "niggers", "nigga", "niggas",
    "faggot", "faggots", "fag", "fags",
    "retard", "retards", "retarded",
    "tranny", "trannies",
    "chink", "chinks", "spic", "spics", "kike", "kikes", "gook", "gooks",
})


_PROFANITY_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in sorted(PROFANITY_WORDS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def _mask_word(word):
    # Preserve the first character (and its case) so masked output stays
    # readable in context — "f***" / "s***" — without spelling the slur back.
    return word[0] + "*" * (len(word) - 1)


def mask_profanity(text):
    """Replace whole-word profanity matches with a first-letter + asterisks
    mask (e.g. 'shit' -> 's***'). Case-insensitive, word-boundary matched so
    substrings inside benign words ('class', 'assassin', 'Scunthorpe') are
    left alone. The first character's case is preserved."""
    if not text:
        return text
    return _PROFANITY_PATTERN.sub(lambda m: _mask_word(m.group(1)), text)
