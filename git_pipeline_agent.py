#!/usr/bin/env python3
"""
git_pipeline_agent.py — Automation tool for git operations.
Creates branches, stages files, commits with clean messages, and pushes to remote.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run_git(args: list[str], cwd: Path = Path.cwd()) -> str:
    """Run a git command safely and return stdout."""
    try:
        proc = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            cwd=str(cwd)
        )
        return proc.stdout.strip()
    except subprocess.CalledProcessError as exc:
        print(f"Error running 'git {' '.join(args)}':\n{exc.stderr.strip()}", file=sys.stderr)
        sys.exit(exc.returncode or 1)
    except FileNotFoundError:
        print("Error: 'git' executable not found on PATH.", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Git Pipeline Agent automation helper")
    parser.add_argument("-b", "--branch", help="Name of the new branch to create/checkout")
    parser.add_argument("-m", "--message", help="Commit message (Conventional Commit style recommended)")
    parser.add_argument("-a", "--add", nargs="*", help="Specific files/folders to stage (defaults to modified/tracked files if not specified)")
    parser.add_argument("-p", "--push", action="store_true", help="Push the branch to origin after commit")
    args = parser.parse_args()

    # Verify we are in a git repo
    cwd = Path.cwd()
    found = False
    for parent in [cwd, *cwd.parents]:
        if (parent / ".git").exists():
            found = True
            break
    if not found:
        print("Error: Not a git repository (or any of the parent directories).", file=sys.stderr)
        sys.exit(1)

    # 1. Branch checkout/creation
    if args.branch:
        print(f"--> Checking out/creating branch: {args.branch}")
        # Check if branch exists
        branches = run_git(["branch", "--list", args.branch])
        if branches:
            print(f"Branch '{args.branch}' already exists. Switching to it...")
            run_git(["checkout", args.branch])
        else:
            print(f"Creating new branch '{args.branch}'...")
            run_git(["checkout", "-b", args.branch])

    # 2. Staging files
    if args.add is not None:
        if len(args.add) == 0:
            print("--> Staging all modified/untracked changes (git add .)...")
            run_git(["add", "."])
        else:
            print(f"--> Staging specific files: {', '.join(args.add)}")
            run_git(["add", *args.add])
    elif args.message:
        # If message is provided but --add wasn't, let's stage all changes (default convenience)
        print("--> Staging all modified/untracked changes (git add .)...")
        run_git(["add", "."])

    # 3. Committing
    if args.message:
        print(f"--> Committing changes with message: '{args.message}'")
        # Check if anything is modified or staged
        status = run_git(["status", "--porcelain"])
        diff_staged = run_git(["diff", "--cached", "--name-only"])
        if not status and not diff_staged:
            print("No changes staged or modified. Nothing to commit.")
        else:
            run_git(["commit", "-m", args.message])

    # 4. Pushing
    if args.push:
        # Get active branch name
        current_branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        print(f"--> Pushing branch '{current_branch}' to origin...")
        run_git(["push", "-u", "origin", current_branch])
        print("Push complete!")


if __name__ == "__main__":
    main()
