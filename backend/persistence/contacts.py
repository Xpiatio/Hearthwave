"""Contact model, helpers, and ContactsStore.

Ported from GMRS-TTY. All Qt (QObject, signals, slots) removed.
ContactsStore owns the contacts.json file and performs atomic writes.
"""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Required, TypedDict

from backend.persistence._utils import atomic_json_write

_log = logging.getLogger(__name__)

# Contact-dict fields that hold a callsign. Order matters for tooltip rendering
# (GMRS line before HAM line) but not for indexing.
_CALLSIGN_FIELDS = ("callsign", "gmrs_callsign", "ham_callsign")

_DEFAULT_PATH = Path("/data/contacts.json")


class ContactDict(TypedDict, total=False):
    """Shape of a single contact record as stored in contacts.json.

    ``callsign`` is the only required key; all others are optional so that
    newly created contacts and legacy records without FCC data remain valid.
    Static analysis tools use this to catch key-name typos at check time.
    """
    callsign: Required[str]
    name: str
    location: str
    gmrs_callsign: str
    ham_callsign: str
    verified: bool
    verified_at: str   # ISO-8601 timestamp string
    fcc_name: str
    fcc_location: str


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------

def normalize_callsign(value) -> str:
    """Canonical form for any callsign value: strip whitespace, uppercase."""
    return (value or "").strip().upper()


def known_callsigns(contacts: list[ContactDict]) -> set[str]:
    """Return the set of UPPERCASED callsigns this contact list 'knows about',
    pulled from every populated callsign field (primary ``callsign``,
    ``gmrs_callsign``, ``ham_callsign``) across every contact. Skips the 'ALL'
    open-call shortcut and blank values."""
    known: set[str] = set()
    for c in contacts or []:
        for field in _CALLSIGN_FIELDS:
            cs = normalize_callsign(c.get(field, ""))
            if not cs or cs == "ALL":
                continue
            known.add(cs)
    return known


def index_contacts_by_callsign(contacts: list[ContactDict]) -> dict[str, list[ContactDict]]:
    """Return {UPPERCASED_CALLSIGN: [contact, …]} for use as a fast lookup.

    A single contact is indexed under each of its callsign fields so the
    display layer finds the contact whichever form a remote operator uses.
    Skips empty callsigns and the 'ALL' open-call shortcut. Preserves input
    order within each bucket. A contact is added to a bucket only once even
    when two of its fields resolve to the same value."""
    index: dict[str, list[ContactDict]] = {}
    for c in contacts or []:
        seen_keys: set[str] = set()
        for field in _CALLSIGN_FIELDS:
            cs = normalize_callsign(c.get(field, ""))
            if not cs or cs == "ALL" or cs in seen_keys:
                continue
            seen_keys.add(cs)
            index.setdefault(cs, []).append(c)
    return index


def format_callsign_tooltip(callsign: str, contacts: list[ContactDict]) -> str:
    """Render a multi-line tooltip body listing every entry that shares
    ``callsign``. Returns '' when no entries are supplied."""
    entries = list(contacts or [])
    if not entries:
        return ""
    lines = [normalize_callsign(callsign)]
    for c in entries:
        name = (c.get("name", "") or "").strip() or "(no name)"
        loc = (c.get("location", "") or "").strip()
        header = f"  • {name} — {loc}" if loc else f"  • {name}"
        lines.append(header)
        gmrs = normalize_callsign(c.get("gmrs_callsign", ""))
        ham = normalize_callsign(c.get("ham_callsign", ""))
        if gmrs:
            lines.append(f"      GMRS: {gmrs}")
        if ham:
            lines.append(f"      HAM: {ham}")
    return "\n".join(lines)


def deduplicate_ham_cross_references(contacts: list[ContactDict]) -> list[ContactDict]:
    """Drop HAM-side duplicates of an existing GMRS-primary contact row.

    A row ``B`` is treated as a duplicate of row ``A`` when:
      * ``A`` and ``B`` have the same operator name (case-insensitive, trimmed)
      * ``A.ham_callsign`` equals ``B.callsign`` (case-insensitive)
      * ``A.ham_callsign`` is *not* ``A.callsign`` (so ``A`` is the GMRS-primary)

    Returns a new list with the duplicates removed, preserving relative order
    of the survivors.
    """
    if not contacts:
        return list(contacts or [])

    canonical_owners: dict[tuple[str, str], ContactDict] = {}
    for c in contacts:
        name = normalize_callsign(c.get("name"))
        primary = normalize_callsign(c.get("callsign"))
        ham = normalize_callsign(c.get("ham_callsign"))
        if not name or not ham:
            continue
        if primary == ham:
            continue
        canonical_owners.setdefault((name, ham), c)

    survivors = []
    for c in contacts:
        name = normalize_callsign(c.get("name"))
        primary = normalize_callsign(c.get("callsign"))
        if name and primary:
            owner = canonical_owners.get((name, primary))
            if owner is not None and owner is not c:
                continue
        survivors.append(c)
    return survivors


def sort_contacts(contacts: list[ContactDict]) -> list[ContactDict]:
    """Return ``contacts`` sorted alphabetically by callsign (case-insensitive),
    with 'ALL' pinned at index 0 and ties broken by operator name."""
    def key(c: ContactDict):
        cs = normalize_callsign(c.get("callsign", ""))
        nm = (c.get("name", "") or "").upper()
        if cs == "ALL":
            return (0, "", "")
        return (1, cs, nm)

    return sorted(contacts, key=key)


def sort_contacts_by_suffix(contacts: list[ContactDict]) -> list[ContactDict]:
    """Return ``contacts`` sorted by the trailing digits of each callsign.
    'ALL' stays pinned at index 0; entries without trailing digits sort last."""
    def key(c: ContactDict):
        cs = normalize_callsign(c.get("callsign", ""))
        nm = (c.get("name", "") or "").upper()
        if cs == "ALL":
            return (0, "", "", "")
        m = re.search(r'(\d+)$', cs)
        if not m:
            return (2, cs, nm, "")
        last3 = m.group(1)[-3:].zfill(3)
        return (1, last3, cs, nm)

    return sorted(contacts, key=key)


# ---------------------------------------------------------------------------
# ContactsStore
# ---------------------------------------------------------------------------

class ContactsStore:
    """Thin persistence layer for contacts.json.

    Loads the file at construction time and keeps an in-memory list. Writes
    are atomic: data is written to a sibling tempfile then renamed over the
    target path so a crash mid-write never corrupts the file.

    No Qt. No threads. Callers are responsible for invoking from the correct
    execution context.
    """

    def __init__(self, path: Path = _DEFAULT_PATH) -> None:
        self._path = Path(path)
        self._contacts: list[dict] = self._load()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load(self) -> list[dict]:
        """Read and return the contacts list from disk, or [] on any error."""
        if not self._path.exists():
            return []
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list):
                return deduplicate_ham_cross_references(data)
            _log.warning("contacts.json did not contain a list; starting empty")
            return []
        except (json.JSONDecodeError, OSError) as exc:
            _log.warning("Could not load %s: %s; starting empty", self._path, exc)
            return []

    def _save(self) -> None:
        """Atomically overwrite the contacts file with the current in-memory list."""
        atomic_json_write(self._path, self._contacts)

    def _dedup(self) -> None:
        """Remove duplicate entries by primary callsign, keeping the last-written."""
        seen: dict[str, int] = {}
        for i, c in enumerate(self._contacts):
            cs = normalize_callsign(c.get("callsign", ""))
            if cs:
                seen[cs] = i
        survivors = []
        for i, c in enumerate(self._contacts):
            cs = normalize_callsign(c.get("callsign", ""))
            if not cs or seen.get(cs) == i:
                survivors.append(c)
        self._contacts = survivors

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_all(self) -> list[dict]:
        """Return the in-memory contact list (no disk re-read)."""
        return list(self._contacts)

    def add_contact(self, contact: dict) -> list[dict]:
        """Append ``contact``, deduplicate by callsign, persist atomically.

        If a contact with the same callsign already exists it is replaced by
        the incoming entry (last-write wins, consistent with GMRS-TTY behaviour).
        Returns the updated list.
        """
        if not contact.get("callsign"):
            raise ValueError("contact must have a non-empty 'callsign' field")
        contact = dict(contact)
        contact["callsign"] = normalize_callsign(contact["callsign"])
        self._contacts.append(contact)
        self._dedup()
        self._save()
        return list(self._contacts)

    def update_contact(self, callsign: str, updates: dict) -> list[dict]:
        """Merge ``updates`` into the contact identified by ``callsign``.

        Raises ``KeyError`` if no contact with that callsign exists.
        Persists atomically. Returns the updated list.
        """
        cs = normalize_callsign(callsign)
        for i, c in enumerate(self._contacts):
            if normalize_callsign(c.get("callsign", "")) == cs:
                merged = dict(c)
                merged.update(updates)
                # Re-normalise callsign in case caller passed an update for it.
                merged["callsign"] = normalize_callsign(merged.get("callsign", cs))
                self._contacts[i] = merged
                self._save()
                return list(self._contacts)
        raise KeyError(f"No contact with callsign {cs!r}")

    def delete_contact(self, callsign: str) -> list[dict]:
        """Remove the contact identified by *callsign*.

        Raises ``KeyError`` if no matching contact exists.
        Persists atomically. Returns the updated list.
        """
        cs = normalize_callsign(callsign)
        before = len(self._contacts)
        self._contacts = [
            c for c in self._contacts
            if normalize_callsign(c.get("callsign", "")) != cs
        ]
        if len(self._contacts) == before:
            raise KeyError(f"No contact with callsign {cs!r}")
        self._save()
        return list(self._contacts)
