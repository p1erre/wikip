---
name: book-reader
description: Read a long PDF book lazily — map its table of contents to physical page ranges (handling the front-matter page-number offset), then extract only the pages you want instead of converting the whole book. Use when the user has a long PDF (book, manual, report) and wants to work chapter-by-chapter, by section, or by page range, or asks to "read this book lazily", "just give me chapter N", or "extract pages A–B".
---

# book-reader

Navigate and extract a long PDF without converting all of it. Three steps:

1. **Probe** — `map.py` reads the embedded outline (exact, when present) or dumps
   the TOC-region text for *you* to read.
2. **Build** — when there's no outline, you read the dumped TOC, author a small
   `draft.json`, and `map.py --build` turns it into the page map.
3. **Read** — `read.py` slices just the pages you want and runs them through the
   existing `pdf-extract` ladder.

## Why a separate skill, and why the agent reads the TOC

`pdf-extract` converts a whole document — wrong tool for a 600-page book. The
hard part here is the **page delta**: a book has two numberings —

- **physical page**: the Nth page object in the PDF (what a slicer operates on),
- **printed folio**: the number printed in the margin, which starts *after* front
  matter (cover, title, copyright, TOC, roman-numeral preface).

A printed TOC says "Chapter 5 → p.123" but the physical page is `123 + delta`.

Book TOC layouts vary wildly (multi-column tables, dot leaders, part dividers).
Parsing them with regex/geometry is brittle and breaks per book. So the work is
split: **the script does the mechanical parts** (outline, metadata, text dump,
delta sampling, range arithmetic) and **you, the agent, read the dumped TOC** —
which you do reliably regardless of layout. Most ebooks ship an embedded outline
(delta = 0, exact) and skip the reading step entirely.

## Step 1 — probe the book

```bash
uv run python3 "${CLAUDE_PLUGIN_ROOT}"/skills/book-reader/scripts/map.py "<book.pdf>"
# optional: --out-dir <dir>   --toc-pages 7-13   --probe-pages 30
```

Each book gets a **self-contained home folder** in the host project's bundle area (this repo's convention: `work/books/<book-slug>/`). On the
first run the source PDF is copied into it (idempotent), and every artifact lives
beside it:

```
work/books/<book-slug>/
  <original>.pdf       copied in once
  book_map.json        the page map
  toc_probe.md         TOC dump (no-outline case)
  probe.json
  draft.json           you author this (no-outline case)
  <section-slug>/       one per extracted section
```

`book_map.json`'s `source_pdf` points at the copied PDF, so later steps operate
on the book's own folder. keep the bundle area out of git (large, often copyrighted) — this repo gitignores `work/`.
Two outcomes:

- **Embedded outline found** → it writes `book_map.json` directly. Done — report
  `toc_source: outline` and the chapter list. Skip to Step 3.
- **No outline** → it writes `toc_probe.md` (+ `probe.json`). Go to Step 2.

## Step 2 — read the TOC and build the map (no-outline case)

1. **Read `<out-dir>/toc_probe.md`.** It contains book metadata, a suggested
   `delta` with folio-sample evidence, and the dumped text of the TOC pages.
2. **Confirm the delta.** The suggestion is the mode of `physical − folio` over
   sampled body pages. Cross-check it: the first chapter's folio + delta should
   equal the physical page where that chapter actually starts (the probe tells
   you which physical pages were dumped — the body chapters start right after).
3. **Author `<out-dir>/draft.json`** from the TOC listing. Record each entry's
   **printed folio** (the TOC number, not a physical page):

   ```json
   {"source_pdf": "<abs path>", "delta": 13,
    "metadata": {"title": "...", "author": "..."},
    "entries": [
      {"level": 1, "number": "I",  "title": "Artificial Intelligence", "printed_page": 1},
      {"level": 2, "number": "1",  "title": "Introduction",            "printed_page": 1},
      {"level": 2, "number": "2",  "title": "Intelligent Agents",      "printed_page": 36}
    ]}
   ```

   - `level 1` = part/top-level (and standalone back matter like Bibliography);
     `level 2` = chapter. Keep it to parts + chapters unless the user wants
     section granularity — a chapter's range auto-extends to the next
     same-or-shallower entry, so sections are optional.
   - `number` is optional (omit for "Bibliography", "Index", etc.).
4. **Finalize:**
   ```bash
   uv run python3 "${CLAUDE_PLUGIN_ROOT}"/skills/book-reader/scripts/map.py --build "<out-dir>/draft.json"
   ```
   Writes `book_map.json`. Show the resulting ranges and have the user
   sanity-check one before bulk extraction.

`book_map.json` entry shape:

```json
{"index": 20, "level": 2, "title": "21 Deep Learning", "slug": "21-deep-learning",
 "printed_page": 750, "physical_start": 763, "physical_end": 801, "pages": 39}
```

## Step 3 — read a section

```bash
# by chapter (title substring, slug, or index from the map)
uv run python3 "${CLAUDE_PLUGIN_ROOT}"/skills/book-reader/scripts/read.py \
    --map work/books/<slug>/book_map.json --section "Deep Learning"

# by printed folio range (delta applied automatically)
read.py --map work/books/<slug>/book_map.json --printed-pages 750-788

# by raw physical pages (no map needed)
read.py --pdf "<book.pdf>" --pages 763-801
```

Useful flags:

- `--quick` — pymupdf-only fast skim (seconds). Drops math/figure fidelity; use
  when just reading. Omit for the full ladder (marker for math/figures).
- `--out-dir DIR` — defaults to the book home (`work/books/<slug>/<section-slug>/`).
  Point it at `work/<corpus>/documents/<doc-slug>/` to feed the wikip pipeline.
- `--force-strategy`, `--quality-threshold` — passed through to `pdf-extract`.

Output is a standard pdf-extract bundle (`content.md`, `figures/`,
`metadata.json`, `pdf_profile.json`) plus a `section.json` recording the book,
selection, and physical range. Because it's pdf-extract-shaped, `wikip` ingests a
chapter slice like any other source — so you can build a wiki from a book one
chapter at a time.

## Idempotency & notes

- `read.py` delegates to `pdf-extract`, which skips re-extraction when
  `content.md` + `pdf_profile.json` already exist in the out-dir. Delete the
  section dir or pass `--force-strategy` to redo.
- Encrypted PDFs: not handled (inherited from `pdf-extract`).
- Scanned books have no extractable TOC text — `toc_probe.md` will be empty/OCR
  garbage. Render the TOC pages to images (`pdf-extract`'s machinery) and read
  those, or fall back to `read.py --pages`.
- If `detect_toc_region` dumps the wrong pages, re-run probe with `--toc-pages`.
- Dependencies: `pymupdf` (this skill) plus whatever `pdf-extract` needs for the
  chosen strategy.
