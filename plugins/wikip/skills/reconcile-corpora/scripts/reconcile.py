#!/usr/bin/env python3
"""Cross-corpus reconciliation for a wikis/ directory.

Two modes:

  scan   Read all per-corpus graph.json files. Compute confirmed same-as bridges
         (exact slug matches). Write wikis/graph.json. Print a JSON inventory of
         all concepts (slug, title, corpus, top-3 outgoing-edge contexts) to
         stdout so the caller (Claude) can reason about candidate synonyms and
         thematic clusters.

  apply  Read wikis/graph.json (which Claude has augmented with candidate same-as?
         edges and thematic-cluster annotations) and regenerate wikis/CONNECTIONS.md.

Usage:
  uv run python3 "${CLAUDE_PLUGIN_ROOT}"/skills/reconcile-corpora/scripts/reconcile.py scan  <wikis-dir>
  uv run python3 "${CLAUDE_PLUGIN_ROOT}"/skills/reconcile-corpora/scripts/reconcile.py apply <wikis-dir>
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

KNOWN_CORPUS_MARKER = "graph.json"  # any subdir with this file is a corpus


def find_corpora(wikis_dir: Path) -> list[str]:
    return sorted(
        d.name
        for d in wikis_dir.iterdir()
        if d.is_dir() and (d / KNOWN_CORPUS_MARKER).exists() and not d.name.startswith(".")
    )


def load_corpus(wikis_dir: Path, name: str) -> dict:
    g = json.loads((wikis_dir / name / KNOWN_CORPUS_MARKER).read_text())
    return {
        "name": name,
        "nodes": {n["slug"]: n for n in g["nodes"]},
        "edges": g["edges"],
    }


def top_outgoing(corpus: dict, slug: str, n: int = 3) -> list[str]:
    edges = [e for e in corpus["edges"] if e["from"] == slug]
    return [f"{e['to']} ({e['predicate']}): {e.get('context', '')[:100]}" for e in edges[:n]]


# ---------------------------------------------------------------------------
# Pass 1 — confirmed bridges (exact slug match)
# ---------------------------------------------------------------------------

def confirmed_bridges(corpora: list[dict]) -> dict[str, list[str]]:
    """slug -> list of corpus names where it appears as a concept."""
    concept_to_corpora: dict[str, list[str]] = defaultdict(list)
    for c in corpora:
        for slug, node in c["nodes"].items():
            if node.get("type") == "concept":
                concept_to_corpora[slug].append(c["name"])
    return {k: v for k, v in concept_to_corpora.items() if len(v) > 1}


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------

def cmd_scan(wikis_dir: Path) -> int:
    corpora = [load_corpus(wikis_dir, n) for n in find_corpora(wikis_dir)]
    if not corpora:
        print("error: no corpora found", file=sys.stderr)
        return 1

    bridges = confirmed_bridges(corpora)

    # Build root graph.json — namespaced nodes + same-as edges
    nodes: list[dict] = []
    edges: list[dict] = []
    seen: set[str] = set()

    for slug, corps in bridges.items():
        for c_name in corps:
            ns = f"{c_name}/{slug}"
            if ns not in seen:
                node = next(c for c in corpora if c["name"] == c_name)["nodes"][slug]
                nodes.append({
                    "slug": ns,
                    "corpus": c_name,
                    "local_slug": slug,
                    "title": node.get("title", slug),
                    "type": "concept",
                })
                seen.add(ns)
        for i, c1 in enumerate(corps):
            for c2 in corps[i + 1 :]:
                edges.append({"from": f"{c1}/{slug}", "to": f"{c2}/{slug}", "predicate": "same-as"})

    root_graph_path = wikis_dir / "graph.json"

    # Preserve any existing candidate / thematic edges Claude added previously
    existing_extra: list[dict] = []
    existing_extra_nodes: list[dict] = []
    if root_graph_path.exists():
        existing = json.loads(root_graph_path.read_text())
        existing_extra = [
            e for e in existing.get("edges", [])
            if e.get("predicate") not in ("same-as",)
        ]
        confirmed_ns = {n["slug"] for n in nodes}
        existing_extra_nodes = [
            n for n in existing.get("nodes", [])
            if n["slug"] not in confirmed_ns
        ]

    root_graph_path.write_text(
        json.dumps(
            {"nodes": nodes + existing_extra_nodes, "edges": edges + existing_extra},
            indent=2,
        )
    )

    # Print concept inventory to stdout for Claude's synonym / thematic analysis
    inventory: list[dict] = []
    for c in corpora:
        for slug, node in c["nodes"].items():
            if node.get("type") == "concept":
                inventory.append({
                    "corpus": c["name"],
                    "slug": slug,
                    "title": node.get("title", slug),
                    "top_edges": top_outgoing(c, slug),
                })

    print(json.dumps({"confirmed_bridges": bridges, "inventory": inventory}, indent=2))
    return 0


# ---------------------------------------------------------------------------
# CONNECTIONS.md generation
# ---------------------------------------------------------------------------

CORPUS_ORDER = ["ai-strategy", "ai-semantic-layer", "semantic-operators", "agentic-analytics"]


def _corpus_link(name: str) -> str:
    return f"[{name}]({name}/README.md)"


def generate_connections(wikis_dir: Path, corpora: list[dict], root_graph: dict) -> str:
    today = date.today().isoformat()
    lines: list[str] = []
    lines += [
        f"> Generated {today} from `graph.json`. Re-run `/reconcile-corpora` to refresh.",
        "",
        "# Cross-Corpus Connections",
        "",
        "Concepts shared across corpora, and reading paths that traverse the full stack.",
        "",
        "---",
        "",
    ]

    # --- Bridge Concepts ---
    lines += ["## Bridge Concepts", ""]
    lines += ["These concepts are developed in multiple corpora — each corpus adds a different lens.", ""]

    # Group confirmed same-as edges by local_slug
    ns_to_node = {n["slug"]: n for n in root_graph["nodes"]}
    confirmed_slugs: dict[str, list[str]] = defaultdict(list)  # local_slug -> [corpus]
    for e in root_graph["edges"]:
        if e["predicate"] == "same-as":
            from_node = ns_to_node.get(e["from"], {})
            slug = from_node.get("local_slug", "")
            corpus = from_node.get("corpus", "")
            if slug and corpus not in confirmed_slugs[slug]:
                confirmed_slugs[slug].append(corpus)
            to_node = ns_to_node.get(e["to"], {})
            to_corpus = to_node.get("corpus", "")
            if to_corpus and to_corpus not in confirmed_slugs[slug]:
                confirmed_slugs[slug].append(to_corpus)

    corpus_map = {c["name"]: c for c in corpora}

    for local_slug, corps in sorted(confirmed_slugs.items(), key=lambda x: -len(x[1])):
        sample_corpus = next((c for c in CORPUS_ORDER if c in corps), corps[0])
        node = corpus_map[sample_corpus]["nodes"].get(local_slug, {})
        title = node.get("title", local_slug)
        lines += [f"### {title}", ""]
        for c_name in [c for c in CORPUS_ORDER if c in corps]:
            c = corpus_map[c_name]
            out = top_outgoing(c, local_slug, 2)
            edge_hint = f" Connects to: {', '.join(e.split('(')[0].strip() for e in out)}." if out else ""
            lines += [f"**{_corpus_link(c_name)}** —{edge_hint}", ""]

    # --- Candidate Synonyms ---
    candidates = [e for e in root_graph["edges"] if e.get("predicate") == "same-as?"]
    if candidates:
        lines += ["---", "", "## Candidate Synonyms", ""]
        lines += ["Concepts with different slugs likely describing the same idea — pending manual confirmation.", ""]
        for e in candidates:
            from_n = ns_to_node.get(e["from"], {})
            to_n = ns_to_node.get(e["to"], {})
            note = e.get("context", "")
            lines += [
                f"- **{from_n.get('title', e['from'])}** ({from_n.get('corpus', '?')}) ↔ "
                f"**{to_n.get('title', e['to'])}** ({to_n.get('corpus', '?')})"
                + (f"  — {note}" if note else ""),
            ]
        lines.append("")

    # --- Thematic Coverage Map ---
    thematic = [n for n in root_graph["nodes"] if n.get("type") == "theme"]
    if thematic:
        lines += ["---", "", "## Thematic Coverage Map", ""]
        ordered_corpora = [c for c in CORPUS_ORDER if c in {cc["name"] for cc in corpora}]
        header = "| Theme | " + " | ".join(ordered_corpora) + " |"
        sep = "|---|" + "|".join(["---"] * len(ordered_corpora)) + "|"
        lines += [header, sep]
        for theme_node in sorted(thematic, key=lambda n: n["slug"]):
            theme_corpora = set(
                ns_to_node.get(e["to"], {}).get("corpus", "")
                for e in root_graph["edges"]
                if e["from"] == theme_node["slug"] and e.get("predicate") == "covers"
            )
            cells = ["●" if c in theme_corpora else "○" for c in ordered_corpora]
            lines.append(f"| {theme_node['title']} | " + " | ".join(cells) + " |")
        lines.append("")

    # --- Reading Paths (preserved verbatim from existing file if present) ---
    existing_path = wikis_dir / "CONNECTIONS.md"
    if existing_path.exists():
        existing = existing_path.read_text()
        marker = "## Cross-Corpus Reading Paths"
        if marker in existing:
            reading_paths_section = existing[existing.index(marker):]
            lines += ["---", "", reading_paths_section]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

def cmd_apply(wikis_dir: Path) -> int:
    root_graph_path = wikis_dir / "graph.json"
    if not root_graph_path.exists():
        print("error: wikis/graph.json not found — run scan first", file=sys.stderr)
        return 1

    root_graph = json.loads(root_graph_path.read_text())
    corpora = [load_corpus(wikis_dir, n) for n in find_corpora(wikis_dir)]

    content = generate_connections(wikis_dir, corpora, root_graph)
    (wikis_dir / "CONNECTIONS.md").write_text(content)
    print(f"Written {wikis_dir}/CONNECTIONS.md")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["scan", "apply"])
    ap.add_argument("wikis_dir", type=Path)
    args = ap.parse_args()

    if args.mode == "scan":
        return cmd_scan(args.wikis_dir)
    return cmd_apply(args.wikis_dir)


if __name__ == "__main__":
    sys.exit(main())
