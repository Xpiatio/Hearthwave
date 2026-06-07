---
name: release
description: Use when cutting a release — guides updating README, USER_MANUAL, and docs/index.html with the new version and feature additions before tagging.
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

1. If the manual does not have a version line at the very top (after the `# Radio-TTY User Manual` heading), add:

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

The version badge appears in **two places** — update both:

1. Around line 102 — in the hero/nav area:
   ```
   <span ...>vOLD_VERSION</span>  →  <span ...>vNEW_VERSION</span>
   ```

2. Around line 559 — in the footer badges:
   ```
   <li ...>vOLD_VERSION</li>  →  <li ...>vNEW_VERSION</li>
   ```

Find both with:
```bash
grep -n "v[0-9]\+\.[0-9]\+\.[0-9]\+" docs/index.html
```

Also locate the features/highlights section on the page (search for the section that lists feature cards or bullet features) and add cards/entries for significant new capabilities, matching the existing style.

## Step 7 — Commit the doc updates

```bash
git add README.md USER_MANUAL.md docs/index.html
git commit -m "docs: update docs for vNEW_VERSION release"
```

Replace `NEW_VERSION` with the actual version (e.g. `v2.4.0`).

## Step 8 — Hand back for review

Tell the user:

> "Docs updated for vNEW_VERSION. Here is a summary of what changed:
> - README.md: added N feature bullets
> - USER_MANUAL.md: added/updated N sections
> - docs/index.html: bumped version badges, added N feature entries
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
