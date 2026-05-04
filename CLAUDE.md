# Repository layout

`.claude/skills/` contains the skill prompts and supporting scripts. Each subdirectory is one skill (`arxiv-fetch`, `pdf-extract`, `web-fetch`, `video-transcript-fetch`, `wikip`).

`wikis/` is a **separate git repository** nested inside this one (not a submodule, just an independent repo on disk). Each subdirectory under `wikis/` is an Obsidian vault produced by the `wikip` skill.

## Implications when working with the wiki

- Changes inside `wikis/**` do **not** show up in this repo's `git status`. To see or commit wiki changes, run git scoped to the wiki repo (e.g. `git -C wikis/my-wiki status`).
- Never `git add wikis/` from this repo — it would either fail or accidentally embed it as a gitlink. Treat it as out-of-tree.
- When asked to commit wiki changes, run git from inside the wiki directory. When asked to commit skill or script changes, run git from the project root.
- If a task touches both code and wiki content, plan **two separate commits in two separate repos**.
