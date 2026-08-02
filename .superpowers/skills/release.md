---
name: release
description: Use when cutting a release — guides bumping every version reference in the tree, updating README and USER_MANUAL with new features, and bumping the version stamp in docs/index.html, before tagging. The landing-page feature grid is curated, not a changelog.
---

# Release Docs Update

Follow these steps in order before pushing a version tag or running `gh release create`.

## Step 1 — Determine versions

Run:
```bash
cat frontend/package.json | grep '"version"'
git describe --tags --abbrev=0
```

Record:
- **NEW_VERSION** — from `frontend/package.json` (e.g. `2.4.0`; the tag will be `v2.4.0`)
- **PREV_TAG** — output of `git describe` (e.g. `v2.3.0`)

## Step 1b — Bump every version reference

The version lives in **nine** places across **six** files, not just `frontend/package.json`.
Missing any of them ships a release that lies about itself. In v2.23.1 the backend
`__version__` was missed, so the running app kept reporting `2.23.0` in its UI — and the
deploy files kept pulling the previous release's images.

| File | What | Why it matters |
|---|---|---|
| `backend/__init__.py` | `__version__` | **This is what the UI displays.** `useVersion.ts` → `GET /health` → `server.py` returns `backend.__version__`. Bumping only package.json does *not* change what users see. |
| `frontend/package.json` | `"version"` | Source of truth for NEW_VERSION in Step 1 |
| `frontend/package-lock.json` | `"version"` ×2 (top level + `packages[""]`) | Must match package.json or `npm ci` warns |
| `docker-compose.images.yml` | backend + frontend `image:` tags | Pre-built-image stack — a stale pin silently deploys the old release |
| `docker-compose.portainer.yml` | header comment + `image:` tags (incl. the commented-out `-cuda` example) | Same, for Portainer users |
| `prereq.sh` | `BACKEND_IMAGE` | Pulls the backend image during setup |

Bump them, then run the automated check — it verifies every location above agrees
with `frontend/package.json`, and CI runs it on every PR and again before publishing:

```bash
python3 scripts/check_version_sync.py
```

If you add a new place the version is written, add a check to that script **and** a
row to the table above.

As a second pass, **verify no stale reference survives**:

```bash
# Both must come back empty (CHANGELOG keeps history, so exclude it).
git grep -n "PREV_VERSION_WITHOUT_V" -- . ':!CHANGELOG*'
git grep -n "$(git describe --tags --abbrev=0 | tr -d v)" -- . ':!CHANGELOG*'
```

Two intentional exceptions — do **not** rewrite these:
- Historical prose in the docs (`Since v2.23.1 Hearthwave stores …`) refers to the release a
  feature actually landed in.
- `CHANGELOG*` entries for past versions.

The grep is the real check, not this table. If it turns up a file not listed above, bump it
**and add a row here** so the next release inherits the fix.

## Step 2 — Gather changes since last release

Run:
```bash
PREV=$(git describe --tags --abbrev=0)
git log ${PREV}..HEAD --oneline
```

Also pull merged PR titles:
```bash
gh pr list --state merged --base master --limit 30 --json number,title,mergedAt \
  --jq '.[] | "#\(.number) \(.title)"'
```

Read the output. Identify user-facing changes — new features, significant fixes, UI changes. Ignore: chore, ci, test, refactor, bump-version commits unless they affect the user experience.

## Step 3 — Write feature prose

For each user-facing change, write a plain-English one-liner:
- Lead with the capability, not the implementation ("Voice PTT pre-roll captures first syllable before PTT is pressed" not "Added 200ms ring buffer to audio input")
- Bold the feature name: `**Feature name** — description`
- Skip internal/dev-only changes entirely

Keep a working list — you will use it in the next three steps.

## Step 4 — Update README.md

Find the `## Features` section. Add a bullet for each new capability identified in Step 3, using the same style as existing bullets:

```
- **New feature name** — one-line description
```

Insert new bullets at the top of the list (most recent first).

If README does not yet have a version callout at the top, add one below the first paragraph:

```markdown
> **Latest release:** vNEW_VERSION
```

## Step 5 — Update USER_MANUAL.md

1. If the manual does not have a version line at the very top (after the `# Hearthwave User Manual` heading), add:

```markdown
> **Version:** vNEW_VERSION
```

If it already has one, update the version number.

2. For each significant new user-facing feature from Step 3, add or update a section in the manual. Follow the existing section numbering style. New sections go at the end of the numbered list (before any appendices).

Section template:
```markdown
## N. Feature name

Brief description of what it does and why a user would use it.

### How to use

Step-by-step or prose explanation. Include any keyboard shortcuts, UI element names, or admin requirements.
```

## Step 6 — Update docs/index.html

### 6a — Bump the version stamp

There is **one** version stamp, in the footer release line. Find it with:
```bash
grep -n "v[0-9]\+\.[0-9]\+\.[0-9]\+" docs/index.html
```
Update `vOLD_VERSION` → `vNEW_VERSION` there. (If a future redesign adds a second stamp, this grep will surface it — update every match.)

### 6b — Curate the feature grid — do NOT append a changelog

**The landing page is a marketing page, not a changelog.** The feature cards in the `#features` bento grid highlight the product's *key, durable capabilities* — they are not a per-release log.

Rules:
- **Never add a version tag to a card.** Card labels (`<span class="k">`) are topical — `RX`, `TX`, `PLUGINS`, `AUDIO` — never `· v2.x`.
- **Default to changing nothing.** Most releases (fixes, polish, incremental UI tweaks) need no new card. A release earns a card only if it adds a *headline capability a new visitor would care about*.
- When a release does warrant a card, prefer **folding it into an existing thematic card** (e.g. a new audio option belongs in the existing `AUDIO` card) over adding a new one.
- Add a genuinely new card only for a major new capability with no existing home. If the grid is getting long (>~12 cards), **retire or merge** a weaker card rather than letting it grow.
- Keep copy benefit-led and short — no benchmark figures or implementation detail (that belongs in USER_MANUAL.md, Step 5).

If in doubt, leave the grid alone. The version stamp in 6a is the only mandatory edit in this file.

### 6c — docs/legality.html (usually no change)

`docs/legality.html` carries a "Reviewed <Month Year>" date, not a version stamp — it only changes when its compliance content changes. If this release altered any transmission behavior (new auto-TX path, linking-adjacent feature, ID logic), update the page and its reviewed date; otherwise leave it alone.

## Step 7 — Commit the doc updates

```bash
git add README.md USER_MANUAL.md docs/index.html docs/legality.html
git commit -m "docs: update docs for vNEW_VERSION release"
```

Replace `NEW_VERSION` with the actual version (e.g. `v2.4.0`).

## Step 8 — Hand back for review

Tell the user:

> "Docs updated for vNEW_VERSION. Here is a summary of what changed:
> - README.md: added N feature bullets
> - USER_MANUAL.md: added/updated N sections
> - docs/index.html: bumped the version stamp (and curated the feature grid only if a headline capability warranted it)
>
> Review with: `git show HEAD`
>
> Ready to tag and release when you are. Run:
> ```bash
> git tag vNEW_VERSION
> git push origin master --tags
> gh release create vNEW_VERSION --generate-notes
> ```"

Wait for the user to confirm before tagging.
