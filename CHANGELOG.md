# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and
this project adheres to [Semantic Versioning](https://semver.org/).

`v0.1.2` below is the first tagged release, covering everything from the
initial commit through the current `main`.

## [Unreleased]

Nothing yet.

## [v0.1.3] - 2026-08-17

### Added
- Embedded visual demo GIF (`public/gitlog-mcp.gif`) at the top of `README.md`.
- `SECURITY.md` defining vulnerability disclosure policy and SLA.
- `CODE_OF_CONDUCT.md` (Contributor Covenant v2.1).
- GitHub issue templates for bug reports and feature requests.
- Python 3.13 added to the CI matrix in `.github/workflows/ci.yml`.
- Windsurf MCP configuration instructions in `README.md`.

### Changed
- Updated README quickstart to reflect live PyPI availability (`pip install gitlog-mcp`).
- Added live PyPI version badge to README.

## [v0.1.2] - 2026-08-16

### Added
- Initial release of `gitlog-mcp`, an MCP (Model Context Protocol) server
  that gives AI agents structured access to git history — changelogs,
  commit analysis, blame attribution, release notes, repo health, and
  commit search. (`640abd9`, `d09a225`)
- `--repo` CLI flag with auto-detection from the current working directory,
  so the server can be pointed at any local git repository. (`640abd9`)
- CI workflow running the test suite across Python 3.10-3.12 on Linux and
  Windows for every push/PR to `main`.
- PyPI publish workflow: tag a `vX.Y.Z` release and it builds + publishes
  automatically via PyPI Trusted Publishing (OIDC) — no stored API token.
  See [RELEASING.md](RELEASING.md) for the full process, including the
  one-time PyPI-side setup.

### Fixed
- Fixed a Windows stdio deadlock: the shared `git()` subprocess helper
  spawned `git` without redirecting stdin, so the child process inherited
  the server's own stdin pipe handle. On Windows this deadlocked against
  the MCP stdio reader thread already blocked on that same pipe —
  `initialize`/`tools/list` worked, but every `tools/call` hung forever.
  Fixed by passing `stdin=subprocess.DEVNULL`. (`3c2d5fe`)
- Fixed an off-by-one bug in `changelog()`'s small-repo clamping logic:
  computing `since=HEAD~(total-1)` and using it as a `since..until` range
  excludes the lower bound, silently dropping the repository's very first
  commit. Now uses `git log -n<total>` for repos with 20 or fewer commits.
  (`3c2d5fe`)
- Fixed git argument-injection vulnerabilities in `changelog()`,
  `analyze_commit()`, and `release_notes()`: user/LLM-supplied revision and
  tag strings (`since`, `until`, `sha`, `from_tag`, `to_tag`) were passed to
  `git` as bare argv tokens, so a value starting with `-` (e.g.
  `sha="--output=../evil.txt"`) was parsed by git as an option rather than a
  revision — turning `git show`/`git log` into an arbitrary-file-write
  primitive reachable directly from an MCP client. Any such value starting
  with `-` is now rejected before it reaches git. (`ee29ad1`)
- Hardened `blame_file()` by inserting `--` before the `path` argument so it
  is always treated as a pathspec rather than a possible option, as
  defense-in-depth against argument injection. (`ee29ad1`)
- Added a 30-second timeout to the shared `git()` subprocess call so a hung
  or adversarial `git` invocation can't stall the whole server. (`ee29ad1`)
- Fixed a crash on non-ASCII commit messages: `git()` decoded `git`'s stdout
  using the process locale (e.g. cp1252 on many English/Western-European
  Windows installs) instead of UTF-8, which is what git actually emits by
  default. Any commit message containing a byte undefined in cp1252 crashed
  subprocess's internal reader thread, surfacing to the MCP client as a
  confusing `'NoneType' object has no attribute 'strip'` error instead of a
  clean result. Output is now decoded as UTF-8 explicitly, with
  `errors="replace"` so genuinely malformed bytes degrade to `U+FFFD`
  instead of crashing. (`ca38781`)

### Changed
- Reorganized the project from a flattened, prefixed file layout
  (`gitlog-mcp-readme.md`, `gitlog-pyproject.txt`, etc.) into a standard
  Python package layout (`README.md`, `pyproject.toml`, `gitlog_mcp.py`,
  `tests/test_gitlog_mcp.py`), and added `.claude/` agent and skill configs
  for the project. (`2a215c8`)
- Capped the `mcp` dependency to `mcp>=1.0,<2.0`, since it was previously
  pinned with no upper bound and a fresh install could pull `mcp` 2.0.0,
  which renamed `FastMCP` and broke the import entirely. (`3c2d5fe`)
- Added five regression tests reproducing each rejected argument-injection
  payload, and a regression test using a real zero-width-joiner emoji
  commit message for the encoding fix. (`ee29ad1`, `ca38781`)
- Added `[project.urls]` (Homepage/Repository/Issues) and capped the
  `setuptools` build-time dependency to `<76` in `pyproject.toml`, so the
  PyPI project page has working links and the publish workflow doesn't
  silently pick up a future breaking setuptools release.

### Docs
- Added `README.md` with project overview, features, quick start, example
  agent prompts, tool reference, and architecture notes. (`68abf2e`,
  `640abd9`)
- Documented installing from source (`pip install -e .`) in the README,
  since the package was not yet published to PyPI. (`3c2d5fe`)
- Added `.claude/launch.json` for launching the MCP Inspector during local
  development. (`3c2d5fe`)
- Fixed a README Quick Start step that told readers to run the MCP
  Inspector (a debugging UI) as if it were how you add gitlog-mcp to an
  agent; added proper Claude Code + Cursor `mcp.json` config blocks and
  relabeled the Inspector command as a "debug it standalone" callout.
- Corrected the README's architecture section, which claimed "~400 lines"
  for a file that was actually 240; replaced a static "GitHub stars" badge
  that displayed the literal text "MCP-server" with a real CI badge and a
  live stars count.
- Added `RELEASING.md`: the full release checklist, SemVer policy, and the
  one-time PyPI Trusted Publishing setup steps (which only a human with
  PyPI access can perform).
- Added this `CHANGELOG.md`, generated from the project's actual git
  history.

[Unreleased]: https://github.com/ManiaSacha/gitlog-mcp/compare/v0.1.3...HEAD
[v0.1.3]: https://github.com/ManiaSacha/gitlog-mcp/compare/v0.1.2...v0.1.3
[v0.1.2]: https://github.com/ManiaSacha/gitlog-mcp/releases/tag/v0.1.2
