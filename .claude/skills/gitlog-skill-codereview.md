---
name: review-code
description: Review code changes for correctness, safety, and the gitlog-mcp single-file philosophy. Use before merging any PR or committing changes.
---

# Review Code

Use this skill to review code changes against gitlog-mcp's standards.

## Checklist
1. **Correctness** — does it parse git output reliably?
2. **Safety** — arg-list subprocess only; no `shell=True`; no path traversal.
3. **Error handling** — clean failure messages, no tracebacks.
4. **Readability** — fits the single-file, read-in-an-afternoon philosophy.
5. **Consistency** — follows the GitRunner → parse → output pattern.

## Process
1. Read the diff carefully.
2. Run the affected tool against a real repo to verify.
3. Report: **Good / Issues** with severity (Critical/High/Med/Low) and location.
4. Suggest the minimal fix — never rewrite for the sake of it.

## Rule
Never approve a change that introduces a shell-injection risk or breaks the single-file constraint without strong justification.