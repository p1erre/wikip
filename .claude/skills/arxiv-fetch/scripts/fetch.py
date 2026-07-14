"""Fetch an arXiv paper and prepare its LaTeX source for section-by-section conversion.

Pipeline:
  1. Normalize the arxiv ID (arxiv_api).
  2. Hit arxiv.org/e-print/<id> — that endpoint either returns a tarball of the
     LaTeX source, a single gzipped .tex, or a PDF (when no source was uploaded).
     (arxiv_api)
  3. If we got a PDF, write paper.pdf + no_source.flag and stop.
  4. Otherwise locate the main .tex, split off the preamble, recursively inline
     nested \\input/\\include/\\subfile, and emit one section file per top-level
     boundary. (sections)
  5. Copy raster figures and convert EPS/PDF figures to PNG. (figures)
  6. Extract figure metadata (caption, label, image refs, has_tikz) into
     figures.json. (figures)
  7. Surface bibliography files and write structure.json.
  8. Derive content.md — the bundle contract's single-file, LLM-legible
     rendition of the source (preamble + sections concatenated, fenced as
     LaTeX). Downstream skills (wikip source-doc staging) read only this.

Idempotent: skips if raw/structure.json or raw/no_source.flag already exists;
the skip path self-heals a missing content.md. Use --derive-only to (re)write
content.md from an already-extracted raw/ without any network access.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.error
from pathlib import Path

from arxiv_api import (
    download_eprint,
    extract_source,
    fetch_metadata,
    looks_like_pdf,
    parse_arxiv_id,
)
from figures import copy_figures, extract_figures, figure_stats
from sections import (
    find_main_tex,
    find_top_level_inputs,
    find_unhandled_includes,
    inline_includes,
    slugify,
    split_body_by_input,
    split_body_by_section,
    split_preamble,
)
from tex_utils import strip_comments
from tikz_render import render_tikz_figures, sanitize_preamble

# Four-backtick fences so occasional triple backticks inside the source
# don't terminate the block.
FENCE = "````"


def figures_gallery(raw_dir: Path) -> str:
    """Markdown gallery of every figure in figures.json.

    Images are embedded via bundle-root-relative refs (raw/figures/...,
    raw/_tikz/...) so downstream staging can rewrite them into a vault.
    Full captions are kept as visible blockquote text — the author's own
    description of each figure must never be lost. Figures without a
    rendered image fall back to their raw TikZ source plus caption.
    """
    figures_path = raw_dir / "figures.json"
    if not figures_path.exists():
        return ""
    records = json.loads(figures_path.read_text()).get("figures", [])
    if not records:
        return ""

    def entry(rec: dict, heading: str, fallback_label: str) -> list[str]:
        label = rec.get("label") or fallback_label
        section = rec.get("section_file") or ""
        lines = [f"{heading} {label}" + (f" — `{section}`" if section else ""), ""]
        for p in dict.fromkeys(rec.get("resolved_paths", [])):  # dedupe, keep order
            lines += [f"![{label}](raw/{p})", ""]
        if not rec.get("resolved_paths") and rec.get("tikz_sources"):
            lines += ["_No rendered image — raw TikZ source:_", ""]
            for src in rec["tikz_sources"]:
                lines += [f"{FENCE}latex\n{src.strip()}\n{FENCE}", ""]
        caption = (rec.get("caption") or "").strip()
        if caption:
            lines += ["> " + caption.replace("\n", "\n> "), ""]
        return lines

    lines = ["## Figures", ""]
    for i, rec in enumerate(records, start=1):
        lines += entry(rec, "###", f"figure-{i}")
        for j, sub in enumerate(rec.get("subfigures", []), start=1):
            lines += entry(sub, "####", f"subfigure-{i}.{j}")
    return "\n".join(lines).rstrip() + "\n"


def write_content_md(out_dir: Path, raw_dir: Path) -> Path:
    """Derive <out_dir>/content.md from the extracted LaTeX under raw/.

    Preamble first (macro context), then sections in structure.json order,
    each prefixed with a `% ==== <file> ====` marker. The whole body sits in
    a four-backtick latex fence so the file is markdown-presentable as-is.
    A `## Figures` gallery (figures_gallery) follows the fence so every
    figure is visible with its caption, not just referenced in the LaTeX.
    """
    structure = json.loads((raw_dir / "structure.json").read_text())
    meta_path = raw_dir / "arxiv_meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    title = meta.get("title") or structure.get("arxiv_id", "")

    parts: list[str] = []
    preamble = raw_dir / "preamble.tex"
    if preamble.exists():
        parts.append(f"% ==== preamble.tex ====\n{preamble.read_text(errors='replace').strip()}")
    for section in structure.get("sections", []):
        sec = raw_dir / section["file"]
        if sec.exists():
            parts.append(
                f"% ==== {section['file']} ====\n{sec.read_text(errors='replace').strip()}"
            )

    gallery = figures_gallery(raw_dir)
    content_path = out_dir / "content.md"
    content_path.write_text(
        "---\n"
        f"title: {json.dumps(title, ensure_ascii=False)}\n"
        f"arxiv_id: {structure.get('arxiv_id', '')}\n"
        "---\n\n"
        f"{FENCE}latex\n" + "\n\n".join(parts) + f"\n{FENCE}\n"
        + (f"\n{gallery}" if gallery else "")
    )
    return content_path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("arxiv_id", help="arxiv ID, URL, or 'arXiv:NNNN.NNNNN' form")
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument(
        "--derive-only",
        action="store_true",
        help="only (re)write content.md from an already-extracted raw/ (no network)",
    )
    args = ap.parse_args()

    arxiv_id, version = parse_arxiv_id(args.arxiv_id)
    out_dir: Path = args.out_dir
    raw_dir = out_dir / "raw"
    structure_path = raw_dir / "structure.json"
    no_source_flag = raw_dir / "no_source.flag"

    if args.derive_only:
        if not structure_path.exists():
            sys.exit(f"--derive-only needs {structure_path}; run a full fetch first")
        content_path = write_content_md(out_dir, raw_dir)
        print(f"derived {content_path} ({content_path.stat().st_size:,} bytes)")
        return 0

    if structure_path.exists():
        if not (out_dir / "content.md").exists():
            content_path = write_content_md(out_dir, raw_dir)
            print(f"derived missing {content_path}")
        print(f"already extracted (structure.json present); delete {raw_dir} to refetch")
        return 0
    if no_source_flag.exists():
        print(f"already determined: no LaTeX source for {arxiv_id} (delete {raw_dir} to retry)")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    print(f"fetching metadata for {arxiv_id}...")
    meta = fetch_metadata(arxiv_id)
    (raw_dir / "arxiv_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))

    print(f"downloading e-print for {arxiv_id}...")
    try:
        blob = download_eprint(arxiv_id, version)
    except urllib.error.HTTPError as e:
        sys.exit(f"e-print fetch failed ({e.code}): {e.reason}")

    if looks_like_pdf(blob):
        print("e-print is a PDF — no LaTeX source available")
        (raw_dir / "paper.pdf").write_bytes(blob)
        no_source_flag.write_text(f"arxiv {arxiv_id} has no LaTeX source\n")
        return 0

    source_root = raw_dir / "_source"
    extract_source(blob, source_root)

    main_tex = find_main_tex(source_root)
    print(f"main file: {main_tex.relative_to(source_root)}")
    main_text = strip_comments(main_tex.read_text(encoding="utf-8", errors="replace"))
    preamble, body = split_preamble(main_text)

    (raw_dir / "preamble.tex").write_text(preamble.strip() + "\n")

    sections_dir = raw_dir / "sections"
    sections_dir.mkdir(exist_ok=True)

    top_inputs = find_top_level_inputs(body)
    warnings: list[str] = []
    if len(top_inputs) >= 2:
        parts, split_warnings = split_body_by_input(body, source_root, main_tex.parent)
        warnings.extend(split_warnings)
    else:
        # Monolithic — fully inline (in case there are scattered \input's), then split on \section
        visited: set[Path] = set()
        inlined = inline_includes(body, main_tex.parent, source_root, visited, warnings)
        parts = split_body_by_section(inlined)

    structure: list[dict] = []
    for i, (title, content) in enumerate(parts, start=1):
        slug = slugify(title, fallback=f"section-{i:02d}")
        fname = f"{i:02d}_{slug}.tex"
        (sections_dir / fname).write_text(content.strip() + "\n")
        structure.append({"file": f"sections/{fname}", "title_hint": title})
        for frag in find_unhandled_includes(content):
            warnings.append(
                f"unhandled include macro in {fname}: {frag!r} — "
                f"content may be missing (original file under raw/_source/)"
            )

    figure_warnings = copy_figures(source_root, raw_dir / "figures")
    warnings.extend(figure_warnings)

    figure_records = extract_figures(
        sorted(sections_dir.glob("*.tex")),
        raw_dir / "figures",
        sections_dir,
    )

    sanitized = sanitize_preamble(preamble)
    tikz_warnings = render_tikz_figures(figure_records, raw_dir, sanitized, source_root)
    warnings.extend(tikz_warnings)

    stats = figure_stats(figure_records)
    (raw_dir / "figures.json").write_text(
        json.dumps({"figures": figure_records, "stats": stats}, indent=2, ensure_ascii=False)
    )

    # Surface bibliography files for downstream citation resolution.
    for bib in source_root.rglob("*.bib"):
        shutil.copy2(bib, raw_dir / bib.name)
    for bbl in source_root.rglob("*.bbl"):
        shutil.copy2(bbl, raw_dir / bbl.name)

    structure_path.write_text(
        json.dumps(
            {
                "arxiv_id": arxiv_id,
                "version": version or meta.get("version"),
                "main_tex": str(main_tex.relative_to(source_root)),
                "sections": structure,
                "warnings": warnings,
            },
            indent=2,
            ensure_ascii=False,
        )
    )

    content_path = write_content_md(out_dir, raw_dir)

    print(f"wrote {len(structure)} sections to {sections_dir}")
    print(f"derived {content_path} ({content_path.stat().st_size:,} bytes)")
    print(
        f"figures: {stats['total']} total, "
        f"{stats['with_image']} with raster image, "
        f"{stats['tikz_only']} TikZ-only"
    )
    if warnings:
        print(f"{len(warnings)} warnings — see structure.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
