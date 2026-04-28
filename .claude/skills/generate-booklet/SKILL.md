---
name: generate-booklet
description: Write the final markdown booklet for a video. Use after /generate-chapters has produced chapters.json (and optionally /analyze-slides has produced slides/analysis.md). Uses a planner-then-workers pattern — one Claude pass plans the global structure, then N parallel subagents each write one chapter. Output is work/<video_id>/booklet.md.
---

# generate-booklet

Produces the final `<work-dir>/booklet.md` — title page, intro paragraph, table of contents, and one chapter of polished prose per `chapters.json` entry.

## Inputs

- **work-dir** (required) — typically `work/<video_id>/`. Must contain:
  - `chapters.json` (from `/generate-chapters`)
  - `metadata.json` (for title page)
- **slides analysis** (optional) — `<work-dir>/slides/analysis.md`. If present, the planner uses it to assign per-slide handling modes; if absent, the booklet is transcript-only.

## Three-step process

### Step 1 — Planner pass

Read `chapters.json`, `metadata.json`, and (if present) `slides/analysis.md`.

Produce a single JSON file `<work-dir>/plan.json` with:

```json
{
  "booklet_title": "...",            // 3–10 words, distilled from video title and content
  "intro": "...",                    // ONE paragraph (~100–150 words). What the booklet covers, who it's for, what they'll learn.
  "style_guide": [
    "Audience: smart non-expert.",
    "Tone: precise but accessible; no fluff.",
    "Code blocks: fenced with language hints.",
    "Diagrams from slides: describe in prose unless visual is essential.",
    "Citations: each chapter heading shows starting timestamp."
  ],
  "chapters": [
    {
      "number": 1,
      "title": "...",                // refine the chapters.json title if needed
      "must_cover": ["...", "..."],  // 3–6 bullet points the chapter must address
      "must_not_repeat": ["..."],    // concepts already introduced in earlier chapters
      "slide_callouts": [
        {"slide_number": 5, "mode": "embed"},     // visual-only content, can't substitute prose
        {"slide_number": 7, "mode": "code"},      // verbatim code block in prose
        {"slide_number": 12, "mode": "describe"}  // describe in prose, no image
      ]
    },
    ...
  ]
}
```

### Planner reasoning

- **Title**: distill the video title + chapter outline. Drop channel boilerplate ("Lecture 5:", "Part II:") unless meaningful.
- **Intro**: one paragraph. State the topic, the angle, what's covered, expected reader level. No hype.
- **must_not_repeat**: scan earlier chapters' must_cover lists to catch redundancy. Chapter 4 should not re-introduce concepts established in chapter 1.
- **slide_callouts**: for each `slide_number` in the chapter, decide:
  - `embed` — the slide is visual-only (chart, screenshot, diagram with no extractable code/prose). Will render as `![](slides/slide_NNN.jpg)`.
  - `code` — the slide is primarily code. Worker reads the slide's `Code:` field from `analysis.md` and renders as a fenced code block.
  - `describe` — slide is text/bullets that prose can fully convey. Worker mentions it in prose without an image.
  - Default: `describe` for slides whose analysis has bullets but no diagram or code; `embed` for slides with `Diagram:` populated and no extractable code; `code` for slides with `Code:` populated.

### Step 2 — Worker pass

For each chapter, **spawn one general-purpose subagent in parallel** via the Agent tool. Each subagent gets:

- The chapter object from `chapters.json` (number, title, start, end, transcript, slide_numbers).
- Its brief from `plan.json` (must_cover, must_not_repeat, slide_callouts).
- The `style_guide` list.
- The relevant slide analysis blocks (extract from `slides/analysis.md` for the slide_numbers in this chapter; pass them inline to avoid the worker re-reading the whole file).

#### Worker prompt template

> You are writing one chapter of a markdown booklet derived from a video transcript.
>
> **Chapter:** {number}. {title}
>
> **Source transcript** (what was actually said):
> ```
> {chapter.transcript}
> ```
>
> **Your brief:**
> - Must cover: {must_cover}
> - Must NOT re-introduce (covered earlier): {must_not_repeat}
> - Slide callouts: {slide_callouts}
>
> **Slide analyses** (for the slides shown during this chapter):
> ```markdown
> {extracted slide blocks from analysis.md}
> ```
>
> **Style guide:**
> {style_guide}
>
> **Length target:** soft ~2000 words. Write to fit the content (1000–4000 OK). Don't pad.
>
> **Output format:**
> ```markdown
> ## Chapter {number} — {title} *(starts at mm:ss)*
>
> {prose, with code blocks / image embeds / inline references per the slide_callouts}
> ```
>
> Convert the chapter `start` (seconds) to `mm:ss` for the heading.
>
> For each `slide_callout`:
> - `embed`: insert `![Slide N](slides/slide_NNN.jpg)` on its own line, with a one-line caption above or below describing what it shows.
> - `code`: extract the `Code:` block from the slide analysis and render as a fenced code block, with a sentence introducing it.
> - `describe`: weave the slide's content into prose; do NOT include the image.
>
> Output ONLY the chapter markdown — no preamble, no summary, no metadata fences.

### Step 3 — Stitch

Assemble `<work-dir>/booklet.md`:

1. **Frontmatter** (YAML at the top):
   ```yaml
   ---
   title: {plan.booklet_title}
   source: {metadata.url}
   video_title: {metadata.title}
   channel: {metadata.channel}
   duration: {format duration as h:mm:ss or m:ss}
   generated: {ISO date}
   ---
   ```
2. **Title** (`# {booklet_title}`).
3. **Intro paragraph** (`plan.intro`).
4. **Table of contents**: `## Contents` followed by an ordered list of links: `1. [Chapter Title](#chapter-1--chapter-title)`. Use markdown anchor format that matches the chapter headings.
5. **Chapters**: subagent outputs in order, separated by blank lines.
6. NO conclusion/outro. Booklet ends when the video ends.

Write to `<work-dir>/booklet.md`. Report total word count and chapter count.

## Idempotency

If `<work-dir>/booklet.md` exists and is non-empty, skip with "using existing booklet". To regenerate (e.g., after editing the planner prompt), delete the file or use the meta-skill's `--force-stage generate-booklet`.

## Notes

- The plan is small (typically <2KB). Persist it so you can iterate on workers without re-running the planner.
- If a subagent's output looks malformed (e.g., missing the heading), re-run that single chapter.
- The booklet is the final artifact `/video-to-booklet` copies into `output/<title>/`. This skill writes only into `<work-dir>/`.
