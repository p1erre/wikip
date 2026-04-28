---
name: video-to-booklet
description: End-to-end pipeline. Turn a YouTube video URL into a polished markdown booklet. Use when the user pastes a YouTube URL alone, or asks to "make a booklet from this video". Orchestrates the six atomic skills (transcript fetch, video download, slide extraction, slide analysis, chapter generation, booklet writing). Output ends up in output/<title>/booklet.md.
---

# video-to-booklet

The meta-skill. Coordinates two parallel pipeline arms then a serial join.

## Inputs

- **URL or 11-char video ID** (required)
- **`--no-slides`** (optional flag) — skip the slide arm entirely. Use for non-presentation content (interviews, talking heads). Default: slides ON.
- **`--force`** (optional flag) — delete `work/<video_id>/` before starting. Equivalent to a clean run.
- **`--force-stage <name>`** (optional, repeatable) — delete only one stage's output. Valid stages: `transcript`, `video`, `slides`, `analysis`, `chapters`, `plan`, `booklet`.

## Pipeline

```
                                ┌─ /yt-fetch-transcript ─────────────────────────────┐
URL ──→ derive video_id ──┤                                                            ├─→ /generate-chapters → /generate-booklet → copy to output/
                                └─ /yt-fetch-video → /extract-slides → /analyze-slides ┘
```

The two arms run as parallel tool calls. They join at `/generate-chapters`.

## Steps

1. **Derive `video_id`**:
   - 11-char alphanumeric+`-_` string → use directly.
   - Otherwise extract from URL patterns (`youtube.com/watch?v=ID`, `youtu.be/ID`, `youtube.com/embed/ID`).
   - If extraction fails, error with a clear message.

2. **Apply `--force` flags**:
   - `--force`: `rm -rf work/<video_id>/`.
   - `--force-stage transcript`: delete `work/<video_id>/transcript.txt` and `metadata.json`.
   - `--force-stage video`: delete `work/<video_id>/video.mp4`.
   - `--force-stage slides`: delete `work/<video_id>/slides/` (excluding `analysis.md`).
   - `--force-stage analysis`: delete `work/<video_id>/slides/analysis.md`.
   - `--force-stage chapters`: delete `work/<video_id>/chapters.json`.
   - `--force-stage plan`: delete `work/<video_id>/plan.json`.
   - `--force-stage booklet`: delete `work/<video_id>/booklet.md`.

3. **Ensure work-dir**: `mkdir -p work/<video_id>`.

4. **Run both arms in parallel** (single message, multiple tool calls):
   - **Arm A — transcript**: invoke `/yt-fetch-transcript` with the URL.
     - If exit 2 (no captions): abort the whole pipeline immediately. Surface the no-captions error and the suggestion to use `/transcribe-audio`. Do NOT attempt a slides-only booklet.
   - **Arm B — slides** (skip entirely if `--no-slides`):
     - `/yt-fetch-video` → `/extract-slides` → `/analyze-slides`. These run serially within the arm; the arm itself runs concurrently with Arm A.
     - If `/extract-slides` finds zero or only 1–2 unique slides for a video longer than 5 minutes, log a warning but continue. The booklet writer will simply have no slide context.

5. **Wait for both arms.** Once Arm A succeeds and Arm B has finished (or was skipped), proceed.

6. **Run `/generate-chapters`** against `work/<video_id>/`.

7. **Run `/generate-booklet`** against `work/<video_id>/`.

8. **Copy to user-facing output as a self-contained bundle**:
   - Read `work/<video_id>/metadata.json` to get the video title.
   - Sanitize for filesystem: replace `/`, `\`, `:`, `*`, `?`, `"`, `<`, `>`, `|` with `_`, collapse whitespace to `_`, trim to 80 chars. Call this `<title>`.
   - `mkdir -p "output/<title>"`.
   - `cp work/<video_id>/booklet.md "output/<title>/booklet.md"`.
   - If slides were extracted: `mkdir -p "output/<title>/slides" && cp work/<video_id>/slides/slide_*.jpg "output/<title>/slides/"`.
   - The markdown's `![Slide N](slides/slide_NNN.jpg)` references resolve naturally because the bundle has the same `slides/` subfolder structure.
   - DO NOT copy `analysis.md`, `metadata.json` from the slides dir — those are build artifacts, not user-facing.

9. **Final report**:
   - Path of the booklet (`output/<title>/booklet.md`).
   - Word count.
   - Number of chapters.
   - Whether slides were included (and how many).
   - Total wall time.

## Failure handling

- **No captions** (exit 2 from `/yt-fetch-transcript`): fail fast with the remediation pointer. Don't fall through to a slides-only booklet — that's a different deliverable.
- **Video download fails**: report the yt-dlp error. If `--no-slides` was already off, ask the user whether to retry with `--no-slides` (transcript-only booklet still works).
- **Slide extraction yields nothing**: warn but continue. The booklet just won't have slide content.
- **Subagent failures inside `/analyze-slides` or `/generate-booklet`**: those skills handle re-runs themselves. If they bubble an error here, surface it.

## Examples

```
/video-to-booklet https://www.youtube.com/watch?v=Hm-ZIiwiN1o
/video-to-booklet Hm-ZIiwiN1o --no-slides
/video-to-booklet Hm-ZIiwiN1o --force-stage booklet     # regenerate just the booklet
/video-to-booklet Hm-ZIiwiN1o --force                   # full clean run
```

## Notes

- All seven skills can be called individually for partial pipelines. This skill is just the convenience wrapper for the most common path.
- The `work/<video_id>/` directory is the durable build dir — gitignored, but stable across runs (resume semantics).
- The `output/` directory is the user-facing artifact dir — also gitignored.
