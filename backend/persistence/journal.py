"""Session journal persistence — save and load JSON entries from journals_dir."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path


def save_journal(
    title: str,
    summary: str,
    callsigns_with_locations: list[dict],
    transcript: str,
    journals_dir: Path,
) -> str:
    """Write a journal entry to journals_dir and return its file path."""
    journals_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    filename = now.strftime("%Y%m%d_%H%M%S") + ".json"
    path = journals_dir / filename
    entry = {
        "exported_at": now.isoformat(timespec="seconds"),
        "title": title,
        "callsigns": [c.get("callsign", "") for c in callsigns_with_locations],
        "callsigns_locations": list(callsigns_with_locations),
        "transcript": transcript,
        "summary": summary,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(entry, fh, indent=2, ensure_ascii=False)
    return str(path)


def load_journals(journals_dir: Path) -> list[dict]:
    """Return all journal entries sorted newest-first.

    Each entry includes a ``_file`` key with the absolute path to its source
    file so callers can pass it to delete_journal.
    """
    if not journals_dir.is_dir():
        return []
    entries = []
    for name in sorted(os.listdir(journals_dir), reverse=True):
        if not name.endswith(".json"):
            continue
        path = journals_dir / name
        try:
            with open(path, encoding="utf-8") as fh:
                entry = json.load(fh)
            entry["_file"] = str(path)
            entries.append(entry)
        except (OSError, json.JSONDecodeError):
            continue
    return entries


def delete_journal(file_path: str, journals_dir: Path) -> None:
    """Delete the journal entry at file_path.

    Raises ValueError if file_path is outside journals_dir.
    """
    resolved_dir = journals_dir.resolve()
    target = Path(file_path).resolve()
    if not target.is_relative_to(resolved_dir):
        raise ValueError(f"Refusing to delete file outside journals directory: {file_path}")
    os.remove(target)
