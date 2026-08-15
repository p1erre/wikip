# Repository layout

Skills live in **two plugins** served from this repo's own marketplace (`.claude-plugin/marketplace.json`, name `corpus-tools`):

- `plugins/fetch/skills/` — source fetchers (`arxiv-fetch`, `web-fetch`, `pdf-extract`, `video-transcript-fetch`, `book-reader`). Each produces a bundle satisfying the contract: `content.md` (single-file, complete, LLM-legible rendition) + `metadata.json` + a profile marker file.
- `plugins/wikip/skills/` — corpus wiki system (`wikip`, `clip`, `reconcile-corpora`), consuming bundles through that contract only.

`.claude/settings.json` enables both plugins for this repo (skills are namespaced: `/fetch:arxiv-fetch`, `/wikip:wikip`). Settings-enabled plugins load from a **cached copy**, not the working tree — after changing skill code, refresh with `/plugin marketplace update corpus-tools`, or develop live with `claude --plugin-dir ./plugins/fetch --plugin-dir ./plugins/wikip`. Script paths inside SKILL.md files use `${CLAUDE_PLUGIN_ROOT}` (the installed plugin's root); when working in this repo directly, that resolves to `plugins/<name>/`.

`wikis/` is a **separate git repository** nested inside this one (not a submodule, just an independent repo on disk). Each subdirectory under `wikis/` is an Obsidian vault produced by the `wikip` skill.

## Implications when working with the wiki

- Changes inside `wikis/**` do **not** show up in this repo's `git status`. To see or commit wiki changes, run git scoped to the wiki repo (e.g. `git -C wikis/my-wiki status`).
- Never `git add wikis/` from this repo — it would either fail or accidentally embed it as a gitlink. Treat it as out-of-tree.
- When asked to commit wiki changes, run git from inside the wiki directory. When asked to commit skill or script changes, run git from the project root.
- If a task touches both code and wiki content, plan **two separate commits in two separate repos**.

## Committing & merging

One logical unit = one entry on `main`, so `git log --oneline` reads as a changelog and any unit reverts cleanly.

- **Project repo (public, `p1erre/wikip`):** land work via a GitHub PR, **squash-merged** — never push a feature branch straight onto `main`. Develop on a branch with clean conventional commits, then:
  ```bash
  git push -u origin <feature-branch>
  gh pr create --base main --title "<conventional title>" --body "..."
  gh pr merge --squash --delete-branch
  git checkout main && git pull
  ```
  Squash keeps `main` linear (one commit per feature); the PR permanently archives the branch's individual commits + diff, so nothing is lost. Don't use `--no-ff` here — squash is the convention.
- **Wikis repo (personal corpus, `p1erre/wiki0`):** one ingest = one atomic commit directly on `main` via `scripts/wiki-commit.py` (scoped to the wikis repo; pathspec to scope a commit to one vault when two ingests share the working tree). No branch/PR ceremony — a single commit is its own revertable unit (`git revert <sha>`). It's data, not the code showcase.
