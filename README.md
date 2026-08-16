# 🔍 gitlog-mcp

**Give your AI coding agent superpowers over git history.**

`gitlog-mcp` is a Model Context Protocol (MCP) server that lets AI agents (Claude Code, Cursor, Windsurf, and any MCP client) understand *what changed in a repository* — auto-generate changelogs, analyze commits, attribute blame, and draft release notes.

> "What changed in this repo?" is the question every AI agent gets wrong. This fixes it.

![CI](https://github.com/ManiaSacha/gitlog-mcp/actions/workflows/ci.yml/badge.svg)
![GitHub stars](https://img.shields.io/github/stars/ManiaSacha/gitlog-mcp)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB)
![License](https://img.shields.io/badge/License-MIT-green)
![Zero deps](https://img.shields.io/badge/Zero%20runtime%20deps-%E2%9C%93-brightgreen)

---

## Why this exists

AI coding agents are great at *writing* code but famously bad at *knowing the history* of a codebase. They hallucinate changelogs, misattribute blame, and guess at release notes. `gitlog-mcp` gives them a reliable, structured window into `git log` — so their answers are grounded in what actually happened, not invented.

## Features

- 📝 **Auto-changelog** — generate a clean, grouped changelog from any tag/commit range
- 🔎 **Commit analysis** — explain *why* a change happened, not just what changed
- 👤 **Blame attribution** — who touched what, and when (with context)
- 🏷️ **Release notes** — draft release notes from tag-to-tag diffs
- 📊 **Repo health** — commit frequency, top contributors, churn hotspots
- 🧱 **Zero runtime dependencies** — pure Python stdlib + the MCP SDK, one file

## Quick start

```bash
# 1. Install (not yet on PyPI — install from source)
git clone https://github.com/ManiaSacha/gitlog-mcp.git
cd gitlog-mcp
pip install -e .

# 2. Run standalone (for testing) — defaults to the current directory
gitlog-mcp
gitlog-mcp --repo /path/to/your/repo

# 3. Or add directly to your agent's MCP config (see below)
```

> `pip install gitlog-mcp` will work once this is published to PyPI. Until then, install from source as shown above. There's a real, tested publish pipeline ready to go (tag-triggered, PyPI Trusted Publishing) — see [RELEASING.md](RELEASING.md) for the full process.

> Want the [local web dashboard](#web-dashboard-optional) too? It's an optional extra, not installed by default: `pip install -e ".[ui]"` (or `pip install "gitlog-mcp[ui]"` once on PyPI). Plain `pip install gitlog-mcp` stays exactly as dependency-free as ever.

### Claude Code config

```json
{
  "mcpServers": {
    "gitlog": {
      "command": "gitlog-mcp",
      "args": ["--repo", "."]
    }
  }
}
```

### Cursor config (`.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "gitlog": {
      "command": "gitlog-mcp",
      "args": ["--repo", "."]
    }
  }
}
```

### Debug it standalone

Want to poke at the tools directly before wiring up an agent? The [MCP Inspector](https://github.com/modelcontextprotocol/inspector) gives you a UI to call each tool by hand:

```bash
npx @modelcontextprotocol/inspector gitlog-mcp --repo .
```

## Example agent prompts

> "Generate a changelog of everything that changed between `v1.2.0` and `v1.3.0`."

> "Who introduced this buggy line in `src/parser.py` and why?"

> "Draft release notes for the next version based on recent commits."

## Tools exposed

| Tool | Description |
|------|-------------|
| `changelog` | Grouped changelog for a commit/tag range |
| `analyze_commit` | Explain a specific commit's intent and impact |
| `blame_file` | Line-level attribution for a file |
| `release_notes` | Draft release notes between two tags |
| `repo_health` | Contributor + churn summary |
| `search_commits` | Find commits by message/author/date |

## Web dashboard (optional)

Prefer a browser to a terminal? `gitlog-mcp-ui` serves a small local dashboard on top of the same git-reading code the MCP tools use — same data, human-readable.

```bash
pip install "gitlog-mcp[ui]"
gitlog-mcp-ui --repo /path/to/repo
```

This prints a URL (`http://127.0.0.1:8765` by default) — open it in your browser; it won't open one for you.

| View | What it shows |
|------|-------------|
| Changelog | Commit range picker (`since` / `until`) |
| Repo Health | Contributor stats, commit totals |
| Blame | Per-file, per-line attribution |

Read-only — no write actions anywhere. Local-only by construction: binds to `127.0.0.1` only (there's no `--host` flag, so it can't be exposed to the network even by accident), and validates every request's `Host` header too, closing the DNS-rebinding gap a loopback bind alone doesn't cover. No auth needed, because nothing but your own machine can reach it.

It's an optional extra (`pip install gitlog-mcp[ui]`), not installed by default. The core `gitlog-mcp` server has zero runtime dependencies beyond the MCP SDK, full stop — the dashboard doesn't change that. It's `http.server` from the stdlib, no framework, no extra deps of its own.

## Architecture

```
gitlog-mcp (single file, ~250 lines)
├── FastMCP server (stdio transport)
├── GitRunner — thin wrapper over `git` CLI
└── Tools — each maps to a git subcommand + parsing
```

Deliberately small. You can read the whole thing in an afternoon — that's a feature.

## Contributing

PRs welcome. Small, focused, well-tested changes only. See [CONTRIBUTING.md](CONTRIBUTING.md).

Release process and versioning are documented in [RELEASING.md](RELEASING.md).

## Roadmap

- [x] `--repo` auto-detection from cwd
- [ ] Structured JSON output for all tools
- [ ] GitHub/GitLab remote integration
- [x] Tests + CI badge

## License

MIT © 2026 — built in the open, for the open-source community.

---

**Star this repo** if you want AI agents to stop hallucinating your changelog. ⭐