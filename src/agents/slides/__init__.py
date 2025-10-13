"""
Slides Processing Module (Legacy)

This module re-exports slide processing functions for backward compatibility.
New code should import from src.processing.slides and src.processing.vision instead.

Usage (legacy):
    from src.agents.slides import extract_slides_robust, analyze_slides_with_vision
    
Usage (new):
    from src.processing.slides import extract_slides_robust
    from src.processing.vision import analyze_slides_with_vision
"""

# Re-export from processing modules for backward compatibility
from src.processing.slides import (
    extract_video_frames,
    detect_slide_changes,
    extract_slides,
    extract_slides_robust,
    analyze_slide_content,
    align_slides_with_transcript,
)

from src.processing.vision import (
    SlideVisionAnalyzer,
    analyze_slides_with_vision,
)

__all__ = [
    "extract_video_frames",
    "detect_slide_changes",
    "extract_slides",
    "extract_slides_robust",
    "analyze_slide_content",
    "align_slides_with_transcript",
    "SlideVisionAnalyzer",
    "analyze_slides_with_vision",
]
