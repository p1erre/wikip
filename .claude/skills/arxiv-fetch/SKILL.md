---
name: arxiv-fetch
description: Fetch an arXiv paper and prepare its LaTeX source as a structured bundle for downstream processing. Splits the paper at top-level \input boundaries so a downstream skill can read it section-by-section. Falls back to a PDF download (and the pdf-extract skill) when no LaTeX source is available. Use when the user gives an arXiv ID/URL (e.g. arXiv:2003.02320), asks to ingest an arXiv paper into the wiki, or wants to work from LaTeX source instead of OCR'd PDF.
---

# arxiv-fetch

Fetch a single arXiv paper and lay out its LaTeX source so the downstream wikip skill (or any other consumer) can read it directly. This skill does **not** convert to markdown — that's the consumer's job, on demand.

## Inputs

- **arxiv-id** (required) — accepted forms: `2003.02320`, `arXiv:2003.02320`, `https://arxiv.org/abs/2003.02320`, `https://arxiv.org/pdf/2003.02320`. Optional version pin: `2003.02320v3` (bare ID = latest).
- **out-dir** (required) — where to write outputs (e.g., `work/<corpus>/documents/arxiv-<id>/`).

## What to do

1. Run the fetcher. It downloads the e-print tarball, recursively flattens `\input`/`\include`/`\subfile`, splits at top-level boundaries, and writes a `raw/` bundle:
   ```bash
   uv run python3 .claude/skills/arxiv-fetch/scripts/fetch.py "<arxiv-id>" --out-dir "<out_dir>"
   ```
2. If `<out_dir>/raw/no_source.flag` exists, the paper has no LaTeX source on arXiv. Invoke `/pdf-extract` on `<out_dir>/raw/paper.pdf` and stop.
3. Otherwise report what was prepared: number of sections, whether figures were extracted, whether bibliography is present, and any warnings from `raw/structure.json`.

## Output structure

```
<out_dir>/raw/
  preamble.tex          everything before \begin{document} (document class, packages, custom macros)
  sections/01_*.tex     one file per top-level \input boundary (or per top-level \section{} if monolithic), nested \input's already inlined; leading block is 01_front-matter.tex (title/authors/abstract)
  structure.json        {arxiv_id, version, main_tex, sections: [{file, title_hint}, ...], warnings: [...]}
  figures/              raster figures + EPS/PDF figures pre-converted to PNG (empty if the paper uses TikZ exclusively)
  arxiv_meta.json       arXiv API metadata (title, authors, abstract, categories, version, primary_class)
  *.bib / *.bbl         bibliography sources, copied verbatim for downstream citation resolution
  paper.pdf             only present when no LaTeX source available
  no_source.flag        only present when no LaTeX source available
```

## Idempotency

Skips if `raw/structure.json` (or `raw/no_source.flag`) already exists. To force a refetch, delete `<out_dir>/raw/`.

## Failure modes

- **No e-print source**: writes `paper.pdf` + `no_source.flag`, exits 0. Caller falls back to `/pdf-extract`.
- **Paper withdrawn / 404**: hard error.
- **Tarball is a single PDF**: treated as no source — `no_source.flag` is written.
- **Cyclic `\input`**: resolver tracks visited paths and skips on cycle. Logged in `raw/structure.json` warnings.
- **Unresolvable `\input` path**: the include is left verbatim and logged in warnings.

## Notes

- This skill does NOT convert LaTeX to markdown. The downstream wikip skill reads `raw/sections/*.tex` directly when synthesising wiki content, avoiding a redundant Claude pass through an intermediate markdown file.
- This skill does NOT resolve bibliography keys to full citations. The `.bib` / `.bbl` files in `raw/` let a downstream skill do that.
- arXiv API metadata uses `https://export.arxiv.org/api/query?id_list=<id>` — no key required, but rate-limited to ~1 req/3s.
- System deps: only `pdftoppm` (poppler) for converting EPS/PDF figures to PNG. Install via `brew install poppler` on macOS if missing.
