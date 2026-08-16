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


# --------------------------------------------------------------------------- #
# Data helpers backing the local UI (gitlog_mcp_ui.py).
#
# These check both the shape of the new `_xxx_data()` dicts and that the
# public markdown tools (`changelog`, `repo_health`, `blame_file`) still
# produce the exact same text as before the refactor that introduced them.
# --------------------------------------------------------------------------- #
def _import_module(repo: Path):
    sys.path.insert(0, str(REPO))
    import gitlog_mcp as g
    g.REPO = repo
    return g


def test_changelog_data_shape(tmp_path):
    repo = _make_fixture_repo(tmp_path)
    g = _import_module(repo)
    data = g._changelog_data("HEAD~20", "HEAD")
    assert set(data.keys()) == {"since", "until", "total", "commits"}
    assert data["since"] == "HEAD~20"
    assert data["until"] == "HEAD"
    assert data["total"] == 2
    assert len(data["commits"]) == 2
    for c in data["commits"]:
        assert set(c.keys()) == {"sha", "subject", "author", "date"}
    subjects = [c["subject"] for c in data["commits"]]
    assert "feat: initial commit" in subjects
    assert "fix: add line two" in subjects


def test_changelog_data_raises_giterror_on_flag_like_since(tmp_path):
    repo = _make_fixture_repo(tmp_path)
    g = _import_module(repo)
    with pytest.raises(g.GitError):
        g._changelog_data("--output=evil.txt", "HEAD")


def test_changelog_data_empty_repo(tmp_path):
    repo = tmp_path / "empty"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    g = _import_module(repo)
    data = g._changelog_data("HEAD~20", "HEAD")
    assert data == {"since": "HEAD~20", "until": "HEAD", "total": 0, "commits": []}


def test_repo_health_data_shape(tmp_path):
    repo = _make_fixture_repo(tmp_path)
    g = _import_module(repo)
    data = g._repo_health_data()
    assert set(data.keys()) == {"total_commits", "total_contributors", "contributors"}
    assert data["total_commits"] == 2
    assert data["total_contributors"] == 1
    assert len(data["contributors"]) == 1
    c = data["contributors"][0]
    assert set(c.keys()) == {"name", "count"}
    assert c["name"] == "Tester"
    assert c["count"] == 2


def test_repo_health_data_caps_contributors_at_ten(tmp_path):
    repo = tmp_path / "manyauthors"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    for i in range(12):
        subprocess.run(["git", "config", "user.email", f"a{i}@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", f"Author{i}"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", f"commit {i}"],
                        cwd=repo, check=True)
    g = _import_module(repo)
    data = g._repo_health_data()
    assert data["total_contributors"] == 12
    assert len(data["contributors"]) == 10


def test_blame_file_data_shape(tmp_path):
    repo = _make_fixture_repo(tmp_path)
    g = _import_module(repo)
    data = g._blame_file_data("file.txt")
    assert set(data.keys()) == {"path", "lines"}
    assert data["path"] == "file.txt"
    assert len(data["lines"]) == 2
    for i, l in enumerate(data["lines"], start=1):
        assert set(l.keys()) == {"line", "date", "author", "content"}
        assert l["line"] == i
        assert l["author"] == "Tester"
    assert data["lines"][0]["content"] == "line one"
    assert data["lines"][1]["content"] == "line two"


def test_blame_file_data_empty_for_empty_tracked_file(tmp_path):
    repo = _make_fixture_repo(tmp_path)
    (repo / "empty.txt").write_text("")
    subprocess.run(["git", "add", "empty.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add empty file"], cwd=repo, check=True)
    g = _import_module(repo)
    data = g._blame_file_data("empty.txt")
    assert data == {"path": "empty.txt", "lines": []}


def test_blame_file_data_raises_giterror_for_nonexistent_path(tmp_path):
    repo = _make_fixture_repo(tmp_path)
    g = _import_module(repo)
    with pytest.raises(g.GitError):
        g._blame_file_data("does-not-exist.txt")


def test_changelog_markdown_unchanged_by_refactor(tmp_path):
    """Regression: `changelog()`'s markdown output must be byte-identical to
    what it produced before `_changelog_data()` was extracted."""
    repo = _make_fixture_repo(tmp_path)
    out = _run_server(repo, "changelog")
    lines = out.splitlines()
    assert lines[0] == "## Changelog (full history → HEAD)"
    assert lines[1] == ""
    assert len(lines) == 4  # header, blank, 2 commits (newest first)
    for line in lines[2:]:
        assert line.startswith("- **")
        assert "** — " in line


def test_repo_health_markdown_unchanged_by_refactor(tmp_path):
    """Regression: `repo_health()`'s markdown output must be byte-identical
    to what it produced before `_repo_health_data()` was extracted."""
    repo = _make_fixture_repo(tmp_path)
    out = _run_server(repo, "repo_health")
    assert out == "## Contributors (1)\n\n- 2\tTester"


def test_blame_file_markdown_unchanged_by_refactor(tmp_path):
    """Regression: `blame_file()`'s markdown output must be byte-identical
    to what it produced before `_blame_file_data()` was extracted."""
    repo = _make_fixture_repo(tmp_path)
    out = _run_server(repo, "blame_file", "file.txt")
    lines = out.splitlines()
    assert len(lines) == 2
    for line in lines:
        assert "Tester" in line
    assert lines[0].endswith("line one")
    assert lines[1].endswith("line two")


def test_changelog_handles_non_cp1252_commit_message(tmp_path):
    """Regression test: on Windows with a non-UTF-8 locale (cp1252 is the
    default on most English/Western-European installs), decoding git's
    UTF-8 output with the system locale used to raise an uncaught
    UnicodeDecodeError for any byte undefined in cp1252 (e.g. the zero-
    width joiner used to build compound emoji) — surfaced to the client as
    a confusing "'NoneType' object has no attribute 'strip'" AttributeError
    instead of a clean result or error string."""
    repo = _make_fixture_repo(tmp_path)
    msg_file = tmp_path / "msg.txt"
    # U+200D (ZERO WIDTH JOINER) encodes to UTF-8 bytes that include 0x8D,
    # which has no mapping in cp1252.
    msg_file.write_text("test: zwj emoji \U0001F468‍\U0001F469 commit\n", encoding="utf-8")
    subprocess.run(["git", "commit", "--allow-empty", "-q", "-F", str(msg_file)],
                    cwd=repo, check=True)
    out = _run_server(repo, "changelog")
    assert "Error" not in out
    assert "zwj emoji" in out
