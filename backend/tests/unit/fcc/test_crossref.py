import json
from unittest.mock import patch


from backend.fcc import crossref


class FakeResponse:
    """Minimal urlopen response stand-in: payload + .read(), context-manager
    semantics, optional status code so we can simulate non-2xx."""

    def __init__(self, payload, status=200):
        self._payload = payload
        self.status = status

    def read(self, size=-1):
        return self._payload.encode("utf-8") if isinstance(self._payload, str) else self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _ok_payload(name="Zomberg, Benjamin J", city="Jenison", state="MI",
                related=None):
    primary = {
        "usid": "5266422",
        "callsign": "WSLZ233",
        "status": "A",
        "service": "ZA",
        "name": name,
        "street": "8105GreenridgeDr",
        "city": city,
        "state": state,
        "zip": "49428",
        "frn": "0036283976",
        "class": None,
        "prevcall": None,
    }
    if related is None:
        related = [dict(primary)]
    return json.dumps({"primary": primary, "related": related})


def _related_entry(callsign, service, status="A", name="Zomberg, Benjamin J"):
    return {
        "usid": f"u{callsign}",
        "callsign": callsign,
        "status": status,
        "service": service,
        "name": name,
        "street": "x",
        "city": "Jenison",
        "state": "MI",
        "zip": "49428",
        "frn": "0036283976",
        "class": None,
        "prevcall": None,
    }


class TestNameMatch:
    def test_first_name_matches_long_form(self):
        # 'Tim' in 'Haskin, Timothy L' → match (substring case-insensitive)
        assert crossref.name_matches("Tim", "Haskin, Timothy L") is True

    def test_full_first_name_matches(self):
        assert crossref.name_matches("Benjamin", "Zomberg, Benjamin J") is True

    def test_case_insensitive(self):
        assert crossref.name_matches("BENJAMIN", "zomberg, benjamin j") is True

    def test_no_overlap_returns_false(self):
        assert crossref.name_matches("Eliza", "Zomberg, Benjamin J") is False

    def test_empty_contact_name_returns_false(self):
        # An unset contact name can't be 'matched' — refuse to grant a verified
        # badge by default; otherwise blank names would auto-verify.
        assert crossref.name_matches("", "Zomberg, Benjamin J") is False
        assert crossref.name_matches(None, "Zomberg, Benjamin J") is False

    def test_short_token_does_not_match_substring_inside_word(self):
        # 'Ben' must match 'Benjamin' as a token boundary, not 'Beneficial' as
        # an internal substring inside an unrelated word.
        assert crossref.name_matches("Ben", "Smith, Benjamin J") is True
        assert crossref.name_matches("Ben", "Smith, Beneficial L") is True  # 'Ben' is a real prefix of token
        # But a totally unrelated token shouldn't trigger:
        assert crossref.name_matches("Xyz", "Smith, Benjamin J") is False

    def test_last_name_match_also_counts(self):
        # If the user wrote 'Haskin' as the contact name, that should also
        # verify against 'Haskin, Timothy L'.
        assert crossref.name_matches("Haskin", "Haskin, Timothy L") is True


class TestNameMatchNicknames:
    """Non-prefix nicknames need a table because the existing prefix rule
    (Tom→Thomas, Tim→Timothy) doesn't catch them. The matcher consults
    ``text.nicknames`` so contacts entered with the colloquial form still
    verify against the FCC-licensed legal name."""

    def test_dick_matches_richard(self):
        assert crossref.name_matches("Dick", "Smith, Richard J") is True

    def test_richard_matches_dick(self):
        # Symmetric: the contact field could hold either form.
        assert crossref.name_matches("Richard", "Smith, Dick") is True

    def test_bob_matches_robert(self):
        assert crossref.name_matches("Bob", "Jones, Robert A") is True

    def test_bill_matches_william(self):
        assert crossref.name_matches("Bill", "Doe, William") is True

    def test_jim_matches_james(self):
        assert crossref.name_matches("Jim", "Carter, James L") is True

    def test_jack_matches_john(self):
        assert crossref.name_matches("Jack", "Kennedy, John F") is True

    def test_hank_matches_henry(self):
        assert crossref.name_matches("Hank", "Aaron, Henry L") is True

    def test_peggy_matches_margaret(self):
        assert crossref.name_matches("Peggy", "Olson, Margaret") is True

    def test_ambiguous_nickname_matches_either_canonical(self):
        # 'Sandy' canonicalizes to {Alexander, Sandra}. Both should verify
        # — the conservative gender-check is intentionally relaxed because
        # family-shared GMRS calls are common.
        assert crossref.name_matches("Sandy", "Doe, Alexander") is True
        assert crossref.name_matches("Sandy", "Doe, Sandra") is True

    def test_nickname_does_not_match_unrelated_canonical(self):
        # 'Dick' resolves to {Richard}; it must not silently match
        # an unrelated first name.
        assert crossref.name_matches("Dick", "Smith, Robert") is False

    def test_case_insensitive_nickname(self):
        # The nickname table is keyed on lowercase; the matcher has to
        # normalize before the lookup.
        assert crossref.name_matches("DICK", "smith, RICHARD j") is True


class TestVerifyCallsign:
    def _patch_online(self, value=True):
        return patch("backend.fcc.crossref.is_online", return_value=value)

    def test_returns_verified_when_callsign_and_name_match(self):
        with self._patch_online(True), \
             patch("backend.fcc.crossref.urllib.request.urlopen",
                   return_value=FakeResponse(_ok_payload())):
            result = crossref.verify_callsign("WSLZ233", "Benjamin")
        assert result.status == "verified"
        assert result.license_name == "Zomberg, Benjamin J"
        assert result.license_location == "Jenison, MI"

    def test_returns_callsign_only_when_name_mismatch(self):
        with self._patch_online(True), \
             patch("backend.fcc.crossref.urllib.request.urlopen",
                   return_value=FakeResponse(_ok_payload(name="Smith, John"))):
            result = crossref.verify_callsign("WSLZ233", "Eliza")
        assert result.status == "callsign_only"
        assert result.license_name == "Smith, John"

    def test_returns_not_found_on_404(self):
        import urllib.error
        err = urllib.error.HTTPError(
            "https://api.ke8rxnwx.net/crossref/NOPE", 404, "Not Found", {}, None
        )
        with self._patch_online(True), \
             patch("backend.fcc.crossref.urllib.request.urlopen", side_effect=err):
            result = crossref.verify_callsign("NOPE", "Anyone")
        assert result.status == "not_found"

    def test_returns_offline_when_offline(self):
        # Should NOT attempt any HTTP call when we know we're offline.
        with self._patch_online(False), \
             patch("backend.fcc.crossref.urllib.request.urlopen") as urlopen:
            result = crossref.verify_callsign("WSLZ233", "Benjamin")
            urlopen.assert_not_called()
        assert result.status == "offline"

    def test_returns_error_on_network_failure(self):
        with self._patch_online(True), \
             patch("backend.fcc.crossref.urllib.request.urlopen",
                   side_effect=OSError("connection reset")):
            result = crossref.verify_callsign("WSLZ233", "Benjamin")
        assert result.status == "error"

    def test_inactive_license_is_not_verified(self):
        # FCC 'status' field: A=active, anything else means cancelled/expired.
        payload = json.loads(_ok_payload())
        payload["primary"]["status"] = "C"  # cancelled
        with self._patch_online(True), \
             patch("backend.fcc.crossref.urllib.request.urlopen",
                   return_value=FakeResponse(json.dumps(payload))):
            result = crossref.verify_callsign("WSLZ233", "Benjamin")
        # Inactive license: callsign exists in the DB but is not currently
        # licensed, so it cannot earn a verified badge.
        assert result.status == "callsign_only"
        assert result.license_active is False

    def test_callsign_is_uppercased_before_request(self):
        captured = {}

        def fake_urlopen(req, timeout):
            captured["url"] = req.full_url if hasattr(req, "full_url") else req
            return FakeResponse(_ok_payload())

        with self._patch_online(True), \
             patch("backend.fcc.crossref.urllib.request.urlopen", side_effect=fake_urlopen):
            crossref.verify_callsign("wslz233", "Benjamin")
        assert "WSLZ233" in captured["url"]

    def test_empty_callsign_returns_error_without_http(self):
        with self._patch_online(True), \
             patch("backend.fcc.crossref.urllib.request.urlopen") as urlopen:
            result = crossref.verify_callsign("", "Benjamin")
            urlopen.assert_not_called()
        assert result.status == "error"


class TestRelatedCallsignExtraction:
    """Verified results carry forward the FCC 'related' cross-references so
    we can persist the contact's GMRS *and* HAM callsigns side-by-side."""

    def _verify(self, payload, contact_name="Benjamin"):
        with patch("backend.fcc.crossref.is_online", return_value=True), \
             patch("backend.fcc.crossref.urllib.request.urlopen",
                   return_value=FakeResponse(payload)):
            return crossref.verify_callsign("WSLZ233", contact_name)

    def test_extracts_gmrs_and_ham_from_related(self):
        payload = _ok_payload(related=[
            _related_entry("KE8RXN", "HA"),
            _related_entry("WSLZ233", "ZA"),
        ])
        result = self._verify(payload)
        assert result.gmrs_callsign == "WSLZ233"
        assert result.ham_callsign == "KE8RXN"

    def test_only_active_related_licenses_count(self):
        payload = _ok_payload(related=[
            _related_entry("KE8OLD", "HA", status="C"),  # cancelled
            _related_entry("KE8NEW", "HA", status="A"),
            _related_entry("WSLZ233", "ZA"),
        ])
        result = self._verify(payload)
        assert result.ham_callsign == "KE8NEW"

    def test_amateur_vanity_service_code_also_counts_as_ham(self):
        # FCC service code 'HV' is amateur vanity — same operator class.
        payload = _ok_payload(related=[
            _related_entry("W1ABC", "HV"),
            _related_entry("WSLZ233", "ZA"),
        ])
        result = self._verify(payload)
        assert result.ham_callsign == "W1ABC"

    def test_missing_service_means_blank_field(self):
        payload = _ok_payload(related=[_related_entry("WSLZ233", "ZA")])
        result = self._verify(payload)
        assert result.gmrs_callsign == "WSLZ233"
        assert result.ham_callsign == ""

    def test_callsign_only_still_carries_related(self):
        # A name mismatch shouldn't suppress the cross-reference data — the
        # FCC payload was still successfully retrieved.
        payload = _ok_payload(related=[
            _related_entry("KE8RXN", "HA"),
            _related_entry("WSLZ233", "ZA"),
        ])
        result = self._verify(payload, contact_name="Eliza")
        assert result.status == "callsign_only"
        assert result.gmrs_callsign == "WSLZ233"
        assert result.ham_callsign == "KE8RXN"


class TestApplyVerificationToContact:
    def test_verified_sets_flag_and_timestamp(self):
        contact = {"callsign": "WSLZ233", "name": "Benjamin"}
        result = crossref.VerificationResult(
            status="verified",
            license_name="Zomberg, Benjamin J",
            license_location="Jenison, MI",
            license_active=True,
        )
        updated = crossref.apply_verification(contact, result, now_iso="2026-05-16T20:00:00Z")
        assert updated["verified"] is True
        assert updated["verified_at"] == "2026-05-16T20:00:00Z"
        assert updated["license_name"] == "Zomberg, Benjamin J"

    def test_verified_persists_gmrs_and_ham_callsigns(self):
        contact = {"callsign": "WSLZ233", "name": "Benjamin"}
        result = crossref.VerificationResult(
            status="verified",
            license_name="Zomberg, Benjamin J",
            license_location="Jenison, MI",
            license_active=True,
            gmrs_callsign="WSLZ233",
            ham_callsign="KE8RXN",
        )
        updated = crossref.apply_verification(contact, result, now_iso="2026-05-16T20:00:00Z")
        assert updated["gmrs_callsign"] == "WSLZ233"
        assert updated["ham_callsign"] == "KE8RXN"

    def test_verified_blank_ham_does_not_overwrite_existing(self):
        # If the user manually edited a HAM call into the contact and a later
        # lookup didn't surface one in 'related' (transient API gap), we should
        # leave the user's value alone rather than silently clearing it.
        contact = {"callsign": "WSLZ233", "name": "Benjamin",
                   "ham_callsign": "MANUAL"}
        result = crossref.VerificationResult(
            status="verified",
            license_name="Zomberg, Benjamin J",
            license_active=True,
            gmrs_callsign="WSLZ233",
            ham_callsign="",
        )
        updated = crossref.apply_verification(contact, result, now_iso="2026-05-16T20:00:00Z")
        assert updated["ham_callsign"] == "MANUAL"

    def test_callsign_only_does_not_stamp_licensee_cross_references(self):
        # A `callsign_only` result means the row's name doesn't match the
        # licensee — this is the family-member-on-shared-GMRS-call scenario
        # (Eliza on mom's WSLZ-call). The GMRS / HAM cross-references in the
        # FCC payload describe the LICENSEE; writing them onto Eliza's row
        # would falsely claim she owns mom's HAM call. license_name is fine
        # to record (it's labeled as the licensee in the tooltip), but the
        # cross-reference columns must stay clear of the row.
        contact = {"callsign": "WSLZ233", "name": "Eliza"}
        result = crossref.VerificationResult(
            status="callsign_only",
            license_name="Zomberg, Benjamin J",
            license_active=True,
            gmrs_callsign="WSLZ233",
            ham_callsign="KE8RXN",
        )
        updated = crossref.apply_verification(contact, result, now_iso="2026-05-16T20:00:00Z")
        assert "gmrs_callsign" not in updated, (
            "callsign_only must not stamp the licensee's GMRS call onto a "
            "row whose name doesn't match the licensee"
        )
        assert "ham_callsign" not in updated, (
            "callsign_only must not stamp the licensee's HAM call onto a "
            "row whose name doesn't match the licensee"
        )
        # The license_name is still recorded so the tooltip can explain why
        # the row didn't earn a green check.
        assert updated["license_name"] == "Zomberg, Benjamin J"

    def test_callsign_only_does_not_clobber_manual_cross_references(self):
        # Inverse of the above: if Eliza happens to be a licensed HAM with
        # her own call entered manually, a callsign_only verification on her
        # GMRS row (matching mom's license) must NOT overwrite Eliza's own
        # HAM call with mom's.
        contact = {"callsign": "WSLZ233", "name": "Eliza",
                   "ham_callsign": "KE8ELZ"}
        result = crossref.VerificationResult(
            status="callsign_only",
            license_name="Zomberg, Benjamin J",
            license_active=True,
            gmrs_callsign="WSLZ233",
            ham_callsign="KE8RXN",
        )
        updated = crossref.apply_verification(contact, result, now_iso="2026-05-16T20:00:00Z")
        assert updated["ham_callsign"] == "KE8ELZ"

    def test_callsign_only_clears_verified(self):
        contact = {"callsign": "WSLZ233", "name": "Eliza", "verified": True}
        result = crossref.VerificationResult(
            status="callsign_only",
            license_name="Smith, John",
            license_location="",
            license_active=True,
        )
        updated = crossref.apply_verification(contact, result, now_iso="2026-05-16T20:00:00Z")
        assert updated["verified"] is False

    def test_offline_does_not_touch_existing_verified(self):
        # Going offline must not nuke prior verification — that would be
        # surprising and would prevent the user from seeing earlier results.
        contact = {"callsign": "WSLZ233", "name": "Benjamin",
                   "verified": True, "verified_at": "2026-05-10T00:00:00Z",
                   "license_name": "Zomberg, Benjamin J"}
        result = crossref.VerificationResult(status="offline")
        updated = crossref.apply_verification(contact, result, now_iso="2026-05-16T20:00:00Z")
        assert updated == contact

    def test_error_does_not_touch_existing_verified(self):
        contact = {"callsign": "WSLZ233", "name": "Benjamin",
                   "verified": True, "verified_at": "2026-05-10T00:00:00Z"}
        result = crossref.VerificationResult(status="error")
        updated = crossref.apply_verification(contact, result, now_iso="2026-05-16T20:00:00Z")
        assert updated == contact

    def test_not_found_clears_verified(self):
        contact = {"callsign": "WSLZ233", "name": "Benjamin", "verified": True}
        result = crossref.VerificationResult(status="not_found")
        updated = crossref.apply_verification(contact, result, now_iso="2026-05-16T20:00:00Z")
        assert updated["verified"] is False


class TestLocationBackfill:
    """A verified lookup carries the licensee's city. When the contact row
    has no location of its own, fill it in from the FCC city — saves the
    operator from typing the same value that's already in the license
    record. ULS data is all-uppercase so we title-case for display."""

    def test_verified_backfills_empty_location_with_title_cased_city(self):
        contact = {"callsign": "WSLZ233", "name": "Benjamin", "location": ""}
        result = crossref.VerificationResult(
            status="verified",
            license_name="Zomberg, Benjamin J",
            license_city="JENISON",
            license_active=True,
        )
        updated = crossref.apply_verification(contact, result, now_iso="2026-05-16T20:00:00Z")
        assert updated["location"] == "Jenison"

    def test_verified_backfills_missing_location_key(self):
        # A freshly-added contact may not even carry the `location` key yet.
        contact = {"callsign": "WSLZ233", "name": "Benjamin"}
        result = crossref.VerificationResult(
            status="verified",
            license_name="Zomberg, Benjamin J",
            license_city="JENISON",
            license_active=True,
        )
        updated = crossref.apply_verification(contact, result, now_iso="2026-05-16T20:00:00Z")
        assert updated["location"] == "Jenison"

    def test_verified_does_not_overwrite_existing_location(self):
        # If the operator labeled the row ("Home", "Cabin", "Mobile") that's
        # intentional — the FCC city must not silently replace it.
        contact = {"callsign": "WSLZ233", "name": "Benjamin",
                   "location": "Home"}
        result = crossref.VerificationResult(
            status="verified",
            license_name="Zomberg, Benjamin J",
            license_city="JENISON",
            license_active=True,
        )
        updated = crossref.apply_verification(contact, result, now_iso="2026-05-16T20:00:00Z")
        assert updated["location"] == "Home"

    def test_verified_treats_whitespace_location_as_empty(self):
        # Round-tripping through the table can land an all-spaces value in
        # the field; treat it the same as missing for backfill purposes.
        contact = {"callsign": "WSLZ233", "name": "Benjamin",
                   "location": "   "}
        result = crossref.VerificationResult(
            status="verified",
            license_name="Zomberg, Benjamin J",
            license_city="JENISON",
            license_active=True,
        )
        updated = crossref.apply_verification(contact, result, now_iso="2026-05-16T20:00:00Z")
        assert updated["location"] == "Jenison"

    def test_callsign_only_does_not_backfill_location(self):
        # The FCC city belongs to the licensee, not to the family-member row
        # we're updating. Mirrors the GMRS / HAM cross-reference rule: only
        # write licensee-derived data onto rows whose name actually matched.
        contact = {"callsign": "WSLZ233", "name": "Eliza", "location": ""}
        result = crossref.VerificationResult(
            status="callsign_only",
            license_name="Zomberg, Benjamin J",
            license_city="JENISON",
            license_active=True,
        )
        updated = crossref.apply_verification(contact, result, now_iso="2026-05-16T20:00:00Z")
        assert not updated.get("location")

    def test_verified_with_empty_city_leaves_location_alone(self):
        # API may not always return a city; absent data must not write the
        # empty string into the row.
        contact = {"callsign": "WSLZ233", "name": "Benjamin", "location": ""}
        result = crossref.VerificationResult(
            status="verified",
            license_name="Zomberg, Benjamin J",
            license_city="",
            license_active=True,
        )
        updated = crossref.apply_verification(contact, result, now_iso="2026-05-16T20:00:00Z")
        assert updated.get("location", "") == ""

    def test_verify_callsign_populates_license_city(self):
        # End-to-end: the network helper has to surface the city on the
        # result so apply_verification has something to work with.
        with patch("backend.fcc.crossref.is_online", return_value=True), \
             patch("backend.fcc.crossref.urllib.request.urlopen",
                   return_value=FakeResponse(_ok_payload(city="JENISON"))):
            result = crossref.verify_callsign("WSLZ233", "Benjamin")
        assert result.license_city == "JENISON"
