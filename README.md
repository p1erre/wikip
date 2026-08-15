# wikip

Claude Code skills that fetch **papers, videos, and web pages** and synthesize them into a linked knowledge wiki — an [Obsidian](https://obsidian.md/) vault where paper pages and concept pages connect through typed edges.

The motivating example: start from an arXiv paper, a conference talk, and a blog post on the same topic — wikip links them into a structured Obsidian vault with paper pages, concept pages, and typed edges between them.

## How it works

Each source has a fetcher skill that downloads it and normalises it into a structured bundle. The `wikip` skill reads any bundle and writes — or updates — paper and concept pages in your corpus wiki.

```
arxiv-fetch            ─┐
pdf-extract            ─┤   book-reader: page-range helper for long PDFs
web-fetch              ─┤
video-transcript-fetch ─┼──→ bundle ──→ wikip ──→ Obsidian wiki
clip                   ─┘
```

Fetchers handle the messy parts: LaTeX extraction, TikZ figure rendering, PDF OCR escalation, math recovery from HTML, caption-based transcription. When a source can't be fetched automatically (LinkedIn, paywalled posts) you hand it to `clip`. `wikip` is a synthesis skill — it decides what concept pages to create, how to link them, and how to update existing pages when a new source overlaps with what the corpus already knows. Once several sources have landed, `reconcile-corpora` audits concept overlap across vaults.

## Install

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/). For PDF OCR and TikZ rendering, also `pdflatex` and `pdftoppm` on your `PATH`.

```bash
git clone https://github.com/<your-handle>/wikip
cd wikip
uv sync
```

The skills ship as two plugins (`fetch` and `wikip`) from this repo's own
marketplace. Working inside this repo, they're enabled automatically via
`.claude/settings.json`. To use them in **any other project**:

```
/plugin marketplace add p1erre/wikip
/plugin install fetch@corpus-tools
/plugin install wikip@corpus-tools     # optional: only if you want corpus wikis
```

Skills are then invoked namespaced (`/fetch:arxiv-fetch`, `/wikip:wikip`) or
just by asking in natural language. For live plugin development in this repo:
`claude --plugin-dir ./plugins/fetch --plugin-dir ./plugins/wikip` (settings-
enabled plugins load from a cached copy; refresh with
`/plugin marketplace update corpus-tools` after landing changes).

## Set up your corpus

Your wikis live in a `wikis/` directory at the repo root. It's a **single git
repo of its own** (your personal corpus, kept separate from the skills code) —
each subdirectory under it is one Obsidian vault. Create it once, then bootstrap
a vault inside it with `init.py`:

```bash
# 1. The corpus is its own git repo, nested in the project root
mkdir wikis && git -C wikis init

# 2. Bootstrap a vault inside it (pages/, graph.json, _schema.json, …)
python3 plugins/wikip/skills/wikip/scripts/init.py wikis/my-wiki
```

`init.py` is idempotent — re-running it on an existing vault is a no-op. Add as
many vaults as you like (`wikis/ai-strategy`, `wikis/agentic-ai`, …); `wikip`
asks which one to write into. Because `wikis/` is a separate repo, its changes
never show up in the project repo's `git status` — commit them with
`wiki-commit.py` (see [Utilities](#utilities)).

## Quick start

```
# Bootstrap a vault to ingest into (first time only)
python3 plugins/wikip/skills/wikip/scripts/init.py wikis/my-wiki

# Fetch a paper
/fetch:arxiv-fetch 1706.03762

# Fetch a video
/fetch:video-transcript-fetch https://www.youtube.com/watch?v=<video-id>

# Synthesize both into a wiki
/wikip:wikip

# Validate and regenerate the index
python3 plugins/wikip/skills/wikip/scripts/validate.py wikis/my-wiki
```

## Skills

| Skill | Input | What it does |
|---|---|---|
| `/arxiv-fetch` | arXiv ID or URL | Downloads LaTeX source, renders TikZ figures, extracts section structure |
| `/pdf-extract` | PDF path or URL | Extracts text with strategy escalation (pymupdf → marker → nougat / OCR); preserves math |
| `/book-reader` | Long PDF | Maps the table of contents to physical pages and extracts only the ranges you want — read a book chapter-by-chapter instead of converting the whole thing |
| `/web-fetch` | URL | Fetches page with math recovery (KaTeX / MathJax / MathML), downloads figures; crawls multi-page docs sites |
| `/video-transcript-fetch` | Video URL | Fetches captions or transcribes with Whisper; works with YouTube and 1000+ sites |
| `/clip` | Pasted text + image URLs | Builds a bundle from hand-copied content (LinkedIn, tweets, paywalled posts) that can't be fetched automatically |
| `/wikip` | Bundle dir | Synthesizes paper and concept pages, updates `graph.json` |
| `/reconcile-corpora` | `wikis/` dir | Audits concept overlap across vaults: confirms bridges, surfaces slug synonyms, regenerates `CONNECTIONS.md` |

## Wiki layout

Each wiki is an Obsidian vault with two kinds of pages:

- **Paper pages** (`pages/papers/<slug>.md`) — literature-review view of one source: TL;DR, key claims, methodology, results, links to concept pages.
- **Concept pages** (`pages/concepts/<slug>.md`) — synthesized explanation of one idea, drawn from every paper in the corpus that discusses it.

Pages link through **typed predicates** (`defines`, `extends`, `compares-with`, `is-a`, …). `graph.json` is the machine-readable edge list; `validate.py` enforces the schema.

```
wikis/my-wiki/
  pages/
    papers/arxiv-1706.03762.md
    concepts/attention-mechanism.md
    concepts/transformer.md
  assets/
    arxiv-1706.03762/fig-1.png
  graph.json
  _schema.json
  index.md
```

`wikis/` is a separate git repo — committed independently from the skills code.

## Utilities

| Script | What it does |
|---|---|
| `wikip/scripts/init.py <wiki>` | Bootstrap a new wiki with standard layout and default predicate schema |
| `wikip/scripts/validate.py <wiki>` | Check frontmatter, wiki-link resolution, predicate types; regenerate `index.md` |
| `wikip/scripts/audit.py <wiki>` | Report under-developed concepts: orphans, single-paper concepts, mentioned-but-undefined |
| `wikip/scripts/merge.py <src> --into <tgt>` | Merge two wikis (pages + graph + schema) with configurable conflict resolution |
| `wikip/scripts/wiki-commit.py -m <msg> [-- <vault>]` | Commit changes on the `wikis/` repo (one ingest = one atomic commit); optional pathspec scopes a commit to a single vault |

## License

MIT
