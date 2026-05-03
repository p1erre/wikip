#!/usr/bin/env python3
"""
Crawl a documentation site section and stitch pages into a single content bundle.

Designed for JS-rendered doc sites (Next.js, Docusaurus, MkDocs, GitBook, etc.)
where the navigation is not in static HTML and page content is split across many URLs.

Usage:
  crawl.py <seed-url> --out-dir <dir>
           [--path-prefix <prefix>]   only follow links whose path starts with <prefix>
                                       default: same directory as seed URL
           [--max-pages <N>]          safety cap, default 40
           [--delay <seconds>]        polite inter-page delay, default 0.5
           [--user-agent <ua>]        override default UA
           [--timeout <seconds>]      per-page timeout, default 30

Output (same shape as fetch.py so wikip/wikip-like consumers work unchanged):
  <out-dir>/content.md          combined markdown, one ## section per page
  <out-dir>/metadata.json       {url, title, author, site_name, pages_crawled}
  <out-dir>/web_profile.json    {fetcher:"playwright-multi", pages_crawled:[...], warnings:[...]}

Idempotent: skips if content.md + metadata.json both exist.

Requires playwright:
  uv pip install -e '.[playwright]' && uv run playwright install chromium
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)

# ─── nav-link discovery ──────────────────────────────────────────────────────

def discover_nav_links(page, seed_url: str, path_prefix: str) -> list[str]:
    """Return unique URLs found in the rendered page that match path_prefix."""
    links = page.evaluate(
        """(prefix) => {
            return Array.from(document.querySelectorAll('a[href]'))
                .map(a => a.href)
                .filter(h => h && !h.includes('#') && h.includes(prefix));
        }""",
        path_prefix,
    )
    seen, ordered = set(), []
    for link in links:
        clean = link.split("?")[0].rstrip("/")
        if clean and clean not in seen:
            seen.add(clean)
            ordered.append(clean)
    return ordered


# ─── per-page content extraction ─────────────────────────────────────────────

# These phrases reliably appear as the last nav item before article content
# on most doc sites. We truncate everything before the first match.
_CONTENT_MARKERS = [
    "Print page\n",
    "Edit this page\n",
    "On this page\n",          # some sites put TOC before content
]

# Footer phrases — strip everything from these onwards
_FOOTER_MARKERS = [
    "\nWas this helpful?",
    "\nEdit this page",
    "\nPrevious\n",
    "\nNext\n",
    "\nContribute",
    "\nCopyright",
]


def extract_article_body(raw: str) -> str:
    """Strip nav/header/footer from innerText, keeping only the article body."""
    body = raw

    # Find content start: look for the last "Print page" or equivalent marker
    start_idx = -1
    for marker in _CONTENT_MARKERS:
        idx = body.rfind(marker)   # rfind: last occurrence (past all nav items)
        if idx >= 0 and idx > start_idx:
            start_idx = idx + len(marker)

    if start_idx > 0:
        body = body[start_idx:]
        # The first non-blank line is often the article title repeated — skip it
        lines = body.split("\n")
        for i, line in enumerate(lines):
            if line.strip():
                # skip this line (repeated title) and start from next non-blank
                body = "\n".join(lines[i + 1:])
                break

    # Trim footer
    for marker in _FOOTER_MARKERS:
        idx = body.find(marker)
        if idx > 100:          # don't trim if it's at the very start
            body = body[:idx]

    # Collapse 3+ consecutive blank lines into 2
    body = re.sub(r"\n{3,}", "\n\n", body)

    return body.strip()


# ─── main crawl ──────────────────────────────────────────────────────────────

def crawl(
    seed_url: str,
    out_dir: Path,
    path_prefix: str,
    max_pages: int,
    delay: float,
    user_agent: str,
    timeout_ms: int,
) -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "Playwright not installed. Run: uv pip install -e '.[playwright]' && "
            "uv run playwright install chromium",
            file=sys.stderr,
        )
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)

    sections: list[dict] = []    # {title, url, body}
    warnings: list[str] = []
    fetched_at = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(user_agent=user_agent)
        nav_page = ctx.new_page()

        # ── step 1: load seed, discover nav links ──
        print(f"[web-crawl] seed: {seed_url}", file=sys.stderr)
        nav_page.goto(seed_url, wait_until="networkidle", timeout=timeout_ms)
        nav_page.wait_for_timeout(1000)

        site_title = nav_page.title().split("|")[0].strip()
        site_name = nav_page.title().split("|")[-1].strip() if "|" in nav_page.title() else ""

        all_links = discover_nav_links(nav_page, seed_url, path_prefix)
        # Ensure seed is first if not already in list
        seed_clean = seed_url.split("?")[0].rstrip("/")
        if seed_clean not in all_links:
            all_links = [seed_clean] + all_links

        print(f"[web-crawl] discovered {len(all_links)} candidate links under {path_prefix}", file=sys.stderr)
        if len(all_links) > max_pages:
            warnings.append(f"Capped at {max_pages} pages (discovered {len(all_links)})")
            all_links = all_links[:max_pages]

        # ── step 2: fetch + extract each page ──
        fetch_page = ctx.new_page()
        for i, url in enumerate(all_links):
            try:
                fetch_page.goto(url, wait_until="networkidle", timeout=timeout_ms)
                fetch_page.wait_for_timeout(500)

                raw = fetch_page.evaluate("document.body.innerText")

                # Auth-gated check — small body with "sign in" is a redirect
                if len(raw.strip()) < 200 and any(
                    kw in raw.lower() for kw in ("sign in", "log in", "okta", "authenticate")
                ):
                    warnings.append(f"Skipped (auth-gated): {url}")
                    print(f"[web-crawl]   skip (auth): {url}", file=sys.stderr)
                    continue

                body = extract_article_body(raw)
                if len(body.split()) < 30:
                    warnings.append(f"Skipped (too thin after extraction): {url}")
                    print(f"[web-crawl]   skip (thin): {url}", file=sys.stderr)
                    continue

                # Derive a section title from the URL slug
                slug = url.rstrip("/").rsplit("/", 1)[-1]
                title = slug.replace("-", " ").replace("_", " ").title()

                sections.append({"title": title, "url": url, "body": body})
                word_count = len(body.split())
                print(f"[web-crawl]   [{i+1}/{len(all_links)}] {word_count:>5} words  {title}", file=sys.stderr)

                if delay > 0:
                    fetch_page.wait_for_timeout(int(delay * 1000))

            except Exception as exc:
                warnings.append(f"Error fetching {url}: {exc}")
                print(f"[web-crawl]   error: {url}: {exc}", file=sys.stderr)

        browser.close()

    if not sections:
        print("[web-crawl] no content extracted — check path-prefix and auth", file=sys.stderr)
        return 1

    # ── step 3: stitch into content.md ──
    combined_title = site_title or f"Documentation crawl of {urlparse(seed_url).netloc}"

    front = (
        f"---\n"
        f"url: {seed_url}\n"
        f'title: {json.dumps(combined_title)}\n'
        f'author: {json.dumps(site_name or "")}\n'
        f'site_name: {json.dumps(site_name or "")}\n'
        f"fetched_at: {fetched_at}\n"
        f"---\n\n"
    )

    body_parts = [f"# {combined_title}\n"]
    body_parts.append(
        f"*Assembled from {len(sections)} pages crawled under `{path_prefix}`.*\n"
    )
    if warnings:
        body_parts.append(f"*Warnings: {len(warnings)} (see web_profile.json for details).*\n")
    body_parts.append("")

    for sec in sections:
        body_parts.append(f"---\n\n## {sec['title']}\n")
        body_parts.append(f"*Source: <{sec['url']}>*\n")
        body_parts.append(f"\n{sec['body']}\n")

    content = front + "\n".join(body_parts)
    (out_dir / "content.md").write_text(content, encoding="utf-8")

    metadata = {
        "url": seed_url,
        "final_url": seed_url,
        "title": combined_title,
        "author": site_name or None,
        "published": None,
        "modified": None,
        "site_name": site_name or None,
        "description": f"Multi-page crawl: {len(sections)} pages from {path_prefix}",
        "language": None,
        "fetched_at": fetched_at,
        "pages_crawled": len(sections),
        "page_urls": [s["url"] for s in sections],
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    profile = {
        "url": seed_url,
        "final_url": seed_url,
        "fetcher": "playwright-multi",
        "extractor": "multi-page-nav-crawl",
        "math": {"katex": 0, "mathjax_script": 0, "mathml": 0, "raw_delim": 0},
        "images": {"found": 0, "downloaded": 0, "skipped": 0, "failed": 0},
        "inline_svgs": 0,
        "warnings": warnings,
        "pages_crawled": [{"title": s["title"], "url": s["url"]} for s in sections],
    }
    (out_dir / "web_profile.json").write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")

    char_count = len(content)
    line_count = content.count("\n")
    print(
        f"[web-crawl] done: {out_dir}/content.md "
        f"({len(sections)} pages, {line_count} lines, {char_count:,} chars)",
        file=sys.stderr,
    )
    return 0


# ─── CLI ─────────────────────────────────────────────────────────────────────

def _default_prefix(url: str) -> str:
    """Same directory as the seed URL (up to the last path segment)."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    parent = path.rsplit("/", 1)[0] if "/" in path else path
    return f"{parsed.scheme}://{parsed.netloc}{parent}"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("url", help="Seed URL — nav links will be discovered from this page")
    p.add_argument("--out-dir", required=True, help="Directory to write the bundle into")
    p.add_argument(
        "--path-prefix",
        default=None,
        help="Only follow links whose URL starts with this prefix. "
             "Default: same directory as seed URL.",
    )
    p.add_argument("--max-pages", type=int, default=40, help="Safety cap on pages fetched (default 40)")
    p.add_argument("--delay", type=float, default=0.5, help="Polite delay between fetches in seconds (default 0.5)")
    p.add_argument("--user-agent", default=DEFAULT_UA)
    p.add_argument("--timeout", type=int, default=30, help="Per-page timeout in seconds (default 30)")
    args = p.parse_args()

    out_dir = Path(args.out_dir)

    # Idempotency check
    if (out_dir / "content.md").exists() and (out_dir / "metadata.json").exists():
        print(f"[web-crawl] already done: {out_dir} — delete it to re-crawl", file=sys.stderr)
        return 0

    path_prefix = args.path_prefix or _default_prefix(args.url)
    return crawl(
        seed_url=args.url,
        out_dir=out_dir,
        path_prefix=path_prefix,
        max_pages=args.max_pages,
        delay=args.delay,
        user_agent=args.user_agent,
        timeout_ms=args.timeout * 1000,
    )


if __name__ == "__main__":
    sys.exit(main())
