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

from src.processing.video.workflow import (
    analyze_video_workflow,
    get_transcript,
    analyze_video,
)

__all__ = [
    # YouTube operations
    "extract_video_id_from_url",
    "get_video_metadata",
    "get_youtube_transcript",
    "download_youtube_content",
    "generate_transcript_from_audio",
    # Workflows
    "analyze_video_workflow",
    "get_transcript",
    "analyze_video",
]
