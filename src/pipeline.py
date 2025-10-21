"""
Main pipeline API - backward compatible wrapper

This module provides a unified API for all video processing pipelines.
Imports are delegated to specialized pipeline modules for better organization.
"""

import logging
from typing import Dict, Any

# Import pipelines from specialized modules
from src.slides_pipeline import process_video_with_slides
from src.transcript_pipeline import transcript_to_booklet

# Import utilities
from src.utils.cache import get_cache
from src.utils.video_input import normalize_video_input

logger = logging.getLogger(__name__)


def clear_video_cache(input_source: str, cache_dir: str = ".cache") -> None:
    """
    Clear all cached data for a video.
    
    Args:
        input_source: YouTube URL/ID or local video file path
        cache_dir: Cache directory
    """
    cache = get_cache(cache_dir)
    video_id, _, _ = normalize_video_input(input_source)
    
    logger.info(f"Clearing cache for: {video_id}")
    cache.clear_video(video_id)
    logger.info("✅ Cache cleared")


def get_cache_info(cache_dir: str = ".cache") -> Dict[str, Any]:
    """
    Get cache statistics.
    
    Args:
        cache_dir: Cache directory
        
    Returns:
        Dict with cache information
    """
    cache = get_cache(cache_dir)
    return cache.get_cache_info()


# Export all public APIs
__all__ = [
    'process_video_with_slides',
    'transcript_to_booklet',
    'clear_video_cache',
    'get_cache_info',
]
