"""Shared STT helpers: Whisper initial-prompt construction and the
hallucination/empty-output drop. Used by both the CPU (faster-whisper) and
GPU (transformers) transcribers so the logic lives in exactly one place.
"""
from backend.constants import HALLUCINATIONS

# Whisper keeps only ~223 prompt tokens (the tail). Callers order phrases
# lowest-priority-first, so trimming from the front drops generic vocab
# while callsigns/custom phrases survive. 220 leaves a small margin.
MAX_PROMPT_TOKENS = 220

_BASE = "GMRS radio."


def _render_list(phrases: list) -> str:
    return f"{_BASE} Phrases: {', '.join(phrases)}."


def _render_transcript(phrases: list) -> str:
    return f"{_BASE} " + " ".join(p.rstrip(".") + "." for p in phrases) + " Over."


# "list" is today's labeled-word-list framing (production default).
# "transcript" renders phrases as terse on-air log lines, for eval A/B testing.
_RENDERERS = {"list": _render_list, "transcript": _render_transcript}


def build_prompt(phrases, *, count_tokens, style="list") -> str:
    """Frame saved phrases into a Whisper initial_prompt within the token budget.
    Trims from the front (lowest priority) until it fits. Unknown styles fall
    back to "list" (mirrors how config.py normalizes unknown enums)."""
    phrases = [p for p in (phrases or []) if p]
    if not phrases:
        return _BASE
    render = _RENDERERS.get(style, _render_list)
    while phrases:
        prompt = render(phrases)
        if count_tokens(prompt) <= MAX_PROMPT_TOKENS:
            return prompt
        phrases.pop(0)
    return _BASE


def is_hallucination(text: str) -> bool:
    """True when text is empty or matches a known Whisper-on-silence hallucination."""
    if not text:
        return True
    normalized = text.lower().strip(".,!?;: ")
    return not normalized or normalized in HALLUCINATIONS
