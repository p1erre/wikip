"""
Slide-based video processing pipeline

Specialized pipeline for videos with slides/presentations.
Handles slide extraction, transcript fetching, and vision analysis.
"""

import logging
from typing import Dict, Any, Optional

from src.utils.cache import get_cache
from src.utils.video_input import normalize_video_input
from src.processing.video import get_youtube_transcript, download_youtube_content
from src.processing.slides import extract_slides_robust
from src.processing.vision import analyze_slides_with_vision

logger = logging.getLogger(__name__)


def process_video_with_slides(
    input_source: str,
    force_reprocess: bool = False,
    skip_vision: bool = False,
    vision_provider: Optional[str] = None,
    vision_model: Optional[str] = None,
    cache_dir: str = ".cache"
) -> Dict[str, Any]:
    """
    Complete video processing pipeline with slide extraction and vision analysis.
    
    This pipeline is specialized for videos with slides/presentations.
    It handles:
    1. Input normalization (YouTube URL/ID or local file)
    2. Video download (if YouTube)
    3. Slide extraction with caching
    4. Transcript fetching with caching
    5. Vision analysis of slides with caching
    
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
        >>> # YouTube video with slides
        >>> result = process_video_with_slides("https://youtube.com/watch?v=...")
        >>> 
        >>> # Local presentation video
        >>> result = process_video_with_slides("./my_video.mp4")
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
    
    # Download YouTube video if needed (need actual video for slide extraction, not just audio)
    if video_type == 'youtube' and not video_path:
        logger.info(f"Downloading video file for slide extraction...")
        result = download_youtube_content.func(video_id, download_video=True)
        if not result.get('success'):
            raise RuntimeError(f"Failed to download video: {result.get('error')}")
        video_path = result['file_path']
    
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
                transcript_result = get_youtube_transcript.func(video_id)
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
