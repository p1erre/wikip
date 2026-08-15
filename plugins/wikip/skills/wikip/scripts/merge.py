"""Merge a source wikip wiki into a target wikip wiki.

Usage:
  uv run python3 .../merge.py <source-wiki> --into <target-wiki> \
      [--on-conflict={skip|replace|rename}]

Behaviour:
  - Pages: copy from source/pages/<subdir>/ into target/pages/<subdir>/, preserving
    the subdirectory layout (papers/ vs concepts/).
      skip:    keep target's page on slug clash; ignore source's.
      replace: source's page overwrites target's.
      rename:  source's page is added with a "-2" suffix; edges referencing
               the old slug in the source graph are rewritten to the new slug.
  - graph.json: union of nodes and edges. Edges deduplicated by (from, to, predicate).
  - _schema.json: union of predicates. Errors out if a predicate name appears
                  in both with different definitions — resolve manually.
  - index.md: not regenerated here. Run validate.py afterwards.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


def load(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"missing {path}")
    return json.loads(path.read_text())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", type=Path, help="source wiki dir")
    ap.add_argument("--into", dest="target", type=Path, required=True, help="target wiki dir")
    ap.add_argument(
        "--on-conflict",
        choices=("skip", "replace", "rename"),
        default="skip",
        help="how to handle slug clashes (default: skip)",
    )
    args = ap.parse_args()

    src: Path = args.source
    tgt: Path = args.target
    if not (src / "pages").exists() or not (tgt / "pages").exists():
        sys.exit("both source and target must already be initialised wikis (pages/ dir present)")

    # 1. Reconcile schemas (predicates may be either str descriptions or dicts)
    src_schema = load(src / "_schema.json").get("predicates", {})
    tgt_schema = load(tgt / "_schema.json").get("predicates", {})
    merged_predicates = dict(tgt_schema)
    for name, defn in src_schema.items():
        if name in merged_predicates and merged_predicates[name] != defn:
            sys.exit(
                f"predicate {name!r} differs between wikis:\n"
                f"  target: {json.dumps(merged_predicates[name])}\n"
                f"  source: {json.dumps(defn)}\n"
                f"resolve manually in _schema.json before merging"
            )
        merged_predicates[name] = defn

    # 2. Resolve page conflicts (recurse into subdirs, slugs are flat)
    rewrites: dict[str, str] = {}
    src_pages = sorted((src / "pages").rglob("*.md"))
    tgt_slugs = {p.stem for p in (tgt / "pages").rglob("*.md")}
    page_actions: list[tuple[Path, str, str]] = []  # (src_path, action, dest_slug)
    for sp in src_pages:
        slug = sp.stem
        if slug not in tgt_slugs:
            page_actions.append((sp, "copy", slug))
            continue
        if args.on_conflict == "skip":
            page_actions.append((sp, "skip", slug))
        elif args.on_conflict == "replace":
            page_actions.append((sp, "replace", slug))
        elif args.on_conflict == "rename":
            new_slug = f"{slug}-2"
            n = 2
            while new_slug in tgt_slugs or any(a[2] == new_slug for a in page_actions):
                n += 1
                new_slug = f"{slug}-{n}"
            rewrites[slug] = new_slug
            page_actions.append((sp, "rename", new_slug))

    # 3. Apply page actions, preserving subdir structure
    for sp, action, dest_slug in page_actions:
        rel_subdir = sp.relative_to(src / "pages").parent
        dest_dir = tgt / "pages" / rel_subdir
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{dest_slug}.md"
        if action == "skip":
            print(f"  skip: {sp.relative_to(src)} (target has it)")
        elif action == "copy":
            shutil.copy2(sp, dest)
            print(f"  copy: {sp.relative_to(src)}")
        elif action == "replace":
            shutil.copy2(sp, dest)
            print(f"  replace: {sp.relative_to(src)}")
        elif action == "rename":
            text = sp.read_text(encoding="utf-8")
            # Rewrite the slug field in frontmatter
            text = text.replace(f"slug: {sp.stem}", f"slug: {dest_slug}", 1)
            dest.write_text(text)
            print(f"  rename: {sp.relative_to(src)} -> {dest.relative_to(tgt)}")

    # 4. Merge graphs
    src_graph = load(src / "graph.json")
    tgt_graph = load(tgt / "graph.json")
    merged_nodes = {n["slug"]: n for n in tgt_graph.get("nodes", []) if n.get("slug")}
    skipped_slugs = {a[2] for a in page_actions if a[1] == "skip"}
    for n in src_graph.get("nodes", []):
        slug = n.get("slug")
        if not slug:
            continue
        new_slug = rewrites.get(slug, slug)
        if new_slug in skipped_slugs:
            continue
        merged_nodes[new_slug] = {**n, "slug": new_slug}

    edge_keys: set[tuple[str, str, str]] = set()
    merged_edges = []
    for e in tgt_graph.get("edges", []):
        key = (e.get("from", ""), e.get("to", ""), e.get("predicate", ""))
        if key not in edge_keys:
            edge_keys.add(key)
            merged_edges.append(e)
    for e in src_graph.get("edges", []):
        f = rewrites.get(e.get("from", ""), e.get("from", ""))
        t = rewrites.get(e.get("to", ""), e.get("to", ""))
        if f in skipped_slugs or t in skipped_slugs:
            continue
        new_edge = {**e, "from": f, "to": t}
        key = (f, t, e.get("predicate", ""))
        if key not in edge_keys:
            edge_keys.add(key)
            merged_edges.append(new_edge)

    # 5. Write back
    (tgt / "_schema.json").write_text(json.dumps({"predicates": merged_predicates}, indent=2) + "\n")
    (tgt / "graph.json").write_text(
        json.dumps(
            {"nodes": list(merged_nodes.values()), "edges": merged_edges},
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )

    print(
        f"merged: {len(page_actions)} page actions, "
        f"{len(merged_nodes)} nodes, {len(merged_edges)} edges, "
        f"{len(merged_predicates)} predicates"
    )
    print("run validate.py to regenerate index.md and check for issues")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
