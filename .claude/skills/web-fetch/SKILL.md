---
name: web-fetch
description: Fetch a web page and prepare it as a structured bundle for downstream wiki ingestion — clean markdown with images downloaded locally, math preserved as LaTeX, and inline SVG figures extracted to files. Use when the user gives a URL (blog post, research write-up, docs page, online book) and wants to ingest it into a corpus wiki, or whenever the wikip skill needs a web source. Output bundle mirrors pdf-extract's shape so wikip detects it automatically.
---

# web-fetch

Fetch a single web page and lay out a content bundle that the downstream `wikip` skill (or any other consumer) can read directly. Designed for **research-blog-shaped pages** with prose, figures, and math: things like distill.pub, lilianweng.github.io, Anthropic / OpenAI / Karpathy blog posts, and HTML books. Output mirrors `pdf-extract` so `wikip` consumes it without special-casing.

## Inputs

- **url** (required) — fully-qualified `http(s)://` URL.
- **out-dir** (required) — where to write outputs (e.g., `work/<corpus>/documents/<doc-slug>/`). The basename becomes the wiki paper-slug.
- **--playwright** (optional) — render with a headless browser instead of plain `httpx`. Only needed for SPAs / JS-rendered content. Requires `uv pip install -e '.[playwright]' && uv run playwright install chromium`.
- **--user-agent** (optional) — override default UA (some sites block bots).
- **--timeout** (optional, default 30s).
- **--no-images** (optional) — skip image download (markdown still references original remote URLs).
- **--max-image-bytes** (optional, default 10 MB) — cap individual image size.

## What to do

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

## Output structure

```
<out_dir>/
  content.md          markdown body with YAML frontmatter; $...$ / $$...$$ for math; ![alt](figures/…) for images
  figures/            downloaded raster figures + extracted inline SVGs (sha-suffixed for dedupe)
  metadata.json       {url, final_url, title, author, published, modified, site_name, description, language, fetched_at}
  web_profile.json    {fetcher, extractor, math: {...}, images: {...}, inline_svgs, warnings: [...]}
```

This is intentionally the same shape as `pdf-extract` (`content.md` + `metadata.json` + `figures/`), so `wikip` detects it automatically. The presence of `web_profile.json` (instead of `pdf_profile.json`) is the disambiguator.

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
