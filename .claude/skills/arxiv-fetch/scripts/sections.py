"""Find the main .tex file, split off the preamble, and emit per-section files.

This module is the LaTeX *structure* layer: it takes the unpacked source tree
and turns it into (preamble.tex, sections/01_*.tex, ...). It handles
\\input/\\include/\\subfile/\\import/\\subimport resolution, recursive
flattening with cycle protection, and splits at the natural boundaries
(top-level \\input or, for monolithic papers, top-level \\section{}).
Include-like macros it does not resolve are detected and surfaced as
warnings (find_unhandled_includes) rather than silently dropped.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from tex_utils import strip_comments

# One-argument includes plus two-argument \import{dir}{file} / \subimport.
# resolve_path tries the target against both the current file's dir and the
# project root, which covers import (root-relative) and subimport (file-relative).
INPUT_RE = re.compile(
    r"\\(?:input|include|subfile)\s*\{(?P<file>[^}]+)\}"
    r"|\\(?:import|subimport)\s*\{(?P<dir>[^}]*)\}\s*\{(?P<impfile>[^}]+)\}"
)
SECTION_RE = re.compile(r"^\s*\\section\*?\s*\{(.+?)\}", re.MULTILINE)
TITLE_HINT_RE = re.compile(r"\\(?:section|chapter)\*?\s*\{(.+?)\}")

# Include-like macros the resolver does NOT inline. If one survives into a
# section file, its content is missing from the bundle without any resolver
# error — detect and warn so the failure is visible instead of silent.
# (The referenced file is still on disk under raw/_source/ for manual reading.)
UNHANDLED_INCLUDE_RE = re.compile(
    r"\\(?:includestandalone|InputIfFileExists|subfileinclude|lstinputlisting|verbatiminput)\s*\{[^}]*\}"
    r"|\\inputminted\s*\{[^}]*\}\s*\{[^}]*\}"
    r"|\\input\s+[A-Za-z0-9_./-]+"
)


def include_target(m: re.Match[str]) -> str:
    """File target of an INPUT_RE match; joins \\import's dir and file args."""
    if m.group("file") is not None:
        return m.group("file").strip()
    d = m.group("dir").strip()
    f = m.group("impfile").strip()
    return f"{d.rstrip('/')}/{f}" if d else f


def find_unhandled_includes(tex: str) -> list[str]:
    """Return include-like macro invocations that the resolver left un-inlined."""
    return [m.group(0) for m in UNHANDLED_INCLUDE_RE.finditer(tex)]


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
    comments: dict[str, list[tuple[int, str]]] | None = None,
) -> str:
    """Recursively inline \\input/\\include/\\subfile, with cycle protection."""
    if depth > 32:
        warnings.append(f"max include depth exceeded at base={base}")
        return tex

    def repl(m: re.Match[str]) -> str:
        target = include_target(m)
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
        collect = None
        if comments is not None:
            collect = comments.setdefault(str(path.relative_to(root)), [])
        sub = strip_comments(sub, collect=collect)
        return inline_includes(sub, path.parent, root, visited, warnings, depth + 1, comments)

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
    return [(m.start(), m.end(), include_target(m)) for m in INPUT_RE.finditer(main_tex_body)]


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
    raw_main_body: str,
    root: Path,
    base: Path,
    comments: dict[str, list[tuple[int, str]]] | None = None,
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
        target = include_target(m)
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
            collect = None
            if comments is not None:
                collect = comments.setdefault(str(path.relative_to(root)), [])
            sub = strip_comments(sub, collect=collect)
            inlined = inline_includes(
                sub, path.parent, root, visited_local, warnings, comments=comments
            )
            title = first_section_title(inlined) or path.stem
            parts.append((title, inlined))
        cursor = m.end()
    tail = raw_main_body[cursor:].strip()
    if tail:
        parts.append((f"tail-{counter}", tail))
    return parts, warnings
