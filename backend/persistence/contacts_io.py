"""Import / export helpers for contacts (JSON and CSV).

Ported from GMRS-TTY. Qt file dialogs removed — all functions accept plain
file-path strings or Path objects. No GUI dependencies.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from backend.persistence.contacts import ContactDict, normalize_callsign

_CSV_FIELDS = ("callsign", "name", "location", "gmrs_callsign", "ham_callsign")


def export_contacts_json(contacts: list[ContactDict], path: str | Path) -> None:
    """Write ``contacts`` to ``path`` as pretty-printed JSON."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(contacts, fh, indent=4, ensure_ascii=False)


def export_contacts_csv(contacts: list[ContactDict], path: str | Path) -> None:
    """Write ``contacts`` to ``path`` as CSV (standard fields only)."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for contact in contacts:
            writer.writerow({f: contact.get(f, "") for f in _CSV_FIELDS})


def import_contacts_json(path: str | Path) -> list[ContactDict]:
    """Load contacts from a JSON file.

    Raises ``ValueError`` if the file does not contain a top-level list.
    Skips entries that are not dicts or lack a ``callsign`` key.
    """
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError("JSON file must contain a list of contacts")
    result: list[ContactDict] = []
    for c in data:
        if not isinstance(c, dict) or not c.get("callsign"):
            continue
        c = dict(c)
        c["callsign"] = normalize_callsign(c["callsign"])
        result.append(c)
    return result


def import_contacts_csv(path: str | Path) -> list[ContactDict]:
    """Load contacts from a CSV file.

    Skips rows with an empty or missing ``callsign`` column.
    """
    contacts: list[ContactDict] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            cs = normalize_callsign(row.get("callsign", ""))
            if not cs:
                continue
            contact: ContactDict = {"callsign": cs}
            for field in ("name", "location", "gmrs_callsign", "ham_callsign"):
                val = (row.get(field) or "").strip()
                if val:
                    contact[field] = val  # type: ignore[literal-required]
            contacts.append(contact)
    return contacts


def merge_contacts(
    existing: list[ContactDict], incoming: list[ContactDict]
) -> list[ContactDict]:
    """Merge ``incoming`` into ``existing``, keyed by (uppercase callsign, lowercased name).

    When a key matches, non-empty fields from ``incoming`` overwrite the existing
    entry; metadata absent from ``incoming`` (e.g. verified/verified_at on a CSV
    import) is left untouched. New keys are appended after existing entries.
    """
    by_key: dict[tuple[str, str], ContactDict] = {}
    key_order: list[tuple[str, str]] = []

    for c in existing:
        key = _contact_key(c)
        if key not in by_key:
            key_order.append(key)
            by_key[key] = dict(c)  # type: ignore[arg-type]

    for contact in incoming:
        cs = normalize_callsign(contact.get("callsign", ""))
        if not cs:
            continue
        key = _contact_key(contact)
        if key in by_key:
            for k, v in contact.items():
                if v is not None and v != "":
                    by_key[key][k] = v  # type: ignore[literal-required]
        else:
            key_order.append(key)
            by_key[key] = dict(contact)  # type: ignore[arg-type]

    return [by_key[k] for k in key_order]


def _contact_key(c: ContactDict) -> tuple[str, str]:
    return (
        normalize_callsign(c.get("callsign", "")),
        (c.get("name") or "").strip().lower(),
    )
