# Releasing gitlog-mcp

This document describes how to cut a release of `gitlog-mcp`, including the
**one-time manual setup on pypi.org** that must be done before the publish
workflow can work at all.

`gitlog-mcp` follows [SemVer](https://semver.org/):

- **MAJOR** — breaking API/tool changes
- **MINOR** — new tools or features (backward compatible)
- **PATCH** — bug fixes and docs

Keep releases small and frequent. Each release is a chance to get fresh eyes
on the project.

---

## One-time setup: PyPI Trusted Publishing (do this before the first release)

Publishing is done via [`.github/workflows/publish.yml`](.github/workflows/publish.yml),
which uses PyPI's **Trusted Publishing** (OIDC) instead of a long-lived
`PYPI_API_TOKEN` secret. This means there is no API token stored anywhere in
the repo or GitHub Actions secrets — GitHub's OIDC identity for this specific
workflow run is exchanged for a short-lived PyPI upload credential at publish
time.

**This requires a manual, one-time step on pypi.org that only the project
owner (an actual human with a PyPI account) can perform — it cannot be done
from a CI job, a script, or by an agent.** Nobody orchestrating this from
outside pypi.org's own UI can complete it on your behalf.

Steps (do this once, before pushing the first `v*` tag):

1. Log in to [pypi.org](https://pypi.org) with the account that will own the
   `gitlog-mcp` project (create an account first if you don't have one).
2. Check whether the project name `gitlog-mcp` is already registered:
   - If it's free, you don't need to create it manually — PyPI supports
     registering a brand-new project's *first* release via trusted
     publishing, using a "pending publisher".
   - **Before this step**, go to the repo's **Settings → Environments** and
     create an environment named `pypi` with **required reviewers**
     configured. `publish.yml` already targets this environment
     (`environment: pypi`). For a solo maintainer this isn't protection
     against a second, untrusted collaborator — it's a deliberate manual
     checkpoint before an irreversible action (a public PyPI publish) goes
     out, catching things like an accidental or premature tag push. Worth
     the one extra click even solo.
   - Go to **your PyPI account → Publishing** (or directly:
     https://pypi.org/manage/account/publishing/) and add a **new pending
     publisher** with:
     - **PyPI project name**: `gitlog-mcp`
     - **Owner**: `ManiaSacha`
     - **Repository name**: `gitlog-mcp`
     - **Workflow filename**: `publish.yml`
     - **Environment name**: `pypi` — must exactly match the GitHub
       Environment name from the step above.
   - If the project already exists on PyPI (e.g. you or someone already
     claimed the name), go to the project's **Settings → Publishing** page
     instead and add the same trusted publisher there.
3. Save. That's it — no secrets to copy anywhere. The very first tag push
   that triggers `publish.yml` will use this pending publisher to claim the
   project and publish `0.1.0` (or whatever version is tagged).

If the trusted publisher config (owner/repo/workflow filename/environment)
doesn't match exactly what GitHub Actions presents in its OIDC token, the
publish step will fail with an authentication error — double-check all four
fields if that happens.

**Recommended second gate:** restrict who can create `v*` tags at all.
Repo **Settings → Tags → Rulesets** lets you add a ruleset limiting tag
creation matching `v*` to maintainers only. Combined with the required
reviewer on the `pypi` environment, this means a rogue or compromised
collaborator token can't both create the triggering tag *and* approve the
publish.

---

## Release checklist

1. **Confirm all target PRs merged and tests green.**
   Check that CI (pytest across supported Python versions) is passing on
   `main` for the commit you're about to release.

2. **Security review passed for this release.**
   Re-read any changes touching subprocess/`git` invocation, argument
   handling, or file I/O since the last release. gitlog-mcp shells out to
   `git` with user/LLM-supplied input, so this is not optional — see
   `ee29ad1` and `ca38781` in the git history for the kind of issues to
   watch for (argument injection, encoding bugs).

3. **Update `pyproject.toml` version.**
   Bump the `version` field under `[project]` following SemVer. This is a
   deliberate, explicit step — never automated as part of routine tooling
   changes.

4. **Generate changelog.**
   Use the `changelog` tool / skill (`.claude/skills/gitlog-skill-changelog.md`)
   to produce a grouped changelog for the range since the last tag (or since
   the beginning, for the first release). Move the relevant entries from
   `CHANGELOG.md`'s `[Unreleased]` section into a new dated section:

   ```
   ## [v1.1.0] - 2026-08-15
   ### Added
   - ...
   ### Fixed
   - ...
   ### Changed
   - ...
   ```

5. **Update README if behavior changed.**
   In particular, once the first release is actually published, remove the
   "not yet on PyPI — install from source" caveat from `README.md`'s Quick
   start section, since `pip install gitlog-mcp` will then really work.

6. **(Optional) Test the build locally before tagging.**
   `python -m build` is not a project dependency (runtime or test) — it's
   only needed in CI and for this kind of manual local sanity check. Install
   it on demand:

   ```bash
   python -m pip install "build>=1.0"
   python -m build
   ```

   This produces `dist/*.whl` and `dist/*.tar.gz`. Sanity-check the sdist
   contents (`tar tzf dist/gitlog_mcp-*.tar.gz`) to make sure nothing
   unexpected is included/excluded, then delete `dist/` and `build/` before
   tagging — the CI workflow builds fresh anyway.

7. **Tag and push.**

   ```bash
   git tag vX.Y.Z
   git push --tags
   ```

   Pushing the tag triggers `.github/workflows/publish.yml`, which builds
   the sdist/wheel and publishes to PyPI via Trusted Publishing. Watch the
   Actions run to confirm it succeeds — if the trusted publisher isn't
   configured correctly (see above), it will fail at the publish step, not
   before.

8. **Write GitHub Release notes.**
   Grouped the same way as the changelog: Features / Fixes / Docs. Create
   the release from the pushed tag in the GitHub UI, or with:

   ```bash
   gh release create vX.Y.Z --title vX.Y.Z --notes-file <path-to-notes>
   ```

9. **Announce.**
   Relevant topic tags, socials, wherever the project's audience is.

---

## Known deferred item: SPDX license format

`pyproject.toml` currently declares `license = { text = "MIT" }` plus a
`"License :: OSI Approved :: MIT License"` classifier — the older,
still-fully-supported format. Setuptools' newer PEP 639 SPDX string format
(`license = "MIT"` + `license-files = [...]`, no classifier) was tried and
reverted: it requires a newer setuptools than the `<76` upper bound this
project intentionally pins (see the security review behind that cap, above).
Setuptools doesn't *require* the new format until 77 (~Feb 2027), so this is
safe to leave as-is for now. Revisit when deliberately bumping the
`setuptools` upper bound — don't change the license format and the version
cap in the same change without rebuilding and running `twine check` to
confirm they're still compatible (they aren't, today).
