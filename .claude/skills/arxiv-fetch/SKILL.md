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
<out_dir>/
  paper.pdf             the paper compiled from its own source (pdflatex present + compile succeeded) — canonical visual rendition; absent otherwise
  content.md            bundle contract: single-file, LLM-legible rendition of the source, produced by content_md.py's translator — ordered, conservative passes that rewrite constructs into markdown in place and pass everything else through as verbatim LaTeX. Currently: figure/table environments are replaced in-line with image embeds (raw/-relative refs) + full captions as blockquotes. TikZ figures additionally keep their source folded in a <details> block beside the render — the image is opaque to a text-reading agent, the TikZ names every node/edge/label. Unrendered TikZ falls back to visible fenced source + caption; unplaceable figures land in a trailing ## Figures gallery, never dropped. Preamble stays in a ````latex fence. Read by wikip's source-doc staging; synthesis still reads raw/sections/ lazily.
<out_dir>/raw/
  preamble.tex          everything before \begin{document} (document class, packages, custom macros)
  sections/01_*.tex     one file per top-level \input boundary (or per top-level \section{} if monolithic), nested \input's already inlined; leading block is 01_front-matter.tex (title/authors/abstract)
  structure.json        {arxiv_id, version, main_tex, sections: [{file, title_hint}, ...], warnings: [...]}
  figures/              raster figures + EPS/PDF figures pre-converted to PNG (empty if the paper uses TikZ exclusively)
  _tikz/                TikZ figures rasterised to PNG (only when pdflatex is available); separate from figures/ so source-derived assets are never mixed with regenerated ones
  figures.json          per-figure metadata: caption, label (e.g. fig:foo), section_file, image_refs (raw \includegraphics paths), resolved_paths (paths under raw/, may point into figures/ or _tikz/), has_tikz, tikz_sources (raw \begin{tikzpicture}...\end{tikzpicture} blocks), available, subfigures[]; plus stats {total, with_image, tikz_only, missing}
  arxiv_meta.json       arXiv API metadata (title, authors, abstract, categories, version, primary_class)
  *.bib / *.bbl         bibliography sources, copied verbatim for downstream citation resolution
  comments.txt          comments stripped from the source (author notes, commented-out text), tagged file:line against raw/_source/. NOT part of the published paper — never inlined into sections or content.md; worth a downstream skim for author intent. Absent when the source has no substantive comments.
  paper.pdf             only present when no LaTeX source available
  no_source.flag        only present when no LaTeX source available
```

## Idempotency

Skips if `raw/structure.json` (or `raw/no_source.flag`) already exists; the skip path self-heals a missing `content.md`. To force a refetch, delete `<out_dir>/raw/`.

To (re)derive `content.md` for an already-extracted bundle without any network access (e.g. retrofitting legacy bundles):
```bash
uv run python3 .claude/skills/arxiv-fetch/scripts/fetch.py "<arxiv-id>" --out-dir "<out_dir>" --derive-only
```

## Failure modes

- **No e-print source**: writes `paper.pdf` + `no_source.flag`, exits 0. Caller falls back to `/pdf-extract`.
- **Paper withdrawn / 404**: hard error.
- **Tarball is a single PDF**: treated as no source — `no_source.flag` is written.
- **Cyclic `\input`**: resolver tracks visited paths and skips on cycle. Logged in `raw/structure.json` warnings.
- **Unresolvable `\input` path**: the include is left verbatim and logged in warnings.
- **Include-like macros the resolver doesn't inline** (`\lstinputlisting`, `\verbatiminput`, `\inputminted`, `\includestandalone`, unbraced `\input file`, …): detected after splitting and logged in warnings as `unhandled include macro` — content may be missing from sections, but the original file remains under `raw/_source/`. (`\input`/`\include`/`\subfile`/`\import`/`\subimport` are resolved.)

## Notes

- This skill does NOT convert LaTeX to markdown. `content.md` is a *concatenation* of the LaTeX inside a fence (the bundle contract's legible single-file rendition), not a conversion. The downstream wikip skill reads `raw/sections/*.tex` directly when synthesising wiki content, avoiding a redundant Claude pass through an intermediate markdown file.
- This skill does NOT resolve bibliography keys to full citations. The `.bib` / `.bbl` files in `raw/` let a downstream skill do that.
- arXiv API metadata uses `https://export.arxiv.org/api/query?id_list=<id>` — no key required, but rate-limited to ~1 req/3s.
- System deps:
  - **`pdftoppm` (poppler)** — required for converting EPS/PDF figures and TikZ-rendered PDFs to PNG. `brew install poppler` on macOS.
  - **`pdflatex` (TeX Live or MacTeX)** — *optional, but strongly recommended.* When available, the fetcher renders each `\begin{tikzpicture}` block to a PNG in `raw/_tikz/` and keeps the compiled `paper.pdf`, so the downstream wikip skill can embed diagrams visually instead of as opaque text. Without `pdflatex`, TikZ figures degrade to fenced source + caption in `content.md`, with a warning. Install via `brew install --cask mactex-no-gui` on macOS.
- TikZ rendering is **compiler-first**: the real paper is compiled with TikZ's `external` library (`mode=list only`; per-figure jobs driven by the fetcher, so no `-shell-escape`), which renders every picture in true context — paper's own class and styles, body-defined macros and colors included — and side-produces `paper.pdf`. Pictures are matched to `figures.json` records by document-order alignment of the `.figlist` against the flattened sections; on any mismatch or compile failure the fetcher falls back per-figure to a `\documentclass{standalone}` rebuild with a sanitised preamble (journal-class machinery dropped, `pdfcrop` + last-page rasterisation guarding against page-geometry overrides). All compilation is sandboxed with `-no-shell-escape` and per-run timeouts. Figures that fail both paths are listed in `structure.json` warnings and appear in `content.md` as fenced `tikz_sources` with their captions.
