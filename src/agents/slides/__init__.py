"""
Slides Extraction Agent

This module provides tools for extracting and analyzing slides from presentation videos.

Components:
- extract_slides: Extract unique slides from video using frame extraction and change detection
- extract_slides_robust: Advanced slide extraction with progressive reveal detection
- analyze_slide_content: Extract text from slides using OCR
- align_slides_with_transcript: Match slides to transcript segments by timestamp
- SlideVisionAnalyzer: Analyze slides using vision LLMs (Gemini, GPT-4V)
- analyze_slides_with_vision: Convenience function for vision-based slide analysis

Usage:
    from src.agents.slides import extract_slides_robust, analyze_slides_with_vision
    
    # Extract slides from video
    slides = extract_slides_robust.func(video_path, output_dir="./slides")
    
    # Analyze with vision LLM
    enriched = analyze_slides_with_vision(slides, provider='openrouter', model='openai/gpt-4o')
"""

from src.agents.slides.tools import (
    extract_video_frames,
    detect_slide_changes,
    extract_slides,
    extract_slides_robust,
    analyze_slide_content,
    align_slides_with_transcript,
)

from src.agents.slides.vision_analyzer import (
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
