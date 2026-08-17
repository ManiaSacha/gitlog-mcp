# Security Policy

## Reporting a Vulnerability

**Please do NOT open a public GitHub issue for security vulnerabilities.**

`gitlog-mcp` executes `git` CLI commands with user/LLM-supplied input. While we
harden all subprocess calls (argument injection rejection, `--` separators,
timeouts, no `shell=True`), security issues in this surface area are taken
extremely seriously.

### How to report

Use GitHub's **private vulnerability reporting**:

1. Go to the [Security tab](https://github.com/ManiaSacha/gitlog-mcp/security) of this repository.
2. Click **"Report a vulnerability"**.
3. Fill out the form with as much detail as possible.

You will receive a response within **48 hours** acknowledging the report, and a
fix timeline within **7 days**.

### What qualifies

- Argument injection via any MCP tool parameter (`sha`, `since`, `until`,
  `from_tag`, `to_tag`, `path`, `query`)
- Path traversal or file read/write beyond the target repository
- Denial of service (e.g. crafted input causing unbounded resource consumption)
- Any bypass of the UI server's `Host` header validation or loopback binding

### What does NOT qualify

- Bugs that require local filesystem access beyond what `git` already has
- Issues in the `git` CLI itself (report those upstream)
- Feature requests

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅        |

Only the latest release receives security patches.
