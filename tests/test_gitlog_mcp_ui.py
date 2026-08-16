"""HTTP-level smoke tests for gitlog_mcp_ui.py. Run: pytest"""
import json
import socket
import subprocess
import sys
import threading
import urllib.request
import urllib.error
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _make_fixture_repo(tmp_path: Path) -> Path:
    """Create a tiny git repo with a couple of commits (mirrors the fixture
    in test_gitlog_mcp.py)."""
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


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def live_server(tmp_path):
    """Start a real ThreadingHTTPServer against a fixture repo on an
    ephemeral port, and tear it down after the test."""
    sys.path.insert(0, str(REPO))
    import gitlog_mcp as g
    import gitlog_mcp_ui as ui

    repo = _make_fixture_repo(tmp_path)
    g.REPO = repo

    port = _free_port()
    server = ui.ThreadingHTTPServer(("127.0.0.1", port), ui.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}", repo
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _get(url: str):
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_index_serves_html(live_server):
    base, _ = live_server
    with urllib.request.urlopen(base + "/", timeout=10) as resp:
        assert resp.status == 200
        assert "text/html" in resp.headers.get("Content-Type", "")
        body = resp.read().decode("utf-8")
        assert "<title>gitlog-mcp</title>" in body


def test_style_and_app_js_served(live_server):
    base, _ = live_server
    with urllib.request.urlopen(base + "/style.css", timeout=10) as resp:
        assert resp.status == 200
        assert "text/css" in resp.headers.get("Content-Type", "")
    with urllib.request.urlopen(base + "/app.js", timeout=10) as resp:
        assert resp.status == 200
        assert "javascript" in resp.headers.get("Content-Type", "")


def test_no_cors_header_present(live_server):
    base, _ = live_server
    with urllib.request.urlopen(base + "/api/repo_health", timeout=10) as resp:
        assert "Access-Control-Allow-Origin" not in resp.headers


def test_api_changelog_default_range(live_server):
    base, _ = live_server
    status, data = _get(base + "/api/changelog")
    assert status == 200
    assert set(data.keys()) == {"since", "until", "total", "commits"}
    assert data["total"] == 2
    subjects = [c["subject"] for c in data["commits"]]
    assert "feat: initial commit" in subjects


def test_api_changelog_rejects_flag_like_since(live_server):
    base, _ = live_server
    status, data = _get(base + "/api/changelog?since=--output=evil.txt&until=HEAD")
    assert status == 400
    assert "error" in data


def test_api_repo_health(live_server):
    base, _ = live_server
    status, data = _get(base + "/api/repo_health")
    assert status == 200
    assert set(data.keys()) == {"total_commits", "total_contributors", "contributors"}
    assert data["total_commits"] == 2
    assert data["total_contributors"] == 1
    assert data["contributors"][0]["name"] == "Tester"


def test_api_blame(live_server):
    base, _ = live_server
    status, data = _get(base + "/api/blame?path=file.txt")
    assert status == 200
    assert data["path"] == "file.txt"
    assert len(data["lines"]) == 2
    assert data["lines"][0]["line"] == 1
    assert data["lines"][0]["content"] == "line one"


def test_api_blame_missing_path_param(live_server):
    base, _ = live_server
    status, data = _get(base + "/api/blame")
    assert status == 400
    assert "error" in data


def test_api_blame_error_for_nonexistent_path(live_server):
    base, _ = live_server
    status, data = _get(base + "/api/blame?path=does-not-exist.txt")
    assert status == 400
    assert "error" in data


def test_api_blame_no_data_for_empty_tracked_file(live_server):
    base, repo = live_server
    (repo / "empty.txt").write_text("")
    subprocess.run(["git", "add", "empty.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add empty file"], cwd=repo, check=True)
    status, data = _get(base + "/api/blame?path=empty.txt")
    assert status == 400
    assert "No blame data" in data["error"]


def _get_with_host(url: str, host_header: str):
    req = urllib.request.Request(url, headers={"Host": host_header})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_spoofed_host_header_is_rejected(live_server):
    """Regression test for a DNS-rebinding gap: binding to 127.0.0.1 alone
    doesn't stop a browser page served from an attacker-controlled domain
    (with a low-TTL DNS record pointing at 127.0.0.1) from reaching this
    server with an arbitrary Host header. The server must validate Host on
    every request, not just the socket bind address."""
    base, _ = live_server
    port = base.rsplit(":", 1)[1]
    status, data = _get_with_host(base + "/api/repo_health", f"evil.attacker.com:{port}")
    assert status == 403
    assert "error" in data


def test_legitimate_host_headers_are_allowed(live_server):
    base, _ = live_server
    port = base.rsplit(":", 1)[1]
    status, _ = _get_with_host(base + "/api/repo_health", f"127.0.0.1:{port}")
    assert status == 200
    status, _ = _get_with_host(base + "/api/repo_health", f"localhost:{port}")
    assert status == 200


def test_api_changelog_default_range_with_shallow_first_parent_history(live_server, tmp_path):
    """Regression test: changelog()'s default range used to build a
    `HEAD~20..HEAD` revision range, which fails to resolve when the
    first-parent chain is shorter than 20 commits even though the repo has
    more than 20 commits reachable overall (merge commits can do this: they
    add reachable history without deepening first-parent ancestry). This
    repro mirrors that shape: a short first-parent chain merges in a longer
    side branch, so total commits > 20 but first-parent depth < 20."""
    base, repo = live_server  # repo already has 2 commits from the fixture

    main_branch = subprocess.run(
        ["git", "symbolic-ref", "--short", "HEAD"], cwd=repo,
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    for i in range(3):
        (repo / "file.txt").write_text(f"main line {i}\n")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", f"main commit {i}"], cwd=repo, check=True)

    subprocess.run(["git", "checkout", "-q", "-b", "side"], cwd=repo, check=True)
    for i in range(20):
        (repo / "side.txt").write_text(f"side line {i}\n")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", f"side commit {i}"], cwd=repo, check=True)

    subprocess.run(["git", "checkout", "-q", main_branch], cwd=repo, check=True)
    subprocess.run(["git", "merge", "-q", "--no-ff", "-m", "merge side into main", "side"],
                    cwd=repo, check=True)

    total = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"], cwd=repo,
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    first_parent_depth = subprocess.run(
        ["git", "rev-list", "--count", "--first-parent", "HEAD"], cwd=repo,
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert int(total) > 20, "fixture setup didn't produce >20 total commits"
    assert int(first_parent_depth) < 20, "fixture setup didn't produce a shallow first-parent chain"

    status, data = _get(base + "/api/changelog")
    assert status == 200, f"expected 200, got {status}: {data}"
    assert data["total"] == 20
    assert len(data["commits"]) == 20
