"""
Complete video-to-content pipeline with caching

Provides a simple API for processing videos (YouTube or local) with automatic caching.
"""

import logging
import importlib
from pathlib import Path
from typing import Dict, Any, Optional

from src.utils.cache import get_cache
from src.utils.video_input import normalize_video_input, get_or_download_youtube_video
from src.agents.slides import extract_slides_robust, analyze_slides_with_vision

logger = logging.getLogger(__name__)

# Lazy load video tools to avoid importing agent
_video_tools = None

def _get_video_tools():
    """Lazy load video tools module"""
    global _video_tools
    if _video_tools is None:
        _video_tools = importlib.import_module('src.agents.video.tools')
    return _video_tools


def process_video(
    input_source: str,
    force_reprocess: bool = False,
    skip_vision: bool = False,
    vision_provider: Optional[str] = None,
    vision_model: Optional[str] = None,
    cache_dir: str = ".cache"
) -> Dict[str, Any]:
    """
    Complete video processing pipeline with automatic caching.
    
    This function handles:
    1. Input normalization (YouTube URL/ID or local file)
    2. Video download (if YouTube)
    3. Slide extraction with caching
    4. Transcript fetching with caching
    5. Vision analysis with caching
    
    Args:
        input_source: YouTube URL/ID or local video file path
        force_reprocess: Skip cache and reprocess everything
        skip_vision: Skip vision analysis (faster, cheaper)
        vision_provider: Vision model provider ('google', 'openai', 'openrouter')
        vision_model: Vision model name
        cache_dir: Cache directory (default: .cache)
        
    Returns:
        Dict with:
            - video_id: Unique video identifier
            - video_type: 'youtube' or 'local'
            - video_path: Path to video file
            - slides: Slides extraction result
            - transcript: Transcript data (if available)
            - vision_analysis: Vision analysis result (if not skipped)
            - from_cache: Dict indicating what was loaded from cache
            
    Raises:
        ValueError: If input is invalid
        RuntimeError: If processing fails
        
    Example:
        >>> # YouTube video
        >>> result = process_video("https://youtube.com/watch?v=...")
        >>> 
        >>> # Local file
        >>> result = process_video("./my_video.mp4")
        >>> 
        >>> # Access results
        >>> slides = result['slides']
        >>> transcript = result['transcript']
        >>> vision = result['vision_analysis']
    """
    cache = get_cache(cache_dir)
    
    # Normalize input
    logger.info(f"Processing video: {input_source}")
    video_id, video_path, video_type = normalize_video_input(input_source)
    
    # Download YouTube video if needed
    if video_type == 'youtube' and not video_path:
        video_path = get_or_download_youtube_video(video_id, cache_dir)
    
    logger.info(f"Video ID: {video_id}")
    logger.info(f"Video type: {video_type}")
    logger.info(f"Video path: {video_path}")
    
    # Track what comes from cache
    from_cache = {
        'slides': False,
        'transcript': False,
        'vision_analysis': False
    }
    
    # ========================================================================
    # SLIDES EXTRACTION
    # ========================================================================
    
    slides = None
    if not force_reprocess:
        slides = cache.get_slides(video_id)
        if slides:
            logger.info("✅ Using cached slides")
            from_cache['slides'] = True
    
    if not slides:
        logger.info("🔄 Extracting slides from video...")
        slides_dir = cache.get_slides_dir(video_id)
        
        slides = extract_slides_robust.func(
            video_path=video_path,
            output_dir=str(slides_dir),
            fps_sample=2.0,
            build_policy="build_collapse",
            save_keyframes=True,
        )
        
        if not slides.get('success'):
            raise RuntimeError(f"Slide extraction failed: {slides.get('error')}")
        
        # Cache the slides
        cache.save_slides(video_id, slides)
        logger.info(f"✅ Extracted {slides['num_unique_slides']} slides")
    
    # ========================================================================
    # TRANSCRIPT
    # ========================================================================
    
    transcript = None
    if video_type == 'youtube':
        if not force_reprocess:
            transcript = cache.get_transcript(video_id)
            if transcript:
                logger.info("✅ Using cached transcript")
                from_cache['transcript'] = True
        
        if not transcript:
            logger.info("🔄 Fetching YouTube transcript...")
            try:
                video_tools = _get_video_tools()
                transcript_result = video_tools.get_youtube_transcript(video_id)
                if transcript_result.get('success'):
                    transcript = transcript_result['transcript']
                    cache.save_transcript(video_id, transcript)
                    logger.info("✅ Fetched transcript")
                else:
                    logger.warning("⚠️  No transcript available")
            except Exception as e:
                logger.warning(f"⚠️  Could not fetch transcript: {e}")
    
    # ========================================================================
    # VISION ANALYSIS
    # ========================================================================
    
    vision_analysis = None
    if not skip_vision:
        if not force_reprocess:
            vision_analysis = cache.get_vision_analysis(video_id)
            if vision_analysis:
                logger.info("✅ Using cached vision analysis")
                from_cache['vision_analysis'] = True
        
        if not vision_analysis:
            logger.info("🔄 Analyzing slides with vision LLM...")
            vision_analysis = analyze_slides_with_vision(
                slides_result=slides,
                transcript=transcript,
                provider=vision_provider,
                model=vision_model,
            )
            
            # Cache the vision analysis
            cache.save_vision_analysis(
                video_id,
                vision_analysis,
                metadata={
                    'video_id': video_id,
                    'num_slides': len(vision_analysis),
                    'provider': vision_provider,
                    'model': vision_model
                }
            )
            logger.info(f"✅ Analyzed {len(vision_analysis)} slides")
    
    # ========================================================================
    # RETURN RESULTS
    # ========================================================================
    
    logger.info("✅ Processing complete!")
    
    return {
        'video_id': video_id,
        'video_type': video_type,
        'video_path': video_path,
        'slides': slides,
        'transcript': transcript,
        'vision_analysis': vision_analysis,
        'from_cache': from_cache,
        'cache_dir': cache_dir
    }


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
