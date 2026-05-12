# deep-research — Reference

## Subagent prompt template

Launch one Agent per sub-query in a **single message** (parallel). Use `subagent_type: "general-purpose"`.

```
You are a focused web search agent. Your job:

QUERY: "<sub-query>"

ALREADY FETCHED (skip these URLs):
<contents of working/fetched_urls.txt, or "none">

STEPS:
1. Call WebSearch with the query above. Get the top results.
2. Pick the <N> most relevant URLs (ignore already-fetched ones).
3. Call WebFetch on each chosen URL.
4. Return a structured block in exactly this format:

---FINDINGS---
query: <the sub-query you were given>
sources:
  - url: <url>
    title: <page title>
    key_claims:
      - <one concrete claim from this source>
      - <another claim>
  - url: ...
synthesis: |
  <3-5 sentences integrating the findings across all sources>
gaps:
  - <something this search could not answer>
  - <another gap>
---END FINDINGS---

Rules:
- key_claims must be specific facts, numbers, or definitions — not vague summaries.
- synthesis must integrate across sources, not repeat per-source bullets.
- gaps must be genuinely unanswered by what you found.
- If WebFetch fails on a URL, note it under the source as fetch_error: true and continue.
```

## Iteration synthesis format (`working/iter_N.md`)

```markdown
# Iteration N synthesis

**Focus**: <what this iteration was researching>
**Sub-queries run**: query1 | query2 | query3
**New sources fetched**: N

## Integrated findings

<prose synthesis across all subagent findings for this iteration>

## What is now known

<bullet list of the most important confirmed facts/claims>

## Gaps identified

- <specific unanswered question 1>
- <specific unanswered question 2>
- ...

## Focus for next iteration

<1-2 sentences: what should iteration N+1 investigate>
```

## `content.md` schema

wikip reads `content.md` as the primary source document. Write it like a well-structured research report, not a wiki page — wikip synthesises wiki pages *from* it.

```markdown
---
query: "<original research question>"
title: "<descriptive title derived from findings>"
date: YYYY-MM-DD
sources:
  - url: <url>
    title: <title>
  - ...
---

## Executive Summary

3-5 sentences covering the most important findings and why they matter.

## [Topic / Sub-question 1]

Prose findings. Cite sources inline as footnote markers [1], [2] matching the
sources list in frontmatter (by position).

## [Topic / Sub-question 2]

...

## Key Claims

- <Concrete claim 1> [source N]
- <Concrete claim 2> [source N]
- ...

## Limitations & Gaps

What this research could not establish, contradictions between sources, areas
that need deeper investigation.

## Sources

1. [Title](url) — one-line description of what this source contributed.
2. ...
```

Structure sections around the sub-questions from the research, not around the iterations — the iterations are an implementation detail, not a narrative structure.

## `metadata.json` schema

```json
{
  "query": "original natural-language query",
  "title": "derived descriptive title",
  "date": "YYYY-MM-DD",
  "sources": [
    {"url": "https://...", "title": "Page Title", "fetched_at": "ISO8601"}
  ]
}
```

## `deep_research_profile.json` schema

```json
{
  "iterations": 3,
  "queries_run": 9,
  "sources_fetched": 23,
  "sources_failed": 2,
  "warnings": [
    "WebFetch failed for https://example.com/paywalled — skipped"
  ]
}
```

## wikip integration

wikip detects `content.md` + `deep_research_profile.json` as a deep-research bundle. It reads:
- `content.md` — the synthesized research report (primary source content)
- `metadata.json` — query, title, date, sources list

When building the paper page, wikip uses:
- **TL;DR** from the Executive Summary
- **Key claims** from the Key Claims section
- **Slug** = `out-dir` basename (e.g. `my-research`)
- **Type** = `paper` (deep-research bundles are treated as primary sources)

The sources list in `metadata.json` is for provenance, not for wikip to re-fetch.

## Stopping criteria

The loop stops at `--iterations` by default. You may also stop early if:
- The "Gaps identified" section in `working/iter_N.md` is empty (full coverage reached)
- Two consecutive iterations add zero new key claims (diminishing returns)

## Failure modes

- **WebSearch returns irrelevant results**: narrow the sub-query in the next iteration. Note in `deep_research_profile.json` warnings.
- **WebFetch blocked (403, Cloudflare)**: log URL as `fetch_error` in the subagent findings, continue with other sources.
- **Conflicting claims across sources**: keep both in the synthesis with attribution ("Source A claims X; Source B claims the opposite, citing Y"). Flag in "Limitations & Gaps".
- **Context growing too large**: if the main agent context feels crowded mid-iteration, write what you have to `working/iter_N_partial.md` and continue from there. Never let raw source text accumulate — always summarize first.
