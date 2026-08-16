---
name: generate-changelog
description: Generate a clean, grouped changelog from a git commit range. Use whenever the user asks for a changelog, release notes, or "what changed" between versions.
---

# Generate a Changelog

Use this skill to produce a clean, grouped changelog from git history.

## When to use
- User asks for a changelog, release notes, or "what changed between X and Y"
- Before cutting a release

## Steps
1. Determine the range (e.g. `v1.0.0..HEAD` or a tag pair).
2. Fetch commits with author + date:
   ```bash
   git log --pretty=format:"%h|%ad|%aN|%s" --date=short <since>..<until>
   ```
3. Group subjects by Conventional-Commits type:
   - `feat:` → **Added**
   - `fix:` → **Fixed**
   - `docs:` → **Docs**
   - `refactor:` / `chore:` → **Changed**
   - `breaking:` → **Breaking**
4. Output the grouped changelog.

## Output template
```
## Changelog (<since> → <until>)
### Added
- ...
### Fixed
- ...
### Changed
- ...
### Breaking
- ...
```

## Notes
- If no commits match, say so clearly.
- Keep each line a single, human-readable sentence.