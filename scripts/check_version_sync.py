#!/usr/bin/env python3
"""Fail if any version reference in the tree disagrees with frontend/package.json.

v2.23.1 shipped with backend/__init__.py left at 2.23.0, so the running app
reported the wrong version in its UI, and the three deploy files stayed pinned to
the previous release's images. The release checklist in
.superpowers/skills/release.md lists every location; this script enforces it.

Deliberately a *consistency* check, not a "grep for the old version" check —
docs legitimately name past releases ("Since v2.23.1 Hearthwave stores ..."), so
scanning for stale strings would cry wolf on prose that is correct.

Run from the repo root:
    python3 scripts/check_version_sync.py

Adding a new place the version is written? Add a check here and a row to the
table in .superpowers/skills/release.md.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Files whose every hearthwave image tag must name the current version. A stale
# pin here is worse than cosmetic: it silently deploys the previous release.
IMAGE_PINNED = (
    "docker-compose.images.yml",
    "docker-compose.portainer.yml",
    "prereq.sh",
)
IMAGE_TAG_RE = re.compile(
    r"ghcr\.io/xpiatio/hearthwave-(?:backend|frontend):v(\d+\.\d+\.\d+)"
)

# Single-occurrence stamps: (path, regex with one capture group, description).
STAMPS = (
    (
        "backend/__init__.py",
        re.compile(r'^__version__ = "(\d+\.\d+\.\d+)"', re.M),
        "__version__ — this is the version the UI displays "
        "(useVersion.ts -> GET /health -> server.py -> backend.__version__)",
    ),
    (
        "README.md",
        re.compile(r"^> \*\*Latest release:\*\* v(\d+\.\d+\.\d+)", re.M),
        "release callout",
    ),
    (
        "USER_MANUAL.md",
        re.compile(r"^> \*\*Version:\*\* v(\d+\.\d+\.\d+)", re.M),
        "version line",
    ),
    (
        "docs/index.html",
        re.compile(r'<span class="tag">v(\d+\.\d+\.\d+)</span>'),
        "footer version stamp",
    ),
    (
        "docker-compose.portainer.yml",
        re.compile(r"^# Hearthwave v(\d+\.\d+\.\d+)", re.M),
        "header comment",
    ),
)

failures: list[str] = []


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def canonical_version() -> str:
    pkg = json.loads(read("frontend/package.json"))
    version = pkg.get("version")
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        sys.exit(f"frontend/package.json has no usable version: {version!r}")
    return version


def check_lockfile(expected: str) -> None:
    lock = json.loads(read("frontend/package-lock.json"))
    for label, actual in (
        ('"version"', lock.get("version")),
        ('packages[""]["version"]', lock.get("packages", {}).get("", {}).get("version")),
    ):
        if actual != expected:
            failures.append(
                f"frontend/package-lock.json: {label} is {actual!r}, expected {expected!r}"
            )


def check_stamps(expected: str) -> None:
    for rel, pattern, description in STAMPS:
        found = pattern.findall(read(rel))
        if not found:
            failures.append(
                f"{rel}: no {description} found — did the format change? "
                f"Update the pattern in {Path(__file__).name}."
            )
            continue
        for actual in found:
            if actual != expected:
                failures.append(
                    f"{rel}: {description} says {actual}, expected {expected}"
                )


def check_image_pins(expected: str) -> None:
    for rel in IMAGE_PINNED:
        found = IMAGE_TAG_RE.findall(read(rel))
        if not found:
            failures.append(
                f"{rel}: no hearthwave image tag found — did the image name change? "
                f"Update IMAGE_TAG_RE in {Path(__file__).name}."
            )
            continue
        for actual in found:
            if actual != expected:
                failures.append(
                    f"{rel}: image pinned to v{actual}, expected v{expected} "
                    "(a stale pin deploys the previous release)"
                )


def check_tag_matches(expected: str) -> None:
    """When the build was triggered by a version tag, the tag must agree too."""
    ref = os.environ.get("GITHUB_REF", "")
    if not ref.startswith("refs/tags/"):
        return
    tag = ref[len("refs/tags/") :]
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        return
    if tag != f"v{expected}":
        failures.append(
            f"tag {tag} does not match frontend/package.json version {expected} — "
            "the tag would publish images that disagree with the tree"
        )


def main() -> int:
    expected = canonical_version()
    check_lockfile(expected)
    check_stamps(expected)
    check_image_pins(expected)
    check_tag_matches(expected)

    if failures:
        print(f"Version references disagree with frontend/package.json ({expected}):\n")
        for failure in failures:
            print(f"  ✗ {failure}")
        print(
            "\nEvery place the version is written is listed in "
            ".superpowers/skills/release.md (Step 1b)."
        )
        return 1

    print(f"All version references agree: {expected}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
