"""Stage a source document into a wikip vault.

Derives a single, complete, LLM-legible rendition of a source bundle and
writes it to <wiki-dir>/sources/<paper-slug>-source.md, so the paper page
can link back to the full source text (frontmatter `source_doc:` plus a
visible `**Source text:** [[<paper-slug>-source]]` line).

Bundle types (detected by file presence, same rules as SKILL.md):
  raw/structure.json                 arxiv-fetch    -> sections concatenated as LaTeX
  booklet.md                         video booklet  -> booklet markdown
  content.md + *_profile.json        web/clip/deep-research/pdf -> content markdown
  transcript.txt + metadata.json     bare video transcript -> fenced transcript

For markdown sources, image refs into the bundle's figures/ are rewritten to
../assets/<paper-slug>/ and the referenced figures are copied into the vault
so the source doc renders in Obsidian.

Deterministic derivation: re-running overwrites the staged file.

Exit codes: 0 staged; 2 nothing stageable (e.g. arxiv bundle with
no_source.flag — extract the PDF first); 1 bad invocation.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sys
from pathlib import Path

FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
FIGURE_REF_RE = re.compile(r"(!?\[[^\]]*\]\()figures/")

# Four-backtick fences so occasional triple backticks inside the source
# don't terminate the block.
FENCE = "````"


def detect(source_dir: Path) -> str:
    if (source_dir / "raw" / "structure.json").exists():
        return "arxiv"
    if (source_dir / "raw" / "no_source.flag").exists():
        return "arxiv-pdf-only"
    if (source_dir / "booklet.md").exists():
        return "booklet"
    if (source_dir / "content.md").exists():
        for profile, kind in (
            ("web_profile.json", "web"),
            ("clip_profile.json", "clip"),
            ("deep_research_profile.json", "deep-research"),
        ):
            if (source_dir / profile).exists():
                return kind
        if (source_dir / "metadata.json").exists():
            return "pdf"
    if (source_dir / "transcript.txt").exists() and (source_dir / "metadata.json").exists():
        return "transcript"
    sys.exit(f"unrecognised bundle: {source_dir} matches no known bundle shape")


def bundle_title(source_dir: Path, kind: str) -> str | None:
    meta_path = (
        source_dir / "raw" / "arxiv_meta.json" if kind == "arxiv" else source_dir / "metadata.json"
    )
    if meta_path.exists():
        try:
            return json.loads(meta_path.read_text()).get("title")
        except (json.JSONDecodeError, OSError):
            return None
    return None


def arxiv_body(source_dir: Path) -> str:
    raw = source_dir / "raw"
    structure = json.loads((raw / "structure.json").read_text())
    parts: list[str] = []
    preamble = raw / "preamble.tex"
    if preamble.exists():
        parts.append(f"% ==== preamble.tex ====\n{preamble.read_text(errors='replace')}")
    for section in structure.get("sections", []):
        sec_path = raw / "sections" / section["file"]
        if sec_path.exists():
            parts.append(f"% ==== {section['file']} ====\n{sec_path.read_text(errors='replace')}")
    return f"{FENCE}latex\n" + "\n\n".join(parts).strip() + f"\n{FENCE}\n"


def markdown_body(content_path: Path, source_dir: Path, wiki_dir: Path, paper_slug: str) -> str:
    text = FRONTMATTER_RE.sub("", content_path.read_text(errors="replace"), count=1)
    figures = source_dir / "figures"
    if figures.is_dir() and FIGURE_REF_RE.search(text):
        assets = wiki_dir / "assets" / paper_slug
        assets.mkdir(parents=True, exist_ok=True)
        for fig in figures.iterdir():
            if fig.is_file() and not (assets / fig.name).exists():
                shutil.copy2(fig, assets / fig.name)
        text = FIGURE_REF_RE.sub(rf"\g<1>../assets/{paper_slug}/", text)
    return text.strip() + "\n"


def transcript_body(source_dir: Path) -> str:
    text = (source_dir / "transcript.txt").read_text(errors="replace").strip()
    return f"{FENCE}text\n{text}\n{FENCE}\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source_dir", type=Path, help="source bundle directory")
    ap.add_argument("wiki_dir", type=Path, help="corpus wiki (vault) directory")
    ap.add_argument("paper_slug", help="title-based slug of the paper page this source backs")
    ap.add_argument("--title", help="source title for the doc header (default: bundle metadata)")
    args = ap.parse_args()

    source_dir: Path = args.source_dir
    wiki_dir: Path = args.wiki_dir
    slug: str = args.paper_slug
    if not source_dir.is_dir():
        sys.exit(f"source dir not found: {source_dir}")
    if not (wiki_dir / "pages").is_dir():
        sys.exit(f"not a wikip vault (no pages/): {wiki_dir}")

    kind = detect(source_dir)
    if kind == "arxiv-pdf-only":
        print(
            f"{source_dir}: no LaTeX source (no_source.flag) — run pdf-extract on "
            "raw/paper.pdf and stage from that bundle instead",
            file=sys.stderr,
        )
        return 2

    if kind == "arxiv":
        body = arxiv_body(source_dir)
    elif kind == "transcript":
        body = transcript_body(source_dir)
    else:
        content = source_dir / ("booklet.md" if kind == "booklet" else "content.md")
        body = markdown_body(content, source_dir, wiki_dir, slug)

    title = args.title or bundle_title(source_dir, kind) or slug
    out_dir = wiki_dir / "sources"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{slug}-source.md"
    out_path.write_text(
        "---\n"
        f"slug: {slug}-source\n"
        f"paper: {slug}\n"
        f"source: {source_dir.name}\n"
        f"kind: {kind}\n"
        f"staged: {dt.date.today().isoformat()}\n"
        "---\n\n"
        f"# Source: {title}\n\n"
        f"> Raw source text staged from bundle `{source_dir.name}` ({kind}). "
        f"Complete, LLM-legible rendition of the source; the synthesised view is [[{slug}]].\n\n"
        + body
    )
    print(f"staged {out_path} ({kind}, {out_path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
