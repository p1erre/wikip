# Repository layout

`wikis/` is a **separate git repository** nested inside this one (not a submodule, just an independent repo on disk). Each subdirectory under `wikis/` (e.g. `wikis/semantic-operators/`) is an Obsidian vault produced by the `wikip` skill.

## Implications when working with the wiki

- Changes inside `wikis/**` do **not** show up in this repo's `git status`. To see or commit wiki changes, run git from inside `wikis/` (e.g. `git -C wikis status`).
- Never `git add wikis/` from this repo — it would either fail or accidentally embed it as a gitlink. Treat it as out-of-tree.
- When the user asks to commit wiki changes, run the git commands scoped to `wikis/` (`git -C wikis ...`). When they ask to commit code changes (skills, scripts, README), run git from the project root and ignore `wikis/`.
- If a task touches both code and wiki content, plan **two separate commits in two separate repos** — don't try to bundle them.
