"""Tests for git_pipeline_agent.py"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _make_fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "fixture"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True)
    (repo / "file.txt").write_text("line one\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "feat: initial commit"], cwd=repo, check=True)
    return repo


def test_pipeline_not_a_git_repo(tmp_path, monkeypatch):
    non_git = tmp_path / "non_git"
    non_git.mkdir()
    monkeypatch.chdir(non_git)

    sys.path.insert(0, str(REPO))
    if "git_pipeline_agent" in sys.modules:
        del sys.modules["git_pipeline_agent"]
    import git_pipeline_agent

    with pytest.raises(SystemExit) as excinfo:
        monkeypatch.setattr(sys, "argv", ["git_pipeline_agent.py"])
        git_pipeline_agent.main()
    assert excinfo.value.code == 1


def test_pipeline_branch_creation(tmp_path, monkeypatch):
    repo = _make_fixture_repo(tmp_path)
    monkeypatch.chdir(repo)

    sys.path.insert(0, str(REPO))
    if "git_pipeline_agent" in sys.modules:
        del sys.modules["git_pipeline_agent"]
    import git_pipeline_agent

    monkeypatch.setattr(sys, "argv", ["git_pipeline_agent.py", "-b", "feat/test-branch"])
    git_pipeline_agent.main()

    branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert branch == "feat/test-branch"


def test_pipeline_add_and_commit(tmp_path, monkeypatch):
    repo = _make_fixture_repo(tmp_path)
    monkeypatch.chdir(repo)

    sys.path.insert(0, str(REPO))
    if "git_pipeline_agent" in sys.modules:
        del sys.modules["git_pipeline_agent"]
    import git_pipeline_agent

    (repo / "new_file.txt").write_text("hello world")

    monkeypatch.setattr(sys, "argv", ["git_pipeline_agent.py", "-m", "feat: add new_file"])
    git_pipeline_agent.main()

    log = subprocess.run(
        ["git", "log", "-1", "--format=%s"],
        cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert log == "feat: add new_file"
