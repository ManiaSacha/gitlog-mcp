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
            stdin=subprocess.DEVNULL,
        )
        return proc.stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise GitError(f"git {args[0]} failed: {exc.stderr.strip()}") from exc
    except FileNotFoundError as exc:
        raise GitError("git executable not found on PATH.") from exc


def parse_commit(line: str) -> dict:
    """Parse a single `--pretty=format` commit line into a dict."""
    fields = {}
    for part in line.split("\x00"):
        if "=" in part:
            key, _, val = part.partition("=")
            fields[key] = val
    return fields


def commit_count() -> int:
    """Total number of commits reachable from HEAD (0 for an empty repo)."""
    try:
        raw = git("rev-list", "--count", "HEAD")
        return int(raw) if raw else 0
    except GitError:
        return 0


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #
@mcp.tool()
def changelog(since: str = "HEAD~20", until: str = "HEAD") -> str:
    """Generate a grouped changelog for a commit range (e.g. v1.2.0..v1.3.0)."""
    try:
        fmt = "%x00type=%h%x00scope=%s%x00author=%aN%x00date=%aI"

        # Default range assumes >=20 commits exist. For smaller/younger repos,
        # a `HEAD~N..HEAD` range would either fail ("unknown revision") or
        # silently exclude the root commit (two-dot ranges are exclusive of
        # the lower bound), so show the full history via max-count instead.
        if since == "HEAD~20":
            total = commit_count()
            if total == 0:
                return "No commits found in that range."
            if total <= 20:
                raw = git("log", "--pretty=format:" + fmt, f"-n{total}")
                commits = [parse_commit(l) for l in raw.splitlines() if l.strip()]
                lines = [f"## Changelog (full history → {until})", ""]
                for c in commits:
                    lines.append(f"- **{c.get('scope', '?')}** — {c.get('type', '?')} "
                                 f"({c.get('author', '?')}, {c.get('date', '?')[:10]})")
                return "\n".join(lines)

        raw = git("log", "--pretty=format:" + fmt, f"{since}..{until}")
        commits = [parse_commit(l) for l in raw.splitlines() if l.strip()]
        if not commits:
            return "No commits found in that range."
        lines = [f"## Changelog ({since} → {until})", ""]
        for c in commits:
            lines.append(f"- **{c.get('scope', '?')}** — {c.get('type', '?')} "
                         f"({c.get('author', '?')}, {c.get('date', '?')[:10]})")
        return "\n".join(lines)
    except GitError as exc:
        return f"Error: {exc}"


@mcp.tool()
def analyze_commit(sha: str) -> str:
    """Explain a specific commit's intent and impact."""
    try:
        fmt = "%x00sha=%h%x00subject=%s%x00body=%b%x00author=%aN%x00date=%aI"
        raw = git("show", "--pretty=format:" + fmt, sha)
        c = parse_commit(raw)
        stat = git("show", "--stat", "--format=", sha)
        return (
            f"Commit {c.get('sha')} by {c.get('author')} on {c.get('date', '')[:10]}\n"
            f"Subject: {c.get('subject')}\n\n"
            f"Body:\n{c.get('body', '(none)') or '(none)'}\n\n"
            f"Impact:\n{stat}"
        )
    except GitError as exc:
        return f"Error: {exc}"


@mcp.tool()
def blame_file(path: str) -> str:
    """Line-level attribution for a file (who, when, which commit)."""
    try:
        raw = git("blame", "--line-porcelain", path)
    except GitError as exc:
        return f"Error: {exc}"
    if not raw:
        return f"No blame data for '{path}' (file may be empty or untracked)."
    out, cur = [], {}
    for line in raw.splitlines():
        if line.startswith("author "):
            cur["author"] = line.split(" ", 1)[1]
        elif line.startswith("author-time "):
            cur["time"] = datetime.fromtimestamp(
                int(line.split(" ", 1)[1])
            ).strftime("%Y-%m-%d")
        elif line.startswith("\t"):
            author = cur.get("author") or "unknown"
            time = cur.get("time") or "----------"
            out.append(f"{time} {author:<20} {line.strip()}")
    return "\n".join(out) if out else f"No blame data for '{path}'."


@mcp.tool()
def release_notes(from_tag: str, to_tag: str) -> str:
    """Draft release notes between two tags."""
    try:
        raw = git("log", "--pretty=format:%s", f"{from_tag}..{to_tag}")
    except GitError as exc:
        return f"Error: {exc}"
    lines = [f"## Release notes ({from_tag} → {to_tag})", ""]
    for subject in raw.splitlines():
        if subject.strip():
            lines.append(f"- {subject}")
    if len(lines) == 2:
        return f"No commits found between {from_tag} and {to_tag}."
    return "\n".join(lines)


@mcp.tool()
def repo_health() -> str:
    """Contributor + churn summary for the repo."""
    try:
        raw = git("shortlog", "-sn", "--all")
    except GitError as exc:
        return f"Error: {exc}"
    if not raw:
        return "## Contributors (0)\n\nNo commits yet."
    lines = [f"## Contributors ({len(raw.splitlines())})", ""]
    for entry in raw.splitlines()[:10]:
        lines.append(f"- {entry.strip()}")
    return "\n".join(lines)


@mcp.tool()
def search_commits(query: str) -> str:
    """Find commits by message, author, or date."""
    try:
        raw = git("log", "--pretty=format:%h %ad %an %s",
                  "--date=short", f"--grep={query}", "-i")
    except GitError as exc:
        return f"Error: {exc}"
    return raw if raw else f"No commits matched '{query}'."


# --------------------------------------------------------------------------- #
# Entrypoint
# --------------------------------------------------------------------------- #
def main() -> None:
    global REPO
    parser = argparse.ArgumentParser(description="gitlog-mcp server")
    parser.add_argument("--repo", type=Path, default=Path.cwd(),
                        help="Path to the git repository to serve (default: cwd)")
    args = parser.parse_args()
    REPO = args.repo.resolve()
    if not (REPO / ".git").exists():
        sys.exit(f"error: {REPO} is not a git repository")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
