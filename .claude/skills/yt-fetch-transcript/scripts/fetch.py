#!/usr/bin/env python3
"""
Fetch YouTube transcript and metadata.

Usage: fetch.py <url-or-id> --out-dir <dir>

Writes:
  <out-dir>/transcript.txt   plain text with [mm:ss] timestamps
  <out-dir>/metadata.json    title, channel, duration, native chapters

Exit codes:
  0  success
  2  no captions available (caller should suggest /transcribe-audio)
  1  any other failure
"""

import argparse
import json
import re
import sys
from pathlib import Path


YOUTUBE_ID_PATTERNS = [
    r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
    r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
    r'youtube\.com/v/([a-zA-Z0-9_-]{11})',
]


def extract_video_id(url_or_id: str) -> str:
    if len(url_or_id) == 11 and re.fullmatch(r'[a-zA-Z0-9_-]{11}', url_or_id):
        return url_or_id
    for pattern in YOUTUBE_ID_PATTERNS:
        m = re.search(pattern, url_or_id)
        if m:
            return m.group(1)
    raise ValueError(f"could not extract video id from: {url_or_id}")


def fetch_metadata(video_id: str) -> dict:
    import yt_dlp

    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
        info = ydl.extract_info(
            f"https://www.youtube.com/watch?v={video_id}",
            download=False,
        )

    return {
        "video_id": video_id,
        "title": info.get("title"),
        "channel": info.get("uploader"),
        "duration": info.get("duration"),
        "upload_date": info.get("upload_date"),
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "chapters": info.get("chapters") or [],
        "has_subtitles": bool(info.get("subtitles")),
        "has_automatic_captions": bool(info.get("automatic_captions")),
    }


def fetch_transcript(video_id: str) -> list[dict]:
    from youtube_transcript_api import YouTubeTranscriptApi

    api = YouTubeTranscriptApi()
    raw = api.fetch(video_id)
    return [
        {
            "text": seg.text,
            "start": seg.start,
            "duration": seg.duration,
            "end": seg.start + seg.duration,
        }
        for seg in raw
    ]


def format_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def write_transcript_text(segments: list[dict], path: Path) -> None:
    with path.open("w") as f:
        for seg in segments:
            f.write(f"[{format_timestamp(seg['start'])}] {seg['text'].strip()}\n")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", help="YouTube URL or 11-char video ID")
    p.add_argument("--out-dir", required=True, help="Output directory")
    args = p.parse_args()

    try:
        video_id = extract_video_id(args.source)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    metadata_path = out_dir / "metadata.json"
    transcript_path = out_dir / "transcript.txt"

    if metadata_path.exists() and transcript_path.exists():
        print(f"skip: {metadata_path} and {transcript_path} already exist")
        return 0

    try:
        metadata = fetch_metadata(video_id)
    except Exception as e:
        print(f"error fetching metadata: {e}", file=sys.stderr)
        return 1

    try:
        segments = fetch_transcript(video_id)
    except Exception as e:
        msg = str(e).lower()
        if "transcript" in msg and ("disabled" in msg or "not available" in msg or "no transcript" in msg):
            print(f"no captions available for {video_id}", file=sys.stderr)
            print("suggestion: use /transcribe-audio to generate one from the audio", file=sys.stderr)
            return 2
        print(f"error fetching transcript: {e}", file=sys.stderr)
        return 2  # treat as no-captions; caller can decide

    metadata_path.write_text(json.dumps(metadata, indent=2))
    write_transcript_text(segments, transcript_path)

    print(f"wrote {metadata_path} ({metadata.get('title', '?')})")
    print(f"wrote {transcript_path} ({len(segments)} segments, {format_timestamp(segments[-1]['end'])} duration)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
