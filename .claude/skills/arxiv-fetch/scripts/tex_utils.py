"""Generic LaTeX text utilities used by the section and figure parsers.

Pure-text helpers; no I/O. The parsing here is intentionally lightweight (regex
+ a brace-balance scan), not a full LaTeX parser — sufficient for the kinds of
constructs we care about (comments, balanced braces, balanced begin/end pairs).
"""

from __future__ import annotations

import re

COMMENT_RE = re.compile(r"(?<!\\)%.*$", re.MULTILINE)


def strip_comments(tex: str) -> str:
    """Remove `%`-to-end-of-line comments while preserving escaped `\\%`."""
    return COMMENT_RE.sub("", tex)


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
