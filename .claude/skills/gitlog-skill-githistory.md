---
name: analyze-git-history
description: Analyze a repository's git history to explain changes, attribute blame, find contributors, and assess repo health. Use when the user asks who changed what, why a change happened, or for a repo overview.
---

# Analyze Git History

Use this skill to answer questions about a repo's history with grounded facts from `git`.

## When to use
- "Who wrote this line / introduced this bug?"
- "Why did this change happen?"
- "What's the state of this repo?"

## Commands
- **Blame a file:**
  ```bash
  git blame --line-porcelain <file>
  ```
- **Explain a commit:**
  ```bash
  git show --stat <sha>
  ```
- **Top contributors:**
  ```bash
  git shortlog -sn --all
  ```
- **Recent activity:**
  ```bash
  git log --oneline -20
  ```

## Output style
Always cite the actual SHA, author, and date. Never guess or invent history — if the data isn't there, say so. Distinguish "what the commit says" from "what it likely did" when the message is ambiguous.