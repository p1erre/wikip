---
name: yt-fetch-video
description: Download a YouTube video as MP4. Use when the user wants to save a YouTube video locally, or as a prerequisite for slide extraction. Idempotent — skips if the file already exists.
---

# yt-fetch-video

Downloads a YouTube video to `<work-dir>/video.mp4`. Deterministic; just runs `yt-dlp` via a Python wrapper.

## Inputs

- **URL or 11-char video ID** (required)
- **work-dir** (optional, default `work/<video_id>/`)

## What to do

1. Determine `video_id` from the URL or accept it directly.
2. Set `OUT=work/<video_id>` unless the user specified a different work-dir.
3. Run:
   ```bash
   uv run python3 .claude/skills/yt-fetch-video/scripts/download.py "<URL or ID>" --out-dir "$OUT"
   ```
4. Report the resulting file path and size in MB.

## Idempotency

Skips if `<OUT>/video.mp4` exists and is non-empty. To force re-download, delete the file first.

## Notes

- This skill is the prerequisite for `/extract-slides`. The meta-skill `/video-to-booklet` calls them in sequence.
- Video can be large (hundreds of MB to several GB). Files live under `work/` and are gitignored.
- Once `/extract-slides` has run, `video.mp4` can be safely deleted to reclaim space — slides are derived from it but no later stage needs it.
