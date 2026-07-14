"""Generic LaTeX text utilities used by the section and figure parsers.

Pure-text helpers; no I/O. The parsing here is intentionally lightweight (regex
+ a brace-balance scan), not a full LaTeX parser — sufficient for the kinds of
constructs we care about (comments, balanced braces, balanced begin/end pairs).
"""

from __future__ import annotations

import re

COMMENT_RE = re.compile(r"(?<!\\)%.*$", re.MULTILINE)


def strip_comments(tex: str, collect: list[tuple[int, str]] | None = None) -> str:
    """Remove `%`-to-end-of-line comments while preserving escaped `\\%`.

    When `collect` is given, substantive stripped comments are appended to it
    as (1-based line number, comment text). Separator art (`%%%%`, `% ====`)
    and bare line-continuation `%` are skipped — only comments containing a
    letter or digit are kept. Comments are author workshop material: they must
    never enter the executed text (a commented \\input is not an include), but
    they can carry intent worth surfacing, so callers may preserve them in a
    sidecar. The verbatim originals always remain under raw/_source/.
    """
    if collect is None:
        return COMMENT_RE.sub("", tex)
    out_lines: list[str] = []
    for n, line in enumerate(tex.split("\n"), start=1):
        m = COMMENT_RE.search(line)
        if m:
            body = m.group(0).lstrip("%").strip()
            if re.search(r"[A-Za-z0-9]", body):
                collect.append((n, body))
            line = line[: m.start()]
        out_lines.append(line)
    return "\n".join(out_lines)


def extract_braced_arg(s: str, start: int) -> tuple[str | None, int]:
    """At s[start], expect '{'; return (content, position-just-after-})."""
    if start >= len(s) or s[start] != "{":
        return None, start
    depth = 1
    i = start + 1
    while i < len(s) and depth > 0:
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            i += 2  # skip escaped character (e.g. \{, \})
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[start + 1 : i], i + 1
        i += 1
    return None, start  # unbalanced


def find_matching_end(text: str, start_pos: int, start_re: re.Pattern, end_re: re.Pattern) -> int:
    """Given the position right after a \\begin{X}, find the position of the matching \\end{X}.

    Handles nested begin/end pairs of the same kind.
    Returns the start-position of the closing \\end, or -1 on imbalance.
    """
    depth = 1
    i = start_pos
    while depth > 0 and i < len(text):
        m_start = start_re.search(text, i)
        m_end = end_re.search(text, i)
        if not m_end:
            return -1
        if m_start and m_start.start() < m_end.start():
            depth += 1
            i = m_start.end()
        else:
            depth -= 1
            if depth == 0:
                return m_end.start()
            i = m_end.end()
    return -1
