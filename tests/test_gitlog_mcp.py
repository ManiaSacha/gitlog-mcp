"""Basic smoke tests for gitlog-mcp. Run: pytest"""
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _make_fixture_repo(tmp_path: Path) -> Path:
    """Create a tiny git repo with a couple of commits."""
    repo = tmp_path / "fixture"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True)
    (repo / "file.txt").write_text("line one\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "feat: initial commit"], cwd=repo, check=True)
    (repo / "file.txt").write_text("line one\nline two\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fix: add line two"], cwd=repo, check=True)
    return repo


def _run_server(repo: Path, tool: str, *args: str) -> str:
    """Invoke a tool by importing the module directly and calling the
    underlying function (FastMCP's @mcp.tool() decorator returns the
    original callable, so this works without spinning up a real MCP
    client/transport)."""
    sys.path.insert(0, str(REPO))
    import gitlog_mcp as g
    g.REPO = repo
    fn = getattr(g, tool)
    return fn(*args)


def test_changelog(tmp_path):
    repo = _make_fixture_repo(tmp_path)
    out = _run_server(repo, "changelog")
    assert "Changelog" in out
    assert "initial commit" in out


def test_analyze_commit(tmp_path):
    repo = _make_fixture_repo(tmp_path)
    sha = subprocess.run(
        ["git", "log", "--format=%h", "-1"], cwd=repo,
        capture_output=True, text=True, check=True
    ).stdout.strip()
    out = _run_server(repo, "analyze_commit", sha)
    assert "Subject" in out


def test_repo_health(tmp_path):
    repo = _make_fixture_repo(tmp_path)
    out = _run_server(repo, "repo_health")
    assert "Contributors" in out


def test_repo_health_empty_repo(tmp_path):
    """repo_health should not crash on a repo with zero commits."""
    repo = tmp_path / "empty"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    out = _run_server(repo, "repo_health")
    assert "Error" not in out
    assert "Contributors (0)" in out


def test_changelog_small_repo_does_not_crash(tmp_path):
    """Regression test: a repo with fewer than 20 commits used to crash
    changelog() because the default range `HEAD~20..HEAD` referenced a
    revision that doesn't exist yet."""
    repo = _make_fixture_repo(tmp_path)  # only 2 commits
    out = _run_server(repo, "changelog")
    assert "Error" not in out
    assert "Changelog" in out


def test_blame_file(tmp_path):
    repo = _make_fixture_repo(tmp_path)
    out = _run_server(repo, "blame_file", "file.txt")
    assert "Error" not in out
    assert "line one" in out


def test_search_commits_no_match(tmp_path):
    repo = _make_fixture_repo(tmp_path)
    out = _run_server(repo, "search_commits", "definitely-not-a-real-query")
    assert "No commits matched" in out


def test_release_notes_no_commits(tmp_path):
    repo = _make_fixture_repo(tmp_path)
    subprocess.run(["git", "tag", "v1.0.0"], cwd=repo, check=True)
    out = _run_server(repo, "release_notes", "v1.0.0", "v1.0.0")
    assert "No commits found" in out
