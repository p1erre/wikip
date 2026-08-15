#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pymupdf>=1.24.0",
# ]
# ///
"""
Map a (long) PDF book to physical page ranges, so a downstream slicer can land
on the right pages without converting the whole book.

The hard part is *reading* the table of contents — book TOC layouts vary wildly
(multi-column tables, dot leaders, part dividers, roman front matter). Rather
than parse that with brittle heuristics, this script splits the work:

  - The SCRIPT does the mechanical parts: read the embedded outline when present
    (exact), dump book metadata, dump the TOC-region *text* for the agent to
    read, sample body-page folios to suggest the front-matter delta, and do the
    page-range arithmetic.
  - The AGENT does the interpretation: read the dumped TOC text, extract each
    entry's printed folio, decide the delta, and author a small draft.json.

Two modes:

  PROBE (default):
    map.py <pdf> [--out-dir DIR] [--toc-pages A-B] [--probe-pages N]
    If the PDF has an embedded outline -> writes book_map.json directly (done).
    Otherwise -> writes toc_probe.md (metadata + folio samples + TOC-region
    text) for the agent to read, and probe.json (machine-readable companion).

  BUILD (finalize the agent's reading):
    map.py --build <draft.json> [--out-dir DIR]
    draft.json = {"source_pdf": "...", "delta": N,
                  "entries": [{"level":1, "number":"1", "title":"...",
                               "printed_page": 1}, ...]}
    -> writes book_map.json with physical ranges computed from delta + levels.

Each book gets a self-contained home folder work/books/<book-slug>/ (the source
PDF is copied in on first run). Writes there (override with --out-dir):
  <original>.pdf  the book, copied in once
  book_map.json   final map (both modes' end product)
  toc_probe.md    agent-facing TOC dump (probe mode, no-outline case only)
  probe.json      machine companion to toc_probe.md
"""

import argparse
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

import fitz  # pymupdf

BOOKS_DIR = "work/books"  # default base; each book gets its own slug folder under it


def slugify(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    s = re.sub(r"[\s_-]+", "-", s)
    return s[:60].strip("-") or "section"


def ensure_book_home(pdf_path: Path, out_dir_arg: str | None) -> tuple[Path, Path, str]:
    """Resolve the book's self-contained folder, copying the PDF into it once.

    Returns (home, book_pdf, slug). The book lives at <home>/<original-name.pdf>;
    all artifacts (book_map.json, toc_probe.md, section dirs) sit beside it. If
    the source PDF isn't already inside home, it's copied in (idempotent)."""
    slug = slugify(pdf_path.stem)
    home = (Path(out_dir_arg).resolve() if out_dir_arg
            else (Path(BOOKS_DIR) / slug).resolve())
    home.mkdir(parents=True, exist_ok=True)
    book_pdf = home / pdf_path.name
    if book_pdf.resolve() != pdf_path.resolve() and not book_pdf.exists():
        shutil.copy2(pdf_path, book_pdf)
        print(f"Copied book into {book_pdf}", file=sys.stderr)
    return home, book_pdf, slug


# ---------- printed-folio reading (delta calibration) ----------

_FOLIO_RE = re.compile(r"^\(?(\d{1,4})\)?$")


def read_folio(text: str) -> int | None:
    """Return the printed page number from a page's header/footer, or None.

    Only the first two and last two non-blank lines are considered, so digits
    buried in body text don't masquerade as a folio.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None
    for ln in (lines[-1], lines[-2] if len(lines) > 1 else "",
               lines[0], lines[1] if len(lines) > 1 else ""):
        m = _FOLIO_RE.match(ln)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 9999:
                return n
    return None


def calibrate_delta(doc) -> dict | None:
    """Suggest delta = physical_index - printed_folio via the *mode* of sampled
    interior pages. The mode is robust to a few misread folios (a stray "1", a
    part divider that resets numbering) that would shift a median. The agent
    confirms/overrides this using toc_probe.md."""
    n = doc.page_count
    start = max(int(n * 0.15), 5)
    end = max(n - 2, start + 1)
    if end <= start:
        return None
    step = max((end - start) // 20, 1)
    samples = []
    for i in range(start, end, step):
        folio = read_folio(doc[i].get_text())
        if folio is not None:
            samples.append({"physical": i + 1, "folio": folio,
                            "delta": (i + 1) - folio})
    if len(samples) < 3:
        return {"delta": None, "samples": samples, "confidence": 0.0}
    d, cnt = Counter(s["delta"] for s in samples).most_common(1)[0]
    return {"delta": d, "confidence": round(cnt / len(samples), 2),
            "samples": samples}


# ---------- TOC-region detection / dump ----------

def detect_toc_region(doc, probe_pages: int) -> tuple[int, int]:
    """Return a (start, end) physical-page window likely containing the TOC.

    Looks for a 'Contents' heading in the front of the book; falls back to the
    first `probe_pages` pages. 0-based, end exclusive.
    """
    n = doc.page_count
    scan = min(max(probe_pages, 30), n)
    for i in range(scan):
        head = "\n".join(doc[i].get_text().splitlines()[:3]).lower()
        if re.search(r"\bcontents\b", head):
            return i, min(i + 14, n)
    return 0, min(probe_pages, n)


def dump_toc_text(doc, lo: int, hi: int) -> str:
    parts = []
    for i in range(lo, hi):
        parts.append(f"===== PHYSICAL PAGE {i + 1} =====\n{doc[i].get_text()}")
    return "\n\n".join(parts)


# ---------- range assignment ----------

def assign_ranges_outline(toc: list[list], n: int) -> list[dict]:
    """toc entries are [level, title, physical_page] (1-based)."""
    entries = []
    for idx, (level, title, page) in enumerate(toc):
        end = n
        for level2, _t2, page2 in toc[idx + 1:]:
            if level2 <= level:
                end = page2 - 1
                break
        page = max(1, min(page, n))
        end = max(page, min(end, n))
        entries.append({
            "index": idx, "level": level, "title": title, "slug": slugify(title),
            "printed_page": None, "physical_start": page,
            "physical_end": end, "pages": end - page + 1,
        })
    return entries


def assign_ranges_draft(entries_in: list[dict], delta: int, n: int) -> list[dict]:
    """Agent-authored entries (printed folios + levels) -> physical ranges.
    End of an entry = (start of next entry at same-or-shallower level) - 1, so a
    chapter's range spans all its sections."""
    entries = []
    for idx, e in enumerate(entries_in):
        level = e.get("level", 1)
        start = e["printed_page"] + delta
        end = n
        for e2 in entries_in[idx + 1:]:
            if e2.get("level", 1) <= level:
                end = e2["printed_page"] + delta - 1
                break
        start = max(1, min(start, n))
        end = max(start, min(end, n))
        title = f"{e['number']} {e['title']}".strip() if e.get("number") else e["title"]
        entries.append({
            "index": idx, "level": level, "title": title,
            "slug": slugify(f"{e.get('number') or ''} {e['title']}"),
            "printed_page": e["printed_page"], "physical_start": start,
            "physical_end": end, "pages": end - start + 1,
        })
    return entries


# ---------- modes ----------

def run_build(draft_path: Path, out_dir_arg: str | None) -> int:
    draft = json.loads(draft_path.read_text())
    src = Path(draft["source_pdf"]).resolve()
    if not src.is_file():
        print(f"source_pdf not found: {src}", file=sys.stderr)
        return 2
    delta = int(draft.get("delta", 0))
    book_slug = slugify(src.stem)
    # default: write the map beside the draft (i.e. into the book's home folder)
    out_dir = (Path(out_dir_arg).resolve() if out_dir_arg
               else draft_path.resolve().parent)
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(src)
    n = doc.page_count
    result = {
        "source_pdf": str(src), "book_slug": book_slug, "page_count": n,
        "toc_source": "printed", "delta": delta,
        "metadata": draft.get("metadata"),
        "entries": assign_ranges_draft(draft["entries"], delta, n),
    }
    doc.close()
    out = out_dir / "book_map.json"
    out.write_text(json.dumps(result, indent=2))
    print(f"Wrote {out}", file=sys.stderr)
    print(f"  source=printed delta={delta} entries={len(result['entries'])} "
          f"pages={n}", file=sys.stderr)
    return 0


def run_probe(pdf_path: Path, out_dir_arg: str | None,
              toc_pages: str | None, probe_pages: int) -> int:
    out_dir, book_pdf, book_slug = ensure_book_home(pdf_path, out_dir_arg)

    doc = fitz.open(book_pdf)
    n = doc.page_count
    meta = {k: doc.metadata.get(k) for k in ("title", "author", "subject")
            if doc.metadata.get(k)}
    outline = doc.get_toc(simple=True)

    # Best case: embedded outline -> exact map, no agent reading needed.
    if outline:
        result = {
            "source_pdf": str(book_pdf), "book_slug": book_slug, "page_count": n,
            "toc_source": "outline", "delta": 0, "metadata": meta or None,
            "entries": assign_ranges_outline(outline, n),
        }
        doc.close()
        out = out_dir / "book_map.json"
        out.write_text(json.dumps(result, indent=2))
        print(f"Wrote {out}", file=sys.stderr)
        print(f"  source=outline entries={len(result['entries'])} pages={n}",
              file=sys.stderr)
        return 0

    # No outline: dump TOC-region text + delta evidence for the agent to read.
    if toc_pages:
        a, _, b = toc_pages.partition("-")
        lo, hi = int(a) - 1, int(b or a)
    else:
        lo, hi = detect_toc_region(doc, probe_pages)

    delta = calibrate_delta(doc)
    toc_text = dump_toc_text(doc, lo, hi)
    doc.close()

    probe = {
        "source_pdf": str(book_pdf), "book_slug": book_slug, "page_count": n,
        "metadata": meta or None, "toc_region_physical": [lo + 1, hi],
        "delta_suggestion": delta,
    }
    (out_dir / "probe.json").write_text(json.dumps(probe, indent=2))

    md = [
        f"# Book probe: {book_slug}",
        "",
        f"- source_pdf: `{book_pdf}`",
        f"- page_count: {n}",
        f"- metadata.title: {meta.get('title') or '(none)'}",
        f"- metadata.author: {meta.get('author') or '(none)'}",
        f"- TOC region dumped: physical pages {lo + 1}–{hi}",
        "",
        "## Delta (front-matter offset)",
        "",
        "`physical_page = printed_folio + delta`. Suggested from sampling body "
        "pages (mode of physical−folio):",
        "",
        f"- **suggested delta: {delta['delta'] if delta else 'unknown'}** "
        f"(confidence {delta['confidence'] if delta else 0.0})",
        "",
        "Folio samples (physical → folio → delta):",
        "",
        "| physical | folio | delta |",
        "|---|---|---|",
    ]
    for s in (delta or {}).get("samples", [])[:20]:
        md.append(f"| {s['physical']} | {s['folio']} | {s['delta']} |")
    md += [
        "",
        "Confirm delta by cross-checking: the TOC's first chapter folio + delta "
        "should equal the physical page where that chapter actually starts.",
        "",
        "## TOC-region text",
        "",
        "Read the pages below, find the contents listing, and record each "
        "entry's **printed folio** (the number in the TOC, not the physical "
        "page). Then author `draft.json` and run `map.py --build draft.json`.",
        "",
        "draft.json shape:",
        "```json",
        '{"source_pdf": "%s", "delta": %s, "metadata": %s,' % (
            book_pdf, delta["delta"] if delta else 0, json.dumps(meta or None)),
        ' "entries": [{"level": 1, "number": "1", "title": "Introduction",'
        ' "printed_page": 1}]}',
        "```",
        "(level 1 = chapter/part, level 2 = section; `number` optional.)",
        "",
        "---",
        "",
        toc_text,
    ]
    (out_dir / "toc_probe.md").write_text("\n".join(md))
    print(f"No embedded outline. Wrote {out_dir / 'toc_probe.md'}", file=sys.stderr)
    print(f"  Read it, author draft.json, then: "
          f"map.py --build {out_dir / 'draft.json'}", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", nargs="?", help="PDF to probe (probe mode)")
    ap.add_argument("--build", help="draft.json to finalize into book_map.json")
    ap.add_argument("--out-dir")
    ap.add_argument("--toc-pages", help="hint for TOC location, e.g. 7-13")
    ap.add_argument("--probe-pages", type=int, default=30,
                    help="pages to dump when no Contents heading is found")
    args = ap.parse_args()

    if args.build:
        return run_build(Path(args.build).resolve(), args.out_dir)

    if not args.pdf:
        ap.error("provide a PDF (probe mode) or --build draft.json")
    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.is_file():
        print(f"PDF not found: {pdf_path}", file=sys.stderr)
        return 2
    return run_probe(pdf_path, args.out_dir, args.toc_pages, args.probe_pages)


if __name__ == "__main__":
    sys.exit(main())
