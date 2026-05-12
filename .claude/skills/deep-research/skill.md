---
name: deep-research
description: Run a multi-iteration web research loop using only Claude Code's native WebSearch, WebFetch, and Agent tools — no external libraries or APIs — producing a wikip-compatible bundle (content.md + deep_research_profile.json + metadata.json) from a natural language query. Use when the user asks to "deep research [topic]", "research and ingest [topic] into the wiki", "build a wiki bundle about [X]", or needs a synthesised research report on a topic that spans many sources.
---

# deep-research

Implements the [[search-reason-loop]] pattern natively: decompose → parallel-search → synthesize → identify gaps → refine. Loops N times then writes a wikip-ingestible bundle. No LangChain, no Firecrawl, no OpenAI API — just Claude + native tools.

## Inputs

- **query** (required) — natural language research question
- **out-dir** (required) — where to write the bundle (e.g. `wikis/agentic-ai/documents/my-research/`)
- **--iterations** (optional, default `3`) — search-reason-refine cycles
- **--sources-per-query** (optional, default `5`) — URLs to fetch per sub-query

## Workflow

### 1. Setup
```bash
uv run python3 .claude/skills/deep-research/scripts/init.py "<out-dir>"
```
Creates `working/` and `sources/` subdirs. Exits early if `content.md` already exists (idempotent).

### 2. Search-reason loop (repeat `--iterations` times)

**a. Decompose** — derive 3–5 focused sub-queries from the current research focus. First iteration: from the raw query. Subsequent iterations: from gaps identified in the previous synthesis.

**b. Search (parallel subagents)** — launch one Agent per sub-query in a single message. See [REFERENCE.md](REFERENCE.md) for the exact subagent prompt template. Each subagent:
- Runs `WebSearch` for its sub-query
- Calls `WebFetch` on the top URLs (skipping any in `working/fetched_urls.txt`)
- Returns a structured findings block (query · sources · key claims)

**c. Synthesize** — read all subagent findings. Write synthesis to `working/iter_N.md`. Append newly fetched URLs to `working/fetched_urls.txt`. Write each source summary to `sources/NNN_<slug>.md`.

**d. Identify gaps** — list 3–5 specific questions the current synthesis cannot answer. These become the focus for the next iteration.

### 3. Finalize bundle

Assemble `content.md` from the iteration syntheses (see schema in [REFERENCE.md](REFERENCE.md)). Write `metadata.json` and `deep_research_profile.json`. Report: iterations run, sources fetched, any fetch failures.

## Context management rules

- **Never hold raw fetched HTML/markdown in main context.** Subagents summarize to structured findings; main agent writes summaries to disk and discards raw content.
- **Subagents run in isolation.** Pass only: sub-query + already-fetched URL list + instructions.
- **Between iterations, read only `working/iter_N.md`** — not the full source files — to keep context bounded.

## Output bundle shape

```
<out-dir>/
  content.md                   # synthesized report — wikip reads this
  metadata.json                # {query, title, date, sources[]}
  deep_research_profile.json   # {iterations, queries_run, sources_fetched, warnings[]}
  working/
    iter_01.md                 # partial synthesis (kept for traceability)
    iter_02.md
    fetched_urls.txt           # dedup registry
  sources/
    001_<slug>.md              # per-source summaries
```

Wikip detects this bundle type via `deep_research_profile.json`. See [REFERENCE.md](REFERENCE.md).
