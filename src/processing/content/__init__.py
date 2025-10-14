"""
Content generation processing

Simple LLM-based content generation without agents.
Direct API calls for generating booklets, summaries, etc.
"""

from src.processing.content.generation import (
    generate_booklet_from_transcript,
    format_transcript_for_llm,
)

from src.processing.content.chapters import (
    generate_booklet_by_chapters,
    create_chapters,  # Main API
    auto_create_chapters,  # Deprecated, kept for backward compatibility
    extract_chapter_transcript,
)

__all__ = [
    "generate_booklet_from_transcript",
    "generate_booklet_by_chapters",
    "format_transcript_for_llm",
    "create_chapters",  # ← Main API for chapter creation
    "auto_create_chapters",  # Deprecated
    "extract_chapter_transcript",
]
