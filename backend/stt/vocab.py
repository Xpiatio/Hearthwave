"""Curated radio-domain vocabulary and the phrase-assembly logic used to bias
both Whisper engines via initial_prompt.

Pure module (no I/O). Terms are stored as ordered tuples for deterministic
output and so the tail-trim in WhisperTranscriber._build_prompt drops the
lowest-priority terms first.
"""
from __future__ import annotations

import logging

_log = logging.getLogger(__name__)

NATO: tuple[str, ...] = (
    "Alfa", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf", "Hotel",
    "India", "Juliett", "Kilo", "Lima", "Mike", "November", "Oscar", "Papa",
    "Quebec", "Romeo", "Sierra", "Tango", "Uniform", "Victor", "Whiskey",
    "X-ray", "Yankee", "Zulu",
)

# High-value procedure words and Q-codes. Kept deliberately small: the full
# curated set consumed Whisper's entire ~223-token initial_prompt budget,
# leaving no room for contact callsigns (~6 tokens each). See spec revision.
PROCEDURE: tuple[str, ...] = (
    "over", "out", "roger", "affirmative", "negative", "copy that",
    "say again", "standing by", "break break", "CQ", "QSL", "QSY", "QRZ",
    "seventy three",
)

CURATED: tuple[str, ...] = NATO + PROCEDURE


def assemble_phrases(callsigns, saved_phrases, *, max_callsigns) -> list[str]:
    """Build the ordered bias list, lowest priority first.

    Order: CURATED -> saved_phrases -> callsigns (callsigns last so they sit in
    the surviving tail of Whisper's initial_prompt). Callsigns over
    ``max_callsigns`` are trimmed from the FRONT (oldest), keeping the newest;
    the dropped count is logged. Case-insensitive dedup keeps the last
    (highest-priority) occurrence of any repeated term.
    """
    callsigns = list(callsigns or [])
    if len(callsigns) > max_callsigns:
        dropped = len(callsigns) - max_callsigns
        callsigns = callsigns[-max_callsigns:]
        _log.info("STT vocab: callsign list over cap, dropped %d oldest", dropped)

    ordered = list(CURATED) + list(saved_phrases or []) + callsigns

    seen: set[str] = set()
    deduped: list[str] = []
    for term in reversed(ordered):
        cleaned = (term or "").strip()
        key = cleaned.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
    deduped.reverse()
    return deduped
