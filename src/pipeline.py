"""
Complete video-to-content pipeline with caching

Provides a simple API for processing videos (YouTube or local) with automatic caching.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional

from src.utils.cache import get_cache
from src.utils.video_input import normalize_video_input, get_or_download_youtube_video
from src.processing.video import get_youtube_transcript, get_video_metadata
from src.processing.slides import extract_slides_robust
from src.processing.vision import analyze_slides_with_vision
from src.processing.content import generate_booklet_from_transcript, generate_booklet_by_chapters

logger = logging.getLogger(__name__)


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


def generate_booklet(
    input_source: str,
    model: str = "gpt-4o",
    provider: str = "openai",
    temperature: float = 0.7,
    force_reprocess: bool = False,
    use_chapters: bool = True,
    words_per_section: int = 2000,
    cache_dir: str = ".cache"
) -> Dict[str, Any]:
    """
    Generate comprehensive booklet from YouTube video transcript.
    
    Workflow:
    1. Get transcript from YouTube (cached)
    2. Get video metadata (for chapters if available)
    3. Generate booklet using chapter-based or single-pass approach (cached)
    4. Return booklet content
    
    Chapter-based generation (recommended):
    - Processes each chapter/section independently
    - Produces more detailed, comprehensive output
    - Better for long videos (30+ minutes)
    - Each section gets ~2000 words of detailed content
    
    Args:
        input_source: YouTube URL or video ID
        model: LLM model to use (default: gpt-4o)
        provider: LLM provider ('openai', 'anthropic', 'openrouter')
        temperature: LLM temperature for creative writing (default: 0.7)
        force_reprocess: If True, regenerate even if cached
        use_chapters: If True, use chapter-based generation (default: True, recommended)
        words_per_section: Target words per section for chapter-based (default: 2000)
        cache_dir: Cache directory
        
    Returns:
        Dict with:
            - success: bool
            - booklet: str (markdown content)
            - video_id: str
            - video_title: str
            - from_cache: dict (what was loaded from cache)
            - model: str (model used)
            - num_sections: int (if chapter-based)
            
    Example:
        >>> # Chapter-based (recommended for long videos)
        >>> result = generate_booklet("https://youtube.com/watch?v=...", use_chapters=True)
        >>> 
        >>> # Single-pass (faster, less detailed)
        >>> result = generate_booklet("https://youtube.com/watch?v=...", use_chapters=False)
        >>> 
        >>> # Save to file
        >>> Path("booklet.md").write_text(result['booklet'])
    """
    logger.info("=" * 80)
    logger.info(f"🚀 BOOKLET GENERATION PIPELINE")
    logger.info("=" * 80)
    logger.info(f"Input: {input_source}")
    logger.info(f"Mode: {'Chapter-based' if use_chapters else 'Single-pass'}")
    logger.info(f"Model: {provider}/{model}")
    logger.info("")
    
    cache = get_cache(cache_dir)
    from_cache = {
        'transcript': False,
        'booklet': False,
    }
    
    # ========================================================================
    # STEP 1: Normalize input and get video ID
    # ========================================================================
    
    logger.info("STEP 1: Normalizing input...")
    video_id, video_path, video_type = normalize_video_input(input_source)
    logger.info(f"   Video ID: {video_id}")
    logger.info(f"   Type: {video_type}")
    logger.info("")
    
    if video_type != 'youtube':
        return {
            "success": False,
            "error": "Only YouTube videos are supported for booklet generation",
            "video_id": video_id,
        }
    
    # ========================================================================
    # STEP 2: Get transcript (with caching)
    # ========================================================================
    
    logger.info("STEP 2: Getting transcript...")
    transcript = None
    video_title = f"Video {video_id}"
    
    if not force_reprocess:
        transcript = cache.get_transcript(video_id)
        if transcript:
            num_segments = len(transcript.get('segments', []))
            logger.info(f"   ✅ Using cached transcript ({num_segments} segments)")
            from_cache['transcript'] = True
    
    if not transcript:
        logger.info("   Fetching from YouTube...")
        try:
            transcript_result = get_youtube_transcript.func(video_id)
            if transcript_result.get('success'):
                # The result IS the transcript (has 'segments' key)
                transcript = transcript_result
                cache.save_transcript(video_id, transcript)
                num_segments = len(transcript.get('segments', []))
                logger.info(f"   ✅ Fetched transcript ({num_segments} segments)")
            else:
                logger.error("   ❌ No transcript available")
                return {
                    "success": False,
                    "error": "No transcript available for this video",
                    "video_id": video_id,
                }
        except Exception as e:
            logger.error(f"   ❌ Failed to get transcript: {e}")
            return {
                "success": False,
                "error": f"Failed to get transcript: {e}",
                "video_id": video_id,
            }
    
    logger.info("")
    
    # Get video metadata (for title and chapters)
    logger.info("STEP 3: Getting video metadata...")
    metadata = cache.get_metadata(video_id)
    if not metadata and not force_reprocess:
        # Try to fetch metadata
        logger.info("   Fetching from YouTube...")
        try:
            metadata_result = get_video_metadata.func(video_id)
            if metadata_result.get('success'):
                metadata = metadata_result
                cache.save_metadata(video_id, metadata)
                logger.info(f"   ✅ Got metadata")
        except Exception as e:
            logger.warning(f"   ⚠️  Could not fetch metadata: {e}")
    elif metadata:
        logger.info("   ✅ Using cached metadata")
    
    if metadata:
        video_title = metadata.get('title', video_title)
        has_chapters = 'chapters' in metadata and metadata['chapters']
        if has_chapters:
            logger.info(f"   Video has {len(metadata['chapters'])} chapters")
    
    logger.info("")
    
    # ========================================================================
    # STEP 4: Generate booklet (with caching)
    # ========================================================================
    
    logger.info("STEP 4: Generating booklet...")
    
    # Create model key for cache (include chapter mode)
    cache_suffix = "chapters" if use_chapters else "single"
    model_key = f"{provider}_{model.replace('/', '_')}_{cache_suffix}"
    booklet_content = None
    num_sections = None
    
    if not force_reprocess:
        # Try to load from cache
        booklet_data = cache.get_booklet(video_id, model_key)
        if booklet_data:
            logger.info(f"   ✅ Using cached booklet")
            from_cache['booklet'] = True
            booklet_content = booklet_data['content']
            num_sections = booklet_data.get('num_sections')
    
    if not booklet_content:
        video_url = f"https://youtube.com/watch?v={video_id}"
        
        if use_chapters:
            # Chapter-based generation (recommended)
            logger.info(f"   Using chapter-based generation...")
            logger.info("")
            
            # Get chapters from metadata or create intelligently
            if metadata and metadata.get('chapters'):
                logger.info(f"   Using {len(metadata['chapters'])} chapters from video metadata")
                chapters = metadata['chapters']
            else:
                # Create chapters intelligently (semantic with fallback)
                from src.processing.content import create_chapters
                chapters = create_chapters(
                    transcript,
                    strategy="auto",  # Tries semantic, falls back to time-based
                    model="gpt-4o-mini",  # Fast and cheap for chapter detection
                    provider=provider,
                )
            
            result = generate_booklet_by_chapters(
                transcript=transcript,
                video_title=video_title,
                video_url=video_url,
                chapters=chapters,
                model=model,
                provider=provider,
                temperature=temperature,
                words_per_section=words_per_section,
            )
        else:
            # Single-pass generation (faster, less detailed)
            logger.info(f"   Using single-pass generation...")
            
            result = generate_booklet_from_transcript(
                transcript=transcript,
                video_title=video_title,
                video_url=video_url,
                model=model,
                provider=provider,
                temperature=temperature,
            )
        
        if not result.get('success'):
            logger.error(f"   ❌ Generation failed: {result.get('error')}")
            return {
                "success": False,
                "error": result.get('error', 'Unknown error'),
                "video_id": video_id,
            }
        
        booklet_content = result['content']
        num_sections = result.get('num_sections')
        
        # Cache the booklet under video directory
        logger.info("")
        logger.info("   💾 Caching booklet...")
        cache.save_booklet(video_id, model_key, {
            'content': booklet_content,
            'model': result['model'],
            'video_id': video_id,
            'video_title': video_title,
            'num_sections': num_sections,
            'use_chapters': use_chapters,
        })
    
    # ========================================================================
    # RETURN RESULT
    # ========================================================================
    
    logger.info("✅ Pipeline complete!")
    
    result = {
        "success": True,
        "booklet": booklet_content,
        "video_id": video_id,
        "video_title": video_title,
        "video_url": f"https://youtube.com/watch?v={video_id}",
        "from_cache": from_cache,
        "model": f"{provider}/{model}",
        "length": len(booklet_content),
        "use_chapters": use_chapters,
    }
    
    if num_sections is not None:
        result["num_sections"] = num_sections
    
    return result
