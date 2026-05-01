"""Fetch an arXiv paper and prepare its LaTeX source for section-by-section conversion.

Pipeline:
  1. Normalize the arxiv ID.
  2. Hit arxiv.org/e-print/<id> — that endpoint either returns a tarball of the
     LaTeX source, a single gzipped .tex, or a PDF (when no source was uploaded).
  3. If we got a PDF, write paper.pdf + no_source.flag and stop.
  4. Otherwise locate the main .tex, split off the preamble, recursively inline
     nested \\input/\\include/\\subfile into each top-level boundary, and emit
     one section file per boundary.
  5. Convert EPS/PDF figures to PNG so downstream markdown can reference them.
  6. Fetch arxiv API metadata into raw/arxiv_meta.json.

Idempotent: skips if raw/structure.json or no_source.flag already exists.
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ARXIV_ID_RE = re.compile(
    r"""
    (?:arXiv:)?
    (?:https?://arxiv\.org/(?:abs|pdf|e-print)/)?
    (?P<id>\d{4}\.\d{4,5}|[a-z\-]+(?:\.[A-Z]{2})?/\d{7})
    (?:v(?P<version>\d+))?
    (?:\.pdf)?
    """,
    re.VERBOSE,
)

INPUT_RE = re.compile(r"\\(?:input|include|subfile)\s*\{([^}]+)\}")
SECTION_RE = re.compile(r"^\s*\\section\*?\s*\{(.+?)\}", re.MULTILINE)
COMMENT_RE = re.compile(r"(?<!\\)%.*$", re.MULTILINE)
TITLE_HINT_RE = re.compile(r"\\(?:section|chapter)\*?\s*\{(.+?)\}")
ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"

USER_AGENT = "wikip-arxiv-fetch/0.1 (https://github.com; mailto:noreply@example.com)"


def parse_arxiv_id(raw: str) -> tuple[str, str | None]:
    """Return (id, version) from any accepted input form."""
    m = ARXIV_ID_RE.search(raw.strip())
    if not m:
        sys.exit(f"could not parse arxiv id from: {raw!r}")
    return m.group("id"), m.group("version")


def http_get(url: str, *, accept: str = "*/*", retries: int = 3) -> bytes:
    last_err: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            last_err = e
        except urllib.error.URLError as e:
            last_err = e
        time.sleep(2 ** attempt)
    raise RuntimeError(f"GET {url} failed after {retries} attempts: {last_err}")


def fetch_metadata(arxiv_id: str) -> dict:
    url = f"https://export.arxiv.org/api/query?id_list={arxiv_id}"
    body = http_get(url, accept="application/atom+xml")
    root = ET.fromstring(body)
    entry = root.find(f"{ATOM_NS}entry")
    if entry is None:
        return {"arxiv_id": arxiv_id, "title": None, "authors": [], "abstract": None}
    title = (entry.findtext(f"{ATOM_NS}title") or "").strip()
    summary = (entry.findtext(f"{ATOM_NS}summary") or "").strip()
    authors = [
        (a.findtext(f"{ATOM_NS}name") or "").strip()
        for a in entry.findall(f"{ATOM_NS}author")
    ]
    primary = entry.find(f"{ARXIV_NS}primary_category")
    primary_class = primary.get("term") if primary is not None else None
    categories = [c.get("term") for c in entry.findall(f"{ATOM_NS}category") if c.get("term")]
    id_url = (entry.findtext(f"{ATOM_NS}id") or "").strip()
    version = id_url.rsplit("v", 1)[-1] if "v" in id_url.rsplit("/", 1)[-1] else None
    return {
        "arxiv_id": arxiv_id,
        "title": " ".join(title.split()),
        "authors": authors,
        "abstract": " ".join(summary.split()),
        "primary_class": primary_class,
        "categories": categories,
        "version": version,
        "abs_url": id_url,
    }


def download_eprint(arxiv_id: str, version: str | None) -> bytes:
    suffix = f"v{version}" if version else ""
    url = f"https://arxiv.org/e-print/{arxiv_id}{suffix}"
    return http_get(url)


def looks_like_pdf(blob: bytes) -> bool:
    return blob[:5] == b"%PDF-"


def looks_like_gzip(blob: bytes) -> bool:
    return blob[:2] == b"\x1f\x8b"


def extract_source(blob: bytes, dest: Path) -> Path:
    """Unpack the e-print blob into dest/. Returns dest."""
    dest.mkdir(parents=True, exist_ok=True)
    if not looks_like_gzip(blob):
        # arxiv occasionally returns a bare .tex
        (dest / "main.tex").write_bytes(blob)
        return dest
    decompressed = gzip.decompress(blob)
    # Could be a tar archive or a single .tex file
    try:
        with tarfile.open(fileobj=io.BytesIO(decompressed)) as tf:
            kwargs = {"filter": "data"} if sys.version_info >= (3, 12) else {}
            tf.extractall(dest, **kwargs)
        return dest
    except tarfile.TarError:
        (dest / "main.tex").write_bytes(decompressed)
        return dest


def strip_comments(tex: str) -> str:
    return COMMENT_RE.sub("", tex)


def find_main_tex(root: Path) -> Path:
    """Pick the entry .tex: contains \\documentclass and \\begin{document}."""
    candidates: list[tuple[int, Path]] = []
    for p in root.rglob("*.tex"):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        stripped = strip_comments(text)
        if r"\documentclass" in stripped and r"\begin{document}" in stripped:
            # Prefer shallower paths and conventional names
            score = -len(p.parts) * 10
            if p.name in ("main.tex", "paper.tex", "ms.tex", "manuscript.tex"):
                score += 100
            candidates.append((score, p))
    if not candidates:
        sys.exit("no main .tex file found (need one with \\documentclass and \\begin{document})")
    candidates.sort(reverse=True)
    return candidates[0][1]


def resolve_path(name: str, base: Path, root: Path) -> Path | None:
    """Find an \\input target — try as-is, with .tex, and relative to project root."""
    candidates = [base / name, base / f"{name}.tex", root / name, root / f"{name}.tex"]
    for c in candidates:
        if c.is_file():
            return c
    return None


def inline_includes(
    tex: str,
    base: Path,
    root: Path,
    visited: set[Path],
    warnings: list[str],
    depth: int = 0,
) -> str:
    """Recursively inline \\input/\\include/\\subfile, with cycle protection."""
    if depth > 32:
        warnings.append(f"max include depth exceeded at base={base}")
        return tex

    def repl(m: re.Match[str]) -> str:
        target = m.group(1).strip()
        path = resolve_path(target, base, root)
        if path is None:
            warnings.append(f"unresolved include: {target} (from {base})")
            return m.group(0)
        if path in visited:
            warnings.append(f"cyclic include skipped: {path}")
            return ""
        visited.add(path)
        try:
            sub = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            warnings.append(f"unreadable include {path}: {e}")
            return m.group(0)
        sub = strip_comments(sub)
        return inline_includes(sub, path.parent, root, visited, warnings, depth + 1)

    return INPUT_RE.sub(repl, tex)


def split_preamble(tex: str) -> tuple[str, str]:
    """Return (preamble, body). Body is everything between \\begin{document}..\\end{document}."""
    begin = tex.find(r"\begin{document}")
    end = tex.rfind(r"\end{document}")
    if begin == -1 or end == -1 or end <= begin:
        sys.exit("missing \\begin{document} or \\end{document} in main file")
    preamble = tex[:begin]
    body = tex[begin + len(r"\begin{document}") : end]
    return preamble, body


def first_section_title(tex: str) -> str | None:
    m = TITLE_HINT_RE.search(tex)
    if not m:
        return None
    return " ".join(m.group(1).split())[:80]


def slugify(s: str, fallback: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or fallback


def find_top_level_inputs(main_tex_body: str) -> list[tuple[int, int, str]]:
    """Return [(start, end, target), ...] for \\input commands in the main body.

    Only used to detect whether the paper is multi-file or monolithic — we don't
    use these positions for content extraction (inline_includes already handled that).
    """
    return [(m.start(), m.end(), m.group(1).strip()) for m in INPUT_RE.finditer(main_tex_body)]


def split_body_by_section(body: str) -> list[tuple[str, str]]:
    """For monolithic papers: return [(title_hint, content), ...] split on \\section{}."""
    matches = list(SECTION_RE.finditer(body))
    if not matches:
        return [("body", body)]
    out: list[tuple[str, str]] = []
    head = body[: matches[0].start()].strip()
    if head:
        out.append(("front-matter", head))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        title = " ".join(m.group(1).split())
        out.append((title, body[m.start() : end]))
    return out


def split_body_by_input(
    raw_main_body: str, root: Path, base: Path
) -> tuple[list[tuple[str, str]], list[str]]:
    """For multi-file papers: one section per top-level \\input, with nested includes inlined.

    Walks raw_main_body (still containing \\input markers), splits at each, and
    inlines each \\input target recursively. Free text between inputs becomes
    its own slot so nothing is dropped. Returns (parts, warnings).
    """
    parts: list[tuple[str, str]] = []
    cursor = 0
    counter = 0
    visited: set[Path] = set()
    warnings: list[str] = []
    for m in INPUT_RE.finditer(raw_main_body):
        between = raw_main_body[cursor : m.start()].strip()
        if between:
            label = "front-matter" if cursor == 0 else f"interlude-{counter}"
            parts.append((label, between))
            counter += 1
        target = m.group(1).strip()
        path = resolve_path(target, base, root)
        if path is None:
            warnings.append(f"unresolved include: {target}")
            parts.append((f"unresolved-{counter}", m.group(0)))
            counter += 1
        else:
            visited_local = visited | {path}
            try:
                sub = path.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                warnings.append(f"unreadable include {path}: {e}")
                cursor = m.end()
                continue
            sub = strip_comments(sub)
            inlined = inline_includes(sub, path.parent, root, visited_local, warnings)
            title = first_section_title(inlined) or path.stem
            parts.append((title, inlined))
        cursor = m.end()
    tail = raw_main_body[cursor:].strip()
    if tail:
        parts.append((f"tail-{counter}", tail))
    return parts, warnings


def copy_figures(source_root: Path, raw_figures: Path) -> list[str]:
    """Copy and convert figures into raw/figures/. Returns a list of warnings."""
    raw_figures.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    image_exts = {".png", ".jpg", ".jpeg", ".pdf", ".eps"}
    for src in source_root.rglob("*"):
        if not src.is_file() or src.suffix.lower() not in image_exts:
            continue
        if "raw/figures" in str(src) or src.is_relative_to(raw_figures):
            continue
        dest_name = src.stem + ".png" if src.suffix.lower() in {".pdf", ".eps"} else src.name
        dest = raw_figures / dest_name
        if dest.exists():
            continue
        if src.suffix.lower() in {".pdf", ".eps"}:
            if shutil.which("pdftoppm") is None:
                warnings.append(f"pdftoppm not installed, skipped {src.name}")
                continue
            try:
                subprocess.run(
                    ["pdftoppm", "-png", "-r", "150", "-singlefile", str(src), str(dest.with_suffix(""))],
                    check=True,
                    capture_output=True,
                    timeout=60,
                )
            except subprocess.CalledProcessError as e:
                warnings.append(f"pdftoppm failed on {src.name}: {e.stderr.decode(errors='replace')[:200]}")
            except subprocess.TimeoutExpired:
                warnings.append(f"pdftoppm timed out on {src.name}")
        else:
            shutil.copy2(src, dest)
    return warnings


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
        # Monolithic — fully inline (in case there are scattered \input's) then split on \section
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
    if warnings:
        print(f"{len(warnings)} warnings — see structure.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
