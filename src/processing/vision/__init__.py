"""
Vision-based slide analysis

Uses vision LLMs to analyze slide content:
- Gemini 1.5 Flash
- GPT-4 Vision
- OpenRouter models
"""

from src.processing.vision.analyzer import (
    SlideVisionAnalyzer,
    analyze_slides_with_vision,
)

__all__ = [
    "SlideVisionAnalyzer",
    "analyze_slides_with_vision",
]
