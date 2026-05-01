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

Idempotent: skips if raw/structure.json or raw/no_source.flag already exists.
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
    inline_includes,
    slugify,
    split_body_by_input,
    split_body_by_section,
    split_preamble,
)
from tex_utils import strip_comments


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("arxiv_id", help="arxiv ID, URL, or 'arXiv:NNNN.NNNNN' form")
    ap.add_argument("--out-dir", required=True, type=Path)
    args = ap.parse_args()

    arxiv_id, version = parse_arxiv_id(args.arxiv_id)
    out_dir: Path = args.out_dir
    raw_dir = out_dir / "raw"
    structure_path = raw_dir / "structure.json"
    no_source_flag = raw_dir / "no_source.flag"

    if structure_path.exists():
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

    figure_warnings = copy_figures(source_root, raw_dir / "figures")
    warnings.extend(figure_warnings)

    figure_records = extract_figures(
        sorted(sections_dir.glob("*.tex")),
        raw_dir / "figures",
        sections_dir,
    )
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

    print(f"wrote {len(structure)} sections to {sections_dir}")
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
