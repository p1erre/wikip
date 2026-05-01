# wikip — Reference

## Page schema

Every page in `<wiki-dir>/pages/<slug>.md` has YAML frontmatter and a structured body.

### Frontmatter

```yaml
---
slug: arxiv-2003.02320           # filename stem; must match the file
title: "Knowledge Graphs"        # human title (paper title, video title, etc.)
source: arxiv-2003.02320         # source-dir basename
type: paper                      # paper | video | pdf | note
date: 2020-03                    # YYYY or YYYY-MM (best estimate)
authors: [Hogan, Blomqvist, ...] # for papers/videos with named authors
tags: [survey, tutorial]         # free-text tags
concepts: [knowledge-graph, RDF, SPARQL, ontology, embedding]   # central concepts
ingested: 2026-05-01             # date this page was written
---
```

`slug`, `title`, `source`, `type`, `ingested` are required. The rest are optional but encouraged.

### Body

Use these section headings, in this order, omitting any that don't apply:

```markdown
## TL;DR
3-5 sentences. What is this document, in plain language.

## Why it matters
One paragraph. The motivation, the gap it fills, who should care.

## Key claims & contributions
- Claim or contribution 1 (with source ref if useful — e.g., §3.2).
- Claim or contribution 2.

## Methodology / approach
How the document does what it does. Be concrete: data, model, formal framework.

## Results
What was demonstrated, with numbers if the source has them.

## Connections
- `extends` [[other-paper-slug]] — one-line context: "builds on X's GNN encoder".
- `compares-with` [[third-paper-slug]] — "argues against the closed-world assumption used there".
- ...

## Open questions
What the document leaves unanswered or what reviewers typically push back on.
```

The **Connections** section mirrors the edges that go into `graph.json`. Use predicates exactly as defined in `_schema.json`.

## Predicate vocabulary

The default `_schema.json` ships with ten predicates. Use them as follows:

| Predicate | Use when this page's document… | Example |
|---|---|---|
| `cites` | …explicitly references the other paper, with no stronger relation | "[Smith21] is cited as background reading" |
| `extends` | …builds directly on the other paper's method, advancing or generalising it | "Our GNN extends the propagation rule of [Kipf17]" |
| `compares-with` | …compares its approach against the other paper, side-by-side | "We benchmark against [Wang19] on FB15k" |
| `criticizes` | …refutes, challenges, or substantively disagrees with the other paper | "Contra [Pearl09], we show that…" |
| `formalizes` | …provides a formal definition for ideas the other paper introduces informally | "We formalise the notion of context proposed by [McCarthy93]" |
| `applies` | …applies methods from the other paper to a new problem or domain | "We apply [Bordes13]'s TransE to biomedical KGs" |
| `surveys` | …includes the other paper in its survey/review (use for survey papers) | A survey listing dozens of cited works |
| `motivates` | …provides motivation/background that *the other paper* needs | "[Schneider72] motivates the term knowledge graph" |
| `disambiguates` | …clarifies or distinguishes terms ambiguously used in the other paper | "We disambiguate [EhrlingerW16]'s definition" |
| `same-topic` | …addresses the same topic without any direct relation above | Two papers on KGs that don't cite each other |

### Choosing a predicate

Pick the **strongest applicable** predicate. If both `cites` and `extends` apply, use `extends`. If both `same-topic` and `compares-with` apply, use `compares-with`. Use `cites` only when no stronger predicate fits.

`surveys` is the only one-to-many predicate by convention — a survey paper will have many `surveys` edges.

### Adding predicates

Edit `_schema.json` directly. New predicates should describe relations between *whole documents* (which is the page granularity), not between concepts within a document. If you find yourself wanting "Page A `defines` concept X" — use the `concepts:` frontmatter on Page A instead.

When `merge.py` reconciles two `_schema.json` files, it errors if a predicate is defined differently in each — resolve manually.

## graph.json schema

```json
{
  "nodes": [
    {"slug": "arxiv-2003.02320", "title": "Knowledge Graphs", "type": "paper"}
  ],
  "edges": [
    {
      "from": "arxiv-2003.02320",
      "to": "arxiv-1503.00759",
      "predicate": "cites",
      "context": "Cited as foundational work on KG embeddings."
    }
  ]
}
```

Edges are keyed by `from`. `validate.py` enforces that:
- Every `from` and `to` is a slug for which `pages/<slug>.md` exists.
- Every `predicate` appears in `_schema.json`.
- Every `from` slug also appears in `nodes`.

When re-running wikip on a source that already has edges, **replace** all edges with that `from` slug rather than appending — this keeps the graph consistent with the page body when the page is rewritten.

## Source-type readers

When implementing the read step in workflow point 3:

| Source type | What to read | Notes |
|---|---|---|
| arxiv-fetch | `raw/structure.json` for section list, then walk `raw/sections/*.tex` in order. Read `raw/preamble.tex` once for macro context. Pull metadata from `raw/arxiv_meta.json` (title, authors, abstract, primary_class). | TikZ figures will be visible as raw LaTeX — ignore. Custom macros from preamble.tex give context but don't need rendering. |
| video-to-booklet | `booklet.md` is the prose. `<source-dir>/output/<title>/booklet.md` is the canonical path. Pull title from the booklet H1 and authors from the video metadata if available. | Booklets are already markdown — just synthesise; don't re-render. |
| pdf-extract | `content.md` for prose, `metadata.json` for header info. | If `pdf_profile.json` has `unreliable: true`, flag it in the Open questions section. |

## Merging two wikis

`merge.py source-wiki --into target-wiki [--on-conflict=skip|replace|rename]`:

- **Pages**: if a slug exists in both wikis:
  - `skip`: keep target's page, ignore source's.
  - `replace`: source's page overwrites target's.
  - `rename`: source's page is added with a `-2` suffix on the slug; edges from the source wiki are rewritten to the new slug.
- **graph.json**: union of edges, deduplicated by `(from, to, predicate)` triple.
- **_schema.json**: union of predicates. If a predicate name appears in both with different descriptions, errors out — resolve manually.
- **index.md**: regenerated post-merge.

## Worked example

Given a corpus wiki with one page (`arxiv-2003.02320` — Hogan et al. KG survey), ingest a second paper `arxiv-1503.00759` (Nickel et al., "A Review of Relational Machine Learning"):

1. Survey existing wiki: pages = `[arxiv-2003.02320]`, predicates = default ten.
2. Read `documents/arxiv-1503.00759/raw/sections/*.tex`.
3. Plan: TL;DR (relational ML for KGs), key claims (tensor factorisation models, statistical relational learning), methodology (decomposes RESCAL/TransE/etc.).
4. Connections: this paper precedes the Hogan survey; the Hogan survey `cites` and `surveys` it. Since this is the *new* paper and we're writing *its* page, the edge goes the other way: `arxiv-1503.00759` `motivates` `arxiv-2003.02320`? No — that's not quite right. `motivates` would mean this paper motivates the other. Closer: this paper has no edges *to* the Hogan survey because it predates it. The Hogan survey's edges *to* this paper would be `cites`/`surveys` — but those edges already exist in the Hogan page. So this new page might have zero outgoing edges, which is fine.
5. Write `pages/arxiv-1503.00759.md`.
6. Append node to `graph.json`.
7. Validate. The new page is "orphan-out" (no outgoing edges) but not "orphan-in" (the Hogan survey points to it via `surveys`). validate.py flags orphans-in only — orphan-out is normal for foundational/older papers in a corpus.
