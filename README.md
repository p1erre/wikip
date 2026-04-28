# video-to-booklet

A bundle of Claude Code skills that turn YouTube videos (lectures, talks, tutorials) into Markdown booklets.

The "intelligence" lives in seven SKILL.md prompts; three small Python scripts handle deterministic glue (yt-dlp, ffmpeg, slide deduplication). All LLM work runs through Claude Code itself — no external provider API keys, no multi-provider abstraction.

## Install

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/), and `ffmpeg` on your `PATH`.

```bash
git clone <this repo>
cd video-to-booklet
uv sync
```

Optionally make the skills available from any directory:

```bash
ln -s "$(pwd)/.claude/skills"/* ~/.claude/skills/
```

## Use

Open Claude Code in this directory, then:

```
/video-to-booklet https://www.youtube.com/watch?v=Hm-ZIiwiN1o
```

The pipeline downloads the transcript and video in parallel, extracts unique slides, analyzes them with vision, generates a chapter outline, writes the booklet, and copies the result to `output/<video-title>/booklet.md`.

Common variants:

```
/video-to-booklet <url> --no-slides             # interview/talking-head; skip slide arm
/video-to-booklet <url> --force-stage booklet   # regenerate just the prose
/video-to-booklet <url> --force                 # full clean run
```

## Skills

Each skill is independently invokable:

| Skill | What it does |
|---|---|
| `/yt-fetch-transcript` | Fetch YouTube captions + metadata (title, channel, native chapters). Hard-errors if no captions. |
| `/yt-fetch-video` | Download the MP4. Idempotent. |
| `/extract-slides` | Pull unique slides from the video using perceptual hashing + SSIM + build detection. |
| `/analyze-slides` | Vision pass over slide images. Spawns parallel subagents (~10 slides each). Vision-only — no transcript context. |
| `/generate-chapters` | Produce a rich chapter outline. Uses native chapters if present; rebalances toward ~2000 words/chapter. |
| `/generate-booklet` | Planner-then-workers prose generation. One planner pass + N parallel chapter writers. |
| `/video-to-booklet` | Meta-orchestrator that runs the above. |

## Layout

```
.claude/skills/<name>/SKILL.md   # the prompt
.claude/skills/<name>/scripts/   # bundled Python (only for deterministic skills)
work/<video_id>/                 # build directory, gitignored, resume-able
  metadata.json
  transcript.txt
  video.mp4
  slides/
    slide_NNN.jpg
    metadata.json
    analysis.md
  chapters.json
  plan.json
  booklet.md
output/<video-title>/             # user-facing artifact bundle
  booklet.md
  slides/
    slide_NNN.jpg                 # only if slides were extracted
```

`work/` is the durable build dir — re-running on the same URL skips stages whose output already exists. `output/` holds the final, user-friendly markdown.

## Failure modes

- **No captions on YouTube**: `/yt-fetch-transcript` exits cleanly with a pointer to `/transcribe-audio` (a future Whisper-backed skill, not bundled). The pipeline does not silently fall back to Whisper — that's a different cost class.
- **Non-presentation video**: pass `--no-slides` to skip the slide arm. The booklet will be transcript-only.
- **Want to iterate on prose**: `--force-stage booklet` (or `plan`, `chapters`) regenerates downstream stages without re-fetching anything.

## License

MIT.
