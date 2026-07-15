---
name: video-transcript-fetch
description: Fetch or generate a transcript for any video URL. Tries captions first (yt-dlp, free and instant); falls back to local faster-whisper transcription when none are available. Works with YouTube, Vimeo, Twitter/X, and 1000+ sites supported by yt-dlp.
---

# video-transcript-fetch

Fetches the transcript and metadata for any video URL. Uses yt-dlp to get captions when available (free, instant, no model needed); falls back to local faster-whisper transcription when not.

## Inputs

- **URL** (required) — any video URL supported by yt-dlp
- **work-dir** (optional, default `work/<slug>/`)
- **--lang** (optional, default `en`) — BCP-47 language code, or `auto` for auto-detect

## What to do

1. Derive a slug from the URL: for YouTube use the 11-char video ID; for other URLs sanitize the hostname+path (e.g. `vimeo-123456789`).
2. Set `OUT=work/<slug>` unless the user specified a different work-dir.
3. Run:
   ```bash
   uv run python3 .claude/skills/video-transcript-fetch/scripts/fetch.py "<URL>" --out-dir "$OUT" [--lang <lang>]
   ```
4. Report what landed:
   - `<OUT>/metadata.json` — title, channel, duration, chapters, `transcript_source`
   - `<OUT>/transcript.txt` — timestamped plain text
   - `<OUT>/content.md` — bundle contract: single-file, LLM-legible rendition (frontmatter + chapter list + complete fenced transcript, verbatim)
   - `<OUT>/video_profile.json` — marker file; downstream skills (wikip) detect the bundle type by its presence
   - One-line summary: title, duration, segment count, source (`captions` or `whisper`).

## How it works

1. **Captions** — yt-dlp tries to download subtitle tracks (manual or auto-generated) without downloading the video. Fast and free.
2. **Whisper fallback** — if no captions exist, downloads audio only (m4a) with yt-dlp and transcribes locally with `faster-whisper` (base model, CPU/int8).

## Exit codes

- `0` — success
- `1` — failure (surface stderr to the user)

## Idempotency

Skips all work if both `metadata.json` and `transcript.txt` already exist — but self-heals a missing `content.md` / `video_profile.json` on that path, offline (the `url` argument is optional then):
```bash
uv run python3 .claude/skills/video-transcript-fetch/scripts/fetch.py --out-dir work/<slug>
```
Re-running over a legacy bundle upgrades it in place. Delete `metadata.json` + `transcript.txt` to force a full re-fetch.
