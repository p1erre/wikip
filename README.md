# wikip

Claude Code skills that fetch **papers, videos, and web pages** and synthesize them into a linked knowledge wiki — an [Obsidian](https://obsidian.md/) vault where paper pages and concept pages connect through typed edges.

The motivating example: start from an arXiv paper, a conference talk, and a blog post on the same topic — wikip links them into a structured Obsidian vault with paper pages, concept pages, and typed edges between them.

## How it works

Each source has a fetcher skill that downloads it and normalises it into a structured bundle. The `wikip` skill reads any bundle and writes — or updates — paper and concept pages in your corpus wiki.

```
arxiv-fetch           ─┐
pdf-extract           ─┤
web-fetch             ─┼──→ bundle ──→ wikip ──→ Obsidian wiki
video-transcript-fetch─┘
```

Fetchers handle the messy parts: LaTeX extraction, TikZ figure rendering, PDF OCR escalation, math recovery from HTML, caption-based transcription. `wikip` is a synthesis skill — it decides what concept pages to create, how to link them, and how to update existing pages when a new source overlaps with what the corpus already knows.

## Install

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/). For PDF OCR and TikZ rendering, also `pdflatex` and `pdftoppm` on your `PATH`.

```bash
git clone https://github.com/<your-handle>/wikip
cd wikip
uv sync
```

Link the skills to your Claude Code install:

```bash
ln -s "$(pwd)/.claude/skills"/* ~/.claude/skills/
```

## Quick start

```
# Fetch a paper
/arxiv-fetch 1706.03762

# Fetch a video
/video-transcript-fetch https://www.youtube.com/watch?v=<video-id>

# Synthesize both into a wiki
/wikip

# Validate and regenerate the index
python3 .claude/skills/wikip/scripts/validate.py wikis/my-wiki
```

## Skills

| Skill | Input | What it does |
|---|---|---|
| `/arxiv-fetch` | arXiv ID or URL | Downloads LaTeX source, renders TikZ figures, extracts section structure |
| `/pdf-extract` | PDF path or URL | Extracts text with strategy escalation (pymupdf → marker → nougat / OCR); preserves math |
| `/web-fetch` | URL | Fetches page with math recovery (KaTeX / MathJax / MathML), downloads figures |
| `/video-transcript-fetch` | Video URL | Fetches captions or transcribes with Whisper; works with YouTube and 1000+ sites |
| `/wikip` | Bundle dir | Synthesizes paper and concept pages, updates `graph.json` |

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

## License

MIT
