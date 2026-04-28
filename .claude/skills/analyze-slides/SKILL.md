---
name: analyze-slides
description: Analyze the visual content of extracted slide images using vision. Use after /extract-slides has produced slide images. Produces a structured per-slide markdown analysis (title, bullets, diagram, code, notable). Vision-only — does NOT use the transcript.
---

# analyze-slides

Reads each slide image and writes a structured per-slide analysis. The downstream consumer is `/generate-booklet`, which fuses this analysis with the transcript.

## Inputs

- **slides-dir** (required) — directory containing `slide_NNN.jpg` files and `metadata.json`. Usually `work/<video_id>/slides/`.

## What to do

1. Read `<slides-dir>/metadata.json` to get the list of slides (paths + slide_numbers + timestamps).
2. Let `N` = number of unique slides. Compute `B = ceil(N / 10)` batches.
3. **Spawn `B` general-purpose subagents in parallel** via the Agent tool. Each subagent receives a slice of ~10 consecutive slides.
4. Wait for all subagents. Concatenate their results in slide-number order.
5. Write to `<slides-dir>/analysis.md`.
6. Report: number of slides analyzed, file path written.

## Subagent prompt template

Each subagent gets this prompt (substitute `{slide_paths}` with a JSON list of `{slide_number, image_path, timestamp}` for its assigned slides, ~10 entries):

> You are analyzing slides from a video presentation. Read each slide image carefully and produce a structured markdown block per slide.
>
> Slides to analyze (read each image with the Read tool):
> ```json
> {slide_paths}
> ```
>
> For EACH slide, output exactly this format (preserve order by slide_number):
>
> ```markdown
> ## Slide {slide_number} — {title or "(no title)"}
> **Timestamp:** {mm:ss from the timestamp field}
> **Bullets:**
> - bullet 1
> - bullet 2
> (use "- (none)" if no bulleted content)
> **Diagram:** {one-paragraph description of any diagram/figure/chart, or "none"}
> **Code:** {verbatim code snippet in a fenced block with language hint, or "none"}
> **Notable:** {anything visually emphasized — callouts, color, animation residue, or "none"}
> ```
>
> Output ONLY the concatenated markdown blocks, one per slide, in slide-number order. No preamble, no summary.

## Stitching

After all subagents return, concatenate their outputs in slide-number order (subagents are dispatched in order, so simple concatenation works). Prepend a one-line header:

```markdown
# Slide Analysis — {N} slides

```

Write to `<slides-dir>/analysis.md`.

## Idempotency

If `<slides-dir>/analysis.md` already exists and is non-empty, skip and report "using existing analysis". To force re-analysis, delete the file.

## Notes

- This is the only "intelligence" in this skill — no scripts, just vision via Claude Code's Read tool.
- Cost is bounded: ~N image reads + N short text outputs. For a 60-slide deck: ~6 subagents × 10 slides each, runs in ~10–20 s wall time.
- If a subagent's output deviates from the schema, re-run that batch (don't let bad blocks land in `analysis.md`).
