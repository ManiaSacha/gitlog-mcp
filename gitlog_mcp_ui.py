#!/usr/bin/env python3
"""
gitlog-mcp-ui — a local-only, read-only web dashboard for gitlog-mcp.

Serves a tiny single-page UI (embedded, no build step, no framework) plus a
JSON API over the same git-reading helpers gitlog_mcp.py uses for its MCP
tools. Everything is in-process — no shelling out beyond what gitlog_mcp.py
already does, and no filesystem access beyond its existing functions.

Binds to 127.0.0.1 only. There is no --host flag: this is intentionally not
exposable to the network. Every request's Host header is also validated
(must be 127.0.0.1 or localhost) to close the DNS-rebinding gap that a bare
loopback bind doesn't cover on its own.

Run:  python gitlog_mcp_ui.py --repo /path/to/repo [--port 8765]
"""
from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import gitlog_mcp


# --------------------------------------------------------------------------- #
# Embedded static assets
# --------------------------------------------------------------------------- #
INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>gitlog-mcp</title>
<link rel="stylesheet" href="/style.css">
</head>
<body>
<header class="topbar">
  <div class="repo-path" id="repo-path"></div>
  <nav class="tabs" id="tabs">
    <button class="tab" data-tab="changelog">Changelog</button>
    <button class="tab" data-tab="health">Repo Health</button>
    <button class="tab" data-tab="blame">Blame</button>
  </nav>
</header>

<main>
  <div class="error-banner" id="error-banner" hidden></div>

  <section id="view-changelog" class="view">
    <form id="changelog-form" class="controls">
      <label>since <input type="text" id="changelog-since" value="HEAD~20"></label>
      <label>until <input type="text" id="changelog-until" value="HEAD"></label>
      <button type="submit">Go</button>
    </form>
    <div class="status-line" id="changelog-count"></div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>sha</th><th>date</th><th>author</th><th>subject</th></tr></thead>
        <tbody id="changelog-body"></tbody>
      </table>
    </div>
  </section>

  <section id="view-health" class="view" hidden>
    <div class="stat-tiles">
      <div class="stat-tile">
        <div class="stat-value" id="health-total-commits">-</div>
        <div class="stat-label">total commits</div>
      </div>
      <div class="stat-tile">
        <div class="stat-value" id="health-total-contributors">-</div>
        <div class="stat-label">total contributors</div>
      </div>
    </div>
    <ol class="contributor-list" id="contributor-list"></ol>
  </section>

  <section id="view-blame" class="view" hidden>
    <form id="blame-form" class="controls">
      <label>path <input type="text" id="blame-path" placeholder="path/to/file"></label>
      <button type="submit">Go</button>
    </form>
    <div class="table-wrap">
      <table>
        <thead><tr><th>line</th><th>date</th><th>author</th><th>code</th></tr></thead>
        <tbody id="blame-body"></tbody>
      </table>
    </div>
  </section>
</main>

<script src="/app.js"></script>
</body>
</html>
"""

STYLE_CSS = """
:root {
  --bg: #ffffff;
  --bg-alt: #f5f5f7;
  --bg-band: #ececef;
  --fg: #1a1a1e;
  --fg-muted: #6b6b73;
  --border: #d9d9de;
  --accent: #2a5adf;
  --error-bg: #fdecec;
  --error-border: #d33;
  --error-fg: #7a1a1a;
  --bar: #2a5adf33;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #16161a;
    --bg-alt: #1e1e23;
    --bg-band: #232329;
    --fg: #e7e7ea;
    --fg-muted: #9a9aa2;
    --border: #35353d;
    --accent: #6d93ff;
    --error-bg: #3a1414;
    --error-border: #c44;
    --error-fg: #ffb4b4;
    --bar: #6d93ff33;
  }
}

* { box-sizing: border-box; }

body {
  margin: 0;
  font-family: ui-monospace, "Cascadia Code", "SF Mono", Consolas, monospace;
  background: var(--bg);
  color: var(--fg);
  font-size: 13px;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-alt);
  gap: 16px;
  flex-wrap: wrap;
}

.repo-path {
  color: var(--fg-muted);
  overflow-wrap: anywhere;
}

.tabs {
  display: flex;
  gap: 4px;
}

.tab {
  font: inherit;
  background: transparent;
  color: var(--fg-muted);
  border: 1px solid transparent;
  border-radius: 6px;
  padding: 6px 12px;
  cursor: pointer;
  transition: background-color 0.12s ease, color 0.12s ease;
}

.tab:hover {
  background: var(--bg-band);
}

.tab.active {
  color: var(--fg);
  border-color: var(--border);
  background: var(--bg);
}

main {
  padding: 16px;
  max-width: 100%;
}

.view[hidden] { display: none; }

.controls {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.controls label {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--fg-muted);
}

.controls input[type="text"] {
  font: inherit;
  background: var(--bg-alt);
  color: var(--fg);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 5px 8px;
  min-width: 160px;
}

.controls button {
  font: inherit;
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: 4px;
  padding: 6px 14px;
  cursor: pointer;
}

.controls button:hover { filter: brightness(1.08); }

.status-line {
  color: var(--fg-muted);
  margin-bottom: 8px;
}

.error-banner {
  background: var(--error-bg);
  color: var(--error-fg);
  border-left: 4px solid var(--error-border);
  padding: 10px 14px;
  margin-bottom: 16px;
  border-radius: 2px;
}

.error-banner[hidden] { display: none; }

.table-wrap {
  overflow-x: auto;
  max-width: 100%;
  border: 1px solid var(--border);
  border-radius: 6px;
}

table {
  border-collapse: collapse;
  width: 100%;
  min-width: 640px;
}

thead th {
  position: sticky;
  top: 0;
  background: var(--bg-alt);
  text-align: left;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  color: var(--fg-muted);
  font-weight: 600;
}

tbody td {
  padding: 6px 10px;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}

tbody tr:last-child td { border-bottom: none; }

td.code, .code-cell {
  white-space: pre;
  font-family: ui-monospace, "Cascadia Code", "SF Mono", Consolas, monospace;
}

tr.band-a { background: var(--bg); }
tr.band-b { background: var(--bg-band); }

.stat-tiles {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
}

.stat-tile {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px 20px;
  background: var(--bg-alt);
  min-width: 140px;
}

.stat-value {
  font-size: 26px;
  font-weight: 700;
}

.stat-label {
  color: var(--fg-muted);
  margin-top: 4px;
}

.contributor-list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-width: 640px;
}

.contributor-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
}

.contributor-name {
  min-width: 180px;
  overflow-wrap: anywhere;
}

.contributor-count {
  min-width: 40px;
  text-align: right;
  color: var(--fg-muted);
}

.contributor-bar-track {
  flex: 1;
  height: 10px;
  background: var(--bg-band);
  border-radius: 4px;
  overflow: hidden;
}

.contributor-bar {
  height: 100%;
  background: var(--bar);
}

.loading {
  color: var(--fg-muted);
  padding: 8px 0;
}
"""

APP_JS = """
(function () {
  "use strict";

  var TABS = ["changelog", "health", "blame"];
  var blameLoaded = false;

  function $(id) { return document.getElementById(id); }

  function showError(msg) {
    var banner = $("error-banner");
    banner.textContent = msg;
    banner.hidden = false;
  }

  function clearError() {
    var banner = $("error-banner");
    banner.hidden = true;
    banner.textContent = "";
  }

  function setTab(name) {
    if (TABS.indexOf(name) === -1) name = "changelog";
    TABS.forEach(function (t) {
      $("view-" + t).hidden = t !== name;
    });
    var buttons = document.querySelectorAll(".tab");
    buttons.forEach(function (b) {
      b.classList.toggle("active", b.dataset.tab === name);
    });
    location.hash = name;
    if (name === "health") loadHealth();
    if (name === "changelog" && !changelogLoaded) loadChangelog();
  }

  function escapeHtml(s) {
    var div = document.createElement("div");
    div.textContent = s == null ? "" : String(s);
    return div.innerHTML;
  }

  // ---- Changelog -----------------------------------------------------
  var changelogLoaded = false;
  var healthLoaded = false;

  function loadChangelog() {
    var since = $("changelog-since").value.trim() || "HEAD~20";
    var until = $("changelog-until").value.trim() || "HEAD";
    clearError();
    $("changelog-count").textContent = "Loading…";
    $("changelog-body").innerHTML = "";
    fetch("/api/changelog?since=" + encodeURIComponent(since) + "&until=" + encodeURIComponent(until))
      .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, data: data }; }); })
      .then(function (res) {
        changelogLoaded = true;
        if (!res.ok) {
          $("changelog-count").textContent = "";
          showError(res.data.error || "Unknown error");
          return;
        }
        var data = res.data;
        $("changelog-count").textContent = data.total + " commits";
        var rows = data.commits.map(function (c) {
          return "<tr>" +
            "<td>" + escapeHtml(c.sha) + "</td>" +
            "<td>" + escapeHtml((c.date || "").slice(0, 10)) + "</td>" +
            "<td>" + escapeHtml(c.author) + "</td>" +
            "<td>" + escapeHtml(c.subject) + "</td>" +
            "</tr>";
        }).join("");
        $("changelog-body").innerHTML = rows;
      })
      .catch(function (err) {
        $("changelog-count").textContent = "";
        showError(String(err));
      });
  }

  // ---- Repo health -----------------------------------------------------
  function loadHealth() {
    if (healthLoaded) return;
    clearError();
    $("health-total-commits").textContent = "…";
    $("health-total-contributors").textContent = "…";
    $("contributor-list").innerHTML = "<li class=\\"loading\\">Loading…</li>";
    fetch("/api/repo_health")
      .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, data: data }; }); })
      .then(function (res) {
        if (!res.ok) {
          $("contributor-list").innerHTML = "";
          showError(res.data.error || "Unknown error");
          return;
        }
        healthLoaded = true;
        var data = res.data;
        $("health-total-commits").textContent = data.total_commits;
        $("health-total-contributors").textContent = data.total_contributors;
        var max = Math.max.apply(null, data.contributors.map(function (c) { return c.count; }).concat([1]));
        $("contributor-list").innerHTML = data.contributors.map(function (c) {
          var pct = Math.round((c.count / max) * 100);
          return "<li class=\\"contributor-row\\">" +
            "<span class=\\"contributor-name\\">" + escapeHtml(c.name) + "</span>" +
            "<span class=\\"contributor-bar-track\\"><span class=\\"contributor-bar\\" style=\\"width:" + pct + "%\\"></span></span>" +
            "<span class=\\"contributor-count\\">" + c.count + "</span>" +
            "</li>";
        }).join("");
      })
      .catch(function (err) {
        $("contributor-list").innerHTML = "";
        showError(String(err));
      });
  }

  // ---- Blame -----------------------------------------------------
  function loadBlame() {
    var path = $("blame-path").value.trim();
    if (!path) return;
    clearError();
    $("blame-body").innerHTML = "<tr><td colspan=\\"4\\" class=\\"loading\\">Loading…</td></tr>";
    fetch("/api/blame?path=" + encodeURIComponent(path))
      .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, data: data }; }); })
      .then(function (res) {
        blameLoaded = true;
        if (!res.ok) {
          $("blame-body").innerHTML = "";
          showError(res.data.error || "Unknown error");
          return;
        }
        var data = res.data;
        var lastAuthor = null;
        var band = "band-a";
        var rows = data.lines.map(function (l) {
          if (l.author !== lastAuthor) {
            band = band === "band-a" ? "band-b" : "band-a";
            lastAuthor = l.author;
          }
          return "<tr class=\\"" + band + "\\">" +
            "<td>" + escapeHtml(l.line) + "</td>" +
            "<td>" + escapeHtml(l.date) + "</td>" +
            "<td>" + escapeHtml(l.author) + "</td>" +
            "<td class=\\"code\\">" + escapeHtml(l.content) + "</td>" +
            "</tr>";
        }).join("");
        $("blame-body").innerHTML = rows || "<tr><td colspan=\\"4\\">No blame data.</td></tr>";
      })
      .catch(function (err) {
        $("blame-body").innerHTML = "";
        showError(String(err));
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    $("repo-path").textContent = document.body.dataset.repo || "";

    document.querySelectorAll(".tab").forEach(function (b) {
      b.addEventListener("click", function () { setTab(b.dataset.tab); });
    });

    $("changelog-form").addEventListener("submit", function (e) {
      e.preventDefault();
      loadChangelog();
    });

    $("blame-form").addEventListener("submit", function (e) {
      e.preventDefault();
      loadBlame();
    });

    var initial = location.hash.replace("#", "") || "changelog";
    setTab(initial);
    loadChangelog();
  });
})();
"""


# --------------------------------------------------------------------------- #
# HTTP handler
# --------------------------------------------------------------------------- #
ALLOWED_HOSTNAMES = {"127.0.0.1", "localhost"}


class Handler(BaseHTTPRequestHandler):
    server_version = "gitlog-mcp-ui/0.1"

    def log_message(self, fmt, *args):  # quieter default logging
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _host_header_is_allowed(self) -> bool:
        """Reject requests whose Host header isn't 127.0.0.1/localhost.

        The server socket is bound to 127.0.0.1 only, but that alone doesn't
        stop DNS rebinding: an attacker-controlled domain with a low-TTL DNS
        record can resolve to 127.0.0.1 after a victim's browser has already
        loaded a page from it, letting same-origin fetch() calls reach this
        server with an arbitrary Host header. Validating Host on every
        request is the standard mitigation for loopback dev servers.
        """
        host_header = self.headers.get("Host", "")
        hostname = host_header.rsplit(":", 1)[0] if ":" in host_header else host_header
        return hostname in ALLOWED_HOSTNAMES

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        # Explicitly no CORS headers — this server is local-only by design.
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def do_GET(self) -> None:
        if not self._host_header_is_allowed():
            self._send_json(403, {"error": "Forbidden: invalid Host header."})
            return

        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/":
            html = INDEX_HTML.replace(
                '<body>', '<body data-repo="%s">' % _escape_attr(str(gitlog_mcp.REPO))
            )
            self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
            return

        if path == "/style.css":
            self._send(200, STYLE_CSS.encode("utf-8"), "text/css; charset=utf-8")
            return

        if path == "/app.js":
            self._send(200, APP_JS.encode("utf-8"), "application/javascript; charset=utf-8")
            return

        if path == "/api/changelog":
            since = query.get("since", ["HEAD~20"])[0]
            until = query.get("until", ["HEAD"])[0]
            try:
                data = gitlog_mcp._changelog_data(since, until)
            except gitlog_mcp.GitError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            self._send_json(200, data)
            return

        if path == "/api/repo_health":
            try:
                data = gitlog_mcp._repo_health_data()
            except gitlog_mcp.GitError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            self._send_json(200, data)
            return

        if path == "/api/blame":
            file_path = query.get("path", [""])[0]
            if not file_path:
                self._send_json(400, {"error": "Missing required query param 'path'."})
                return
            try:
                data = gitlog_mcp._blame_file_data(file_path)
            except gitlog_mcp.GitError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            if not data["lines"]:
                self._send_json(
                    400,
                    {"error": f"No blame data for '{file_path}' (file may be empty or untracked)."},
                )
                return
            self._send_json(200, data)
            return

        self._send_json(404, {"error": "Not found."})


def _escape_attr(s: str) -> str:
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


# --------------------------------------------------------------------------- #
# Entrypoint
# --------------------------------------------------------------------------- #
def main() -> None:
    parser = argparse.ArgumentParser(description="gitlog-mcp-ui — local git history dashboard")
    parser.add_argument("--repo", type=Path, default=Path.cwd(),
                        help="Path to the git repository to serve (default: cwd)")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind (default: 8765)")
    args = parser.parse_args()

    gitlog_mcp.REPO = args.repo.resolve()
    if not (gitlog_mcp.REPO / ".git").exists():
        sys.exit(f"error: {gitlog_mcp.REPO} is not a git repository")

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
