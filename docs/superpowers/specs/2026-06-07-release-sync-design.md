# Release Docs Sync — Design Spec

**Date:** 2026-06-07  
**Status:** Approved

## Goal

When cutting a release, keep README.md, USER_MANUAL.md, and docs/index.html in sync with the new version number and any new feature additions. Claude handles this — not an automated pipeline.

## Trigger

Whenever we are about to tag a release (push a `v*.*.*` tag, run `gh release create`, or equivalent), Claude invokes the `/release` skill before tagging.

## Components

### 1. CLAUDE.md (repo root)

A standing instruction visible every session:

> When cutting a release, invoke the `/release` skill before tagging. It updates README, USER_MANUAL, and the website with the new version and feature additions.

### 2. `/release` skill — `.superpowers/skills/release.md`

A guided checklist skill that walks Claude through the following steps in order:

| Step | Action |
|------|--------|
| 1 | **Determine versions** — new version from `package.json` (or user input); previous tag via `git describe --tags --abbrev=0` |
| 2 | **Gather changes** — `git log <prev>..HEAD --oneline` + merged PR titles since last tag |
| 3 | **Write feature prose** — synthesize commits/PRs into plain-English summaries; skip chore/fix-only changes unless user-facing |
| 4 | **Update README.md** — add bullets to `## Features` for each significant new capability |
| 5 | **Update USER_MANUAL.md** — add/update sections for new user-facing features; update any version callouts |
| 6 | **Update docs/index.html** — bump the two version badge strings; update the features/highlights section on the landing page |
| 7 | **Commit** — `docs: update docs for vX.Y.Z release` |
| 8 | **Hand back** — prompt user to review the diff, then proceed with tag + `gh release create` |

## What each file contains

- **README.md** — `## Features` bulleted list; no version number currently hardcoded (add one if appropriate)
- **USER_MANUAL.md** — prose sections per feature; no version header currently (add one at the top if appropriate)
- **docs/index.html** — version badge appears in two places (lines ~102 and ~559); features section in the middle of the page

## Out of scope

- Automated GitHub Actions version bumping (deferred; Claude handles this for now)
- CHANGELOG.md generation (not a current doc in the repo)
