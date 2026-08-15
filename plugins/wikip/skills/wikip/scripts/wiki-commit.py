"""Commit wiki changes directly on the wikis repo's main branch.

The wikis repo (`wikis/`) is a SEPARATE git repo nested inside the project
repo. This script always operates on that nested repo and refuses to run
against the outer project repo. The default resolves `<cwd's git toplevel>/wikis`;
pass --repo when the host project keeps its vaults elsewhere.

One ingest -> one commit on the base branch (default: main). An optional
pathspec scopes a commit to a single vault, so two ingests sitting in the
working tree at once can each become their own commit:

    wiki-commit.py -m "feat(corpus): ingest <source> into agentic-ai" -- agentic-ai
    wiki-commit.py -m "feat(corpus): ingest <source> into ai-strategy" -- ai-strategy

Each ingest is already a single atomic commit, so `git log --oneline` reads
one line per ingest and `git revert <sha>` undoes a whole ingest — no merge
bubbles needed. Does NOT push by default (pass --push).

Usage:
  uv run python3 "${CLAUDE_PLUGIN_ROOT}"/skills/wikip/scripts/wiki-commit.py \\
      -m "feat(corpus): ingest <source-title> into <vault>" [-- <pathspec>]
  # optional: --repo <path-to-wikis> --base <branch> --push
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command scoped to `repo` with `git -C`."""
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def toplevel(path: Path) -> Path | None:
    """git repo toplevel containing `path`, or None if not a repo."""
    try:
        out = git(path, "rev-parse", "--show-toplevel")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return Path(out.stdout.strip()) if out.returncode == 0 else None


def fail(msg: str) -> int:
    print(f"wiki-commit: {msg}", file=sys.stderr)
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-m", "--message", required=True,
                    help="commit message for the ingest")
    ap.add_argument("--repo", type=Path, default=None,
                    help="path to the wikis repo (default: <project-root>/wikis)")
    ap.add_argument("--base", default="main",
                    help="branch to commit on (default: main)")
    ap.add_argument("--push", action="store_true",
                    help="push the base branch to origin after committing (default: no)")
    ap.add_argument("paths", nargs="*",
                    help="optional pathspec to scope this commit to (e.g. `-- agentic-ai`); "
                         "default: all changes in the repo")
    args = ap.parse_args()

    # --- resolve the OUTER (project) repo from the invoking directory ---
    # (cwd, not this script's location: as a plugin the script lives under
    # ~/.claude/plugins/, which says nothing about the project being worked on)
    outer = toplevel(Path.cwd())

    # --- resolve the wikis repo ---
    if args.repo is not None:
        repo_arg = args.repo.resolve()
    elif outer is not None:
        repo_arg = outer / "wikis"
    else:
        repo_arg = Path.cwd() / "wikis"

    repo = toplevel(repo_arg)
    if repo is None:
        return fail(f"{repo_arg} is not inside a git repo (is the wikis repo present?)")

    # --- SAFETY: must be the nested wikis repo, never the project repo ---
    if outer is not None and repo == outer:
        return fail(
            f"refusing to run — resolved to the project repo ({repo}), not the nested "
            f"wikis repo. Point --repo at the wikis directory."
        )

    # --- must be on the base branch ---
    current = git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if current != args.base:
        return fail(
            f"expected to be on '{args.base}' in {repo}, but on '{current}'. "
            f"Switch to {args.base} (or pass --base {current}) first."
        )

    # --- anything to commit (within the pathspec, if given)? ---
    pathspec = (["--", *args.paths] if args.paths else [])
    status = git(repo, "status", "--porcelain", *pathspec).stdout
    if not status.strip():
        scope = f" under {args.paths}" if args.paths else ""
        print(f"wiki-commit: nothing to commit{scope} — {repo} working tree is clean.")
        return 0

    changed = len([ln for ln in status.splitlines() if ln.strip()])
    print(f"wiki-commit: {repo}")
    print(f"  committing {changed} change(s) on '{args.base}'")

    # --- stage (scoped) + commit ---
    try:
        git(repo, "add", "-A", *pathspec)
        git(repo, "commit", "-m", args.message)
    except subprocess.CalledProcessError as e:
        return fail(f"commit failed on '{args.base}':\n{e.stderr or e.stdout}")

    if args.push:
        push = git(repo, "push", "origin", args.base, check=False)
        if push.returncode != 0:
            print(f"wiki-commit: commit done, but push failed:\n{push.stderr}", file=sys.stderr)
        else:
            print(f"wiki-commit: pushed '{args.base}' to origin.")

    # --- report ---
    log = git(repo, "log", "--oneline", "-3").stdout.strip()
    print("wiki-commit: done. recent history:")
    for line in log.splitlines():
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
