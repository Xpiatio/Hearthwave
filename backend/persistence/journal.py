"""Session journal persistence — save and load JSON entries from journals_dir."""
from __future__ import annotations

import html
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from backend.persistence._utils import atomic_json_write, atomic_text_write

_MAX_PUBLISHED = 10


def save_journal(
    title: str,
    summary: str,
    callsigns_with_locations: list[dict],
    transcript: str,
    journals_dir: Path,
) -> str:
    """Write a journal entry to journals_dir and return its file path."""
    journals_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    filename = now.strftime("%Y%m%d_%H%M%S") + ".json"
    path = journals_dir / filename
    entry = {
        "exported_at": now.isoformat(timespec="seconds"),
        "title": title,
        "callsigns_locations": list(callsigns_with_locations),
        "transcript": transcript,
        "summary": summary,
    }
    atomic_json_write(path, entry)
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


# ---------------------------------------------------------------------------
# Public journal publishing
# ---------------------------------------------------------------------------

def _public_dir(journals_dir: Path) -> Path:
    """Return the public output directory adjacent to journals_dir."""
    return Path(journals_dir).parent / "public"




def load_published_manifest(journals_dir: Path) -> list[dict]:
    """Return the list of published journal entries (newest first), or []."""
    manifest_path = _public_dir(journals_dir) / "journal-manifest.json"
    if not manifest_path.exists():
        return []
    try:
        with open(manifest_path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def publish_journal(file_path: str, published_by: str, journals_dir: Path) -> dict:
    """Publish a journal entry to the public static page.

    Validates file_path is inside journals_dir, reads the entry, prepends it
    to the manifest (capped at _MAX_PUBLISHED), regenerates journal.html, and
    returns the new manifest entry dict.

    Raises ValueError on path traversal or missing file.
    """
    resolved_dir = journals_dir.resolve()
    target = Path(file_path).resolve()
    if not target.is_relative_to(resolved_dir):
        raise ValueError(f"Refusing to publish file outside journals directory: {file_path}")
    if not target.exists():
        raise ValueError(f"Journal file not found: {file_path}")

    with open(target, encoding="utf-8") as fh:
        source = json.load(fh)

    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entry = {
        "published_at": now_iso,
        "published_by": published_by,
        "title": source.get("title") or "(untitled)",
        "summary": source.get("summary") or "",
        "callsigns_locations": source.get("callsigns_locations") or [],
        "exported_at": source.get("exported_at") or "",
        "source_file": target.name,
    }

    manifest = load_published_manifest(journals_dir)
    manifest.insert(0, entry)
    manifest = manifest[:_MAX_PUBLISHED]

    pub_dir = _public_dir(journals_dir)
    atomic_json_write(pub_dir / "journal-manifest.json", manifest)
    atomic_text_write(pub_dir / "journal.html", _render_public_html(manifest))

    return entry


def _fmt_date(iso: str) -> str:
    """Format an ISO timestamp as a readable date string, gracefully."""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        # Use str(dt.day) to avoid the Linux-only %-d format specifier.
        return dt.strftime("%B ") + str(dt.day) + dt.strftime(", %Y")
    except (ValueError, TypeError, AttributeError):
        return iso[:10] if len(iso) >= 10 else iso


def _render_public_html(entries: list[dict]) -> str:
    """Generate a complete ADA-compliant HTML5 page from published entries."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    articles = ""
    if not entries:
        articles = '    <p>No journals have been published yet.</p>\n'
    else:
        for entry in entries:
            title = html.escape(entry.get("title") or "(untitled)")
            # Escape first, then convert newlines to <br> so AI-generated line
            # breaks render correctly without relying on CSS white-space.
            summary = html.escape(entry.get("summary") or "").replace("\n", "<br>")
            published_at = entry.get("published_at") or ""
            published_by = html.escape(entry.get("published_by") or "")
            exported_at = entry.get("exported_at") or ""
            cl_rows = entry.get("callsigns_locations") or []

            pub_date_display = _fmt_date(published_at)
            session_date_display = _fmt_date(exported_at)

            table_rows = ""
            for cl in cl_rows:
                cs = html.escape(str(cl.get("callsign") or ""))
                loc = html.escape(str(cl.get("location") or ""))
                table_rows += f"            <tr><td>{cs}</td><td>{loc}</td></tr>\n"

            stations_section = ""
            if cl_rows:
                stations_section = f"""\
      <section aria-label="Stations on the Air">
        <h3>Stations on the Air</h3>
        <table>
          <caption>Callsigns and locations heard during this session</caption>
          <thead>
            <tr>
              <th scope="col">Call Sign</th>
              <th scope="col">Location</th>
            </tr>
          </thead>
          <tbody>
{table_rows}\
          </tbody>
        </table>
      </section>
"""

            summary_section = ""
            if summary:
                summary_section = f"""\
      <section aria-label="Summary">
        <h3>Summary</h3>
        <p>{summary}</p>
      </section>
"""

            articles += f"""\
    <article aria-label="{title}">
      <header>
        <h2>{title}</h2>
        <p class="meta">
          Session: <time datetime="{html.escape(exported_at)}">{session_date_display}</time>
          &nbsp;&middot;&nbsp;
          Published <time datetime="{html.escape(published_at)}">{pub_date_display}</time>
          by {published_by}
        </p>
      </header>
{summary_section}{stations_section}\
    </article>
"""

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Family Radio Journal</title>
  <meta name="description" content="Published radio session logs from our family GMRS station.">
  <style>
    /* ---- reset & base ---- */
    *, *::before, *::after {{ box-sizing: border-box; }}
    html {{ font-size: 100%; }}
    body {{
      font-family: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      line-height: 1.6;
      margin: 0;
      padding: 0;
      background: #ffffff;
      color: #1a1a1a;
    }}

    /* ---- skip link ---- */
    .skip-link {{
      position: absolute;
      top: -999px;
      left: 0;
      background: #005fcc;
      color: #fff;
      padding: 0.5rem 1rem;
      z-index: 100;
      font-weight: 600;
      text-decoration: none;
      border-radius: 0 0 4px 0;
    }}
    .skip-link:focus {{ top: 0; }}

    /* ---- layout ---- */
    header[role="banner"],
    main,
    footer[role="contentinfo"] {{
      max-width: 720px;
      margin: 0 auto;
      padding: 1rem 1.25rem;
    }}
    header[role="banner"] {{
      border-bottom: 2px solid #005fcc;
      padding-top: 1.5rem;
      padding-bottom: 1rem;
    }}
    header[role="banner"] h1 {{
      margin: 0 0 0.25rem;
      font-size: 1.75rem;
      color: #003d8a;
    }}
    header[role="banner"] p {{
      margin: 0;
      color: #444;
      font-size: 0.95rem;
    }}

    /* ---- articles ---- */
    article {{
      margin: 2rem 0;
      padding-bottom: 2rem;
      border-bottom: 1px solid #ddd;
    }}
    article:last-child {{ border-bottom: none; }}
    article header {{ border: none; padding: 0; }}
    article header h2 {{
      margin: 0 0 0.25rem;
      font-size: 1.35rem;
      color: #003d8a;
    }}
    .meta {{
      margin: 0 0 1rem;
      font-size: 0.875rem;
      color: #555;
    }}
    h3 {{
      font-size: 1rem;
      margin: 1rem 0 0.4rem;
      color: #333;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    p {{ margin: 0 0 0.75rem; }}
    section {{ margin-bottom: 1rem; }}

    /* ---- table ---- */
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.9rem;
    }}
    caption {{
      text-align: left;
      font-size: 0.8rem;
      color: #666;
      margin-bottom: 0.25rem;
    }}
    th, td {{
      text-align: left;
      padding: 0.4rem 0.6rem;
      border: 1px solid #ccc;
    }}
    th {{
      background: #f0f4ff;
      font-weight: 600;
    }}
    tbody tr:nth-child(even) {{ background: #f9f9f9; }}

    /* ---- footer ---- */
    footer[role="contentinfo"] {{
      border-top: 1px solid #ddd;
      padding-top: 0.75rem;
      font-size: 0.8rem;
      color: #888;
    }}

    /* ---- dark mode ---- */
    @media (prefers-color-scheme: dark) {{
      body {{ background: #121212; color: #e8e8e8; }}
      header[role="banner"] {{ border-color: #4a8fff; }}
      header[role="banner"] h1, article header h2 {{ color: #7ab0ff; }}
      header[role="banner"] p, .meta {{ color: #aaa; }}
      article {{ border-color: #333; }}
      h3 {{ color: #ccc; }}
      th {{ background: #1e2a3d; }}
      th, td {{ border-color: #444; }}
      tbody tr:nth-child(even) {{ background: #1a1a1a; }}
      footer[role="contentinfo"] {{ border-color: #333; color: #666; }}
    }}

    /* ---- responsive ---- */
    @media (max-width: 480px) {{
      header[role="banner"] h1 {{ font-size: 1.4rem; }}
      article header h2 {{ font-size: 1.15rem; }}
      th, td {{ padding: 0.3rem 0.4rem; font-size: 0.85rem; }}
    }}
  </style>
</head>
<body>
  <a href="#main-content" class="skip-link">Skip to main content</a>

  <header role="banner">
    <h1>Family Radio Journal</h1>
    <p>Published session logs from our GMRS station.</p>
  </header>

  <main id="main-content" role="main">
{articles}\
  </main>

  <footer role="contentinfo">
    <p>Generated by Radio-TTY &middot; Last updated {html.escape(now_str)}</p>
  </footer>
</body>
</html>
"""
