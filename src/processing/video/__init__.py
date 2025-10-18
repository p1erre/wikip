"""
Video processing functions

Handles YouTube video operations:
- URL parsing and video ID extraction
- Metadata fetching
- Transcript retrieval
- Video/audio downloading
- Transcript generation (Whisper)
"""

from src.processing.video.youtube import (
    extract_video_id_from_url,
    get_video_metadata,
    get_youtube_transcript,
    download_youtube_content,
    generate_transcript_from_audio,
)

__all__ = [
    "extract_video_id_from_url",
    "get_video_metadata",
    "get_youtube_transcript",
    "download_youtube_content",
    "generate_transcript_from_audio",
]
