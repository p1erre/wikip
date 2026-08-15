---
name: reconcile-corpora
description: Cross-corpus concept reconciliation for a wikis/ directory. Finds confirmed concept bridges (exact slug matches), candidate synonyms (different slugs, same idea), and produces a thematic coverage map showing which corpora cover which areas of the space. Updates wikis/graph.json and regenerates wikis/CONNECTIONS.md. Run periodically — not on every ingest — when several new papers have landed and you want to audit cross-corpus coherence.
---

# reconcile-corpora

Bring the cross-corpus knowledge graph up to date: confirm bridges, surface slug synonyms, cluster themes, regenerate CONNECTIONS.md.

## When to run

After a batch of ingests — not after every single paper. The signal is "I've added several papers and want to see how the corpora connect now."

## Inputs

- **wikis-dir** — path to the wikis root, e.g. `wikis/`. Must contain at least two subdirectories each with a `graph.json`.

## Workflow

### Step 1 — Scan (deterministic)

```bash
uv run python3 "${CLAUDE_PLUGIN_ROOT}"/skills/reconcile-corpora/scripts/reconcile.py scan <wikis-dir>
```

This:
- Reads every per-corpus `graph.json`
- Finds all concept slugs that appear in 2+ corpora → **confirmed bridges** → `same-as` edges in `wikis/graph.json`
- Prints a JSON inventory to stdout: every concept with its corpus, title, and top-3 outgoing edge contexts

Capture the output:
```bash
uv run python3 "${CLAUDE_PLUGIN_ROOT}"/skills/reconcile-corpora/scripts/reconcile.py scan <wikis-dir> > /tmp/reconcile_inventory.json
```

Then read `/tmp/reconcile_inventory.json`.

### Step 2 — Candidate synonyms (LLM pass)

Read the `inventory` array from the scan output. For each concept, you have its `slug`, `title`, `corpus`, and `top_edges` (edge targets + predicate + first 100 chars of context).

Identify pairs or clusters where different slugs likely describe the same idea. Signals to look for:
- Near-identical titles (`semantic-operator` / `semantic-operators`)
- Same domain + overlapping edge targets (`agentic-orchestration` → `multi-agent-system` in one corpus, `agentic-ai` → `multi-agent-system` in another)
- Concepts one corpus treats as foundational that another corpus treats as assumed background

For each candidate pair, add a `same-as?` edge to `wikis/graph.json`:
```json
{
  "from": "<corpus-a>/<slug-a>",
  "to":   "<corpus-b>/<slug-b>",
  "predicate": "same-as?",
  "context": "<one sentence explaining why these look synonymous>"
}
```

Also add the corresponding nodes to `wikis/graph.json` if they aren't already there (same schema as confirmed nodes: `slug`, `corpus`, `local_slug`, `title`, `type: "concept"`).

Err on the side of flagging — a false positive is cheap to dismiss; a missed synonym persists invisibly.

### Step 3 — Thematic coverage map (LLM pass)

From the full inventory, cluster concepts into 5–10 broad themes. Good themes are cross-cutting (appear in multiple corpora) and non-trivial (not just "everything in corpus X"). Examples of themes that tend to emerge from AI/enterprise corpora: *Data Representation*, *Agent Architecture*, *Retrieval & Querying*, *Evaluation & Reliability*, *Strategy & Operating Model*, *Orchestration*, *Governance*.

For each theme:
1. Add a node to `wikis/graph.json`:
   ```json
   {"slug": "<theme-slug>", "title": "<Theme Title>", "type": "theme"}
   ```
2. Add `covers` edges from the theme node to every concept (namespaced) that belongs to it:
   ```json
   {"from": "<theme-slug>", "to": "<corpus>/<slug>", "predicate": "covers"}
   ```

Aim for coherent clusters, not exhaustive ones — leave orphan concepts unclustered rather than force-fitting them.

### Step 4 — Apply (regenerate CONNECTIONS.md)

```bash
uv run python3 "${CLAUDE_PLUGIN_ROOT}"/skills/reconcile-corpora/scripts/reconcile.py apply <wikis-dir>
```

This reads `wikis/graph.json` (now enriched with confirmed bridges, candidate synonyms, and theme nodes) and regenerates `wikis/CONNECTIONS.md`. The reading paths section is preserved verbatim from the previous version of the file — only the bridge concepts, candidate synonyms, and thematic coverage map are regenerated.

### Step 5 — Report

Tell the user:
- How many confirmed bridges exist (exact slug matches)
- How many candidate synonyms were flagged, with the top 3 most interesting pairs
- The theme clusters and which corpora are present / absent in each
- Whether CONNECTIONS.md changed materially

Then ask: *"Do you want to promote any candidate synonyms to confirmed (rename a slug in a corpus graph.json), or dismiss any as false positives?"*

## Output files

| File | What changes |
|---|---|
| `wikis/graph.json` | Same-as edges updated; candidate same-as? edges added; theme nodes + covers edges added |
| `wikis/CONNECTIONS.md` | Bridge concepts section, candidate synonyms section, and thematic coverage map regenerated; reading paths preserved |

## Promoting a candidate synonym

If the user confirms that `corpus-a/slug-a` and `corpus-b/slug-b` are the same concept:
1. Decide the canonical slug (more edges wins; tie-break to whichever corpus is more foundational)
2. In the non-canonical corpus: rename the concept page file, update all `[[wiki-links]]` in that corpus pointing to it, update `graph.json` node slug and all edge references
3. In `wikis/graph.json`: replace the `same-as?` edge with `same-as`, update the node slugs
4. Re-run Step 4 to regenerate CONNECTIONS.md
5. Run `uv run python3 "${CLAUDE_PLUGIN_ROOT}"/skills/wikip/scripts/validate.py <corpus-dir>` on the affected corpus
