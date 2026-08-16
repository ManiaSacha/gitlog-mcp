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
            encoding="utf-8",
            errors="replace",
            check=True,
            stdin=subprocess.DEVNULL,
            timeout=30,
        )
        return proc.stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise GitError(f"git {args[0]} failed: {exc.stderr.strip()}") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitError(f"git {args[0]} timed out after {exc.timeout:.0f}s.") from exc
    except FileNotFoundError as exc:
        raise GitError("git executable not found on PATH.") from exc


def reject_flag_like(value: str, label: str) -> str | None:
    """Refuse refs/tags that start with '-'.

    Git treats a bare argv token starting with '-' as an option rather than a
    revision (e.g. '--output=../evil.txt' smuggled in as `since`), which can
    turn `git log`/`git show` into an arbitrary-file-write primitive. Real
    git refs and tags never start with '-' (git's own check-ref-format
    forbids it), so any value that does is rejected outright.
    """
    if value.startswith("-"):
        return f"Error: invalid {label} '{value}' — refs/tags cannot start with '-'."
    return None


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
# Data helpers — pure git-to-dict, no markdown formatting.
#
# These back both the MCP tools below (which format the dicts into the same
# markdown they've always returned) and the local UI's JSON API. Errors
# propagate as GitError; callers decide how to present them.
# --------------------------------------------------------------------------- #
def _changelog_data(since: str, until: str) -> dict:
    """Commit range as structured data. Raises GitError on git failure or an
    invalid (flag-like) since/until."""
    err = reject_flag_like(since, "since") or reject_flag_like(until, "until")
    if err:
        # reject_flag_like() already prefixes its message with "Error: " for
        # its other (direct-return) callers; strip that here so the
        # `f"Error: {exc}"` wrapping in changelog() doesn't double it up.
        raise GitError(err.removeprefix("Error: "))

    fmt = "%x00sha=%h%x00subject=%s%x00author=%aN%x00date=%aI"

    # Default range: always use max-count (-n20) instead of a `HEAD~20..HEAD`
    # revision range. Two independent reasons:
    #  - Small/young repos: a `HEAD~20..HEAD` range fails ("unknown revision")
    #    when there are fewer than 20 commits, or (via the two-dot range's
    #    exclusive lower bound) silently drops the root commit.
    #  - Repos with merge commits: `HEAD~20` walks first-parent ancestry only,
    #    so its depth can be shallower than `commit_count()`'s all-reachable
    #    total. A repo can legitimately have >20 total commits while its
    #    first-parent chain is <20 deep, making `HEAD~20` fail to resolve at
    #    all even though there's plenty of history to show.
    # `-n20` sidesteps both: it's topology-agnostic and simply returns the
    # most recent <=20 commits in log order, same as `HEAD~20..HEAD` would in
    # a purely linear history, but well-defined regardless of merge shape.
    if since == "HEAD~20":
        total = commit_count()
        if total == 0:
            return {"since": since, "until": until, "total": 0, "commits": []}
        raw = git("log", "--pretty=format:" + fmt, "-n20")
        commits = [parse_commit(l) for l in raw.splitlines() if l.strip()]
        return {"since": since, "until": until, "total": len(commits), "commits": commits}

    raw = git("log", "--pretty=format:" + fmt, f"{since}..{until}")
    commits = [parse_commit(l) for l in raw.splitlines() if l.strip()]
    return {"since": since, "until": until, "total": len(commits), "commits": commits}


def _repo_health_data() -> dict:
    """Contributor summary as structured data. Raises GitError on git failure."""
    raw = git("shortlog", "-sn", "--all")
    if not raw:
        return {"total_commits": commit_count(), "total_contributors": 0, "contributors": []}
    entries = raw.splitlines()
    contributors = []
    for entry in entries[:10]:
        stripped = entry.strip()
        count_str, _, name = stripped.partition("\t")
        try:
            count = int(count_str.strip())
        except ValueError:
            count = 0
        contributors.append({"name": name, "count": count})
    return {
        "total_commits": commit_count(),
        "total_contributors": len(entries),
        "contributors": contributors,
    }


def _blame_file_data(path: str) -> dict:
    """Line-level blame as structured data. Raises GitError on git failure."""
    # `--` forces `path` to be treated strictly as a pathspec, not an
    # option — without it, a path like '--contents=../secret.txt' makes
    # git blame echo back the contents of an arbitrary file on disk.
    raw = git("blame", "--line-porcelain", "--", path)
    if not raw:
        return {"path": path, "lines": []}
    lines_out, cur = [], {}
    line_no = 0
    for line in raw.splitlines():
        if line.startswith("author "):
            cur["author"] = line.split(" ", 1)[1]
        elif line.startswith("author-time "):
            cur["time"] = datetime.fromtimestamp(
                int(line.split(" ", 1)[1])
            ).strftime("%Y-%m-%d")
        elif line.startswith("\t"):
            line_no += 1
            lines_out.append({
                "line": line_no,
                "date": cur.get("time") or "----------",
                "author": cur.get("author") or "unknown",
                "content": line[1:],
            })
    return {"path": path, "lines": lines_out}


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #
@mcp.tool()
def changelog(since: str = "HEAD~20", until: str = "HEAD") -> str:
    """Generate a grouped changelog for a commit range (e.g. v1.2.0..v1.3.0)."""
    try:
        data = _changelog_data(since, until)
    except GitError as exc:
        return f"Error: {exc}"
    if data["total"] == 0:
        return "No commits found in that range."
    if since == "HEAD~20" and data["total"] <= 20:
        header = f"## Changelog (full history → {until})"
    else:
        header = f"## Changelog ({since} → {until})"
    lines = [header, ""]
    for c in data["commits"]:
        lines.append(f"- **{c.get('subject', '?')}** — {c.get('sha', '?')} "
                     f"({c.get('author', '?')}, {c.get('date', '?')[:10]})")
    return "\n".join(lines)


@mcp.tool()
def analyze_commit(sha: str) -> str:
    """Explain a specific commit's intent and impact."""
    err = reject_flag_like(sha, "sha")
    if err:
        return err
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
        data = _blame_file_data(path)
    except GitError as exc:
        return f"Error: {exc}"
    if not data["lines"]:
        return f"No blame data for '{path}' (file may be empty or untracked)."
    out = []
    for l in data["lines"]:
        out.append(f"{l['date']} {l['author']:<20} {l['content'].strip()}")
    return "\n".join(out)


@mcp.tool()
def release_notes(from_tag: str, to_tag: str) -> str:
    """Draft release notes between two tags."""
    err = reject_flag_like(from_tag, "from_tag") or reject_flag_like(to_tag, "to_tag")
    if err:
        return err
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
        data = _repo_health_data()
    except GitError as exc:
        return f"Error: {exc}"
    if data["total_contributors"] == 0:
        return "## Contributors (0)\n\nNo commits yet."
    lines = [f"## Contributors ({data['total_contributors']})", ""]
    for c in data["contributors"]:
        lines.append(f"- {c['count']}\t{c['name']}")
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
