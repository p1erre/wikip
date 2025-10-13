"""
Slide extraction and processing

Handles slide detection and extraction from presentation videos:
- Frame extraction
- Slide change detection
- Progressive reveal detection
- OCR and text extraction
- Transcript alignment
"""

from src.processing.slides.extraction import (
    extract_video_frames,
    detect_slide_changes,
    extract_slides,
    extract_slides_robust,
    analyze_slide_content,
    align_slides_with_transcript,
)

__all__ = [
    "extract_video_frames",
    "detect_slide_changes",
    "extract_slides",
    "extract_slides_robust",
    "analyze_slide_content",
    "align_slides_with_transcript",
]
