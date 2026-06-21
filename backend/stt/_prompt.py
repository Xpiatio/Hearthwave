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


def build_prompt(phrases, *, count_tokens) -> str:
    """Frame saved phrases into a Whisper initial_prompt within the token budget.
    Trims from the front (lowest priority) until it fits."""
    phrases = [p for p in (phrases or []) if p]
    if not phrases:
        return _BASE
    while phrases:
        prompt = f"{_BASE} Phrases: {', '.join(phrases)}."
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
