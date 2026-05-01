"""Validate a wikip wiki and regenerate index.md.

Checks:
  - Every page has YAML frontmatter with required fields (slug, title, source, type, ingested).
  - Frontmatter slug matches the filename stem.
  - Every [[wiki-link]] in page bodies resolves to an existing page.
  - Every edge in graph.json has from/to slugs that exist as pages.
  - Every edge predicate is defined in _schema.json.
  - Every node in graph.json corresponds to an existing page.
  - Reports orphan-in pages (no incoming edges) — informational, not an error.

Regenerates index.md grouped by type, sorted by date (newest first within each group).

Exit code: 0 if no errors, 1 if any error-level issues found.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REQUIRED_FRONTMATTER = ("slug", "title", "source", "type", "ingested")
WIKI_LINK_RE = re.compile(r"\[\[([^\]|#]+?)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def parse_frontmatter(text: str) -> dict[str, object] | None:
    """Minimal YAML-ish parser for our flat frontmatter (no nested structures)."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    data: dict[str, object] = {}
    for line in m.group(1).splitlines():
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            data[key] = [v.strip().strip('"').strip("'") for v in inner.split(",")] if inner else []
        elif (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            data[key] = value[1:-1]
        else:
            data[key] = value
    return data


def collect_pages(pages_dir: Path) -> dict[str, dict[str, object]]:
    """Return {slug: {path, frontmatter, body}}."""
    result: dict[str, dict[str, object]] = {}
    for md in sorted(pages_dir.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        body = text[FRONTMATTER_RE.match(text).end() :] if fm is not None else text
        result[md.stem] = {"path": md, "frontmatter": fm, "body": body}
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("wiki_dir", type=Path)
    args = ap.parse_args()

    wiki: Path = args.wiki_dir
    pages_dir = wiki / "pages"
    graph_path = wiki / "graph.json"
    schema_path = wiki / "_schema.json"
    index_path = wiki / "index.md"

    for required in (pages_dir, graph_path, schema_path):
        if not required.exists():
            sys.exit(f"missing {required} — run init.py first")

    schema = json.loads(schema_path.read_text())
    predicates = set(schema.get("predicates", {}).keys())
    graph = json.loads(graph_path.read_text())
    pages = collect_pages(pages_dir)

    errors: list[str] = []
    warnings: list[str] = []

    # 1. Per-page checks
    for slug, info in pages.items():
        fm = info["frontmatter"]
        if fm is None:
            errors.append(f"{slug}.md: missing or unparseable YAML frontmatter")
            continue
        for field in REQUIRED_FRONTMATTER:
            if field not in fm or not fm[field]:
                errors.append(f"{slug}.md: frontmatter missing '{field}'")
        if fm.get("slug") and fm["slug"] != slug:
            errors.append(f"{slug}.md: frontmatter slug={fm['slug']!r} doesn't match filename")
        # 2. Wiki-link resolution
        for m in WIKI_LINK_RE.finditer(info["body"]):
            target = m.group(1).strip()
            if target not in pages:
                errors.append(f"{slug}.md: broken [[wiki-link]] to '{target}'")

    # 3. Graph checks
    node_slugs = {n.get("slug") for n in graph.get("nodes", []) if n.get("slug")}
    for n in graph.get("nodes", []):
        if not n.get("slug"):
            errors.append(f"graph.json: node missing slug: {n}")
        elif n["slug"] not in pages:
            errors.append(f"graph.json: node {n['slug']!r} has no corresponding page")
    for slug in pages:
        if slug not in node_slugs:
            warnings.append(f"page {slug!r} not registered as a node in graph.json")
    for i, edge in enumerate(graph.get("edges", [])):
        for endpoint in ("from", "to"):
            slug = edge.get(endpoint)
            if not slug:
                errors.append(f"graph.json: edge[{i}] missing '{endpoint}'")
            elif slug not in pages:
                errors.append(f"graph.json: edge[{i}] {endpoint}={slug!r} has no page")
        pred = edge.get("predicate")
        if not pred:
            errors.append(f"graph.json: edge[{i}] missing 'predicate'")
        elif pred not in predicates:
            errors.append(f"graph.json: edge[{i}] predicate {pred!r} not in _schema.json")

    # 4. Orphan-in (informational — no incoming edges)
    incoming: dict[str, int] = defaultdict(int)
    for edge in graph.get("edges", []):
        if edge.get("to") in pages:
            incoming[edge["to"]] += 1
    for slug in pages:
        if incoming[slug] == 0:
            warnings.append(f"page {slug!r} has no incoming edges (orphan-in)")

    # 5. Regenerate index.md (grouped by type, sorted by date desc)
    by_type: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for slug, info in pages.items():
        fm = info["frontmatter"] or {}
        ptype = str(fm.get("type", "unknown"))
        title = str(fm.get("title", slug))
        date = str(fm.get("date", ""))
        by_type[ptype].append((date, slug, title))
    lines = ["# Wiki", "", f"_{len(pages)} pages, {len(graph.get('edges', []))} edges._", ""]
    for ptype in sorted(by_type):
        lines.append(f"## {ptype}")
        lines.append("")
        for _, slug, title in sorted(by_type[ptype], reverse=True):
            lines.append(f"- [[{slug}|{title}]]")
        lines.append("")
    index_path.write_text("\n".join(lines))

    # Reporting
    print(f"checked {len(pages)} pages, {len(graph.get('edges', []))} edges")
    for w in warnings:
        print(f"  warn: {w}")
    for e in errors:
        print(f"  ERROR: {e}", file=sys.stderr)
    print(f"regenerated {index_path}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
