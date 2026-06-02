"""Minimal Google Gemini REST client using only stdlib."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
_MODEL = "gemini-3.5-flash"

_PROMPT_TEMPLATE = """You are a radio communication session assistant. \
Based on the following radio session transcript and detected callsigns, \
generate a session journal entry.

Session Date/Time: {timestamp}
Callsigns Detected: {callsigns}

Session Transcript:
{transcript}

Respond ONLY with a JSON object (no markdown fences) containing:
- "title": a concise session title, 10 words or fewer
- "callsigns_locations": an array of objects, one per detected callsign, each with \
"callsign" (the identifier) and "location" (the location the operator stated in the \
transcript, or "Not stated" if no location was mentioned)
- "summary": a detailed narrative summary of the conversations and activities, 3-5 paragraphs
"""


class GeminiError(Exception):
    pass


def generate_journal(
    api_key: str,
    transcript: str,
    callsigns: list[str],
    timestamp: str,
) -> dict:
    """Call Gemini and return a dict with keys title, summary, and callsigns_locations."""
    callsign_str = ", ".join(callsigns) if callsigns else "None detected"
    prompt = _PROMPT_TEMPLATE.format(
        timestamp=timestamp,
        callsigns=callsign_str,
        transcript=transcript,
    )
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }).encode()
    url = f"{_BASE_URL}/{_MODEL}:generateContent"
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read(1024 * 1024))
    except urllib.error.HTTPError as exc:
        detail = exc.read(1024 * 1024).decode(errors="replace")
        raise GeminiError(f"HTTP {exc.code}: {detail}") from exc
    except Exception as exc:
        raise GeminiError(str(exc)) from exc

    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        result = json.loads(text)
        if "title" not in result or "summary" not in result or "callsigns_locations" not in result:
            raise ValueError("missing required keys")
        if not isinstance(result["callsigns_locations"], list):
            raise ValueError("callsigns_locations must be an array")
        return result
    except (KeyError, IndexError, json.JSONDecodeError, ValueError) as exc:
        raise GeminiError(f"Unexpected Gemini response format: {exc}") from exc
