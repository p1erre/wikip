"""Derive content.md — the bundle contract's single-file, LLM-legible rendition.

Translator architecture: content.md is produced by ordered, conservative
translation passes over the LaTeX body. Each pass rewrites one construct it
fully understands into markdown, in place; everything else passes through
verbatim as LaTeX text (legible, never wrong, just not pretty). Adding a pass
progressively improves how much of the document renders as markdown, and
`fetch.py --derive-only` re-runs the translator over an already-extracted
bundle, so improvements retrofit old bundles offline.

Current passes:
  1. translate_figures — replace each figure/table environment matched to a
     figures.json record with markdown image embed(s) + the full caption as a
     blockquote, in the position the author placed it. Records whose
     environment can't be located fall back to a trailing ## Figures gallery
     (placement may degrade; captions and images are never dropped).

The preamble stays inside a latex fence (macro context, not prose). Math in
the body is left as-is on purpose: $...$ / $$...$$ render natively in
Obsidian and VS Code.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# Four-backtick fences so occasional triple backticks inside the source
# don't terminate the block.
FENCE = "````"

FIG_ENV_RE = re.compile(
    r"\\begin\{(figure\*?|table\*?|sidewaysfigure\*?|sidewaystable\*?|wrapfigure\*?)\}"
    r".*?\\end\{\1\}",
    re.DOTALL,
)


def _figure_md(rec: dict, fallback_label: str) -> str:
    """Markdown block for one figures.json record (subfigures included).

    Embeds reference images bundle-root-relative (raw/figures/..., raw/_tikz/...)
    so downstream staging can rewrite them into a vault. The caption is kept
    verbatim as a blockquote with the label as a bold prefix — the author's
    own description must never be lost. Unrendered TikZ falls back to fenced
    source plus caption.
    """
    def entry(r: dict, label: str) -> list[str]:
        lines: list[str] = []
        for p in dict.fromkeys(r.get("resolved_paths", [])):  # dedupe, keep order
            lines += [f"![{label}](raw/{p})", ""]
        if not r.get("resolved_paths") and r.get("tikz_sources"):
            lines += ["_No rendered image — raw TikZ source:_", ""]
            for src in r["tikz_sources"]:
                lines += [f"{FENCE}latex\n{src.strip()}\n{FENCE}", ""]
        caption = (r.get("caption") or "").strip()
        if caption:
            lines += [f"> **{label}** — " + caption.replace("\n", "\n> "), ""]
        return lines

    label = rec.get("label") or fallback_label
    lines = entry(rec, label)
    for j, sub in enumerate(rec.get("subfigures", []), start=1):
        lines += entry(sub, sub.get("label") or f"{label}.{j}")
    return "\n".join(lines).strip()


def translate_figures(body: str, records: list[dict]) -> tuple[str, list[dict]]:
    """Pass 1: replace figure/table environments with markdown blocks, in place.

    A record is placed by locating the environment that contains its \\label.
    Returns (translated_body, unplaced_records). Environments with no
    figures.json record are left as verbatim LaTeX; records with no locatable
    environment are returned for the caller's fallback gallery.
    """
    envs = list(FIG_ENV_RE.finditer(body))
    replacements: dict[int, tuple[int, str]] = {}  # start -> (end, markdown)
    unplaced: list[dict] = []
    for i, rec in enumerate(records, start=1):
        label = rec.get("label")
        target = None
        if label:
            needle = f"\\label{{{label}}}"
            target = next((m for m in envs if needle in m.group(0)), None)
        if target is None or target.start() in replacements:
            unplaced.append(rec)
            continue
        replacements[target.start()] = (target.end(), _figure_md(rec, f"figure-{i}"))

    out: list[str] = []
    cursor = 0
    for start in sorted(replacements):
        end, md = replacements[start]
        out += [body[cursor:start], md]
        cursor = end
    out.append(body[cursor:])
    return "".join(out), unplaced


def fallback_gallery(records: list[dict]) -> str:
    """Trailing gallery for records that couldn't be placed in the body."""
    if not records:
        return ""
    lines = [
        "## Figures",
        "",
        "_Figures whose position in the text could not be determined:_",
        "",
    ]
    for i, rec in enumerate(records, start=1):
        label = rec.get("label") or f"figure-{i}"
        section = rec.get("section_file") or ""
        lines += [f"### {label}" + (f" — `{section}`" if section else ""), ""]
        lines += [_figure_md(rec, label), ""]
    return "\n".join(lines).rstrip() + "\n"


def write_content_md(out_dir: Path, raw_dir: Path) -> Path:
    """Derive <out_dir>/content.md from the extracted LaTeX under raw/.

    Frontmatter (title, arxiv_id), the preamble in a latex fence, then the
    body: sections in structure.json order with `% ==== <file> ====` markers,
    run through the translation passes. Unplaced figures land in a trailing
    gallery so nothing is ever dropped.
    """
    structure = json.loads((raw_dir / "structure.json").read_text())
    meta_path = raw_dir / "arxiv_meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    title = meta.get("title") or structure.get("arxiv_id", "")

    parts: list[str] = []
    for section in structure.get("sections", []):
        sec = raw_dir / section["file"]
        if sec.exists():
            parts.append(
                f"% ==== {section['file']} ====\n{sec.read_text(errors='replace').strip()}"
            )
    body = "\n\n".join(parts)

    figures_path = raw_dir / "figures.json"
    records = (
        json.loads(figures_path.read_text()).get("figures", []) if figures_path.exists() else []
    )
    body, unplaced = translate_figures(body, records)

    preamble_path = raw_dir / "preamble.tex"
    preamble = ""
    if preamble_path.exists():
        preamble = (
            f"{FENCE}latex\n% ==== preamble.tex ====\n"
            f"{preamble_path.read_text(errors='replace').strip()}\n{FENCE}\n\n"
        )

    gallery = fallback_gallery(unplaced)
    content_path = out_dir / "content.md"
    content_path.write_text(
        "---\n"
        f"title: {json.dumps(title, ensure_ascii=False)}\n"
        f"arxiv_id: {structure.get('arxiv_id', '')}\n"
        "---\n\n"
        + preamble
        + body.strip()
        + "\n"
        + (f"\n{gallery}" if gallery else "")
    )
    return content_path
