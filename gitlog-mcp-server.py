#!/usr/bin/env python3
"""
gitlog-mcp — Give AI agents superpowers over git history.

A single-file MCP server exposing git history as structured tools:
changelogs, commit analysis, blame, release notes, and repo health.

Zero runtime dependencies beyond the MCP SDK and the `git` CLI.
Run:  python gitlog_mcp.py --repo /path/to/repo
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("gitlog")
REPO: Path | None = None


# --------------------------------------------------------------------------- #
# Git runner — thin, safe wrapper over the `git` CLI
# --------------------------------------------------------------------------- #
class GitError(RuntimeError):
    pass


def git(*args: str) -> str:
    """Run a git command in the target repo and return stdout."""
    if REPO is None:
        raise GitError("No repo configured. Pass --repo.")
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO), *args],
            capture_output=True,
            text=True,
            check=True,
        )
        return proc.stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise GitError(f"git {args[0]} failed: {exc.stderr.strip()}") from exc


def parse_commit(line: str) -> dict:
    """Parse a single `--pretty=format` commit line into a dict."""
    fields = {}
    for part in line.split("\x00"):
        if "=" in part:
            key, _, val = part.partition("=")
            fields[key] = val
    return fields


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #
@mcp.tool()
def changelog(since: str = "HEAD~20", until: str = "HEAD") -> str:
    """Generate a grouped changelog for a commit range (e.g. v1.2.0..v1.3.0)."""
    fmt = "%x00type=%h%x00scope=%s%x00author=%aN%x00date=%aI"
    raw = git("log", "--pretty=format:" + fmt, f"{since}..{until}")
    commits = [parse_commit(l) for l in raw.splitlines() if l.strip()]
    if not commits:
        return "No commits found in that range."
    lines = [f"## Changelog ({since} → {until})", ""]
    for c in commits:
        lines.append(f"- **{c.get('scope', '?')}** — {c.get('type', '?')} "
                     f"({c.get('author', '?')}, {c.get('date', '?')[:10]})")
    return "\n".join(lines)


@mcp.tool()
def analyze_commit(sha: str) -> str:
    """Explain a specific commit's intent and impact."""
    fmt = "%x00sha=%h%x00subject=%s%x00body=%b%x00author=%aN%x00date=%aI"
    raw = git("show", "--pretty=format:" + fmt, sha)
    c = parse_commit(raw)
    stat = git("show", "--stat", "--format=", sha)
    return (
        f"Commit {c.get('sha')} by {c.get('author')} on {c.get('date', '')[:10]}\n"
        f"Subject: {c.get('subject')}\n\n"
        f"Body:\n{c.get('body', '(none)')}\n\n"
        f"Impact:\n{stat}"
    )


@mcp.tool()
def blame_file(path: str) -> str:
    """Line-level attribution for a file (who, when, which commit)."""
    raw = git("blame", "--line-porcelain", path)
    out, cur = [], {}
    for line in raw.splitlines():
        if line.startswith("author "):
            cur["author"] = line.split(" ", 1)[1]
        elif line.startswith("author-time "):
            cur["time"] = datetime.fromtimestamp(
                int(line.split(" ", 1)[1])
            ).strftime("%Y-%m-%d")
        elif line.startswith("\t"):
            out.append(f"{cur.get('time')} {cur.get('author'):<20} {line.strip()}")
    return "\n".join(out)


@mcp.tool()
def release_notes(from_tag: str, to_tag: str) -> str:
    """Draft release notes between two tags."""
    raw = git("log", "--pretty=format:%s", f"{from_tag}..{to_tag}")
    lines = [f"## Release notes ({from_tag} → {to_tag})", ""]
    for subject in raw.splitlines():
        if subject.strip():
            lines.append(f"- {subject}")
    return "\n".join(lines)


@mcp.tool()
def repo_health() -> str:
    """Contributor + churn summary for the repo."""
    raw = git("shortlog", "-sn", "--all")
    lines = [f"## Contributors ({len(raw.splitlines())})", ""]
    for entry in raw.splitlines()[:10]:
        lines.append(f"- {entry.strip()}")
    return "\n".join(lines)


@mcp.tool()
def search_commits(query: str) -> str:
    """Find commits by message, author, or date."""
    raw = git("log", "--pretty=format:%h %ad %an %s",
              "--date=short", f"--grep={query}", "-i")
    return raw if raw else f"No commits matched '{query}'."


# --------------------------------------------------------------------------- #
# Entrypoint
# --------------------------------------------------------------------------- #
def main() -> None:
    global REPO
    parser = argparse.ArgumentParser(description="gitlog-mcp server")
    parser.add_argument("--repo", type=Path, required=True,
                        help="Path to the git repository to serve")
    args = parser.parse_args()
    REPO = args.repo.resolve()
    if not (REPO / ".git").exists():
        sys.exit(f"error: {REPO} is not a git repository")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()