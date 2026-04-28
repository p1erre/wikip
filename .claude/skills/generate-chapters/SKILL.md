---
name: generate-chapters
description: Produce a rich chapter outline for a video booklet. Use after /yt-fetch-transcript (and optionally /extract-slides) have run. Prefers the video's native chapters if present, otherwise detects them semantically from the transcript. Rebalances chapters toward ~2000 words each. Output is a self-contained JSON where each chapter embeds its transcript slice and the list of slide numbers shown during it.
---

# generate-chapters

Produces `<work-dir>/chapters.json` — the structural backbone the booklet writer consumes. Each chapter is self-contained: the booklet writer can produce one chapter's prose without re-reading the global transcript.

## Inputs

- **work-dir** (required) — typically `work/<video_id>/`. Must contain:
  - `transcript.txt` (timestamped plain text, from `/yt-fetch-transcript`)
  - `metadata.json` (may contain native chapters)
- **slides metadata** (optional) — `<work-dir>/slides/metadata.json`. If present, slide numbers get attached to chapters. If absent, chapters work fine without slides.
- **target-words-per-chapter** (optional, default `2000`) — soft target for rebalancing.

## Output schema

Write `<work-dir>/chapters.json`:

```json
[
  {
    "number": 1,
    "title": "...",
    "start": 0.0,
    "end": 380.5,
    "transcript": "...full text spoken in this range, joined from segments...",
    "slide_numbers": [1, 2, 3, 4],
    "native": true,
    "rebalanced": false
  },
  ...
]
```

- `start`/`end`: seconds (float).
- `transcript`: concatenated segment text within `[start, end)`. Strip timestamps; keep just the prose.
- `slide_numbers`: numbers of slides whose `timestamp` falls in `[start, end)`. Empty list if no slides metadata.
- `native`: true if this chapter came from yt-dlp metadata; false if Claude detected it semantically.
- `rebalanced`: true if Claude split or merged the original chapters during rebalancing.

## Algorithm

### Step 1 — Source chapters

1. Read `<work-dir>/metadata.json`.
2. If `chapters` field is non-empty → **use native chapters** as the starting boundaries. Each becomes a candidate chapter with `native=true`, using the native `title`.
3. Else → **detect semantically**: read `transcript.txt`, identify ~`max(3, duration_minutes / 8)` natural topic boundaries. Mark each detected chapter `native=false`. Generate concise titles (3–7 words) reflecting what's covered.

### Step 2 — Rebalance toward ~2000 words/chapter

For each candidate chapter, compute word count from its transcript slice.

- **If word count > 1.75 × target** (default >3500): **split**. Find a natural mid-point in the transcript (paragraph break, topic shift) and divide. Mark the new sub-chapters `rebalanced=true`. Synthesize titles for each. Both halves keep `native=false` once split (they're no longer the original native unit, even if the parent was native).
- **If word count < 0.4 × target** (default <800): **merge** with the next chapter (or the previous, if last). Pick whichever target is shorter to keep distribution flatter. Mark merged chapter `rebalanced=true`. Use the longer half's title, or synthesize a combined title.
- Otherwise: keep as-is.

After rebalancing, renumber chapters sequentially starting at 1.

### Step 3 — Slice transcript and attach slides

For each final chapter:

1. Slice `transcript.txt`: read the timestamped lines, keep those whose timestamp falls in `[start, end)`. Concatenate the prose (drop the timestamps). This becomes the chapter's `transcript` field.

   The leading `[...]` token is colon-separated and may be `M:SS`, `MM:SS`, `H:MM:SS`, or `HH:MM:SS` depending on video length. Parse the last component as seconds, the second-to-last as minutes, and any earlier component as hours. Convert to total seconds for the range comparison.
2. If `<work-dir>/slides/metadata.json` exists, read it. For each slide, if `timestamp` falls in `[start, end)`, append `slide_number` to this chapter's `slide_numbers`.

### Step 4 — Write

Write the full list to `<work-dir>/chapters.json` (pretty-printed JSON).

Report:
- Total chapter count
- How many native vs semantic, how many rebalanced
- Word-count distribution (min, median, max)

## Idempotency

If `<work-dir>/chapters.json` exists and is non-empty, skip with "using existing chapters". To force re-generation, delete the file.

## Notes

- Slides are NOT used as a chapter-boundary signal. If you find that limiting later, lift it then; don't pre-optimize.
- Do not invent a "Conclusion" chapter if none exists — chapter boundaries reflect what's actually in the video.
- Native chapter titles are usually good; only rewrite them when splitting/merging.
