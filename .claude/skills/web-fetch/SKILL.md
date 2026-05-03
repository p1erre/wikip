---
name: web-fetch
description: Fetch a web page (or an entire documentation section) and prepare it as a structured bundle for downstream wiki ingestion — clean markdown with images downloaded locally, math preserved as LaTeX, and inline SVG figures extracted to files. Use when the user gives a URL (blog post, research write-up, docs page, online book) and wants to ingest it into a corpus wiki, or whenever the wikip skill needs a web source. For JS-rendered documentation sites with many pages under a nav menu (Next.js, Docusaurus, MkDocs, GitBook…), use the multi-page crawl mode. Output bundle mirrors pdf-extract's shape so wikip detects it automatically.
---

# web-fetch

Two modes:

- **Single page** (`fetch.py`) — a research-blog-shaped page with prose, figures, and math. Designed for distill.pub, lilianweng.github.io, Anthropic / OpenAI / Karpathy blog posts, HTML books.
- **Multi-page crawl** (`crawl.py`) — a documentation section spread across many JS-rendered pages under a shared nav menu (Next.js docs sites, Docusaurus, MkDocs, GitBook, docs.*.ai, developer portals). Discovers all nav links under a path prefix, fetches each page, stitches into one combined `content.md`. Use when the source is a vendor documentation site with 5–40 pages in a section.

Both modes output the same bundle shape so `wikip` consumes either without special-casing.

## Mode 1 — Single page (`fetch.py`)

### Inputs

- **url** (required) — fully-qualified `http(s)://` URL.
- **out-dir** (required) — where to write outputs (e.g., `work/<corpus>/documents/<doc-slug>/`). The basename becomes the wiki paper-slug.
- **--playwright** (optional) — render with a headless browser instead of plain `httpx`. Only needed for SPAs / JS-rendered content. Requires `uv pip install -e '.[playwright]' && uv run playwright install chromium`.
- **--user-agent** (optional) — override default UA (some sites block bots).
- **--timeout** (optional, default 30s).
- **--no-images** (optional) — skip image download (markdown still references original remote URLs).
- **--max-image-bytes** (optional, default 10 MB) — cap individual image size.

### What to do

1. Run the fetcher:
   ```bash
   uv run python3 .claude/skills/web-fetch/scripts/fetch.py "<url>" --out-dir "<out_dir>"
   ```
2. Read `<out_dir>/web_profile.json`. Report:
   - `extractor` used (`readability` or `chrome-strip` fallback) — chrome-strip indicates a long-form / image-heavy page where Readability would have dropped figures.
   - Image counts: `images.downloaded / images.found` (gap = duplicates or fetch failures).
   - Math counts per pattern (`katex`, `mathjax_script`, `mathml`, `raw_delim`).
   - Any `warnings` (image download failures, MathML without TeX annotation, etc.).
3. If Playwright was *not* used and the result looks thin (e.g., very short `content.md`, or 0 paragraphs of prose), suggest re-running with `--playwright` for SPA support.

---

## Mode 2 — Multi-page crawl (`crawl.py`)

Use when the source is a **documentation site** where a section spans multiple JS-rendered pages linked through a nav menu. Examples: docs.c3.ai, docs.palantir.com, Docusaurus/MkDocs/GitBook sites, developer portals.

**Signal to use crawl.py instead of fetch.py:**
- The URL is a docs site (pattern: `/docs/`, `/documentation/`, `/reference/`)
- The nav sidebar links to 5–40 pages in the same section

### Architecture

`crawl.py` has one responsibility: **URL discovery + stitching**. Per-page extraction is fully delegated to `fetch.py`:

```
crawl.py                          fetch.py (called once per URL as subprocess)
────────────────────────────────  ──────────────────────────────────────────────
Playwright: load seed URL         Readability / chrome-strip extraction
Evaluate JS → collect nav links   Math recovery (LaTeX)
For each URL → subprocess →       Image download → figures/
  read content.md                 SVG extraction
  strip frontmatter               Full markdown output
  check word count
Merge all figures/ → one dir
Stitch → combined content.md
Write web_profile.json
```

This design is **regression-invariant**: any fix or improvement to `fetch.py` automatically benefits multi-page crawls. `crawl.py` contains no extraction logic of its own.

### Inputs

- **url** (required) — seed URL; nav links are discovered from this page.
- **out-dir** (required) — output directory.
- **--path-prefix** (optional) — only follow links whose URL starts with this prefix. Default: same directory as seed URL.
- **--max-pages** (optional, default 40) — safety cap.
- **--delay** (optional, default 0.5s) — polite inter-page delay.
- **--user-agent** (optional).
- **--timeout** (optional, default 30s, passed to fetch.py per page).

### Output structure

```
<out-dir>/
  content.md        combined markdown; image refs all point to figures/
  figures/          all images from all pages, merged (sha names = no collisions)
  metadata.json
  web_profile.json  fetcher:"playwright-multi", aggregated image/math stats
  .pages/<slug>/    per-page fetch.py output kept for inspection/debugging
```

### What to do

1. **Decide on path-prefix.** For `https://docs.c3.ai/docs/platform/8.9/topic/ts-overview` the right prefix is `https://docs.c3.ai/docs/platform/8.9/topic`.

2. **Run the crawl:**
   ```bash
   uv run python3 .claude/skills/web-fetch/scripts/crawl.py "<seed-url>" \
     --out-dir "<out_dir>" \
     --path-prefix "<prefix>" \
     --timeout 60
   ```

3. **Inspect the result.** Read `web_profile.json`:
   - `pages_crawled` — `{title, url}` for every successfully extracted page.
   - `images.downloaded` — total images across all pages.
   - `warnings` — auth-gated and thin pages logged here (not errors).

4. **Auth-gated pages are expected and OK.** `crawl.py` logs them as warnings and continues.

5. **If coverage is wrong,** adjust `--path-prefix` and check `.pages/<slug>/` to inspect what fetch.py produced for a specific page.

### Failure modes

- **All pages auth-gated**: entire section is behind login. Fall back to single-page `fetch.py` on a public overview page, or use a PDF/whitepaper.
- **Nav links not discovered**: site uses non-standard nav structure. Try a sub-page as seed — some sites only expand the full nav tree when on a child page.
- **Too many pages**: tighten `--path-prefix` or use `--max-pages`.
- **Page timeouts on SPA sites**: Next.js/React docs (e.g. docs.getdbt.com) can be slow. Use `--timeout 60`. Nav discovery uses `wait_until="load"` + 2 s wait to avoid networkidle hangs.

## Output structure (both modes)

```
<out_dir>/
  content.md          markdown; YAML frontmatter + body. Multi-page: one ## section per page.
  figures/            downloaded raster figures + inline SVGs (both modes)
  metadata.json       {url, final_url, title, author, published, site_name, fetched_at, [pages_crawled]}
  web_profile.json    {fetcher, extractor, math, images, warnings, [pages_crawled: [{title, url}]]}
  .pages/<slug>/      (multi-page only) per-page fetch.py output kept for debugging
```

- `fetcher` is `"httpx"` / `"playwright"` (single-page) or `"playwright-multi"` (crawl).
- Both shapes are identical to `pdf-extract` (`content.md` + `metadata.json`), so `wikip` detects either automatically. The presence of `web_profile.json` (instead of `pdf_profile.json`) is the disambiguator.

## How it works

A four-pass pipeline runs on raw HTML — *no* headless browser by default, so KaTeX/MathJax source LaTeX is still in the DOM before client-side rendering would otherwise destroy it.

1. **Content extraction** — tries Mozilla Readability (via `readability-lxml`) with `<img>` and `<svg>` protected by sentinel markers so its content cleaner doesn't drop figures. If too few markers survive (image-heavy book-style pages), falls back to a chrome-strip extractor that picks the best content container (`<article>`, `<main>`, `[role=main]`, `#content`, `.post-content`, …) and removes nav/footer/header/aside/script chrome.
2. **Math recovery** — DOM walk replaces math nodes with placeholder tokens, restored as `$...$` / `$$...$$` after markdownify. Patterns covered:
   - **KaTeX** server-rendered: `<span class="katex">` with `<annotation encoding="application/x-tex">` (display via `katex-display` class).
   - **MathJax** script tags: `<script type="math/tex">` (inline) and `<script type="math/tex; mode=display">`.
   - **MathML**: `<math>` with TeX annotation child.
   - **Raw delimiters**: `\(...\)`, `\[...\]`, `$...$`, `$$...$$` left as text, with a heuristic to reject prose false-positives (rejects long matches that contain no `\`, `_`, `^`, `{`, or `}` and no operator-with-variable pattern).
3. **Inline SVG extraction** — each top-level `<svg>` written to `figures/svg_NNN_<sha>.svg` and replaced with a regular `<img>` pointing to the local file. SVG `<title>` becomes alt text.
4. **Image harvesting** — every `<img>` in the cleaned DOM has its `src` (or `data-src`/`data-lazy-src`/`srcset` lazy variants) resolved against the page base URL, downloaded to `figures/<stem>_<sha>.<ext>`, and rewritten to a local relative path. Failed downloads keep the original remote URL so the markdown still references something.

Then `markdownify` walks the DOM in source order and emits markdown — image positions are preserved natively because we never threw away the DOM structure. Math placeholders get substituted last.

## Idempotency

Skips if `<out_dir>/content.md` and `<out_dir>/metadata.json` both exist. To force a refetch, delete `<out_dir>/`.

## Failure modes

- **Network error / 4xx / 5xx**: hard error.
- **Page is mostly behind JS**: readability returns a thin/empty body. Re-run with `--playwright`.
- **Paywall / Cloudflare interstitial**: the fetcher gets the interstitial HTML, not the article. No automatic detection — visually thin output is the user's signal to bring credentials or use a different source.
- **Image download fails (404, timeout, too-large)**: logged in `web_profile.json` warnings; the original remote URL stays in the markdown so nothing is silently empty.
- **MathML without TeX annotation**: skipped with a warning; future improvement is a MathML→LaTeX fallback (`mathml-to-latex`).

## Notes

- Default UA is a recent macOS Safari string. Override with `--user-agent` if needed.
- Image dedup is by absolute URL — a logo referenced 30 times downloads once.
- Inline SVGs are saved verbatim (no rasterisation). Obsidian renders SVG natively.
- The `chrome-strip` fallback is intentionally simpler than Readability — it may include sidebar widgets or "related posts" sections that Readability would have removed. The trade is: don't lose 100+ figures.
- For *prose-only* pages where markdown polish matters more than fidelity, a future `--prefer-jina` flag could route through Jina Reader. Not implemented yet — only build it when a real use case appears.
- This skill does NOT chunk large outputs. A 200k-token blog post will be a single `content.md`. The downstream `wikip` skill (or a future `outline-wiki`) handles chunking.
