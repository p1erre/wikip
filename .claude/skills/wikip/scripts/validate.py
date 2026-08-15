"""Validate a wikip wiki and regenerate index.md.

Checks:
  - Every page has YAML frontmatter with the required fields for its type.
    Papers/videos/pdfs require: slug, title, source, type, ingested.
    Concepts require:           slug, title, type, ingested.
  - Frontmatter slug matches the filename stem.
  - Pages live under pages/papers/ or pages/concepts/ matching their type.
  - Every [[wiki-link]] in page bodies resolves to an existing page or a
    staged source doc under sources/.
  - A paper-like page's `source_doc:` frontmatter points at an existing
    sources/<name>.md (staged by stage_source.py); paper-like pages without
    `source_doc:` are flagged (informational).
  - Paper-like pages (paper, video, pdf) contain no markdown image embeds.
    Figures belong on concept pages, where they teach a concept; paper pages
    summarise and link out. Embedding on a paper page also breaks rendering
    when the user opens a parent directory as the Obsidian vault, since
    `../../assets/...` then walks outside the vault.
  - Every edge in graph.json has from/to slugs that exist as pages.
  - Every edge predicate is defined in _schema.json.
  - For predicates that declare from_type / to_type, edge endpoints have the
    declared page types.
  - Every node in graph.json corresponds to an existing page.
  - Reports orphan-in pages (no incoming edges) — informational, not an error.
  - Concept pages with no `discusses` / `defines` / `introduces` paper edge
    are flagged as orphan-from-papers (informational).

Regenerates index.md grouped by type, sorted by date desc within each group.

Exit code: 0 if no errors, 1 if any error-level issues found.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REQUIRED_BY_TYPE = {
    "paper": ("slug", "title", "source", "type", "ingested"),
    "video": ("slug", "title", "source", "type", "ingested"),
    "pdf": ("slug", "title", "source", "type", "ingested"),
    "concept": ("slug", "title", "type", "ingested"),
}
WIKI_LINK_RE = re.compile(r"\[\[([^\]|#]+?)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
# Markdown image embed: ![alt](path). Greedy on alt for ergonomics, conservative on path.
IMAGE_EMBED_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")

PAPER_LIKE_TYPES = {"paper", "video", "pdf"}


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
    """Return {slug: {path, frontmatter, body, expected_subdir}} for every .md under pages/.

    Recurses into subdirectories. Slugs are flat (filenames must be unique
    across the whole pages/ tree); the subdirectory is purely cosmetic but
    enforced to match the page's `type` (papers under papers/, concepts under
    concepts/).
    """
    result: dict[str, dict[str, object]] = {}
    for md in sorted(pages_dir.rglob("*.md")):
        text = md.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        body = text[FRONTMATTER_RE.match(text).end() :] if fm is not None else text
        result[md.stem] = {
            "path": md,
            "frontmatter": fm,
            "body": body,
            "subdir": md.parent.name,
        }
    return result


def expected_subdir_for_type(ptype: str) -> str:
    if ptype in PAPER_LIKE_TYPES:
        return "papers"
    if ptype == "concept":
        return "concepts"
    return ""  # unknown — don't enforce


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
    predicates = schema.get("predicates", {})
    graph = json.loads(graph_path.read_text())
    pages = collect_pages(pages_dir)
    sources_dir = wiki / "sources"
    source_docs = {p.stem for p in sources_dir.glob("*.md")} if sources_dir.is_dir() else set()

    errors: list[str] = []
    warnings: list[str] = []

    # Source docs share the [[wiki-link]] namespace with page slugs.
    for stem in sorted(source_docs & pages.keys()):
        errors.append(f"sources/{stem}.md collides with page slug {stem!r}")

    # Detect filename collisions across subdirs
    seen_paths: dict[str, list[Path]] = defaultdict(list)
    for slug, info in pages.items():
        seen_paths[slug].append(info["path"])
    for slug, paths in seen_paths.items():
        if len(paths) > 1:
            errors.append(
                f"slug {slug!r} collides across subdirs: {[str(p.relative_to(wiki)) for p in paths]}"
            )

    # 1. Per-page checks
    for slug, info in pages.items():
        fm = info["frontmatter"]
        if fm is None:
            errors.append(f"{slug}.md: missing or unparseable YAML frontmatter")
            continue
        ptype = str(fm.get("type", "")).strip()
        required_fields = REQUIRED_BY_TYPE.get(ptype)
        if required_fields is None:
            errors.append(
                f"{slug}.md: unknown type {ptype!r} (expected one of {sorted(REQUIRED_BY_TYPE)})"
            )
            continue
        for field in required_fields:
            if field not in fm or not fm[field]:
                errors.append(f"{slug}.md: frontmatter missing '{field}'")
        if fm.get("slug") and fm["slug"] != slug:
            errors.append(f"{slug}.md: frontmatter slug={fm['slug']!r} doesn't match filename")
        # Subdir matches type
        expected = expected_subdir_for_type(ptype)
        if expected and info["subdir"] != expected:
            errors.append(
                f"{slug}.md: type={ptype} but lives under pages/{info['subdir']}/, "
                f"expected pages/{expected}/"
            )
        # 2. Wiki-link resolution (pages and staged source docs both resolve)
        for m in WIKI_LINK_RE.finditer(info["body"]):
            target = m.group(1).strip()
            if target not in pages and target not in source_docs:
                errors.append(f"{slug}.md: broken [[wiki-link]] to '{target}'")
        # 2a. source_doc frontmatter: dangling is an error; absent on a
        # paper-like page is informational (bundle may be gone or underivable).
        source_doc = str(fm.get("source_doc", "")).strip()
        if source_doc and source_doc not in source_docs:
            errors.append(f"{slug}.md: source_doc '{source_doc}' has no file under sources/")
        if ptype in PAPER_LIKE_TYPES and not source_doc:
            warnings.append(f"page {slug!r} has no source_doc (no staged source text)")
        # 2b. Paper-like pages must not embed figures.
        # Figures belong on concept pages, where they teach a concept; paper
        # pages summarise and link out. (Embedding on a paper page also breaks
        # in Obsidian when the user opens a parent dir as the vault.)
        if ptype in PAPER_LIKE_TYPES:
            embeds = IMAGE_EMBED_RE.findall(info["body"])
            for embed in embeds:
                errors.append(
                    f"{slug}.md: image embed on paper page is not allowed — "
                    f"move the figure to a concept page that uses it ({embed})"
                )

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

    def page_type(slug: str) -> str | None:
        fm = pages.get(slug, {}).get("frontmatter") or {}
        return fm.get("type") if isinstance(fm, dict) else None

    for i, edge in enumerate(graph.get("edges", [])):
        f_slug = edge.get("from")
        t_slug = edge.get("to")
        for endpoint, slug in (("from", f_slug), ("to", t_slug)):
            if not slug:
                errors.append(f"graph.json: edge[{i}] missing '{endpoint}'")
            elif slug not in pages:
                errors.append(f"graph.json: edge[{i}] {endpoint}={slug!r} has no page")
        pred_name = edge.get("predicate")
        if not pred_name:
            errors.append(f"graph.json: edge[{i}] missing 'predicate'")
            continue
        pred = predicates.get(pred_name)
        if pred is None:
            errors.append(f"graph.json: edge[{i}] predicate {pred_name!r} not in _schema.json")
            continue
        # Type-constraint enforcement
        if isinstance(pred, dict):
            for endpoint, slug, key in (("from", f_slug, "from_type"), ("to", t_slug, "to_type")):
                expected_type = pred.get(key)
                if not expected_type or expected_type == "*" or not slug or slug not in pages:
                    continue
                actual_type = page_type(slug)
                # paper/video/pdf are interchangeable for predicates that say "paper"
                if expected_type == "paper" and actual_type in PAPER_LIKE_TYPES:
                    continue
                if actual_type != expected_type:
                    errors.append(
                        f"graph.json: edge[{i}] predicate {pred_name!r} expects "
                        f"{key}={expected_type}, but {endpoint}={slug!r} has type {actual_type!r}"
                    )

    # 4. Orphan checks (informational)
    incoming: dict[str, int] = defaultdict(int)
    paper_to_concept: dict[str, int] = defaultdict(int)  # concept -> count of paper edges
    for edge in graph.get("edges", []):
        if edge.get("to") in pages:
            incoming[edge["to"]] += 1
        if edge.get("predicate") in {"defines", "discusses", "introduces"}:
            t = edge.get("to")
            if t in pages and page_type(t) == "concept":
                paper_to_concept[t] += 1
    for slug, info in pages.items():
        fm = info["frontmatter"] or {}
        ptype = fm.get("type")
        if incoming[slug] == 0:
            warnings.append(f"page {slug!r} has no incoming edges (orphan-in)")
        if ptype == "concept" and paper_to_concept[slug] == 0:
            warnings.append(
                f"concept {slug!r} has no paper discussing/defining/introducing it"
            )

    # 5. Regenerate index.md (grouped by type, sorted by date desc within group)
    by_type: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for slug, info in pages.items():
        fm = info["frontmatter"] or {}
        ptype = str(fm.get("type", "unknown"))
        title = str(fm.get("title", slug))
        date = str(fm.get("date", fm.get("ingested", "")))
        by_type[ptype].append((date, slug, title))
    lines = ["# Wiki", "", f"_{len(pages)} pages, {len(graph.get('edges', []))} edges._", ""]
    # Stable order: papers/videos/pdfs first, then concepts, then anything else
    type_order = ["paper", "video", "pdf", "concept"]
    other = sorted(set(by_type) - set(type_order))
    for ptype in type_order + other:
        if ptype not in by_type:
            continue
        heading = ptype.capitalize() + ("s" if not ptype.endswith("s") else "")
        lines.append(f"## {heading}")
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
