#!/usr/bin/env python3
"""
Crawl a documentation site section and stitch pages into a single content bundle.

Designed for JS-rendered doc sites (Next.js, Docusaurus, MkDocs, GitBook, etc.)
where the navigation is not in static HTML and page content is split across many URLs.

Architecture: crawl.py handles only URL discovery and stitching.
Per-page extraction (images, math, SVGs) is fully delegated to fetch.py —
the same battle-tested pipeline used for single-page fetches.

Usage:
  crawl.py <seed-url> --out-dir <dir>
           [--path-prefix <prefix>]   only follow links whose path starts with <prefix>
                                       default: same directory as seed URL
           [--max-pages <N>]          safety cap, default 40
           [--delay <seconds>]        polite inter-page delay, default 0.5
           [--user-agent <ua>]        override default UA
           [--timeout <seconds>]      per-page timeout passed to fetch.py, default 30

Output (same shape as fetch.py so wikip consumes it unchanged):
  <out-dir>/content.md          combined markdown; image refs point to <out-dir>/figures/
  <out-dir>/figures/            all images from all pages, merged (sha names = no collisions)
  <out-dir>/metadata.json
  <out-dir>/web_profile.json    fetcher:"playwright-multi", aggregated image/math stats
  <out-dir>/.pages/<slug>/      per-page fetch.py output, kept for inspection/debugging

Idempotency:
  Top-level: skips entirely if content.md + metadata.json both exist.
  Per-page:  fetch.py is itself idempotent — interrupted crawls resume automatically.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

FETCH_SCRIPT = Path(__file__).parent / "fetch.py"

DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)


# ─── URL discovery ────────────────────────────────────────────────────────────

def discover_nav_links(
    seed_url: str,
    path_prefix: str,
    timeout_ms: int,
    user_agent: str,
) -> tuple[list[str], str, str]:
    """
    Render the seed URL with Playwright and return (links, site_title, site_name).
    Uses wait_until="load" + 2 s extra — avoids networkidle hangs on SPA sites.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError(
            "Playwright not installed. Run: uv pip install -e '.[playwright]' && "
            "uv run playwright install chromium"
        )

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=user_agent)
        page.goto(seed_url, wait_until="load", timeout=timeout_ms)
        page.wait_for_timeout(2000)

        site_title = page.title().split("|")[0].strip()
        site_name = page.title().split("|")[-1].strip() if "|" in page.title() else ""

        links: list[str] = page.evaluate(
            """(prefix) => {
                return Array.from(document.querySelectorAll('a[href]'))
                    .map(a => a.href)
                    .filter(h => h && !h.includes('#') && h.includes(prefix));
            }""",
            path_prefix,
        )
        browser.close()

    seen: set[str] = set()
    ordered: list[str] = []
    for link in links:
        clean = link.split("?")[0].rstrip("/")
        if clean and clean not in seen:
            seen.add(clean)
            ordered.append(clean)

    return ordered, site_title, site_name


# ─── helpers ──────────────────────────────────────────────────────────────────

def url_to_slug(url: str) -> str:
    """
    Full-path slug — collision-free across all pages in the same crawl.
    e.g. https://docs.example.com/docs/build/semantic-models
         → docs-build-semantic-models
    """
    path = urlparse(url).path.strip("/")
    return re.sub(r"[^a-zA-Z0-9]+", "-", path).strip("-") or "index"


def strip_frontmatter(text: str) -> str:
    """Remove the leading --- ... --- YAML block from a content.md."""
    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        try:
            end = lines.index("---", 1)
            return "\n".join(lines[end + 1:]).lstrip()
        except ValueError:
            pass
    return text


# ─── per-page fetch ───────────────────────────────────────────────────────────

def fetch_page(url: str, page_dir: Path, timeout: int, user_agent: str) -> bool:
    """
    Call fetch.py for one URL. Returns True on success.
    fetch.py is idempotent: skips silently if page_dir/content.md already exists.
    """
    result = subprocess.run(
        [
            sys.executable, str(FETCH_SCRIPT),
            url,
            "--out-dir", str(page_dir),
            "--playwright",
            "--timeout", str(timeout),
            "--user-agent", user_agent,
        ],
        capture_output=True,
        text=True,
    )
    if result.stderr.strip():
        print(result.stderr.rstrip(), file=sys.stderr)
    return result.returncode == 0


# ─── main crawl ──────────────────────────────────────────────────────────────

def crawl(
    seed_url: str,
    out_dir: Path,
    path_prefix: str,
    max_pages: int,
    delay: float,
    user_agent: str,
    timeout: int,
) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    pages_dir = out_dir / ".pages"
    pages_dir.mkdir(exist_ok=True)

    warnings: list[str] = []
    fetched_at = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())

    # ── 1. discover nav links ─────────────────────────────────────────────────
    print(f"[web-crawl] seed: {seed_url}", file=sys.stderr)
    try:
        all_links, site_title, site_name = discover_nav_links(
            seed_url, path_prefix, timeout * 1000, user_agent
        )
    except RuntimeError as exc:
        print(f"[web-crawl] nav discovery failed: {exc}", file=sys.stderr)
        return 1

    seed_clean = seed_url.split("?")[0].rstrip("/")
    if seed_clean not in all_links:
        all_links = [seed_clean] + all_links

    print(
        f"[web-crawl] discovered {len(all_links)} candidate links under {path_prefix}",
        file=sys.stderr,
    )
    if len(all_links) > max_pages:
        warnings.append(f"Capped at {max_pages} pages (discovered {len(all_links)})")
        all_links = all_links[:max_pages]

    # ── 2. fetch each page via fetch.py ───────────────────────────────────────
    sections: list[dict] = []

    for i, url in enumerate(all_links):
        slug = url_to_slug(url)
        page_dir = pages_dir / slug

        print(f"[web-crawl]   [{i + 1}/{len(all_links)}] {slug}", file=sys.stderr)

        if not fetch_page(url, page_dir, timeout, user_agent):
            warnings.append(f"fetch.py failed: {url}")
            continue

        content_md = page_dir / "content.md"
        if not content_md.exists():
            warnings.append(f"No content.md: {url}")
            continue

        # Title from fetch.py's metadata.json
        title = slug.replace("-", " ").title()
        meta_path = page_dir / "metadata.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                if meta.get("title"):
                    title = meta["title"]
            except Exception:
                pass

        body = strip_frontmatter(content_md.read_text(encoding="utf-8"))
        word_count = len(body.split())

        if word_count < 30:
            msg = "auth-gated" if any(
                kw in body.lower() for kw in ("sign in", "log in", "okta")
            ) else "too thin"
            warnings.append(f"Skipped ({msg}): {url}")
            print(f"[web-crawl]     → skip ({msg})", file=sys.stderr)
            continue

        n_figs = len(list((page_dir / "figures").iterdir())) if (page_dir / "figures").exists() else 0
        print(f"[web-crawl]     → {word_count:>5} words, {n_figs} figures", file=sys.stderr)

        sections.append({"title": title, "url": url, "body": body, "page_dir": page_dir})

        if delay > 0:
            time.sleep(delay)

    if not sections:
        print("[web-crawl] no content extracted — check path-prefix and auth", file=sys.stderr)
        return 1

    # ── 3. merge figures/ from all pages into one shared figures/ ─────────────
    figures_dir = out_dir / "figures"
    figures_dir.mkdir(exist_ok=True)

    for sec in sections:
        page_figures = sec["page_dir"] / "figures"
        if page_figures.exists():
            for fig in page_figures.iterdir():
                if fig.is_file():
                    dest = figures_dir / fig.name
                    if not dest.exists():
                        shutil.copy2(fig, dest)

    # ── 4. stitch content.md ──────────────────────────────────────────────────
    combined_title = site_title or f"Documentation crawl of {urlparse(seed_url).netloc}"

    front = (
        f"---\n"
        f"url: {seed_url}\n"
        f"title: {json.dumps(combined_title)}\n"
        f"author: {json.dumps(site_name or '')}\n"
        f"site_name: {json.dumps(site_name or '')}\n"
        f"fetched_at: {fetched_at}\n"
        f"---\n\n"
    )

    body_parts = [
        f"# {combined_title}\n",
        f"*Assembled from {len(sections)} pages crawled under `{path_prefix}`.*\n",
    ]
    if warnings:
        body_parts.append(f"*Warnings: {len(warnings)} — see web_profile.json.*\n")
    body_parts.append("")

    for sec in sections:
        body_parts.append(f"---\n\n## {sec['title']}\n")
        body_parts.append(f"*Source: <{sec['url']}>*\n")
        body_parts.append(f"\n{sec['body']}\n")

    content = front + "\n".join(body_parts)
    (out_dir / "content.md").write_text(content, encoding="utf-8")

    # ── 5. write metadata.json + web_profile.json ─────────────────────────────
    agg_images = {"found": 0, "downloaded": 0, "skipped": 0, "failed": 0}
    agg_math = {"katex": 0, "mathjax_script": 0, "mathml": 0, "raw_delim": 0}
    all_warnings: list[str] = list(warnings)

    for sec in sections:
        profile_path = sec["page_dir"] / "web_profile.json"
        if profile_path.exists():
            try:
                pg = json.loads(profile_path.read_text(encoding="utf-8"))
                for k in agg_images:
                    agg_images[k] += pg.get("images", {}).get(k, 0)
                for k in agg_math:
                    agg_math[k] += pg.get("math", {}).get(k, 0)
                all_warnings.extend(pg.get("warnings", []))
            except Exception:
                pass

    (out_dir / "metadata.json").write_text(
        json.dumps({
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
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    (out_dir / "web_profile.json").write_text(
        json.dumps({
            "url": seed_url,
            "final_url": seed_url,
            "fetcher": "playwright-multi",
            "extractor": "fetch.py-per-page",
            "math": agg_math,
            "images": agg_images,
            "inline_svgs": 0,
            "warnings": all_warnings,
            "pages_crawled": [{"title": s["title"], "url": s["url"]} for s in sections],
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(
        f"[web-crawl] done: {out_dir}/content.md "
        f"({len(sections)} pages, {content.count(chr(10))} lines, {len(content):,} chars, "
        f"images: {agg_images['downloaded']} downloaded)",
        file=sys.stderr,
    )
    return 0


# ─── CLI ─────────────────────────────────────────────────────────────────────

def _default_prefix(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    parent = path.rsplit("/", 1)[0] if "/" in path else path
    return f"{parsed.scheme}://{parsed.netloc}{parent}"


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("url", help="Seed URL — nav links are discovered from this page")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--path-prefix", default=None)
    p.add_argument("--max-pages", type=int, default=40)
    p.add_argument("--delay", type=float, default=0.5)
    p.add_argument("--user-agent", default=DEFAULT_UA)
    p.add_argument("--timeout", type=int, default=30)
    args = p.parse_args()

    out_dir = Path(args.out_dir)
    if (out_dir / "content.md").exists() and (out_dir / "metadata.json").exists():
        print(f"[web-crawl] already done: {out_dir} — delete it to re-crawl", file=sys.stderr)
        return 0

    return crawl(
        seed_url=args.url,
        out_dir=out_dir,
        path_prefix=args.path_prefix or _default_prefix(args.url),
        max_pages=args.max_pages,
        delay=args.delay,
        user_agent=args.user_agent,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    sys.exit(main())
