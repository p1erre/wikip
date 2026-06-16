#!/usr/bin/env python3
"""
Extract one section / chapter / page range from a long PDF, lazily.

Resolves a selection to a physical page range (via book_map.json when
available), slices just those pages into a temporary PDF, and hands that slice
to the existing pdf-extract ladder. The output is a normal pdf-extract bundle,
scoped to the slice, so it both reads standalone and flows into wikip.

Sections are written into the book's home folder beside book_map.json (with
--map) or into work/books/<book-slug>/ (with --pdf, copying the PDF in once).
Override with --out-dir.

Usage:
  read.py --map <book_map.json> --section "<title | slug | index>" [--out-dir DIR]
  read.py --map <book_map.json> --printed-pages A-B [--out-dir DIR]
  read.py --pdf <book.pdf>      --pages A-B          [--out-dir DIR]   # physical
                    [--quick]                  # pymupdf-only, fast skim
                    [--force-strategy ...] [--quality-threshold 0.7]

Selection precedence: --pages > --printed-pages > --section.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import fitz  # pymupdf

EXTRACT = Path(__file__).resolve().parents[2] / "pdf-extract" / "scripts" / "extract.py"
BOOKS_DIR = "work/books"


def slugify(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[\s_-]+", "-", s)[:60].strip("-") or "book"


def parse_range(spec: str) -> tuple[int, int]:
    a, _, b = spec.partition("-")
    a = int(a)
    return a, int(b or a)


def resolve_section(book_map: dict, sel: str) -> dict:
    entries = book_map["entries"]
    if not entries:
        raise SystemExit("book_map has no entries; use --pages instead")
    # by index
    if sel.isdigit():
        i = int(sel)
        for e in entries:
            if e["index"] == i:
                return e
    # exact slug
    s = sel.lower()
    for e in entries:
        if e["slug"] == s:
            return e
    # substring on title (first match)
    for e in entries:
        if s in e["title"].lower():
            return e
    raise SystemExit(f"No section matching {sel!r}. "
                     f"Available: {', '.join(e['slug'] for e in entries[:20])}")


def slice_pdf(src: Path, start: int, end: int) -> Path:
    """Copy physical pages [start, end] (1-based, inclusive) into a temp PDF."""
    doc = fitz.open(src)
    n = doc.page_count
    start = max(1, start)
    end = min(end, n)
    out = fitz.open()
    out.insert_pdf(doc, from_page=start - 1, to_page=end - 1)
    tmp = Path(tempfile.mkdtemp(prefix="book-slice-")) / f"slice_{start}-{end}.pdf"
    out.save(tmp)
    out.close()
    doc.close()
    return tmp


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", dest="map_path")
    ap.add_argument("--pdf")
    ap.add_argument("--section")
    ap.add_argument("--pages", help="physical page range, e.g. 120-145")
    ap.add_argument("--printed-pages", help="printed-folio range; needs --map")
    ap.add_argument("--out-dir")
    ap.add_argument("--quick", action="store_true", help="pymupdf-only fast skim")
    ap.add_argument("--force-strategy", default="auto")
    ap.add_argument("--quality-threshold", default="0.7")
    args = ap.parse_args()

    book_map = None
    if args.map_path:
        map_path = Path(args.map_path).resolve()
        book_map = json.loads(map_path.read_text())
        src = Path(book_map["source_pdf"])
        book_slug = book_map.get("book_slug", slugify(src.stem))
        home = map_path.parent  # sections land beside the map, in the book home
    elif args.pdf:
        # ad-hoc: establish the book's home folder and copy the PDF in once
        pdf = Path(args.pdf).resolve()
        if not pdf.is_file():
            raise SystemExit(f"Source PDF not found: {pdf}")
        book_slug = slugify(pdf.stem)
        home = (Path(BOOKS_DIR) / book_slug).resolve()
        home.mkdir(parents=True, exist_ok=True)
        src = home / pdf.name
        if src.resolve() != pdf.resolve() and not src.exists():
            shutil.copy2(pdf, src)
            print(f"Copied book into {src}", file=sys.stderr)
    else:
        raise SystemExit("Provide --map or --pdf")

    if not src.is_file():
        raise SystemExit(f"Source PDF not found: {src}")

    # resolve selection → physical range + a label
    if args.pages:
        start, end = parse_range(args.pages)
        label = f"pages-{start}-{end}"
    elif args.printed_pages:
        if not book_map:
            raise SystemExit("--printed-pages requires --map (for the delta)")
        pa, pb = parse_range(args.printed_pages)
        delta = book_map.get("delta", 0)
        start, end = pa + delta, pb + delta
        label = f"printed-{pa}-{pb}"
    elif args.section:
        if not book_map:
            raise SystemExit("--section requires --map")
        e = resolve_section(book_map, args.section)
        start, end = e["physical_start"], e["physical_end"]
        label = e["slug"]
    else:
        raise SystemExit("Provide --pages, --printed-pages, or --section")

    out_dir = (Path(args.out_dir).resolve() if args.out_dir
               else home / label)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Slicing physical pages {start}-{end} ({end - start + 1} pp)…",
          file=sys.stderr)
    slice_path = slice_pdf(src, start, end)

    strategy = "pymupdf" if args.quick else args.force_strategy
    cmd = ["uv", "run", "python3", str(EXTRACT), str(slice_path),
           "--out-dir", str(out_dir),
           "--force-strategy", strategy,
           "--quality-threshold", str(args.quality_threshold)]
    print(f"Extracting slice → {out_dir}", file=sys.stderr)
    rc = subprocess.run(cmd).returncode

    (out_dir / "section.json").write_text(json.dumps({
        "source_pdf": str(src),
        "book_slug": book_slug,
        "selection": args.section or args.pages or args.printed_pages,
        "label": label,
        "physical_start": start,
        "physical_end": end,
        "pages": end - start + 1,
        "mode": "quick" if args.quick else "full",
        "extract_rc": rc,
    }, indent=2))
    print(f"Done: {out_dir} (extract rc={rc})", file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())
