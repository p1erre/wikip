#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "httpx>=0.27.0",
#   "beautifulsoup4>=4.12.0",
#   "markdownify>=0.13.1",
#   "readability-lxml>=0.8.1",
#   "playwright>=1.40.0",
# ]
# ///
"""
Fetch a web page into clean markdown + extracted figures + metadata.

Usage:
  fetch.py <url> --out-dir <dir>
           [--playwright]              opt-in: render with headless browser (for SPAs)
           [--user-agent <ua>]         override default UA
           [--timeout <seconds>]       fetch timeout, default 30
           [--no-images]               skip image download
           [--max-image-bytes <N>]     skip individual images larger than N bytes (default 10MB)

Writes (mirrors pdf-extract layout so wikip detects the bundle automatically):
  <out-dir>/content.md          markdown body, $...$ / $$...$$ for math, ![](figures/…) for images
  <out-dir>/figures/            downloaded raster + SVG figures
  <out-dir>/metadata.json       {url, final_url, title, author, published, fetched_at, ...}
  <out-dir>/web_profile.json    diagnostics: math patterns matched, image fetch results, warnings

Idempotent: skips if content.md and metadata.json both exist.
"""

import argparse
import datetime as dt
import hashlib
import json
import mimetypes
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, NavigableString, Tag
from markdownify import MarkdownConverter
from readability import Document

DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)


# ---------- profile ----------


@dataclass
class WebProfile:
    url: str
    final_url: str
    fetcher: str = "httpx"  # or "playwright"
    extractor: str = "readability"  # or "chrome-strip"
    title: str | None = None
    math: dict = field(default_factory=lambda: {"katex": 0, "mathjax_script": 0, "mathml": 0, "raw_delim": 0})
    images: dict = field(default_factory=lambda: {"found": 0, "downloaded": 0, "skipped": 0, "failed": 0})
    inline_svgs: int = 0
    warnings: list[str] = field(default_factory=list)


# ---------- fetch ----------


def fetch_html(url: str, user_agent: str, timeout: int, use_playwright: bool) -> tuple[str, str]:
    """Return (html, final_url) following redirects."""
    if use_playwright:
        return _fetch_playwright(url, user_agent, timeout)
    headers = {"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml"}
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text, str(resp.url)


def _fetch_playwright(url: str, user_agent: str, timeout: int) -> tuple[str, str]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit(
            "Playwright not installed. Run: uv pip install -e '.[playwright]' && "
            "uv run playwright install chromium"
        )
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=user_agent)
        page = ctx.new_page()
        page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
        html = page.content()
        final_url = page.url
        browser.close()
        return html, final_url


# ---------- metadata ----------


def extract_metadata(soup: BeautifulSoup, url: str, final_url: str, fetched_at: str) -> dict:
    def meta(name: str) -> str | None:
        for sel in [
            {"property": name},
            {"name": name},
            {"itemprop": name},
        ]:
            tag = soup.find("meta", attrs=sel)
            if tag and tag.get("content"):
                return tag["content"].strip()
        return None

    def title() -> str | None:
        for getter in (lambda: meta("og:title"), lambda: meta("twitter:title")):
            v = getter()
            if v:
                return v
        if soup.title and soup.title.string:
            return soup.title.string.strip()
        return None

    def language() -> str | None:
        html = soup.find("html")
        if html and html.get("lang"):
            return html["lang"]
        return meta("og:locale")

    return {
        "url": url,
        "final_url": final_url,
        "title": title(),
        "author": meta("author") or meta("article:author") or meta("og:author"),
        "published": meta("article:published_time") or meta("datePublished") or meta("date"),
        "modified": meta("article:modified_time") or meta("dateModified"),
        "site_name": meta("og:site_name"),
        "description": meta("description") or meta("og:description"),
        "language": language(),
        "fetched_at": fetched_at,
    }


# ---------- math recovery ----------

MATH_TOKEN = "@@WEBFETCH_MATH_{kind}_{idx}@@"
RAW_INLINE_RE = re.compile(r"\\\((.+?)\\\)", re.DOTALL)
RAW_DISPLAY_RE = re.compile(r"\\\[(.+?)\\\]", re.DOTALL)
# $$...$$ display blocks (greedy across newlines, but non-greedy on content)
RAW_DOLLAR_DISPLAY_RE = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
# $...$ inline. Reject: empty, leading/trailing whitespace inside, newlines, adjacent $.
# This filters most currency false positives ($5, $1.50) since math has no plain numbers alone.
RAW_DOLLAR_INLINE_RE = re.compile(r"(?<![\$\w])\$(?!\s)([^\n$]{1,500}?)(?<!\s)\$(?![\$\w])")


def recover_math(soup: BeautifulSoup, profile: WebProfile) -> dict[str, tuple[str, bool]]:
    r"""
    Walk the DOM and replace math nodes with sentinel text tokens. Returns a dict
    {token: (latex_source, is_display)} for post-markdown substitution.

    Patterns covered:
      1. KaTeX:    <span class="katex"> with <annotation encoding="application/x-tex">
      2. MathJax:  <script type="math/tex"> (inline) / "math/tex; mode=display"
      3. MathML:   <math> with <annotation encoding="application/x-tex">
      4. Raw:      \(...\), \[...\], $...$, $$...$$ left as text nodes
    """
    store: dict[str, tuple[str, bool]] = {}
    counter = 0

    def take(latex: str, display: bool, kind: str) -> str:
        nonlocal counter
        counter += 1
        token = MATH_TOKEN.format(kind=kind, idx=counter)
        store[token] = (latex.strip(), display)
        return token

    # Pattern 1: KaTeX
    for span in soup.select("span.katex, .katex"):
        ann = span.find("annotation", attrs={"encoding": "application/x-tex"})
        if not ann or not ann.get_text():
            continue
        display = "katex-display" in (span.get("class") or []) or bool(
            span.find_parent(class_="katex-display")
        )
        token = take(ann.get_text(), display, "katex")
        span.replace_with(NavigableString(token))
        profile.math["katex"] += 1

    # Pattern 2: MathJax script tags
    for script in soup.find_all("script", attrs={"type": re.compile(r"^math/tex")}):
        latex = script.get_text() or ""
        display = "display" in (script.get("type") or "")
        token = take(latex, display, "mathjax")
        script.replace_with(NavigableString(token))
        profile.math["mathjax_script"] += 1

    # Pattern 3: MathML with TeX annotation
    for math_el in soup.find_all("math"):
        ann = math_el.find("annotation", attrs={"encoding": "application/x-tex"})
        if not ann or not ann.get_text():
            profile.warnings.append("MathML block without TeX annotation; skipping")
            continue
        display = math_el.get("display") == "block"
        token = take(ann.get_text(), display, "mathml")
        math_el.replace_with(NavigableString(token))
        profile.math["mathml"] += 1

    # Pattern 4: Raw delimiters in plain text nodes
    def _looks_like_math(s: str) -> bool:
        s = s.strip()
        if not s:
            return False
        # Short single-token expression: $T$, $x$, $N_t$, $f(x)$ — keep.
        if len(s) <= 8 and not re.search(r"\s\s|\bthat\b|\bthe\b|\band\b|\bis\b", s):
            return True
        # Has LaTeX command, subscript, superscript, or grouping: definitely math.
        if re.search(r"[\\_^{}]", s):
            return True
        # Short expression with operator + variable: "a = b + c", "x < 1".
        if len(s) <= 30 and re.search(r"[=+\-*/<>]", s) and re.search(r"[a-zA-Z]", s):
            return True
        return False

    def _replace_in_text(text: str) -> tuple[str, int]:
        hits = 0

        def _inline(m: re.Match) -> str:
            nonlocal hits
            if not _looks_like_math(m.group(1)):
                return m.group(0)
            hits += 1
            return take(m.group(1), False, "raw")

        def _display(m: re.Match) -> str:
            nonlocal hits
            # Display math $$...$$ is almost always real, but still apply the heuristic.
            if not _looks_like_math(m.group(1)):
                return m.group(0)
            hits += 1
            return take(m.group(1), True, "raw")

        # display first ($$ before $, \[ before \()
        text = RAW_DOLLAR_DISPLAY_RE.sub(_display, text)
        text = RAW_DISPLAY_RE.sub(_display, text)
        text = RAW_DOLLAR_INLINE_RE.sub(_inline, text)
        text = RAW_INLINE_RE.sub(_inline, text)
        return text, hits

    for node in list(soup.find_all(string=True)):
        if not isinstance(node, NavigableString) or isinstance(node, Tag):
            continue
        if node.parent is None or node.parent.name in {"script", "style", "code", "pre"}:
            continue
        # also skip if any ancestor is code/pre (nested formatting)
        if node.find_parent(["code", "pre"]) is not None:
            continue
        s = str(node)
        if "\\(" not in s and "\\[" not in s and "$" not in s:
            continue
        new_s, hits = _replace_in_text(s)
        if hits:
            node.replace_with(NavigableString(new_s))
            profile.math["raw_delim"] += hits

    return store


def restore_math(markdown: str, store: dict[str, tuple[str, bool]]) -> str:
    for token, (latex, display) in store.items():
        if display:
            replacement = f"\n\n$$\n{latex}\n$$\n\n"
        else:
            replacement = f"${latex}$"
        markdown = markdown.replace(token, replacement)
    return markdown


# ---------- inline SVG extraction ----------


def extract_inline_svgs(soup: BeautifulSoup, fig_dir: Path, profile: WebProfile) -> None:
    """Save each inline <svg> to figures/svg_NNN.svg and replace with <img>."""
    for idx, svg in enumerate(list(soup.find_all("svg")), start=1):
        if svg.find_parent("svg") is not None:
            continue  # nested svg, skip
        svg_str = str(svg)
        digest = hashlib.sha1(svg_str.encode("utf-8")).hexdigest()[:8]
        fname = f"svg_{idx:03d}_{digest}.svg"
        (fig_dir / fname).write_text(svg_str, encoding="utf-8")
        # alt-text from <title> or <desc> if present
        alt = ""
        t = svg.find("title")
        if t and t.get_text():
            alt = t.get_text().strip()
        replacement = soup.new_tag("img")
        replacement["src"] = f"figures/{fname}"
        replacement["alt"] = alt
        svg.replace_with(replacement)
        profile.inline_svgs += 1


# ---------- image harvesting ----------


def _safe_filename(url: str, content_type: str | None, idx: int) -> str:
    parsed = urlparse(url)
    base = Path(parsed.path).name or f"img_{idx:03d}"
    ext = Path(base).suffix
    if not ext and content_type:
        guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if guessed:
            ext = guessed
    if not ext:
        ext = ".bin"
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
    stem = Path(base).stem or f"img_{idx:03d}"
    # keep names readable but unique
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem)[:40]
    return f"{stem}_{digest}{ext}"


def harvest_images(
    soup: BeautifulSoup,
    base_url: str,
    fig_dir: Path,
    user_agent: str,
    timeout: int,
    max_bytes: int,
    profile: WebProfile,
) -> None:
    """Download every <img> referenced in the soup and rewrite src to local path."""
    seen: dict[str, str] = {}  # absolute_url -> local relative path

    headers = {"User-Agent": user_agent, "Accept": "image/*,*/*;q=0.8"}
    client = httpx.Client(follow_redirects=True, timeout=timeout, headers=headers)
    try:
        imgs = soup.find_all("img")
        profile.images["found"] = len(imgs)
        for idx, img in enumerate(imgs, start=1):
            src = (
                img.get("src")
                or img.get("data-src")
                or img.get("data-lazy-src")
                or img.get("data-original")
            )
            if not src:
                # try srcset
                srcset = img.get("srcset") or img.get("data-srcset")
                if srcset:
                    src = srcset.split(",")[0].strip().split(" ")[0]
            if not src:
                profile.images["skipped"] += 1
                continue
            if src.startswith("data:"):
                profile.images["skipped"] += 1
                continue
            if src.startswith("figures/"):
                # already-extracted asset (inline SVG); leave as-is
                continue
            absolute = urljoin(base_url, src)
            if absolute in seen:
                img["src"] = seen[absolute]
                continue
            try:
                with client.stream("GET", absolute) as resp:
                    resp.raise_for_status()
                    ctype = resp.headers.get("content-type")
                    clen = int(resp.headers.get("content-length") or 0)
                    if clen and clen > max_bytes:
                        profile.images["skipped"] += 1
                        profile.warnings.append(f"image too large, skipped: {absolute}")
                        continue
                    fname = _safe_filename(absolute, ctype, idx)
                    target = fig_dir / fname
                    written = 0
                    with target.open("wb") as fh:
                        for chunk in resp.iter_bytes():
                            written += len(chunk)
                            if written > max_bytes:
                                fh.close()
                                target.unlink(missing_ok=True)
                                raise ValueError("exceeded max_bytes during stream")
                            fh.write(chunk)
                local_rel = f"figures/{fname}"
                seen[absolute] = local_rel
                img["src"] = local_rel
                # strip lazy-load attrs so markdownify doesn't get confused
                for attr in ("data-src", "data-lazy-src", "data-original", "srcset", "data-srcset"):
                    if attr in img.attrs:
                        del img.attrs[attr]
                profile.images["downloaded"] += 1
            except Exception as e:
                profile.images["failed"] += 1
                profile.warnings.append(f"image fetch failed: {absolute} ({e})")
                # leave the original src so the markdown still has *some* reference
                img["src"] = absolute
    finally:
        client.close()


# ---------- markdownify ----------


class WikipMarkdownConverter(MarkdownConverter):
    """markdownify with sensible defaults for wiki ingestion."""

    def convert_pre(self, el, text, parent_tags):
        # keep code fences with language hint when class="language-foo"
        cls = " ".join(el.get("class") or [])
        lang = ""
        m = re.search(r"language-(\S+)", cls)
        if m:
            lang = m.group(1)
        # inner code element may also carry the class
        if not lang:
            code = el.find("code")
            if code:
                cls = " ".join(code.get("class") or [])
                m = re.search(r"language-(\S+)", cls)
                if m:
                    lang = m.group(1)
        body = el.get_text()
        return f"\n\n```{lang}\n{body.rstrip()}\n```\n\n"


def to_markdown(soup: BeautifulSoup) -> str:
    converter = WikipMarkdownConverter(
        heading_style="ATX",
        bullets="-",
        code_language="",
        escape_asterisks=False,
        escape_underscores=False,
    )
    return converter.convert_soup(soup)


# ---------- content extraction ----------

CHROME_TAGS = ["nav", "footer", "header", "aside", "script", "style", "noscript", "iframe", "form"]
CONTENT_SELECTORS = [
    "article",
    "main",
    "[role='main']",
    "#content",
    "#main",
    "#main-content",
    ".post-content",
    ".article-content",
    ".entry-content",
    ".post",
    ".article",
    ".content",
]


def chrome_strip_html(html: str) -> str:
    """Pick the best content container, strip obvious chrome from inside, return HTML."""
    soup = BeautifulSoup(html, "lxml")
    container = None
    for selector in CONTENT_SELECTORS:
        el = soup.select_one(selector)
        if el and len(el.get_text(strip=True)) > 500:
            container = el
            break
    if container is None:
        container = soup.body or soup
    for tag_name in CHROME_TAGS:
        for el in container.find_all(tag_name):
            el.decompose()
    return str(container)


def extract_content_html(html: str, full_image_count: int) -> tuple[str, str]:
    """
    Returns (cleaned_html, strategy).
    Tries Readability with image-protection markers; falls back to chrome-strip
    when the page's images don't survive (e.g. book-shaped pages where Readability
    prunes whole figure-bearing sections).
    """
    protect_soup = BeautifulSoup(html, "lxml")
    marker_map: dict[str, str] = {}
    for idx, el in enumerate(protect_soup.find_all(["img", "svg"]), start=1):
        if el.name == "svg" and el.find_parent("svg") is not None:
            continue
        if el.name == "img" and el.find_parent("svg") is not None:
            continue
        token = f"@@WEBFETCH_PROTECT_{idx}@@"
        marker_map[token] = str(el)
        el.replace_with(NavigableString(token))
    protected_html = str(protect_soup)

    cleaned = Document(protected_html).summary(html_partial=True)
    surviving = sum(1 for t in marker_map if t in cleaned)
    survival_rate = (surviving / full_image_count) if full_image_count else 1.0

    # Fall back when Readability drops most images on an image-heavy page.
    if full_image_count >= 5 and survival_rate < 0.3:
        return chrome_strip_html(html), "chrome-strip"

    for token, original in marker_map.items():
        cleaned = cleaned.replace(token, original)
    return cleaned, "readability"


# ---------- main ----------


def run(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(exist_ok=True)

    content_md = out_dir / "content.md"
    metadata_json = out_dir / "metadata.json"
    if content_md.exists() and metadata_json.exists():
        print(f"[web-fetch] cached: {content_md} (delete to refetch)", file=sys.stderr)
        return 0

    fetched_at = dt.datetime.now(dt.UTC).isoformat()
    print(f"[web-fetch] fetching {args.url}", file=sys.stderr)
    html, final_url = fetch_html(
        args.url,
        user_agent=args.user_agent,
        timeout=args.timeout,
        use_playwright=args.playwright,
    )

    full_soup = BeautifulSoup(html, "lxml")
    metadata = extract_metadata(full_soup, args.url, final_url, fetched_at)
    full_image_count = len(full_soup.find_all(["img", "svg"]))

    cleaned_html, strategy = extract_content_html(html, full_image_count)
    if not metadata.get("title"):
        metadata["title"] = Document(html).short_title()

    content_soup = BeautifulSoup(cleaned_html, "lxml")

    profile = WebProfile(url=args.url, final_url=final_url, title=metadata.get("title"))
    profile.fetcher = "playwright" if args.playwright else "httpx"
    profile.extractor = strategy

    # Order matters: math first (so we don't lose annotations during img/svg passes),
    # then SVG (it rewrites <svg> -> <img>), then images (downloads everything we now reference).
    math_store = recover_math(content_soup, profile)
    extract_inline_svgs(content_soup, fig_dir, profile)
    if not args.no_images:
        harvest_images(
            content_soup,
            base_url=final_url,
            fig_dir=fig_dir,
            user_agent=args.user_agent,
            timeout=args.timeout,
            max_bytes=args.max_image_bytes,
            profile=profile,
        )

    body = to_markdown(content_soup).strip()
    body = restore_math(body, math_store)
    body = re.sub(r"\n{3,}", "\n\n", body)

    title = metadata.get("title") or args.url
    front = (
        f"---\n"
        f"url: {metadata['url']}\n"
        f"final_url: {metadata['final_url']}\n"
        f"title: {json.dumps(title)}\n"
        f"author: {json.dumps(metadata.get('author') or '')}\n"
        f"published: {metadata.get('published') or ''}\n"
        f"site_name: {json.dumps(metadata.get('site_name') or '')}\n"
        f"fetched_at: {fetched_at}\n"
        f"---\n\n"
    )
    md = f"{front}# {title}\n\n{body}\n"
    content_md.write_text(md, encoding="utf-8")

    metadata_json.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "web_profile.json").write_text(
        json.dumps(asdict(profile), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(
        f"[web-fetch] done: {content_md} "
        f"(images: {profile.images['downloaded']}/{profile.images['found']} downloaded, "
        f"math: {sum(profile.math.values())}, svg: {profile.inline_svgs})",
        file=sys.stderr,
    )
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("url")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--playwright", action="store_true", help="use headless browser (for SPAs)")
    p.add_argument("--user-agent", default=DEFAULT_UA)
    p.add_argument("--timeout", type=int, default=30)
    p.add_argument("--no-images", action="store_true")
    p.add_argument("--max-image-bytes", type=int, default=10 * 1024 * 1024)
    args = p.parse_args()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
