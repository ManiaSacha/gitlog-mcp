---
name: draft-release-notes
description: Draft GitHub release notes from a tag-to-tag diff, grouped by feature/fix/docs. Use when cutting a release or writing release notes.
---

# Draft Release Notes

Use this skill to write release notes for a new version.

## Steps
1. Get the commit range since the last tag:
   ```bash
   git log --pretty=format:"%s" <last_tag>..HEAD
   ```
2. Group by Conventional-Commits type (feat → Added, fix → Fixed, docs → Docs).
3. Write in a friendly, concrete tone — describe the user benefit, not just the change.

## Template
```
## What's new in vX.Y.Z

### ✨ Added
- <benefit-focused description>

### 🐛 Fixed
- <what was broken and now works>

### 📚 Docs
- <documentation improvements>

**Full changelog:** https://github.com/<owner>/gitlog-mcp/compare/v<prev>...v<new>
```

## Notes
- Lead with the most impactful change.
- Link the compare view so readers can dig in.
- Keep it scannable — bullets, not paragraphs.