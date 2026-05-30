import re

# Curly-brace `{Name}` tokens in quick-message presets. The tokenizer is
# intentionally dumb — no expressions, no defaults, no escaping — because the
# operator is editing presets, not writing a templating language. Names accept
# letters, digits, underscores, and spaces so prompts like `{Channel Number}`
# stay readable in the inline popover.
_PLACEHOLDER_PATTERN = re.compile(r"\{([A-Za-z0-9_][A-Za-z0-9_ ]*)\}")


def find_placeholders(text):
    """Return the ordered list of placeholder names in `text`, deduplicated
    on first occurrence so a preset that mentions `{N}` twice only prompts
    the operator once."""
    seen = []
    for match in _PLACEHOLDER_PATTERN.finditer(text or ""):
        name = match.group(1).strip()
        if name and name not in seen:
            seen.append(name)
    return seen


def substitute_placeholders(text, values):
    """Replace every `{Name}` token in `text` with the matching entry from
    `values` (keyed by the same normalized name returned by `find_placeholders`).
    Tokens missing from `values` are left untouched so the caller can decide
    whether to abort or transmit the literal text."""
    if not text:
        return text

    def _replace(match):
        name = match.group(1).strip()
        if name in values:
            return str(values[name])
        return match.group(0)

    return _PLACEHOLDER_PATTERN.sub(_replace, text)
