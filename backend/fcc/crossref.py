"""FCC callsign verification via the ke8rxnwx crossref API.

Single network-touching helper; all UI verification flows funnel through
``verify_callsign``. ``VerificationResult.status`` is a small finite alphabet so
the caller can render distinct UX (green check, gray, red) without duck-typing
HTTP errors.

Status values:
  ``verified``       — callsign active in FCC database AND contact name matches.
  ``callsign_only``  — callsign in the database but name doesn't match, or the
                       license is inactive (cancelled/expired).
  ``not_found``      — callsign not in the database.
  ``offline``        — no network probe succeeded; we did not call the API.
  ``error``          — the API call failed for some other reason.
"""
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from backend.net.online import invalidate as _invalidate_online
from backend.net.online import is_online
from backend.persistence.contacts import normalize_callsign
from backend.text.nicknames import canonical_forms

API_BASE = "https://api.ke8rxnwx.net/crossref/"
REQUEST_TIMEOUT_SECONDS = 5.0

# FCC ULS service codes that we care about. ZA is GMRS; HA/HV are Amateur
# (standard + vanity). Anything else in `related` is ignored — the user only
# asked for the GMRS + HAM cross-references.
GMRS_SERVICE_CODES = {"ZA"}
HAM_SERVICE_CODES = {"HA", "HV"}


@dataclass
class VerificationResult:
    status: str  # see module docstring
    license_name: str = ""
    license_location: str = ""
    # Raw city pulled from the FCC primary record — kept separate from the
    # formatted `license_location` (which interleaves state) so callers that
    # want just the city can grab it without parsing the formatted string.
    license_city: str = ""
    license_active: bool = False
    gmrs_callsign: str = ""
    ham_callsign: str = ""
    raw: dict = field(default_factory=dict)


_TOKEN_RE = re.compile(r"[A-Za-z]+")


def _tokens(name):
    return _TOKEN_RE.findall((name or "").lower())


def name_matches(contact_name, license_name):
    """Return True iff any alphabetic token from `contact_name` corresponds
    to any alphabetic token in `license_name`.

    Two kinds of correspondence count:
      • **Prefix** — either token is a prefix of the other. Catches the
        common diminutives that are literally prefixes ("Tim"→"Timothy",
        "Ben"→"Benjamin", "Tom"→"Thomas") plus exact equality.
      • **Nickname canonicalization** — both tokens are expanded to their
        canonical legal-name forms (see ``text.nicknames``) and the
        resulting sets are intersected, then a final prefix check is run
        over every cross-pair so a canonical-vs-canonical comparison
        ("Richard" vs "Richardson") still matches via the prefix rule
        after expansion. This is what lets "Dick" verify against
        "Richard", "Bob" against "Robert", "Bill" against "William",
        and so on.

    Last-name tokens have no nickname mapping, so they pass straight
    through to the prefix check and behave exactly as before.
    """
    if not contact_name or not license_name:
        return False
    contact_tokens = _tokens(contact_name)
    license_tokens = _tokens(license_name)
    if not contact_tokens or not license_tokens:
        return False
    for ct in contact_tokens:
        ct_forms = canonical_forms(ct)
        for lt in license_tokens:
            lt_forms = canonical_forms(lt)
            if ct_forms & lt_forms:
                return True
            for cf in ct_forms:
                for lf in lt_forms:
                    if cf.startswith(lf) or lf.startswith(cf):
                        return True
    return False


def _format_location(primary):
    city = (primary.get("city") or "").strip()
    state = (primary.get("state") or "").strip()
    if city and state:
        return f"{city}, {state}"
    return city or state


def _first_active_callsign_for(related, service_codes):
    """Pull the first ACTIVE callsign from `related` whose FCC service code is
    in `service_codes`. Returns '' when no row qualifies. Order is preserved
    from the API response — the user can hand-edit `contacts.json` later if a
    licensee owns multiple HAM calls and they want a different one surfaced."""
    for row in related or []:
        if (row.get("status") or "").upper() != "A":
            continue
        if (row.get("service") or "").upper() in service_codes:
            cs = normalize_callsign(row.get("callsign", ""))
            if cs:
                return cs
    return ""


def verify_callsign(callsign, expected_name):
    """Look up `callsign` in the FCC crossref API and decide whether it should
    earn a verified badge for the given `expected_name`.

    Skips the HTTP call when ``is_online()`` is False so an offline laptop
    doesn't sit on a 5-second timeout per contact.
    """
    cs = normalize_callsign(callsign)
    if not cs:
        return VerificationResult(status="error")

    if not is_online():
        return VerificationResult(status="offline")

    url = API_BASE + urllib.parse.quote(cs, safe="")
    try:
        with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
            body = resp.read(1024 * 1024)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return VerificationResult(status="not_found")
        _invalidate_online()
        return VerificationResult(status="error")
    except (urllib.error.URLError, OSError, TimeoutError):
        # Connection problem — assume the previously cached 'online' verdict
        # is now stale so the next call gets to re-probe.
        _invalidate_online()
        return VerificationResult(status="error")

    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return VerificationResult(status="error")

    primary = payload.get("primary") or {}
    license_name = (primary.get("name") or "").strip()
    license_location = _format_location(primary)
    license_city = (primary.get("city") or "").strip()
    license_active = (primary.get("status") or "").upper() == "A"

    if not license_name:
        return VerificationResult(status="not_found", raw=payload)

    related = payload.get("related") or []
    gmrs_callsign = _first_active_callsign_for(related, GMRS_SERVICE_CODES)
    ham_callsign = _first_active_callsign_for(related, HAM_SERVICE_CODES)

    if license_active and name_matches(expected_name, license_name):
        status = "verified"
    else:
        status = "callsign_only"

    return VerificationResult(
        status=status,
        license_name=license_name,
        license_location=license_location,
        license_city=license_city,
        license_active=license_active,
        gmrs_callsign=gmrs_callsign,
        ham_callsign=ham_callsign,
        raw=payload,
    )


# Status values whose information we trust to overwrite cached verification on
# the contact dict. ``offline`` and ``error`` are deliberately omitted: a
# transient network blip shouldn't wipe a previously-earned green check.
_PERSISTABLE_STATUSES = {"verified", "callsign_only", "not_found"}


def apply_verification(contact, result, now_iso):
    """Return a new contact dict with verification metadata applied.

    The input is not mutated. Offline / error results pass through unchanged so
    the user's last known verification state survives a temporary outage.
    """
    if result.status not in _PERSISTABLE_STATUSES:
        return dict(contact)

    updated = dict(contact)
    updated["verified"] = (result.status == "verified")
    updated["verified_at"] = now_iso
    if result.license_name:
        updated["license_name"] = result.license_name
    if result.license_location:
        updated["license_location"] = result.license_location
    # GMRS / HAM cross-references describe the LICENSEE, not the row we're
    # updating. Only persist them when the contact's name actually matched
    # the licensee (status == 'verified') — otherwise a family-member row on
    # a shared GMRS callsign (e.g. spouse / kid using mom's WSLZ-call) would
    # silently inherit mom's HAM call as its own. License-holder identity is
    # already surfaced via license_name + the verified column tooltip; the
    # cross-reference columns are reserved for rows that own those calls.
    #
    # Also: only write when the lookup actually returned a value, so a
    # partial API response can't clobber a user's hand-edited entry.
    if result.status == "verified" and result.gmrs_callsign:
        updated["gmrs_callsign"] = result.gmrs_callsign
    if result.status == "verified" and result.ham_callsign:
        updated["ham_callsign"] = result.ham_callsign
    # Backfill the user-facing `location` field from the FCC city when the
    # contact is verified (so we trust the licensee identity) AND the user
    # left location blank. We never overwrite a value the user typed — their
    # label ("Home", "Cabin", "Mobile") is intentional. Title-cased because
    # ULS records are all-uppercase ("JENISON" → "Jenison") and that reads
    # noisier than necessary in the header / target dropdown.
    if (result.status == "verified"
            and result.license_city
            and not (contact.get("location") or "").strip()):
        updated["location"] = result.license_city.title()
    return updated
