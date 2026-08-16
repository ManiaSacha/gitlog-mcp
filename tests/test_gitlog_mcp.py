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


# --------------------------------------------------------------------------- #
# Security regressions: git argument injection.
#
# `since`/`sha`/tag values are passed to `git` as bare argv tokens. A value
# starting with '-' (e.g. "--output=../evil.txt") is parsed by git as an
# *option* rather than a revision, which can turn `git log`/`git show` into
# an arbitrary-file-write primitive reachable directly from an MCP client.
# --------------------------------------------------------------------------- #

def test_analyze_commit_rejects_flag_like_sha(tmp_path):
    repo = _make_fixture_repo(tmp_path)
    evil_target = tmp_path / "evil.txt"
    out = _run_server(repo, "analyze_commit", f"--output={evil_target}")
    assert "Error" in out
    assert not evil_target.exists()


def test_changelog_rejects_flag_like_since(tmp_path):
    repo = _make_fixture_repo(tmp_path)
    evil_target = tmp_path / "evil2.txt"
    out = _run_server(repo, "changelog", f"--output={evil_target}", "HEAD")
    assert "Error" in out
    assert not evil_target.exists()


def test_changelog_rejects_flag_like_until(tmp_path):
    repo = _make_fixture_repo(tmp_path)
    out = _run_server(repo, "changelog", "HEAD~1", "--force")
    assert "Error" in out


def test_release_notes_rejects_flag_like_tag(tmp_path):
    repo = _make_fixture_repo(tmp_path)
    evil_target = tmp_path / "evil3.txt"
    out = _run_server(repo, "release_notes", f"--output={evil_target}", "HEAD")
    assert "Error" in out
    assert not evil_target.exists()


def test_blame_file_flag_like_path_does_not_leak_or_crash(tmp_path):
    """A path starting with '-' must not be interpreted as a git option.
    The `--` separator forces it to be treated strictly as a pathspec."""
    repo = _make_fixture_repo(tmp_path)
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP SECRET DATA 12345\n")
    out = _run_server(repo, "blame_file", f"--contents={secret}")
    assert "TOP SECRET" not in out
