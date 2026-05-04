# wikip — Reference

Two kinds of pages live in a wikip wiki: **paper pages** (literature-review view of one source document) and **concept pages** (synthesised explanation of one idea, drawn from many papers in the corpus). They share a slug namespace and link to each other with typed predicates.

## Paper-page schema

`pages/papers/<slug>.md` where `<slug>` is the source-dir basename (e.g. `arxiv-2003.02320`).

### Frontmatter

```yaml
---
slug: arxiv-2003.02320           # filename stem; must match the file
title: "Knowledge Graphs (Hogan et al., 2020)"
source: arxiv-2003.02320         # source-dir basename
type: paper                      # paper | video | pdf
date: 2020-03                    # YYYY or YYYY-MM (best estimate)
authors: [Hogan, Blomqvist, ...] # for papers/videos with named authors
tags: [survey, tutorial]         # free-text tags
ingested: 2026-05-01             # date this page was written
---
```

`slug`, `title`, `source`, `type`, `ingested` are required.

### Body

**No figures.** Paper pages must not contain markdown image embeds (`![alt](path)`). Figures belong on concept pages, where they teach a concept; the paper page's job is to summarise. Reference the relevant concept page instead — *"see [[chain-of-table]] for the comparison figure"*. validate.py enforces this.

Use these section headings, in this order, omitting any that don't apply:

```markdown
## TL;DR
3-5 sentences. What is this document, in plain language.

## Why it matters
One paragraph. The motivation, the gap it fills, who should care.

## Key claims & contributions
- Claim 1 (with source ref if useful — e.g., §3.2).
- Claim 2.

## Methodology / approach
How the document does what it does. Be concrete: data, model, formal framework.

## Results
What was demonstrated, with numbers if the source has them.

## Concepts
The central concepts this paper defines, introduces, or discusses, each
linking to its concept page:
- [[knowledge-graph]] — defines (the paper's anchor concept)
- [[property-graph]] — discusses
- [[reification]] — introduces three reification styles for KGs
- ...

## Connections
Edges to other paper pages (mirroring graph.json):
- `extends` [[other-paper-slug]] — one-line context.
- `compares-with` [[third-paper-slug]] — "..."

## Open questions
What the document leaves unanswered or what reviewers typically push back on.
```

## Concept-page schema

`pages/concepts/<slug>.md` where `<slug>` is a kebab-case concept name (e.g. `knowledge-graph`, `property-graph`, `reification`).

### Frontmatter

```yaml
---
slug: knowledge-graph
title: "Knowledge Graph"
type: concept
aliases: [KG, knowledge graph]    # free-text variants used in literature
parent: null                       # broader concept slug, or null for top-level
papers: [arxiv-2003.02320, ...]    # papers that discuss/define/introduce this concept
ingested: 2026-05-01               # date this page was first created
updated: 2026-05-01                # date last modified by an ingest
---
```

`slug`, `title`, `type`, `ingested` are required. `papers` should be kept in sync with the `defines`/`discusses`/`introduces` edges in graph.json.

### Body

Concept pages have flexible structure — write what the concept needs. A reasonable default:

```markdown
## Definition
The canonical definition (or competing definitions if the concept is contested).
Cite the paper that gave each definition: "[[arxiv-2003.02320]] defines a knowledge
graph as 'a graph of data intended to accumulate and convey knowledge of the real
world…'".

## Variants / sub-concepts
Different forms or specialisations:
- [[directed-edge-labelled-graph]] — minimal model used by RDF
- [[property-graph]] — richer model used by Neo4j
- ...

## Distinguishing features
What separates this concept from related ones. What would make a reader say
"this is a KG" vs "this is just a graph database"?

## Relations
- `is-a` [[graph-data-model]]    — concept→concept edges, mirroring graph.json
- `alternative-to` [[ontology]]
- ...

## Examples
Concrete instances drawn from the source papers (Wikidata, DBpedia, Google KG, …).

## Open questions
Aspects the literature hasn't settled, or where definitions diverge.

## Discussed in
- [[arxiv-2003.02320]] — defines and surveys (foundational tutorial).
- [[arxiv-XXXX.XXXXX]] — uses without redefining.
- ...
```

The "Discussed in" section mirrors the paper→concept edges in graph.json. The "Relations" section mirrors the concept→concept edges.

### Updating an existing concept page

When ingesting a paper that touches a concept already in the wiki:

1. **Read** the existing concept page.
2. **Decide** what the new paper adds:
   - A new framing or alternative definition? → add to "Definition" with citation.
   - A new variant or sub-concept? → add to "Variants" with citation.
   - A concrete example? → add to "Examples".
   - A new relation to another concept? → add to "Relations" + add edge to graph.json.
   - Just another usage of an already-discussed concept? → just add to "Discussed in" + paper→concept edge.
3. **Update** frontmatter: append the new paper to `papers:`, set `updated:` to today.
4. **Resist duplication**: don't restate things already on the page; integrate.
5. **Resist deletion**: don't remove existing content unless the new paper *contradicts* it; in that case, keep both with attribution ("[@A] argues X, while [@B] argues the opposite, citing…").

## Predicate vocabulary

The default `_schema.json` ships with 16 typed predicates. Each declares `from_type` and `to_type`. validate.py enforces these.

### Paper → Paper (literature relations, 9)

| Predicate | Use when this paper… | Example |
|---|---|---|
| `cites` | …explicitly references the other paper, with no stronger relation | "[Smith21] is cited as background reading" |
| `extends` | …builds directly on the other paper's method, advancing or generalising it | "Our GNN extends the propagation rule of [Kipf17]" |
| `compares-with` | …compares its approach against the other paper, side-by-side | "We benchmark against [Wang19] on FB15k" |
| `criticizes` | …refutes, challenges, or substantively disagrees with the other paper | "Contra [Pearl09], we show that…" |
| `applies` | …applies methods from the other paper to a new problem or domain | "We apply [Bordes13]'s TransE to biomedical KGs" |
| `surveys` | …includes the other paper in its survey/review | A survey listing dozens of cited works |
| `motivates` | …provides motivation/background that *the other paper* needs | "[Schneider72] motivates the term knowledge graph" |
| `disambiguates` | …clarifies or distinguishes terms ambiguously used in the other paper | "We disambiguate [EhrlingerW16]'s definition" |
| `same-topic` | …addresses the same topic without any direct relation above | Two papers on KGs that don't cite each other |

### Paper → Concept (where the concept lives in the literature, 3)

| Predicate | Use when this paper… | Example |
|---|---|---|
| `defines` | …gives a definition (formal or informal) for the concept | "[Hogan20] defines [[knowledge-graph]] as…" |
| `discusses` | …uses or applies the concept without claiming to define it | "[Bordes13] uses [[knowledge-graph-embedding]] without redefining the term" |
| `introduces` | …is the historical origin or canonical introduction of the concept | "[Schneider72] introduces [[knowledge-graph]]" |

A paper can have multiple paper→concept edges to the same concept only if they're different predicates (e.g. `defines` AND `surveys` use of). Usually one is enough.

### Concept → Concept (taxonomy / structure of ideas, 4)

| Predicate | Use when this concept… | Example |
|---|---|---|
| `is-a` | …is a kind of, or instance of, the target concept (subclass, specialisation) | `property-graph is-a graph-data-model` |
| `part-of` | …is a structural component of the target concept | `iri part-of rdf` |
| `alternative-to` | …is a competing or alternative formulation of the same idea | `property-graph alternative-to directed-edge-labelled-graph` |
| `related-to` | …is related to the target without any stronger relation above | `ontology related-to knowledge-graph` |

### Choosing a predicate

Pick the **strongest applicable** predicate. If both `cites` and `extends` apply, use `extends`. If both `is-a` and `related-to` apply, use `is-a`. Use `cites` / `related-to` only when no stronger predicate fits.

### Adding predicates

Edit `_schema.json` directly. Each entry must declare `from_type` and `to_type` (use `"*"` to allow any). When `merge.py` reconciles two `_schema.json` files, it errors if a predicate is defined differently in each — resolve manually.

## graph.json schema

```json
{
  "nodes": [
    {"slug": "arxiv-2003.02320", "title": "Knowledge Graphs", "type": "paper"},
    {"slug": "knowledge-graph",  "title": "Knowledge Graph",  "type": "concept"}
  ],
  "edges": [
    {
      "from": "arxiv-2003.02320",
      "to": "knowledge-graph",
      "predicate": "defines",
      "context": "Adopts an inclusive definition: 'a graph of data intended to accumulate…'"
    },
    {
      "from": "property-graph",
      "to": "directed-edge-labelled-graph",
      "predicate": "alternative-to",
      "context": "Both model graph-structured data; property graphs add property-value pairs and labels to edges and nodes."
    }
  ]
}
```

validate.py enforces:

- Every `from`/`to` is a slug for which `pages/<subdir>/<slug>.md` exists.
- Every `predicate` appears in `_schema.json`.
- Every node corresponds to an existing page.
- Edge endpoints satisfy the predicate's `from_type` / `to_type` constraints. (Predicates that say `from_type: paper` accept any paper-like type — `paper`, `video`, `pdf` — but not `concept`.)

## Using figures and captions

For arxiv-fetch sources, `raw/figures.json` is the manifest of every figure in the paper. Each record has:

- `label` — the LaTeX label (e.g. `fig:delg`), used as the cross-reference target throughout the paper.
- `caption` — the cleaned caption text. **This is the semantic glue**: it's the author's own one-line description of what the figure is about, and it tells you which concept the figure illustrates.
- `section_file` — which section file the figure lives in.
- `resolved_paths` — paths relative to `raw/` where the image lives. May point into `figures/` (raster originals or EPS/PDF→PNG conversions) or `_tikz/` (TikZ blocks rasterised by `pdflatex`+`pdftoppm`). Empty when no image is available — usually because pdflatex is missing or the figure's TikZ source depends on body-text-defined macros that the standalone compile can't see.
- `has_tikz` — whether the figure body contains a `tikzpicture`.
- `tikz_sources` — list of raw `\begin{tikzpicture}…\end{tikzpicture}` source blocks, one per tikzpicture in the figure scope. Use these as a textual fallback when `resolved_paths` is empty for a TikZ figure.
- `available` — `true` iff the figure has a resolved image OR is TikZ.
- `subfigures[]` — same shape, one level deep.

### How to use this when synthesising a concept page

1. **Scan captions for relevance to the concept**. After deciding a concept page is in scope, walk `figures.json` and pick figures whose caption directly relates to the concept. (Example: building a page for `directed-edge-labelled-graph`, the figure with caption *"Directed edge-labelled graph describing events and their venues"* is an obvious match.)

2. **Copy each chosen figure into the vault.** Obsidian only resolves images that live inside the vault directory, so before writing a concept page you must copy the figure file from `<source-dir>/raw/<resolved_path>` into `<wiki-dir>/assets/<paper-slug>/<basename>`:

   ```bash
   mkdir -p <wiki-dir>/assets/<paper-slug>
   cp <source-dir>/raw/_tikz/fig-delg.png <wiki-dir>/assets/<paper-slug>/fig-delg.png
   ```

   Bulk-copying the whole `_tikz/` directory is fine — disk cost is small and unembedded figures stay browsable. Don't symlink: cloud sync tools handle symlinks unreliably.

3. **Embed it in the concept page** using GFM image syntax with the caption as alt text and a visible caption underneath. The image path is relative from `pages/concepts/<slug>.md` to `assets/<paper-slug>/<basename>` — i.e. `../../assets/<paper-slug>/<basename>`:

   ```markdown
   ![Directed edge-labelled graph describing events and their venues](../../assets/arxiv-2003.02320/fig-delg.png)
   *Figure: Directed edge-labelled graph describing events and their venues. From [[arxiv-2003.02320]] §sections/03_data-graphs.tex.*
   ```

   The visible caption underneath both makes the page scannable and creates a backlink to the source paper. This relative form renders identically in Obsidian, GitHub, VS Code preview, and any other vault-aware Markdown renderer.

5. **For TikZ figures with no `resolved_paths` (compile failed or pdflatex missing)**, embed the caption plus a fenced LaTeX block from `tikz_sources` so a reader can still see the figure's structure:

   ```markdown
   *Figure (not rendered): Data about capitals and countries in a directed edge-labelled graph and a heterogeneous graph. See [[arxiv-2003.02320]] for the original.*

   ```latex
   \begin{tikzpicture}
   ...
   \end{tikzpicture}
   ```
   ```

   If `tikz_sources` is large or noisy, just include the caption with the backlink and skip the source block.

6. **Don't embed figures on paper pages**, only on concept pages. The paper page's job is to summarise; the concept page's job is to teach a concept, where the figure is doing real semantic work. validate.py errors on image embeds in paper-like pages — if a figure feels paper-page-shaped, it's actually concept-page-shaped, and naming the right concept usually unblocks the placement.

7. **Multiple papers, same concept**: when a second paper is ingested that adds figures relating to an existing concept, merge them into the same concept page, attributing each figure to the paper it came from. Don't duplicate figures across pages.

## Source-type readers

| Source type | What to read | Notes |
|---|---|---|
| arxiv-fetch | `raw/structure.json` for section list, then walk `raw/sections/*.tex` in order. Read `raw/preamble.tex` once for macro context. Pull metadata from `raw/arxiv_meta.json`. **Read `raw/figures.json` for the figure manifest** (per-figure caption, label, resolved_paths, has_tikz, tikz_sources). | When `pdflatex` was available at fetch time, TikZ figures are pre-rendered to `raw/_tikz/*.png` and listed in `resolved_paths` — embed them like any raster figure. When rendering failed (or pdflatex was missing), `resolved_paths` is empty and `tikz_sources` holds the LaTeX source. Custom macros from preamble.tex give context but don't need rendering. |
| video-to-booklet | `booklet.md` is the prose; pull title from the H1 and authors from video metadata if available. | Booklets are already markdown — just synthesise. |
| pdf-extract | `content.md` for prose, `metadata.json` for header info. If `pdf_profile.json` has `unreliable: true`, flag it in the paper page's "Open questions". | |

## Merging two wikis

`merge.py source-wiki --into target-wiki [--on-conflict=skip|replace|rename]`:

- **Pages**: preserved-subdir copy. On slug clash:
  - `skip`: keep target's page, ignore source's.
  - `replace`: source's page overwrites target's.
  - `rename`: source's page is added with a `-2` suffix; edges in the source graph referencing the old slug are rewritten to the new slug. Frontmatter `slug` field is updated in the renamed page.
- **graph.json**: union of nodes and edges, edges deduplicated by `(from, to, predicate)`.
- **_schema.json**: union of predicates. If a predicate name appears in both with different definitions, errors out — resolve manually.
- **index.md**: not regenerated; run validate.py after.

## Worked example: ingesting a second paper

Initial state: corpus has one paper page (`arxiv-2003.02320`, the Hogan KG survey) and a set of concept pages it created (`knowledge-graph`, `property-graph`, `rdf`, …).

Ingesting `arxiv-1503.00759` (Nickel et al., "A Review of Relational Machine Learning"):

1. **Survey**: existing concept pages include `knowledge-graph`, `property-graph`, `rdf`, `knowledge-graph-embedding`, `ontology`, …
2. **Read source**: walk Nickel's sections.
3. **Plan paper page**: TL;DR (relational ML for KGs), key claims (tensor factorisation models, statistical relational learning), methodology (decomposes RESCAL/TransE/etc.). Concepts covered: `knowledge-graph` (uses), `knowledge-graph-embedding` (defines / canonical reference), `tensor-factorisation` (introduces — new concept page), `relational-learning` (introduces — new concept page).
4. **Plan concept pages**:
   - `knowledge-graph` exists → update: add Nickel to `papers:`, integrate Nickel's view (which is more ML-flavoured than Hogan's data-management view).
   - `knowledge-graph-embedding` exists → update: this is the *canonical* introduction; mark Nickel as the introducer in the Definition.
   - `tensor-factorisation` doesn't exist → create.
   - `relational-learning` doesn't exist → create.
5. **Write paper page** at `pages/papers/arxiv-1503.00759.md`.
6. **Update graph.json**:
   - Add nodes for `arxiv-1503.00759`, `tensor-factorisation`, `relational-learning`.
   - Edges: `arxiv-1503.00759 —[discusses]→ knowledge-graph`, `arxiv-1503.00759 —[introduces]→ knowledge-graph-embedding`, `arxiv-1503.00759 —[introduces]→ tensor-factorisation`, `arxiv-1503.00759 —[introduces]→ relational-learning`.
   - Concept-concept edges: `tensor-factorisation —[part-of]→ knowledge-graph-embedding`, `relational-learning —[related-to]→ knowledge-graph-embedding`.
   - paper→paper edges: probably none here — Nickel predates Hogan, and Hogan's existing edges already cover the citation in the *other* direction.
7. **Validate**, regenerate index.md.

After this, the wiki has 1 + 1 = 2 paper pages and (e.g.) 12 concept pages, with the graph reflecting both bibliographic and conceptual structure. A reader exploring `[[knowledge-graph]]` now sees Nickel and Hogan as discussing it; a reader exploring `[[knowledge-graph-embedding]]` sees the canonical introduction (Nickel) and the survey treatment (Hogan).
