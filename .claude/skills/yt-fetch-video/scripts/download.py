#!/usr/bin/env python3
"""
Download a YouTube video as MP4.

Usage: download.py <url-or-id> --out-dir <dir>

Writes <out-dir>/video.mp4. Idempotent: skips if file exists and non-empty.
"""

import argparse
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


def download_video(video_id: str, out_path: Path) -> None:
    import yt_dlp

    out_path.parent.mkdir(parents=True, exist_ok=True)
    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "outtmpl": str(out_path.with_suffix("")) + ".%(ext)s",
        "quiet": False,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f"https://www.youtube.com/watch?v={video_id}"])


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
    out_path = out_dir / "video.mp4"

    if out_path.exists() and out_path.stat().st_size > 0:
        size_mb = out_path.stat().st_size / (1024 * 1024)
        print(f"skip: {out_path} already exists ({size_mb:.1f} MB)")
        return 0

    try:
        download_video(video_id, out_path)
    except Exception as e:
        print(f"error downloading video: {e}", file=sys.stderr)
        return 1

    if not out_path.exists():
        candidates = list(out_dir.glob("video.*"))
        if candidates:
            candidates[0].rename(out_path)

    if not out_path.exists() or out_path.stat().st_size == 0:
        print(f"error: download did not produce {out_path}", file=sys.stderr)
        return 1

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"wrote {out_path} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
