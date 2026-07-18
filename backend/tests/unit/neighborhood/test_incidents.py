"""Unit tests for backend.neighborhood.incidents (pure validate/format)."""
from __future__ import annotations

import pytest

from backend.neighborhood.incidents import CATEGORIES, format_incident, validate_incident


def _payload(**overrides):
    base = {
        "category": "hazard",
        "description": "Tree down across the road",
        "location": "5th and Main",
    }
    base.update(overrides)
    return base


class TestValidateIncident:
    @pytest.mark.parametrize("category", sorted(CATEGORIES))
    def test_each_category_is_valid(self, category):
        assert validate_incident(_payload(category=category)) is None

    def test_unknown_category_rejected(self):
        err = validate_incident(_payload(category="not-a-category"))
        assert err is not None

    def test_missing_category_rejected(self):
        err = validate_incident(_payload(category=""))
        assert err is not None

    def test_empty_description_rejected(self):
        err = validate_incident(_payload(description=""))
        assert err is not None

    def test_whitespace_only_description_rejected(self):
        err = validate_incident(_payload(description="   "))
        assert err is not None

    def test_oversize_description_rejected(self):
        err = validate_incident(_payload(description="x" * 501))
        assert err is not None

    def test_description_at_max_length_ok(self):
        assert validate_incident(_payload(description="x" * 500)) is None

    def test_empty_location_rejected(self):
        err = validate_incident(_payload(location=""))
        assert err is not None

    def test_whitespace_only_location_rejected(self):
        err = validate_incident(_payload(location="   "))
        assert err is not None

    def test_oversize_location_rejected(self):
        err = validate_incident(_payload(location="x" * 201))
        assert err is not None

    def test_location_at_max_length_ok(self):
        assert validate_incident(_payload(location="x" * 200)) is None


class TestFormatIncident:
    def test_exact_phrase_assembly(self):
        text = format_incident(
            CATEGORIES["hazard"], "Tree down across the road", "5th and Main", "09:41", "W5TST",
        )
        assert text == (
            "NEIGHBORHOOD HAZARD. TREE DOWN ACROSS THE ROAD. "
            "LOCATION 5TH AND MAIN. TIME 09:41 LOCAL. W5TST."
        )

    def test_uses_supplied_category_label_and_uppercases_whole_phrase(self):
        text = format_incident(
            CATEGORIES["lost"], "brown dog, no collar", "Elm St park", "14:05", "w5abc",
        )
        assert text.startswith("NEIGHBORHOOD LOST PET OR PERSON. ")
        assert text == text.upper()
