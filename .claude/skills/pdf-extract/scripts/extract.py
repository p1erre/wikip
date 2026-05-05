#!/usr/bin/env python3
"""
Extract a PDF into structured markdown with LaTeX math, figures, and metadata.

Usage:
  extract.py <pdf_path> --out-dir <dir>
             [--force-strategy auto|pymupdf|marker|nougat|ocr]
             [--quality-threshold 0.7]

Writes:
  <out-dir>/content.md          markdown body, $...$ / $$...$$ for math
  <out-dir>/figures/fig_NNN.png embedded images and figures
  <out-dir>/figures/_low_quality_pages/page_NN.png  (only if needs_vision)
  <out-dir>/metadata.json       {source_pdf, page_count, strategies_used}
  <out-dir>/pdf_profile.json    detection result + per-page strategy + quality

Strategy ladder (math-aware):
  native, no math   : pymupdf → marker
  native, with math : marker  → nougat
  scanned, no math  : ocr     → nougat
  scanned, with math: nougat  → manual vision
  hybrid            : marker  → nougat

Idempotent: skips if content.md and pdf_profile.json both exist.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import fitz  # pymupdf


# ---------- profile ----------

MATH_SIGNAL_RE = re.compile(
    r"[∑∫∂∇≤≥≠≈∞αβγδθλμπρσφψωΓΔΘΛΣΦΨΩ∈∉⊂⊃⊆⊇∪∩⊕⊗]"
    r"|\\frac|\\sum|\\int|\\prod|\\partial|\\nabla|\\sqrt|\\mathbb|\\mathcal"
    r"|\\begin\{(equation|align|matrix|cases)"
)


@dataclass
class PageProfile:
    page_num: int
    chars: int
    images: int
    has_math_signal: bool
    type: str  # native | scanned | mixed
    strategy: Optional[str] = None
    quality: Optional[float] = None


@dataclass
class DocProfile:
    overall_type: str = "native"
    has_math: bool = False
    pages: list[PageProfile] = field(default_factory=list)
    strategies_used: dict[str, int] = field(default_factory=dict)
    needs_vision: list[int] = field(default_factory=list)
    latex_warnings: list[dict] = field(default_factory=list)
    unreliable: bool = False


def detect(pdf_path: Path) -> DocProfile:
    doc = fitz.open(pdf_path)
    pages: list[PageProfile] = []
    for i, page in enumerate(doc):
        text = page.get_text()
        chars = len(text.strip())
        images = len(page.get_images(full=True))
        has_math = bool(MATH_SIGNAL_RE.search(text))
        if chars < 50 and images >= 1:
            ptype = "scanned"
        elif chars > 200:
            ptype = "native"
        else:
            ptype = "mixed"
        pages.append(PageProfile(i + 1, chars, images, has_math, ptype))
    doc.close()

    types = {p.type for p in pages}
    if types == {"native"}:
        overall = "native"
    elif types == {"scanned"}:
        overall = "scanned"
    else:
        overall = "hybrid"

    return DocProfile(
        overall_type=overall,
        has_math=any(p.has_math_signal for p in pages),
        pages=pages,
    )


# ---------- strategies ----------


def _ensure_figures_dir(out_dir: Path) -> Path:
    fig = out_dir / "figures"
    fig.mkdir(parents=True, exist_ok=True)
    return fig


def extract_pymupdf(pdf_path: Path, out_dir: Path) -> str:
    """Native extraction. Fast. No math support."""
    fig_dir = _ensure_figures_dir(out_dir)
    doc = fitz.open(pdf_path)
    parts: list[str] = []
    fig_count = 0
    for page in doc:
        parts.append(page.get_text())
        for img in page.get_images(full=True):
            xref = img[0]
            try:
                pix = fitz.Pixmap(doc, xref)
                if pix.n - pix.alpha >= 4:  # CMYK → RGB
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                fig_count += 1
                pix.save(fig_dir / f"fig_{fig_count:03d}.png")
                pix = None
            except Exception:
                continue
    doc.close()
    return "\n\n".join(parts)


def _run(cmd: list[str], desc: str) -> None:
    # Use a temp file for stderr so tqdm/progress output doesn't fill the pipe buffer
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as log:
        log_path = log.name
    try:
        with open(log_path, "w") as log:
            result = subprocess.run(cmd, stdout=log, stderr=log)
        if result.returncode != 0:
            tail = Path(log_path).read_text()[-500:]
            raise RuntimeError(f"{desc} failed: {tail.strip()}")
    finally:
        Path(log_path).unlink(missing_ok=True)


def extract_marker(pdf_path: Path, out_dir: Path) -> str:
    """Marker via CLI. Math-capable, slower than pymupdf."""
    if shutil.which("marker_single") is None:
        raise RuntimeError("marker_single not found on PATH (install marker-pdf)")
    fig_dir = _ensure_figures_dir(out_dir)
    with tempfile.TemporaryDirectory() as tmp:
        _run(
            ["marker_single", str(pdf_path), "--output_dir", tmp,
             "--output_format", "markdown"],
            "marker",
        )
        md_files = list(Path(tmp).rglob("*.md"))
        if not md_files:
            raise RuntimeError("marker produced no markdown")
        md = md_files[0].read_text()
        # Move marker's extracted images alongside the markdown
        for img in md_files[0].parent.glob("*"):
            if img.suffix.lower() in {".png", ".jpg", ".jpeg"}:
                shutil.copy2(img, fig_dir / img.name)
        return md


def extract_nougat(pdf_path: Path, out_dir: Path) -> str:
    """Nougat for academic papers with math (also handles scanned papers)."""
    if shutil.which("nougat") is None:
        raise RuntimeError("nougat not found on PATH (install nougat-ocr)")
    with tempfile.TemporaryDirectory() as tmp:
        _run(
            ["nougat", str(pdf_path), "--out", tmp, "--markdown", "--no-skipping"],
            "nougat",
        )
        # Nougat writes <stem>.mmd
        mmd_files = list(Path(tmp).rglob("*.mmd"))
        if not mmd_files:
            raise RuntimeError("nougat produced no output")
        return mmd_files[0].read_text()


def extract_ocr(pdf_path: Path, out_dir: Path) -> str:
    """ocrmypdf adds a text layer; then pymupdf reads it."""
    if shutil.which("ocrmypdf") is None:
        raise RuntimeError("ocrmypdf not found on PATH")
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        _run(
            ["ocrmypdf", "--rotate-pages", "--deskew", "--clean-final",
             "--force-ocr", "--quiet", str(pdf_path), str(tmp_path)],
            "ocrmypdf",
        )
        return extract_pymupdf(tmp_path, out_dir)
    finally:
        tmp_path.unlink(missing_ok=True)


STRATEGY_FNS = {
    "pymupdf": extract_pymupdf,
    "marker": extract_marker,
    "nougat": extract_nougat,
    "ocr": extract_ocr,
}


def pick_strategy(profile: DocProfile, force: str) -> str:
    if force != "auto":
        return force
    if profile.overall_type == "scanned":
        return "nougat" if profile.has_math else "ocr"
    if profile.overall_type == "hybrid":
        return "marker"
    return "marker" if profile.has_math else "pymupdf"


ESCALATION = {
    "pymupdf": "marker",
    "marker": "nougat",
    "ocr": "nougat",
    "nougat": None,
}


# ---------- cleanup ----------


def cleanup(md: str) -> str:
    if not md:
        return md
    # Dehyphenation: word-\nword → wordword (when both halves are alpha)
    md = re.sub(r"(\w)-\n(\w)", r"\1\2", md)
    # Collapse 3+ blank lines to 2
    md = re.sub(r"\n{3,}", "\n\n", md)
    # Strip lines that are only a page number
    md = re.sub(r"(?m)^\s*\d{1,4}\s*$\n?", "", md)
    # Trim trailing whitespace per line
    md = re.sub(r"[ \t]+\n", "\n", md)
    return md.strip() + "\n"


# ---------- quality + latex ----------


def quality_score(md: str, profile: DocProfile) -> float:
    """Cheap heuristic in [0, 1]."""
    if not md.strip():
        return 0.0
    expected_chars = sum(p.chars for p in profile.pages if p.type == "native")
    if expected_chars == 0:
        # Scanned doc — base score on absolute density
        chars_per_page = len(md) / max(1, len(profile.pages))
        return min(1.0, chars_per_page / 800.0)
    chars_ratio = min(1.0, len(md) / max(1, expected_chars))
    # Penalize gibberish-like sequences (long runs of non-letters)
    gibberish = len(re.findall(r"[^\w\s]{6,}", md)) / max(1, len(md) / 1000)
    return max(0.0, chars_ratio - 0.05 * gibberish)


def validate_latex(md: str) -> list[dict]:
    try:
        from pylatexenc.latexwalker import LatexWalker, LatexWalkerError
    except ImportError:
        return []
    warnings: list[dict] = []
    for pattern in (r"\$\$(.+?)\$\$", r"(?<!\$)\$(?!\$)([^$\n]+)\$(?!\$)"):
        for m in re.finditer(pattern, md, flags=re.DOTALL):
            try:
                LatexWalker(m.group(1)).get_latex_nodes()
            except LatexWalkerError as e:
                warnings.append({"snippet": m.group(0)[:80], "error": str(e)})
    return warnings


def render_low_quality_pages(
    pdf_path: Path, page_nums: list[int], out_dir: Path
) -> None:
    if not page_nums:
        return
    target = out_dir / "figures" / "_low_quality_pages"
    target.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    for n in page_nums:
        page = doc[n - 1]
        pix = page.get_pixmap(dpi=200)
        pix.save(target / f"page_{n:03d}.png")
    doc.close()


# ---------- main ----------


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument(
        "--force-strategy",
        default="auto",
        choices=["auto", "pymupdf", "marker", "nougat", "ocr"],
    )
    ap.add_argument("--quality-threshold", type=float, default=0.7)
    args = ap.parse_args()

    pdf_path = Path(args.pdf).resolve()
    out_dir = Path(args.out_dir).resolve()
    if not pdf_path.is_file():
        print(f"PDF not found: {pdf_path}", file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    content_path = out_dir / "content.md"
    profile_path = out_dir / "pdf_profile.json"

    if (
        args.force_strategy == "auto"
        and content_path.exists()
        and profile_path.exists()
    ):
        print(f"Skipping (already extracted): {out_dir}", file=sys.stderr)
        return 0

    print("Detecting PDF profile…", file=sys.stderr)
    profile = detect(pdf_path)
    print(
        f"  type={profile.overall_type} has_math={profile.has_math} "
        f"pages={len(profile.pages)}",
        file=sys.stderr,
    )

    strategy = pick_strategy(profile, args.force_strategy)
    md = ""
    score = 0.0

    while strategy:
        print(f"Extracting with {strategy}…", file=sys.stderr)
        try:
            md = STRATEGY_FNS[strategy](pdf_path, out_dir)
        except Exception as e:
            print(f"  {strategy} failed: {e}", file=sys.stderr)
            md = ""

        md = cleanup(md)
        score = quality_score(md, profile)
        profile.strategies_used[strategy] = (
            profile.strategies_used.get(strategy, 0) + 1
        )
        print(f"  quality={score:.2f}", file=sys.stderr)

        if score >= args.quality_threshold:
            for p in profile.pages:
                p.strategy = strategy
                p.quality = score
            break

        next_strategy = ESCALATION.get(strategy)
        if next_strategy is None:
            print(f"  no further escalation from {strategy}", file=sys.stderr)
            break
        print(f"  escalating to {next_strategy}", file=sys.stderr)
        strategy = next_strategy

    if not md:
        print("All strategies failed; nothing to write", file=sys.stderr)
        return 3

    if score < args.quality_threshold:
        profile.unreliable = True
        profile.needs_vision = [
            p.page_num for p in profile.pages if p.type != "native"
        ] or [p.page_num for p in profile.pages]
        render_low_quality_pages(pdf_path, profile.needs_vision, out_dir)

    profile.latex_warnings = validate_latex(md)

    content_path.write_text(md)
    (out_dir / "metadata.json").write_text(
        json.dumps(
            {
                "source_pdf": str(pdf_path),
                "page_count": len(profile.pages),
                "strategies_used": profile.strategies_used,
                "final_quality": round(score, 3),
            },
            indent=2,
        )
    )
    profile_path.write_text(
        json.dumps(
            {
                "overall_type": profile.overall_type,
                "has_math": profile.has_math,
                "strategies_used": profile.strategies_used,
                "unreliable": profile.unreliable,
                "needs_vision": profile.needs_vision,
                "latex_warnings": profile.latex_warnings,
                "final_quality": round(score, 3),
                "pages": [asdict(p) for p in profile.pages],
            },
            indent=2,
        )
    )
    print(f"Done: {out_dir}", file=sys.stderr)
    return 0 if not profile.unreliable else 4


if __name__ == "__main__":
    sys.exit(main())
