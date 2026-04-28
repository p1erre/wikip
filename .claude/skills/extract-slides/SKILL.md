---
name: extract-slides
description: Extract unique slides from a presentation video file. Use when the user has an MP4 (typically from /yt-fetch-video) and wants to pull out one image per unique slide, with progressive-reveal handling and global deduplication.
---

# extract-slides

Runs the robust slide-extraction algorithm: perceptual hashing + SSIM verification + edge-based build detection + global dedup across the whole video.

## Inputs

- **video file path** (required) — usually `work/<video_id>/video.mp4`
- **out-dir** (optional, default: same directory as video, in `slides/` subdir)
- **fps** (optional, default `2.0`) — sampling rate. Higher = more precise but slower. `2.0` is right for typical talks; bump to `5.0` for fast-cut content.
- **build-policy** (optional, default `build_collapse`) — `build_collapse` keeps only the final fully-revealed version of progressive slides; `build_preserve` saves each build step as its own slide.

## What to do

1. Verify the video file exists.
2. Set `OUT` to the slides directory (default: `<video parent>/slides/`).
3. Run:
   ```bash
   uv run python3 .claude/skills/extract-slides/scripts/extract.py "<video path>" --out-dir "$OUT" [--fps 2.0] [--build-policy build_collapse]
   ```
4. Report:
   - Number of unique slides found
   - Number of underlying segments (occurrences before dedup)
   - Path to `<OUT>/metadata.json`

## Output structure

```
<OUT>/
  slide_001.jpg
  slide_002.jpg
  ...
  metadata.json    # [{slide_number, image_path, timestamp, duration, num_occurrences, num_builds}, ...]
```

## Idempotency

Skips if `<OUT>/metadata.json` exists and is non-empty. To force re-extraction, delete `<OUT>/` first.

## Notes

- This skill does NOT analyze slide content. That's `/analyze-slides`.
- This skill does NOT align slides to transcript text. That's done in `/generate-chapters`.
- Heavy dependencies: `opencv-python`, `scikit-image`, `imagehash`, `pillow`, `numpy`. All in `pyproject.toml`.
