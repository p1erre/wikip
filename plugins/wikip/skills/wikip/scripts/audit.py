#!/usr/bin/env python3
"""Audit a wikip wiki for under-developed concepts.

Reads graph.json and prints four buckets of concepts that look like
ingest opportunities, ordered roughly from highest-leverage to lowest:

  A. Mentioned but never DEFINED.
     A paper has discussed the concept but no paper anchors a definition.
     Ingesting the foundational paper for the concept fills this gap.

  B. Orphan concepts (no incoming edges at all).
     Likely stale — a concept page exists but nothing points to it.

  C. Single-paper concepts (defined by exactly one paper).
     Natural candidates to deepen by ingesting a sibling paper that
     extends, criticises, or applies the concept.

  D. Weakly anchored (only `related-to` edges from other concepts).
     The concept floats — no `is-a`, `part-of`, or `alternative-to`
     edge places it in the structural taxonomy.

Usage: uv run python3 "${CLAUDE_PLUGIN_ROOT}"/skills/wikip/scripts/audit.py <wiki-dir>
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def load_graph(wiki_dir: Path) -> dict:
    return json.loads((wiki_dir / "graph.json").read_text())


def audit(graph: dict) -> list[dict]:
    concepts = [n for n in graph["nodes"] if n["type"] == "concept"]
    papers = {n["slug"] for n in graph["nodes"] if n["type"] in ("paper", "video", "pdf")}

    in_edges: dict[str, list[dict]] = defaultdict(list)
    for e in graph["edges"]:
        in_edges[e["to"]].append(e)

    rows = []
    for c in concepts:
        ins = in_edges[c["slug"]]
        from_papers = [e for e in ins if e["from"] in papers]
        from_concepts = [e for e in ins if e["from"] not in papers]
        defining = [e["from"] for e in from_papers if e["predicate"] in ("defines", "introduces")]
        discussing = [e["from"] for e in from_papers if e["predicate"] == "discusses"]
        anchors = [e for e in from_concepts if e["predicate"] in ("is-a", "part-of", "alternative-to")]
        related = [e for e in from_concepts if e["predicate"] == "related-to"]
        rows.append({
            "slug": c["slug"],
            "title": c["title"],
            "papers_count": len({e["from"] for e in from_papers}),
            "defined_by": defining,
            "discussed_by": discussing,
            "anchor_count": len(anchors),
            "related_only_count": len(related),
            "total_in": len(ins),
        })
    return rows


def report(rows: list[dict]) -> None:
    bucket_a = sorted(
        (r for r in rows if not r["defined_by"] and r["total_in"] > 0),
        key=lambda r: -r["total_in"],
    )
    bucket_b = sorted((r for r in rows if r["total_in"] == 0), key=lambda r: r["slug"])
    bucket_c = sorted(
        (r for r in rows if r["papers_count"] == 1 and r["defined_by"]),
        key=lambda r: r["slug"],
    )
    bucket_d = sorted(
        (r for r in rows if r["anchor_count"] == 0 and r["related_only_count"] > 0 and r["defined_by"]),
        key=lambda r: -r["related_only_count"],
    )

    def header(title: str) -> None:
        print(f"\n=== {title} ===\n")

    header("A. Mentioned but never DEFINED — ingest the foundational paper")
    if not bucket_a:
        print("  (none)")
    for r in bucket_a:
        print(f"  {r['slug']:38} {len(r['discussed_by']):>2} discusser(s), {r['related_only_count']:>2} related-to-from-concepts")

    header("B. Orphan concepts — no incoming edges (stale?)")
    if not bucket_b:
        print("  (none)")
    for r in bucket_b:
        print(f"  {r['slug']}")

    header("C. Single-paper concepts — sibling paper would deepen them")
    if not bucket_c:
        print("  (none)")
    for r in bucket_c:
        print(f"  {r['slug']:38} defined by {', '.join(r['defined_by'])}")

    header("D. Weakly anchored — only related-to edges, no is-a / part-of")
    if not bucket_d:
        print("  (none)")
    for r in bucket_d:
        print(f"  {r['slug']:38} related-to×{r['related_only_count']}")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description="Find under-developed concepts in a wikip wiki.")
    ap.add_argument("wiki_dir", type=Path, help="path to the wiki, e.g. wikis/semantic-operators")
    args = ap.parse_args()
    if not (args.wiki_dir / "graph.json").exists():
        print(f"error: {args.wiki_dir}/graph.json not found", file=sys.stderr)
        return 1
    rows = audit(load_graph(args.wiki_dir))
    report(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
