"""Basic smoke tests for gitlog-mcp. Run: pytest tests/"""
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
    """Invoke a tool by running the module and calling it via a tiny client stub."""
    # For smoke tests, just verify the module imports and tools are registered.
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
    repo = _make_fiature_repo(tmp_path)
    out = _run_server(repo, "repo_health")
    assert "Contributors" in out