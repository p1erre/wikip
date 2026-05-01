"""Extract figure metadata and copy/convert figure assets.

Two responsibilities:

  1. **copy_figures**: walk the unpacked source tree, copy raster images
     (PNG/JPG/JPEG) verbatim into raw/figures/, convert vector ones (PDF/EPS)
     to PNG via pdftoppm.
  2. **extract_figures**: scan each section file for \\begin{figure} blocks,
     pull out caption / label / \\includegraphics refs / TikZ presence, and
     resolve image refs to the files copy_figures already produced.

The result is a list of figure records suitable for serialising to figures.json.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from tex_utils import extract_braced_arg, find_matching_end

FIGURE_START_RE = re.compile(r"\\begin\{figure\*?\}")
FIGURE_END_RE = re.compile(r"\\end\{figure\*?\}")
INCLUDEGRAPHICS_RE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\s*\{([^}]+)\}")
LABEL_RE = re.compile(r"\\label\s*\{([^}]+)\}")
CAPTION_RE = re.compile(r"\\caption\s*(?:\[[^\]]*\])?\s*\{")
TIKZ_RE = re.compile(r"\\begin\{tikzpicture\}")
TIKZ_START_RE = re.compile(r"\\begin\{tikzpicture\}(?:\[[^\]]*\])?")
TIKZ_END_RE = re.compile(r"\\end\{tikzpicture\}")
SUBFIGURE_START_RE = re.compile(r"\\begin\{subfigure\}")
SUBFIGURE_END_RE = re.compile(r"\\end\{subfigure\}")

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".pdf", ".eps"}


def extract_caption(body: str) -> str | None:
    """Find the *outermost* \\caption{...} in body and extract its braced argument."""
    m = CAPTION_RE.search(body)
    if not m:
        return None
    arg, _ = extract_braced_arg(body, m.end() - 1)
    if arg is None:
        return None
    # Strip embedded \label{...} from the caption body
    arg = LABEL_RE.sub("", arg)
    # Collapse whitespace
    return " ".join(arg.split()).strip()


def extract_label(body: str) -> str | None:
    """First \\label{...} in body."""
    m = LABEL_RE.search(body)
    return m.group(1).strip() if m else None


def extract_tikz_sources(body: str) -> list[str]:
    """Return each \\begin{tikzpicture}...\\end{tikzpicture} block's full source."""
    out: list[str] = []
    cursor = 0
    while True:
        m = TIKZ_START_RE.search(body, cursor)
        if not m:
            break
        end = find_matching_end(body, m.end(), TIKZ_START_RE, TIKZ_END_RE)
        if end < 0:
            break
        close_end = end + len("\\end{tikzpicture}")
        out.append(body[m.start() : close_end])
        cursor = close_end
    return out


def resolve_includegraphics(ref: str, raw_figures: Path) -> str | None:
    """LaTeX \\includegraphics paths typically omit the extension and use forward slashes.

    Try, in order: the bare ref (with extension if present), then ref.<ext> for
    each known extension, against files we already copied to raw_figures/.
    Returns a path relative to raw/ (e.g. "figures/fig_001.png"), or None.
    """
    if not raw_figures.is_dir():
        return None
    ref = ref.strip()
    candidates = [Path(ref).name]  # strip directory
    stem = Path(ref).stem
    for ext in (".png", ".jpg", ".jpeg", ".pdf", ".eps"):
        candidates.append(stem + ext)
        # EPS/PDF were converted to PNG by copy_figures, so also try stem+.png
        if Path(ref).suffix.lower() in {".pdf", ".eps"}:
            candidates.append(stem + ".png")
    for cand in candidates:
        target = raw_figures / cand
        if target.is_file():
            return f"figures/{cand}"
    return None


def copy_figures(source_root: Path, raw_figures: Path) -> list[str]:
    """Copy and convert figures into raw/figures/. Returns a list of warnings.

    Raster (PNG/JPG/JPEG) → copied as-is. Vector (PDF/EPS) → converted to PNG
    via `pdftoppm` if available; skipped with a warning otherwise.
    """
    raw_figures.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    for src in source_root.rglob("*"):
        if not src.is_file() or src.suffix.lower() not in IMAGE_EXTS:
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


def _parse_subfigures(body: str, raw_figures: Path) -> tuple[list[dict], str]:
    """Pull subfigure records out of body; return (subfigures, body-with-subfigures-removed).

    Stripping the subfigure bodies before searching the parent ensures that
    extract_caption / extract_label on the parent see only the *outer* figure
    scope, not text from the first subfigure.
    """
    subfigures: list[dict] = []
    stripped: list[str] = []
    cursor = 0
    while True:
        sm = SUBFIGURE_START_RE.search(body, cursor)
        if not sm:
            break
        sub_end = find_matching_end(body, sm.end(), SUBFIGURE_START_RE, SUBFIGURE_END_RE)
        if sub_end < 0:
            break
        sub_body = body[sm.end() : sub_end]
        sub_close_end = sub_end + len("\\end{subfigure}")
        stripped.append(body[cursor : sm.start()])
        cursor = sub_close_end
        sub_refs = [im.group(1) for im in INCLUDEGRAPHICS_RE.finditer(sub_body)]
        sub_resolved = [r for r in (resolve_includegraphics(ref, raw_figures) for ref in sub_refs) if r]
        subfigures.append({
            "label": extract_label(sub_body),
            "caption": extract_caption(sub_body),
            "image_refs": sub_refs,
            "resolved_paths": sub_resolved,
            "has_tikz": bool(TIKZ_RE.search(sub_body)),
            "tikz_sources": extract_tikz_sources(sub_body),
        })
    stripped.append(body[cursor:])
    return subfigures, "".join(stripped)


def extract_figures(section_files: list[Path], raw_figures: Path, sections_root: Path) -> list[dict]:
    """Walk every section file; emit one record per \\begin{figure} block.

    Each record contains: label, caption, section_file, image_refs (raw LaTeX
    paths), resolved_paths (paths inside raw/), has_tikz, available, subfigures.
    """
    figures: list[dict] = []
    for section_file in section_files:
        text = section_file.read_text(encoding="utf-8", errors="replace")
        rel_section = str(section_file.relative_to(sections_root.parent))
        pos = 0
        while True:
            m_start = FIGURE_START_RE.search(text, pos)
            if not m_start:
                break
            end_pos = find_matching_end(text, m_start.end(), FIGURE_START_RE, FIGURE_END_RE)
            if end_pos < 0:
                break  # unbalanced — skip rest of file
            body = text[m_start.end() : end_pos]
            pos = end_pos + len("\\end{figure}")

            subfigures, outer_body = _parse_subfigures(body, raw_figures)
            caption = extract_caption(outer_body)
            label = extract_label(outer_body)
            image_refs = [im.group(1) for im in INCLUDEGRAPHICS_RE.finditer(outer_body)]
            resolved = [r for r in (resolve_includegraphics(ref, raw_figures) for ref in image_refs) if r]
            has_tikz = bool(TIKZ_RE.search(outer_body)) or any(s["has_tikz"] for s in subfigures)
            resolved_with_subs = list(resolved) + [r for s in subfigures for r in s["resolved_paths"]]
            tikz_sources = extract_tikz_sources(outer_body)

            figures.append({
                "label": label,
                "caption": caption,
                "section_file": rel_section,
                "image_refs": image_refs,
                "resolved_paths": resolved,
                "has_tikz": has_tikz,
                "tikz_sources": tikz_sources,
                "available": bool(resolved_with_subs) or has_tikz,
                "subfigures": subfigures,
            })
    return figures


def figure_stats(records: list[dict]) -> dict:
    return {
        "total": len(records),
        "with_image": sum(1 for f in records if f["resolved_paths"]),
        "tikz_only": sum(1 for f in records if f["has_tikz"] and not f["resolved_paths"]),
        "missing": sum(1 for f in records if not f["available"]),
    }
