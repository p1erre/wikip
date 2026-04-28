---
name: yt-fetch-transcript
description: Fetch the transcript and metadata for a YouTube video. Use when the user wants captions, transcript, or metadata (title, channel, native chapters) from a YouTube URL. Strict YouTube only; hard-errors if the video has no captions.
---

# yt-fetch-transcript

Fetches the caption track + video metadata for a YouTube video using `yt-dlp` and `youtube-transcript-api`. Deterministic; just runs a Python script.

## Inputs

- **URL or 11-char video ID** (required)
- **work-dir** (optional, default `work/<video_id>/`)

## What to do

1. Determine `video_id` (11-char alphanumeric+`-_`). Either the user gave you an ID directly, or extract from the URL (`youtube.com/watch?v=ID`, `youtu.be/ID`, `youtube.com/embed/ID`).
2. Set `OUT=work/<video_id>` unless the user specified a different work-dir.
3. Run:
   ```bash
   uv run python3 .claude/skills/yt-fetch-transcript/scripts/fetch.py "<URL or ID>" --out-dir "$OUT"
   ```
4. Report what landed:
   - `<OUT>/metadata.json` (title, channel, duration, native chapters)
   - `<OUT>/transcript.txt` (timestamped plain text)
   - One-line summary: title, duration, segment count.

## Exit codes

- `0` — success.
- `2` — no captions available. Tell the user the video has no captions and suggest running `/transcribe-audio` against the audio (a separate skill that wraps Whisper). Do NOT silently fall back; this is a different cost class.
- `1` — other failure. Surface the stderr message.

## Idempotency

The script skips work if both `metadata.json` and `transcript.txt` already exist. To force a refetch, delete those files first.
