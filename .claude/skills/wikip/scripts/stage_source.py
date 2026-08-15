"""Stage a source document into a wikip vault.

Copies a bundle's content.md — the bundle contract's single-file, complete,
LLM-legible rendition of the source, produced by every fetcher — to
<wiki-dir>/sources/<paper-slug>-source.md, so the paper page can link back to
the full source text (frontmatter `source_doc:` plus a visible
`**Source text:** [[<paper-slug>-source]]` line).

Contract-only: this script knows nothing about bundle types. Its one rule for
assets is copy-what-you-reference — every image embed whose relative path
exists in the bundle is copied to <wiki-dir>/assets/<paper-slug>/<same
relative path> (subpaths preserved, so figures/x.png and raw/_tikz/x.png can
never collide) and the ref is rewritten to ../assets/<paper-slug>/<path>.
Obsidian then renders the staged doc entirely from inside the vault.

Deterministic derivation: re-running overwrites the staged file (assets are
only copied when missing).

Exit codes: 0 staged; 1 bad invocation or bundle without content.md (run the
fetcher's derive step first — e.g. arxiv-fetch --derive-only, or re-run
video-transcript-fetch over the bundle).
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import shutil
import sys
from pathlib import Path

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
IMAGE_REF_RE = re.compile(r"(!\[[^\]]*\]\()([^)]+)(\))")
TITLE_LINE_RE = re.compile(r"^title:\s*(.+)$", re.MULTILINE)


def stage_assets(body: str, source_dir: Path, wiki_dir: Path, paper_slug: str) -> tuple[str, int]:
    """Copy every bundle-local image the body references into the vault and
    rewrite the refs. Returns (rewritten_body, copied_count)."""
    assets_root = wiki_dir / "assets" / paper_slug
    copied = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal copied
        ref = m.group(2).strip()
        if ref.startswith(("http://", "https://", "/", "data:")):
            return m.group(0)
        src = source_dir / ref
        if not src.is_file():
            return m.group(0)
        dest = assets_root / ref
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        copied += 1
        return f"{m.group(1)}../assets/{paper_slug}/{ref}{m.group(3)}"

    return IMAGE_REF_RE.sub(repl, body), copied


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source_dir", type=Path, help="source bundle directory")
    ap.add_argument("wiki_dir", type=Path, help="corpus wiki (vault) directory")
    ap.add_argument("paper_slug", help="title-based slug of the paper page this source backs")
    ap.add_argument("--title", help="source title for the doc header (default: content.md frontmatter)")
    args = ap.parse_args()

    source_dir: Path = args.source_dir
    wiki_dir: Path = args.wiki_dir
    slug: str = args.paper_slug
    if not source_dir.is_dir():
        sys.exit(f"source dir not found: {source_dir}")
    if not (wiki_dir / "pages").is_dir():
        sys.exit(f"not a wikip vault (no pages/): {wiki_dir}")
    content_path = source_dir / "content.md"
    if not content_path.exists():
        sys.exit(
            f"{source_dir} has no content.md — every bundle must carry the single-file "
            "rendition. Run the fetcher's derive step first (arxiv-fetch --derive-only; "
            "video-transcript-fetch re-run; web/pdf/clip produce it natively)."
        )

    text = content_path.read_text(encoding="utf-8", errors="replace")
    title = args.title
    fm = FRONTMATTER_RE.match(text)
    if fm and not title:
        m = TITLE_LINE_RE.search(fm.group(1))
        if m:
            title = m.group(1).strip().strip('"').strip("'")
    title = title or slug
    body = FRONTMATTER_RE.sub("", text, count=1).strip()

    body, copied = stage_assets(body, source_dir, wiki_dir, slug)

    out_dir = wiki_dir / "sources"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{slug}-source.md"
    out_path.write_text(
        "---\n"
        f"slug: {slug}-source\n"
        f"paper: {slug}\n"
        f"source: {source_dir.name}\n"
        f"staged: {dt.date.today().isoformat()}\n"
        "---\n\n"
        f"# Source: {title}\n\n"
        f"> Complete source text staged from bundle `{source_dir.name}`. "
        f"The synthesised view is [[{slug}]].\n\n"
        + body
        + "\n"
    )
    print(
        f"staged {out_path} ({out_path.stat().st_size:,} bytes, "
        f"{copied} asset ref(s) → assets/{slug}/)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
