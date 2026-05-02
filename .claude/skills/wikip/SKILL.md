---
name: wikip
description: Synthesise a paper, video booklet, or other source document into a corpus wiki, producing both a paper page (literature-review view of the source) and concept pages (synthesised explanations of the ideas the source introduces or uses). Pages are linked by typed predicates from a constrained vocabulary (paper→paper, paper→concept, concept→concept) forming a knowledge graph between pages. Reads the source bundle (arxiv-fetch's raw/, video-to-booklet's booklet.md, or pdf-extract's content.md), surveys the corpus wiki, writes/updates Obsidian-flavour pages, and updates graph.json. Use when the user asks to ingest a paper/video/document into the wiki, build a wiki from a corpus progressively, or merge two wikis.
---

# wikip

Turn one source document into one paper page **plus a set of concept pages** (created or updated) within a corpus wiki. Pages are concept-centric where it matters (each concept gets its own synthesised explanation drawn from all papers in the corpus) and document-centric for navigation (each paper gets a literature-review landing page). The graph between pages emerges from typed `[[wiki-link]]` relations.

## Inputs

- **source-dir** (required) — a document bundle. Detect type by file presence:
  - `raw/structure.json` present → arxiv-fetch output (read `raw/sections/*.tex` per `raw/structure.json`, plus `raw/arxiv_meta.json`).
  - `booklet.md` present → video-to-booklet output (read `booklet.md` plus `chapters.json` if present).
  - `content.md` + `metadata.json` present → pdf-extract output.
- **wiki-dir** (required) — corpus wiki directory, e.g. `wiki/`. Initialise first if missing.

## Workflow

1. **Initialise wiki/ if needed**: `uv run python3 .claude/skills/wikip/scripts/init.py "<wiki-dir>"`. Creates `pages/papers/`, `pages/concepts/`, `graph.json`, `_schema.json` (typed predicate vocabulary), `index.md` stub.
2. **Survey the corpus**: list `<wiki-dir>/pages/papers/` and `<wiki-dir>/pages/concepts/`, read `graph.json`, read `_schema.json`. You need this to (a) know which slugs are valid `[[wiki-link]]` targets, (b) which predicates are allowed (and their from_type/to_type), and (c) which concept pages already exist that you should *update* rather than recreate.
3. **Detect source type and read it**: load the source content per the rules above.
4. **Plan the paper page** (the literature-review view of *this document*):
   - **TL;DR** — 3–5 sentences.
   - **Why it matters** — one paragraph.
   - **Key claims & contributions** — bulleted, with source-section refs.
   - **Methodology / approach** — what the paper actually does.
   - **Results** — if applicable.
   - **Connections to other papers** — `[[other-paper]]` with predicate from schema.
   - **Concepts** — `[[concept-slug]]` links to concept pages this paper defines / introduces / discusses (you'll write or update those next).
   - **Open questions**.
5. **Plan the concept pages**. From the paper, identify the concepts that deserve their own page — typically 5–15 per paper, the central ideas readers would want to look up by name (e.g. "Knowledge Graph", "Property Graph", "Reification"). For each:
   - **If a concept page already exists** in `pages/concepts/<slug>.md`: read it, then *update* (not replace) — add this paper to the page's `papers:` frontmatter, integrate any new insight from this paper into the existing prose, add it as a citation. Don't duplicate; merge thoughtfully.
   - **If it doesn't exist**: create `pages/concepts/<slug>.md`. See [REFERENCE.md](REFERENCE.md) for the concept-page schema.
6. **Stage figures into the vault**. For arxiv-fetch sources, copy the rendered figures into `<wiki-dir>/assets/<paper-slug>/`. Bulk-copying the whole `_tikz/` and `figures/` folders is fine — **concept pages** embed via `../../assets/<paper-slug>/<file>.png`. Obsidian only renders images that live inside the vault, so this step is required, not optional. (Skip for sources without figures.)
7. **Write `pages/papers/<paper-slug>.md`** in Obsidian flavour. Slug = source-dir basename. See [REFERENCE.md](REFERENCE.md) for the paper-page schema. **Do not embed figures on the paper page** — figures belong on concept pages, where they teach a concept; the paper page summarises and links out (e.g. *"see [[chain-of-table]] for the comparison figure"*). validate.py errors on image embeds in paper-like pages.
8. **Update `graph.json`**:
   - Add a node for the paper page if not already present.
   - Add nodes for any new concept pages.
   - For each connection in the paper page's "Connections to other papers" section, add an edge with the chosen predicate (paper→paper).
   - For each concept the paper covers, add an edge `paper —[defines|discusses|introduces]→ concept` (paper→concept, predicate per schema).
   - For relations *between* concepts you can identify clearly from the paper (e.g. `property-graph —[alternative-to]→ directed-edge-labelled-graph`), add concept→concept edges. Don't force these; only add what's clearly stated.
   - Edges are keyed by `from`. Re-running on the same paper *replaces* its outgoing edges in `graph.json`, so re-ingesting after edits doesn't accumulate duplicates.
9. **Validate**: `uv run python3 .claude/skills/wikip/scripts/validate.py "<wiki-dir>"`. Reports broken `[[wiki-links]]`, edges referencing missing pages, predicate type-mismatches (e.g. using `cites` between two concepts), and orphan pages. Regenerates `index.md`. Fix all errors before finishing.
10. **Consider proposing a `README.md` refresh.** `init.py` scaffolds a placeholder `README.md` at the vault root — the curated landing page that frames the corpus thesis, names the anchor concept, and lists reading paths. *Update it only when this ingest meaningfully shifts the corpus's centre of gravity* (a new dominant theme, a new anchor concept, the vault's first paper, a paper the existing thesis can no longer cover). Don't touch it on routine ingests that just deepen an established thread — the README's value is being a stable, hand-curated synthesis, not a per-ingest log. When you do propose changes, surface them as a diff for the user to approve, not a silent overwrite.
11. **Report** to the user: paper page written, concept pages created vs updated, edges added, any orphans/warnings, and whether a README refresh was proposed.

## Output structure

```
<wiki-dir>/
  pages/
    papers/
      arxiv-2003.02320.md       paper / video / pdf landing page
      <video-id>.md
      ...
    concepts/
      knowledge-graph.md        concept page (synthesises across all papers)
      property-graph.md
      ...
  assets/
    arxiv-2003.02320/           one folder per source; figures embedded by concept pages live here
      fig-delg.png
      ...
  graph.json                    {nodes: [...], edges: [{from, to, predicate, context}]}
  _schema.json                  {predicates: {<name>: {from_type, to_type, description}, ...}}
  index.md                      auto-generated TOC, regenerated by validate.py
  README.md                     hand-curated landing page (thesis, reading paths) — scaffolded by init.py, never auto-regenerated
```

Figures live *inside* the vault (under `assets/<paper-slug>/`) so Obsidian can resolve them — Obsidian only renders images whose path stays within the vault. wikip copies figures from the source bundle into `assets/<paper-slug>/` during ingest; concept pages embed via `../../assets/<paper-slug>/<file>.png`.

Slugs are flat across the wiki — `[[knowledge-graph]]` resolves whether the file is under `papers/` or `concepts/`. Don't reuse a slug across types.

## Predicate vocabulary

The default `_schema.json` ships with 16 typed predicates: 9 paper→paper (`cites`, `extends`, `compares-with`, `criticizes`, `applies`, `surveys`, `motivates`, `disambiguates`, `same-topic`), 3 paper→concept (`defines`, `discusses`, `introduces`), and 4 concept→concept (`is-a`, `part-of`, `alternative-to`, `related-to`). See [REFERENCE.md](REFERENCE.md) for the precise meaning of each, with examples.

Predicates declare `from_type` and `to_type`. `validate.py` enforces these — using `cites` between two concepts is an error. Add or refine predicates by editing `_schema.json`.

## Merging two wikis

To combine corpora (e.g., a "KG papers" wiki and an "embedding papers" wiki):
```bash
uv run python3 .claude/skills/wikip/scripts/merge.py <source-wiki> --into <target-wiki>
```
Handles slug clashes via `--on-conflict={skip,replace,rename}`. Preserves the `papers/` vs `concepts/` subdir layout. Unions `graph.json`. Reconciles `_schema.json` — errors out if predicate definitions diverge so the user resolves explicitly.

## Auditing a wiki

To find under-developed concepts — ingest opportunities that the graph itself surfaces:
```bash
uv run python3 .claude/skills/wikip/scripts/audit.py <wiki-dir>
```
Prints four buckets: (A) concepts mentioned but never `defines`d — ingest the foundational paper; (B) orphan concepts with no incoming edges; (C) single-paper concepts a sibling paper would deepen; (D) weakly anchored concepts (only `related-to` from other concepts, no `is-a` / `part-of`). Run when the user asks to audit the wiki, find gaps, or decide what to ingest next; the bucket-A top entry is usually the highest-leverage next ingest. Bucket D over-flags root-of-tree concepts (e.g. the wiki's anchor concept naturally has no ancestors), so interpret with judgment rather than treating as error.

## Idempotency

- **Page rewriting**: if `pages/papers/<slug>.md` already exists, ask the user before overwriting. Concept pages are *always* updated rather than overwritten — read the existing page, integrate the new paper's contribution, write back.
- **Graph edges**: keyed by `from`. Re-running on the same paper replaces that paper's outgoing edges. Concept↔concept edges added by previous paper ingests are preserved; only the current paper's outgoing edges are touched.

## Notes

- A paper introducing a concept already in the wiki should **update** the concept page (add to its `papers:`, integrate new framing). A paper introducing a *new* concept should **create** a new concept page. Resist the urge to create a separate concept page per paper for the same concept.
- Concept pages are not meant to be exhaustive on first creation — they grow as more papers are ingested. The first paper sets a baseline definition; subsequent papers refine, extend, or contest it.
- This skill does NOT resolve bibliographies. The `.bib` / `.bbl` files in `<source-dir>/raw/` (arxiv-fetch) are available for a downstream skill to use.
- See [REFERENCE.md](REFERENCE.md) for both page schemas, predicate semantics with examples, merge details, and a concept-page synthesis worked example.
