# 🔍 gitlog-mcp

**Give your AI coding agent superpowers over git history.**

`gitlog-mcp` is a Model Context Protocol (MCP) server that lets AI agents (Claude Code, Cursor, Windsurf, and any MCP client) understand *what changed in a repository* — auto-generate changelogs, analyze commits, attribute blame, and draft release notes.

> "What changed in this repo?" is the question every AI agent gets wrong. This fixes it.

![GitHub stars](https://img.shields.io/badge/MCP-server-4B32C3)
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
# 1. Install
pip install gitlog-mcp

# 2. Run standalone (for testing)
gitlog-mcp --repo /path/to/your/repo

# 3. Or add to Claude Code / Cursor
npx @modelcontextprotocol/inspector gitlog-mcp --repo .
```

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

## Architecture

```
gitlog-mcp (single file, ~400 lines)
├── FastMCP server (stdio transport)
├── GitRunner — thin wrapper over `git` CLI
└── Tools — each maps to a git subcommand + parsing
```

Deliberately small. You can read the whole thing in an afternoon — that's a feature.

## Contributing

PRs welcome. Small, focused, well-tested changes only. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Roadmap

- [ ] `--repo` auto-detection from cwd
- [ ] Structured JSON output for all tools
- [ ] GitHub/GitLab remote integration
- [ ] Tests + CI badge

## License

MIT © 2026 — built in the open, for the open-source community.

---

**Star this repo** if you want AI agents to stop hallucinating your changelog. ⭐