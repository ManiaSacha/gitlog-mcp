# Contributing to gitlog-mcp

Thanks for wanting to help! This project is deliberately small, and that's a feature. Please keep contributions aligned with the philosophy.

## Ground rules
- **Single file, ~400 lines.** Big additions need justification and a maintainer sign-off.
- **Zero runtime deps** beyond the MCP SDK and the `git` CLI.
- **Safe subprocess calls** — arg lists, never `shell=True`.
- **Small, focused PRs.** One logical change per PR.

## Getting started
1. Fork the repo.
2. `git clone` your fork and `cd gitlog-mcp`.
3. Create a branch: `git checkout -b feature/your-change`.
4. Make your change, following the existing patterns.

## Checklist before opening a PR
- [ ] Change is small and focused
- [ ] No new runtime dependencies
- No `shell=True` or path traversal
- [ ] Behavior changes update the README
- [ ] Tests added/updated (if applicable)
- [ ] Ran the code against a real repo to verify it works

## Commit messages
Use [Conventional Commits](https://www.conventionalcommits.org/):
`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`.

## Code style
Keep it readable. Clear names, no cleverness. If someone can't read the file in an afternoon, it's too complex.

## Questions?
Open an issue or start a discussion. We're friendly.