"""Render \\begin{tikzpicture} blocks captured by figures.extract_tikz_sources to PNG.

Strategy: build a tiny standalone .tex per figure (\\documentclass{standalone} +
tikz + the relevant chunks of the paper's preamble), compile with pdflatex, then
rasterise the PDF with pdftoppm. Outputs go to raw/_tikz/, separate from
raw/figures/ so we never touch source-derived assets.

Graceful degradation: if pdflatex is missing the whole step is skipped with a
warning; per-figure compile failures are collected as warnings and the figure
keeps its (empty) resolved_paths so downstream code can fall back to the raw
TikZ source as text.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

USEPACKAGE_RE = re.compile(r"\\usepackage(?:\[[^\]]*\])?\s*\{([^}]+)\}")

# Packages incompatible with \documentclass{standalone} or that pull in heavy
# layout/biblio machinery we don't want for a single TikZ figure.
DROP_PACKAGES = {
    "geometry", "fancyhdr", "fancyvrb", "tocbibind",
    "natbib", "biblatex", "cite", "hyperref",
}

# Macros that imply the journal/article class — meaningless inside \documentclass{standalone}.
# We strip the *whole call* (incl. its braced argument). One per line in the table:
# (name, has_optional, n_required_args). Args are eaten greedily through balanced braces.
DROP_MACROS_WITH_ARGS = {
    "documentclass": (True, 1),
    "LoadClass": (True, 1),
    "PassOptionsToPackage": (True, 2),
    "RequirePackage": (True, 1),
    "hypersetup": (False, 1),
    "captionsetup": (True, 1),
    "title": (True, 1),
    "subtitle": (False, 1),
    "author": (True, 1),
    "authornote": (False, 1),
    "affiliation": (True, 1),
    "email": (True, 1),
    "thanks": (False, 1),
    "date": (False, 1),
    "bibliographystyle": (False, 1),
    "bibliography": (False, 1),
    "addbibresource": (True, 1),
    "setcopyright": (False, 1),
    "copyrightyear": (False, 1),
    "acmJournal": (False, 1),
    "acmVolume": (False, 1),
    "acmNumber": (False, 1),
    "acmArticle": (False, 1),
    "acmYear": (False, 1),
    "acmMonth": (False, 1),
    "acmDOI": (False, 1),
    "acmISBN": (False, 1),
    "acmConference": (True, 3),
    "acmBooktitle": (False, 1),
    "acmPrice": (False, 1),
    "acmSubmissionID": (False, 1),
    "settopmatter": (False, 1),
    "ccsdesc": (True, 1),
    "keywords": (False, 1),
    "fancyfoot": (True, 1),
    "fancyhead": (True, 1),
    "pagestyle": (False, 1),
    "thispagestyle": (False, 1),
    "geometry": (False, 1),
}

# Macros without args that we drop wholesale (line-suffix tolerant).
DROP_MACROS_NOARG = {
    "maketitle", "tableofcontents",
    "pdfoutput",  # `\pdfoutput=1` is a TeX assignment, handled separately
}


def _skip_optional(s: str, i: int) -> int:
    """If s[i] == '[', skip past the matching ']'. Returns new i."""
    if i < len(s) and s[i] == "[":
        depth = 1
        j = i + 1
        while j < len(s) and depth > 0:
            if s[j] == "[":
                depth += 1
            elif s[j] == "]":
                depth -= 1
            j += 1
        return j
    return i


def _skip_braced(s: str, i: int) -> int:
    """If s[i] == '{', skip past the matching '}'. Returns new i."""
    if i < len(s) and s[i] == "{":
        depth = 1
        j = i + 1
        while j < len(s) and depth > 0:
            c = s[j]
            if c == "\\" and j + 1 < len(s):
                j += 2
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            j += 1
        return j
    return i


def _skip_ws(s: str, i: int) -> int:
    while i < len(s) and s[i] in " \t":
        i += 1
    return i


def sanitize_preamble(preamble: str) -> str:
    """Keep tikz-relevant directives, drop class-specific cruft.

    Strategy: walk the preamble and *delete* known-bad macros (with their
    arguments) and \\usepackage entries for known-bad packages. Everything else
    (\\newcommand, \\renewcommand, \\def, \\DeclareMathOperator, \\tikzset,
    \\pgfplotsset, \\SetAlFnt, ..., \\IncMargin, etc.) survives — many papers
    define helper macros their TikZ figures depend on.
    """
    out: list[str] = []
    i = 0
    n = len(preamble)
    while i < n:
        if preamble[i] != "\\":
            out.append(preamble[i])
            i += 1
            continue

        # Read macro name
        j = i + 1
        while j < n and (preamble[j].isalpha() or preamble[j] == "@"):
            j += 1
        name = preamble[i + 1 : j]

        if name == "usepackage":
            k = _skip_optional(preamble, _skip_ws(preamble, j))
            k = _skip_ws(preamble, k)
            end = _skip_braced(preamble, k)
            arg = preamble[k + 1 : end - 1] if end > k else ""
            names = [n.strip() for n in arg.split(",") if n.strip()]
            if any(p in DROP_PACKAGES for p in names):
                i = end
                continue
            out.append(preamble[i:end])
            i = end
            continue

        if name in DROP_MACROS_WITH_ARGS:
            has_opt, nargs = DROP_MACROS_WITH_ARGS[name]
            k = j
            if has_opt:
                k = _skip_optional(preamble, _skip_ws(preamble, k))
            for _ in range(nargs):
                k = _skip_ws(preamble, k)
                if k < n and preamble[k] == "{":
                    k = _skip_braced(preamble, k)
                else:
                    break
            i = k
            continue

        if name == "pdfoutput":
            # Consume `\pdfoutput=N` or `\pdfoutput N`
            k = _skip_ws(preamble, j)
            if k < n and preamble[k] == "=":
                k += 1
            k = _skip_ws(preamble, k)
            while k < n and preamble[k].isdigit():
                k += 1
            i = k
            continue

        if name in DROP_MACROS_NOARG:
            i = j
            continue

        # Unknown macro — keep it verbatim
        out.append(preamble[i:j])
        i = j

    sanitized = "".join(out)
    # Many papers \renewcommand class-internal hooks (\@formatdoi, \footnotetextcopyrightpermission)
    # that won't exist when the class isn't loaded. \providecommand makes those tolerant:
    # it's a no-op if the macro is already defined (e.g. by a package), and defines it
    # otherwise — exactly what we want for standalone compilation.
    sanitized = re.sub(r"\\renewcommand\b", r"\\providecommand", sanitized)
    return sanitized


def build_standalone(tikz_source: str, sanitized_preamble: str) -> str:
    """Wrap a TikZ block in a minimal standalone .tex.

    The stub block defines no-op fallbacks for class-internal macros
    (acmart's `\\footnotetextcopyrightpermission`, `\\ACM@NRadjust`, ...) that
    paper-specific .sty files reference but the standalone class can't provide.
    `\\providecommand` is harmless when the macro is already defined.
    """
    stub = (
        "\\makeatletter\n"
        "\\providecommand{\\footnotetextcopyrightpermission}[1]{}\n"
        "\\providecommand{\\ACM@NRadjust}[1]{#1}\n"
        "\\providecommand{\\@subsubsecfont}{\\bfseries}\n"
        "\\providecommand{\\@subsecfont}{\\bfseries}\n"
        "\\providecommand{\\@secfont}{\\bfseries}\n"
        "\\providecommand{\\acmart@}{}\n"
        "\\providecommand{\\IEEEPARstart}[2]{#1#2}\n"
        "\\providecommand{\\IEEEcompsoctitleabstractindextext}[1]{}\n"
        "\\providecommand{\\IEEEdisplaynontitleabstractindextext}{}\n"
        "\\makeatother\n"
    )
    return (
        "\\documentclass[border=2pt]{standalone}\n"
        "\\usepackage{tikz}\n"
        "\\usepackage{amsmath,amssymb}\n"
        f"{stub}"
        f"{sanitized_preamble}\n"
        "\\begin{document}\n"
        f"{tikz_source}\n"
        "\\end{document}\n"
    )


def compile_to_pdf(tex_path: Path, source_root: Path, timeout: int = 60) -> tuple[bool, str]:
    """Run pdflatex on tex_path; return (ok, stderr-or-log-tail)."""
    tex_abs = tex_path.resolve()
    src_abs = source_root.resolve()
    env = dict(os.environ)
    # Let pdflatex find any custom .sty/.cls/images shipped with the source.
    existing = env.get("TEXINPUTS", "")
    env["TEXINPUTS"] = f".:{src_abs}//:{existing}"
    try:
        proc = subprocess.run(
            [
                "pdflatex",
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-no-shell-escape",
                "-output-directory",
                str(tex_abs.parent),
                str(tex_abs),
            ],
            cwd=tex_abs.parent,
            env=env,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, "pdflatex timed out"
    if proc.returncode != 0:
        log = (proc.stdout.decode(errors="replace") + proc.stderr.decode(errors="replace"))
        # Tail: pdflatex error lines start with "!" or "l." (line indicators)
        tail = "\n".join(
            line for line in log.splitlines() if line.startswith(("!", "l."))
        )[-600:]
        return False, tail or log[-600:]
    return tex_abs.with_suffix(".pdf").exists(), ""


def crop_pdf(pdf: Path, timeout: int = 60) -> Path:
    """pdfcrop to a sibling file; return the cropped path, or the original on failure.

    Needed because paper .sty files reachable via TEXINPUTS can override the
    standalone class's tight page geometry (full letter pages, content pushed
    to a later page). pdfcrop restores a content-tight bounding box per page.
    """
    if shutil.which("pdfcrop") is None:
        return pdf
    cropped = pdf.with_name(pdf.stem + "_crop.pdf")
    try:
        proc = subprocess.run(
            ["pdfcrop", str(pdf), str(cropped)], capture_output=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return pdf
    return cropped if proc.returncode == 0 and cropped.exists() else pdf


def pdf_pages(pdf: Path) -> int:
    if shutil.which("pdfinfo") is None:
        return 1
    try:
        proc = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, timeout=30)
    except subprocess.TimeoutExpired:
        return 1
    m = re.search(r"^Pages:\s+(\d+)", proc.stdout.decode(errors="replace"), re.MULTILINE)
    return int(m.group(1)) if m else 1


def pdf_to_png(pdf: Path, dest: Path, dpi: int = 200, page: int | None = None) -> tuple[bool, str]:
    pdf_abs = pdf.resolve()
    dest_abs = dest.resolve()
    cmd = ["pdftoppm", "-png", "-r", str(dpi), "-singlefile"]
    if page is not None:
        cmd += ["-f", str(page), "-l", str(page)]
    cmd += [str(pdf_abs), str(dest_abs.with_suffix(""))]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        return False, "pdftoppm timed out"
    if proc.returncode != 0:
        return False, proc.stderr.decode(errors="replace")[:300]
    return dest.exists(), ""


TIKZPICTURE_RE = re.compile(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}", re.DOTALL)


def _normalize_tikz(s: str) -> str:
    return re.sub(r"\s+", "", s)


def render_via_external(
    figure_records: list[dict],
    raw_dir: Path,
    out_dir: Path | None,
    source_root: Path,
    main_tex: Path,
    warnings: list[str],
    timeout: int = 180,
) -> None:
    """Compiler-first rendering: compile the REAL paper with TikZ's external
    library and harvest each picture as its own tightly-cropped PDF.

    No preamble surgery: the paper's own class, styles, and .bbl are in
    effect, so pictures depending on body-defined macros/colors render
    correctly and page-geometry never interferes. We drive the per-figure
    jobs ourselves (no -shell-escape needed).

    Best-effort: fills resolved_paths on the records it manages to render and
    warns about the rest; the standalone fallback mops up whatever is left.
    Also keeps the compiled paper as <out_dir>/paper.pdf when out_dir is given.
    """
    work = raw_dir / "_tikz" / "_ext"
    work.mkdir(parents=True, exist_ok=True)
    raw_text = main_tex.read_text(encoding="utf-8", errors="replace")
    idx = raw_text.find(r"\begin{document}")
    if idx < 0:
        warnings.append("external render: no \\begin{document} in main tex")
        return
    ext_tex = work / "main_ext.tex"
    ext_tex.write_text(
        raw_text[:idx]
        + "\\usetikzlibrary{external}\\tikzexternalize[mode=list only]\n"
        + raw_text[idx:]
    )

    env = dict(os.environ)
    env["TEXINPUTS"] = (
        f".:{work.resolve()}//:{source_root.resolve()}//:" + env.get("TEXINPUTS", "")
    )

    def run(jobname: str | None = None) -> tuple[bool, str]:
        cmd = [
            "pdflatex", "-interaction=nonstopmode", "-halt-on-error",
            "-no-shell-escape", "-output-directory", str(work.resolve()),
        ]
        if jobname:
            cmd += [
                "-jobname", jobname,
                f"\\def\\tikzexternalrealjob{{main_ext}}\\input{{{ext_tex.resolve()}}}",
            ]
        else:
            cmd.append(str(ext_tex.resolve()))
        try:
            proc = subprocess.run(
                cmd, cwd=main_tex.parent, env=env, capture_output=True, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            return False, "pdflatex timed out"
        if proc.returncode != 0:
            log = proc.stdout.decode(errors="replace")
            tail = "\n".join(l for l in log.splitlines() if l.startswith(("!", "l.")))
            return False, (tail or log)[-400:]
        return True, ""

    # Two main passes: first writes the .figlist (and .aux), second stabilises
    # cross-references so the kept paper.pdf reads cleanly.
    for _ in range(2):
        ok, err = run()
        if not ok:
            warnings.append(
                f"external render: main compile failed: {err.splitlines()[0] if err else '?'}"
            )
            return
    if out_dir is not None and (work / "main_ext.pdf").exists():
        shutil.copy2(work / "main_ext.pdf", out_dir / "paper.pdf")

    figlist = work / "main_ext.figlist"
    if not figlist.exists():
        warnings.append("external render: no .figlist produced")
        return
    names = [l.strip() for l in figlist.read_text().splitlines() if l.strip()]

    # Document-order tikz blocks from the flattened sections; index-align
    # against the figlist. A count mismatch means a picture exists that our
    # flattening didn't capture (or vice versa) — mapping would be unsafe.
    all_blocks: list[str] = []
    for sec in sorted((raw_dir / "sections").glob("*.tex")):
        for m in TIKZPICTURE_RE.finditer(sec.read_text(errors="replace")):
            all_blocks.append(_normalize_tikz(m.group(0)))
    if len(names) != len(all_blocks):
        warnings.append(
            f"external render: {len(names)} externalized pictures vs "
            f"{len(all_blocks)} in flattened sections — mapping unsafe, skipping"
        )
        return

    out_tikz = raw_dir / "_tikz"
    counter = 0
    rendered = 0
    used: set[int] = set()

    def render_scope(scope: dict, scope_label: str | None) -> None:
        nonlocal counter, rendered
        if scope.get("resolved_paths"):
            return
        sources: list[str] = scope.get("tikz_sources", []) or []
        paths = scope.setdefault("resolved_paths", [])
        for k, src in enumerate(sources, start=1):
            counter += 1
            base = _slug_for(scope_label, counter)
            slug = base if k == 1 else f"{base}-{k}"
            png_dest = out_tikz / f"{slug}.png"
            rel = f"_tikz/{png_dest.name}"
            norm = _normalize_tikz(src)
            i = next(
                (j for j, b in enumerate(all_blocks) if j not in used and b == norm), None
            )
            if i is None:
                warnings.append(f"external render: no document match for {slug}")
                continue
            used.add(i)
            pdf = work / f"{names[i]}.pdf"
            if not pdf.exists():
                ok, err = run(jobname=names[i])
                if not ok:
                    warnings.append(
                        f"external render failed for {slug}: "
                        f"{err.splitlines()[0] if err else '?'}"
                    )
                    continue
            ok, err = pdf_to_png(pdf, png_dest)
            if not ok:
                warnings.append(f"external rasterise failed for {slug}: {err}")
                continue
            if rel not in paths:
                paths.append(rel)
            rendered += 1

    for fig in figure_records:
        render_scope(fig, fig.get("label"))
        for sub in fig.get("subfigures", []):
            render_scope(sub, sub.get("label") or fig.get("label"))
    if rendered:
        warnings.append(f"tikz render (external, true context): {rendered} figure(s)")


def _slug_for(label: str | None, fallback_n: int) -> str:
    if not label:
        return f"tikz_{fallback_n:03d}"
    s = re.sub(r"[^a-zA-Z0-9]+", "-", label).strip("-").lower()
    return s or f"tikz_{fallback_n:03d}"


def render_tikz_figures(
    figure_records: list[dict],
    raw_dir: Path,
    sanitized_preamble: str,
    source_root: Path,
    main_tex: Path | None = None,
    bundle_dir: Path | None = None,
) -> list[str]:
    """Render every TikZ block; mutate figure_records in-place to add resolved paths.

    Compiler-first: when main_tex is given, render_via_external compiles the
    real paper and harvests pictures in true context (also keeping
    <bundle_dir>/paper.pdf). The standalone-rebuild loop below then mops up
    only what external rendering left unresolved. Returns warnings. Records
    that already have resolved_paths (raster) are skipped: a paper that ships
    both a PDF and a TikZ source for the same figure is happy with the PDF
    render.
    """
    warnings: list[str] = []
    if shutil.which("pdflatex") is None:
        warnings.append("pdflatex not installed — skipping TikZ rendering")
        return warnings
    if shutil.which("pdftoppm") is None:
        warnings.append("pdftoppm not installed — skipping TikZ rendering")
        return warnings

    if main_tex is not None:
        render_via_external(
            figure_records, raw_dir, bundle_dir, source_root, main_tex, warnings
        )

    out_dir = raw_dir / "_tikz"
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir = out_dir / "_work"
    work_dir.mkdir(exist_ok=True)

    counter = 0
    rendered = 0

    def _render_one(scope: dict, scope_label: str | None) -> None:
        nonlocal counter, rendered
        if scope.get("resolved_paths"):
            return
        sources: list[str] = scope.get("tikz_sources", []) or []
        if not sources:
            return
        for k, src in enumerate(sources, start=1):
            counter += 1
            base = _slug_for(scope_label, counter)
            # A figure can hold several tikzpictures (subplots); each needs its
            # own file or later blocks silently overwrite / skip via the cache.
            slug = base if k == 1 else f"{base}-{k}"
            png_dest = out_dir / f"{slug}.png"
            rel = f"_tikz/{png_dest.name}"
            paths = scope.setdefault("resolved_paths", [])
            if png_dest.exists():
                if rel not in paths:
                    paths.append(rel)
                rendered += 1
                continue
            tex_path = work_dir / f"{slug}.tex"
            tex_path.write_text(build_standalone(src, sanitized_preamble), encoding="utf-8")
            ok, err = compile_to_pdf(tex_path, source_root)
            if not ok:
                warnings.append(f"tikz compile failed for {slug}: {err.splitlines()[0] if err else 'no log'}")
                continue
            # Paper .sty files can defeat standalone's tight geometry: full
            # letter pages, figure pushed past a blank first page. Crop back
            # to content and rasterise the last page, where the picture lands.
            pdf = crop_pdf(tex_path.with_suffix(".pdf"))
            pages = pdf_pages(pdf)
            if pages > 1:
                warnings.append(
                    f"tikz {slug}: {pages}-page pdf (page-geometry override); using last page"
                )
            ok, err = pdf_to_png(pdf, png_dest, page=pages if pages > 1 else None)
            if not ok:
                warnings.append(f"tikz rasterise failed for {slug}: {err}")
                continue
            if rel not in paths:
                paths.append(rel)
            rendered += 1

    for fig in figure_records:
        _render_one(fig, fig.get("label"))
        for sub in fig.get("subfigures", []):
            _render_one(sub, sub.get("label") or fig.get("label"))
        # Recompute figure-level availability after rendering
        sub_paths = [p for s in fig.get("subfigures", []) for p in s.get("resolved_paths", [])]
        if fig.get("resolved_paths") or sub_paths or fig.get("has_tikz"):
            fig["available"] = True

    if rendered:
        warnings.append(f"tikz render: {rendered} figure(s) rendered to _tikz/")
    # Clean intermediate .aux/.log/.pdf
    if work_dir.exists():
        shutil.rmtree(work_dir, ignore_errors=True)
    return warnings
