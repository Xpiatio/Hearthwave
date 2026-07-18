"""Pure validation/formatting for neighborhood incident reports.

Mirrors the SKYWARN spot-report idiom (``plugins/ncs.py``):
``validate_*`` returns an error string or ``None``, ``format_*`` assembles
the standardized on-air/chat phrase and uppercases the whole thing for radio
clarity. No I/O, no server state — kept pure so it's cheap to unit test.
"""
from __future__ import annotations

_DESCRIPTION_MAX = 500
_LOCATION_MAX = 200

CATEGORIES = {
    "suspicious": "Suspicious activity",
    "hazard": "Hazard",
    "medical": "Medical",
    "lost": "Lost pet or person",
    "utility": "Utility outage",
}


def validate_incident(payload: dict) -> str | None:
    """Return an error string if the incident report is invalid, else None."""
    category = payload.get("category")
    if category not in CATEGORIES:
        return "Unknown incident category."

    description = (payload.get("description") or "").strip()
    if not description:
        return "Description is required."
    if len(description) > _DESCRIPTION_MAX:
        return f"Description must be {_DESCRIPTION_MAX} characters or fewer."

    location = (payload.get("location") or "").strip()
    if not location:
        return "Location is required."
    if len(location) > _LOCATION_MAX:
        return f"Location must be {_LOCATION_MAX} characters or fewer."

    return None


def format_incident(
    category_label: str, description: str, location: str, hhmm_local: str, callsign: str,
) -> str:
    """Assemble the standardized on-air/chat incident phrase, uppercased."""
    text = (
        f"NEIGHBORHOOD {category_label}. {description}. "
        f"LOCATION {location}. TIME {hhmm_local} LOCAL. {callsign}."
    )
    return text.upper()
