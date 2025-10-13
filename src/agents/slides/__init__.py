"""
Slides Extraction Agent

This module provides tools for extracting and analyzing slides from presentation videos.

Components:
- extract_slides: Extract unique slides from video using frame extraction and change detection
- analyze_slide_content: Extract text from slides using OCR
- align_slides_with_transcript: Match slides to transcript segments by timestamp

Usage:
    from src.agents.slides import extract_slides, analyze_slide_content
    
    # Extract slides from video
    slides = extract_slides(video_path, output_dir="./slides")
    
    # Analyze slide content
    for slide in slides:
        content = analyze_slide_content(slide['image_path'])
"""

from src.agents.slides.tools import (
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
