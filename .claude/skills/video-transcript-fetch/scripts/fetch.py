#!/usr/bin/env python3
"""Fetch video transcript from any URL.

Strategy:
1. YouTube URL → youtube-transcript-api  (most reliable for YouTube)
       ↓ fails or not YouTube
2. yt-dlp --write-subs --write-auto-subs --skip-download  (1000+ sites)
       ↓ no captions found
3. yt-dlp download audio → faster-whisper  (local, CPU, no cost)

Usage: fetch.py <url> --out-dir <dir> [--lang en]

Writes:
  <out-dir>/transcript.txt       plain text with [mm:ss] timestamps
  <out-dir>/metadata.json        title, channel, duration, chapters, transcript_source
  <out-dir>/content.md           bundle contract: single-file, LLM-legible rendition
                                 (frontmatter + chapters + fenced transcript)
  <out-dir>/video_profile.json   marker file for downstream bundle-type detection

Idempotent: skips when metadata.json + transcript.txt exist, but self-heals a
missing content.md / video_profile.json on that path (no network) — re-running
over a legacy bundle upgrades it in place.

Exit codes:
  0  success
  1  failure
"""

import argparse
import json
import re
import sys
from pathlib import Path

YOUTUBE_RE = re.compile(
    r'(?:youtube\.com/(?:watch\?v=|embed/|v/)|youtu\.be/)([a-zA-Z0-9_-]{11})'
)


def extract_youtube_id(url: str) -> str | None:
    m = YOUTUBE_RE.search(url)
    return m.group(1) if m else None


def fetch_metadata(url: str) -> dict:
    import yt_dlp

    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
        info = ydl.extract_info(url, download=False)
    return {
        "title": info.get("title"),
        "channel": info.get("uploader"),
        "duration": info.get("duration"),
        "upload_date": info.get("upload_date"),
        "url": url,
        "chapters": info.get("chapters") or [],
    }


def try_youtube_transcript_api(video_id: str, lang: str) -> list[dict] | None:
    """Use youtube-transcript-api for YouTube videos. Returns segments or None."""
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

    try:
        api = YouTubeTranscriptApi()
        langs = [lang, f"{lang}-*"] if lang != "auto" else None
        raw = api.fetch(video_id, languages=langs) if langs else api.fetch(video_id)
        return [
            {"start": seg.start, "end": seg.start + seg.duration, "text": seg.text.strip()}
            for seg in raw
        ]
    except (TranscriptsDisabled, NoTranscriptFound):
        return None
    except Exception:
        return None


def try_yt_dlp_captions(url: str, out_dir: Path, lang: str) -> list[dict] | None:
    """Try yt-dlp subtitle download. Returns parsed segments or None."""
    import yt_dlp

    opts = {
        "quiet": True,
        "no_warnings": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": [lang, f"{lang}-*"],
        "skip_download": True,
        "outtmpl": str(out_dir / "%(title)s [%(id)s]"),
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    vtt_files = sorted(out_dir.glob("*.vtt"))
    if not vtt_files:
        return None

    segments = _parse_vtt(vtt_files[0])
    return segments if segments else None


def _parse_vtt(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    segments = []
    for block in re.split(r"\n\n+", text):
        lines = block.strip().splitlines()
        timestamp_line = next((l for l in lines if "-->" in l), None)
        if not timestamp_line:
            continue
        m = re.match(
            r"([\d:]+\.[\d]+)\s*-->\s*([\d:]+\.[\d]+)",
            timestamp_line,
        )
        if not m:
            continue
        start = _vtt_time(m.group(1))
        end = _vtt_time(m.group(2))
        idx = lines.index(timestamp_line)
        raw = " ".join(lines[idx + 1 :])
        text_clean = re.sub(r"<[^>]+>", "", raw).strip()
        if text_clean:
            segments.append({"start": start, "end": end, "text": text_clean})
    return segments


def _vtt_time(s: str) -> float:
    parts = s.replace(",", ".").split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    return int(parts[0]) * 60 + float(parts[1])


def transcribe_with_whisper(url: str, out_dir: Path, lang: str) -> list[dict]:
    """Download audio and transcribe locally with faster-whisper."""
    import yt_dlp

    audio_path = out_dir / "audio.m4a"
    if not audio_path.exists():
        opts = {
            "quiet": True,
            "format": "bestaudio[ext=m4a]/bestaudio",
            "outtmpl": str(out_dir / "audio"),
            "postprocessors": [],
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        candidates = [p for p in out_dir.glob("audio.*") if p.suffix != ".part"]
        if not candidates:
            raise RuntimeError("audio download produced no file")
        audio_path = candidates[0]

    from faster_whisper import WhisperModel

    whisper_lang = None if lang == "auto" else lang
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments_iter, _ = model.transcribe(str(audio_path), language=whisper_lang, beam_size=5)
    return [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments_iter]


def _fmt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def write_transcript(segments: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        for seg in segments:
            f.write(f"[{_fmt_time(seg['start'])}] {seg['text']}\n")


# Four-backtick fence so transcript content can never terminate the block.
FENCE = "````"


def write_content_md(out_dir: Path, metadata: dict) -> Path:
    """Derive <out_dir>/content.md from metadata.json + transcript.txt.

    The bundle contract's single-file, LLM-legible rendition: frontmatter,
    a chapter list when the video has chapters, then the complete timestamped
    transcript in a fence. Verbatim — never summarized.
    """
    transcript = (out_dir / "transcript.txt").read_text(encoding="utf-8", errors="replace")
    title = metadata.get("title") or out_dir.name
    duration = metadata.get("duration")
    lines = [
        "---",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        f"channel: {json.dumps(metadata.get('channel') or '', ensure_ascii=False)}",
        f"url: {metadata.get('url', '')}",
        f"duration: {_fmt_time(duration) if duration else ''}",
        f"transcript_source: {metadata.get('transcript_source', '')}",
        "---",
        "",
        f"# {title}",
        "",
    ]
    chapters = metadata.get("chapters") or []
    if chapters:
        lines += ["## Chapters", ""]
        for ch in chapters:
            start = ch.get("start_time")
            stamp = f"[{_fmt_time(start)}] " if start is not None else ""
            lines.append(f"- {stamp}{ch.get('title', '')}")
        lines.append("")
    lines += ["## Transcript", "", f"{FENCE}text", transcript.rstrip(), FENCE, ""]
    content_path = out_dir / "content.md"
    content_path.write_text("\n".join(lines))
    return content_path


def write_video_profile(out_dir: Path, metadata: dict) -> Path:
    """Marker file: how downstream skills detect this bundle type."""
    profile_path = out_dir / "video_profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "source": "video-transcript-fetch",
                "transcript_source": metadata.get("transcript_source"),
                "url": metadata.get("url"),
            },
            indent=2,
        )
    )
    return profile_path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "url",
        nargs="?",
        default=None,
        help="Video URL (optional when the bundle already exists — self-heal only)",
    )
    p.add_argument("--out-dir", required=True)
    p.add_argument("--lang", default="en", help="Language code or 'auto'")
    args = p.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    metadata_path = out_dir / "metadata.json"
    transcript_path = out_dir / "transcript.txt"

    if metadata_path.exists() and transcript_path.exists():
        metadata = json.loads(metadata_path.read_text())
        if not (out_dir / "content.md").exists():
            print(f"derived missing {write_content_md(out_dir, metadata)}")
        if not (out_dir / "video_profile.json").exists():
            print(f"derived missing {write_video_profile(out_dir, metadata)}")
        print(f"skip: already exists in {out_dir}")
        return 0

    if not args.url:
        print("error: url required (no existing bundle to self-heal)", file=sys.stderr)
        return 1

    try:
        metadata = fetch_metadata(args.url)
    except Exception as e:
        print(f"error fetching metadata: {e}", file=sys.stderr)
        return 1

    segments = None
    transcript_source = "captions"

    # Step 1: YouTube-specific API (most reliable for YouTube)
    youtube_id = extract_youtube_id(args.url)
    if youtube_id:
        print("trying youtube-transcript-api...", file=sys.stderr)
        segments = try_youtube_transcript_api(youtube_id, args.lang)
        if segments:
            transcript_source = "youtube-transcript-api"

    # Step 2: yt-dlp captions (works for 1000+ sites)
    if not segments:
        print("trying yt-dlp captions...", file=sys.stderr)
        try:
            segments = try_yt_dlp_captions(args.url, out_dir, args.lang)
            if segments:
                transcript_source = "yt-dlp-captions"
        except Exception as e:
            print(f"yt-dlp captions failed ({e})", file=sys.stderr)

    # Step 3: faster-whisper fallback
    if not segments:
        print("no captions found — transcribing with faster-whisper...", file=sys.stderr)
        transcript_source = "whisper"
        try:
            segments = transcribe_with_whisper(args.url, out_dir, args.lang)
        except Exception as e:
            print(f"error transcribing: {e}", file=sys.stderr)
            return 1

    metadata["transcript_source"] = transcript_source
    metadata_path.write_text(json.dumps(metadata, indent=2))
    write_transcript(segments, transcript_path)
    content_path = write_content_md(out_dir, metadata)
    write_video_profile(out_dir, metadata)

    duration = _fmt_time(segments[-1]["end"]) if segments else "?"
    print(f"wrote {transcript_path} ({len(segments)} segments, {duration}, source={transcript_source})")
    print(f"derived {content_path} ({content_path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
