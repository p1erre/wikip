"""
Transcript-based booklet generation pipeline

Generates educational booklets from YouTube video transcripts.
Does NOT process slides or use vision analysis.
"""

import logging
from pathlib import Path
from typing import Dict, Any

from src.utils.cache import get_cache
from src.utils.video_input import normalize_video_input
from src.processing.video import get_youtube_transcript, get_video_metadata
from src.processing.content import generate_booklet_from_transcript, generate_booklet_by_chapters

logger = logging.getLogger(__name__)


def transcript_to_booklet(
    input_source: str,
    model: str = "gpt-4o",
    provider: str = "openai",
    temperature: float = 0.5,
    use_chapters: bool = True,
    words_per_section: int = 2000,
    parallel: bool = False,
    # Cache control (explicit and clear)
    use_cached_transcript: bool = True,
    use_cached_metadata: bool = True,
    use_cached_booklet: bool = True,
    cache_dir: str = ".cache"
) -> Dict[str, Any]:
    """
    Generate comprehensive booklet from YouTube video transcript only (no slides).
    
    This pipeline generates text-based booklets from video transcripts.
    It does NOT process slides or use vision analysis.
    
    Workflow:
    1. Get transcript from YouTube (cached)
    2. Get video metadata (for chapters if available)
    3. Generate booklet using chapter-based or single-pass approach (cached)
    4. Return booklet content
    
    Chapter-based generation (recommended):
    - Processes each chapter/section with context from previous chapters
    - Produces more detailed, comprehensive output
    - Better for long videos (30+ minutes)
    - Each section gets ~2000 words of detailed content
    - Maintains concept continuity and consistent terminology
    
    Args:
        input_source: YouTube URL or video ID
        model: LLM model to use (default: gpt-4o)
        provider: LLM provider ('openai', 'anthropic', 'openrouter')
        temperature: LLM temperature for content generation (default: 0.5, balanced consistency/creativity)
        use_chapters: If True, use chapter-based generation (default: True, recommended)
        words_per_section: Target words per section for chapter-based (default: 2000)
        parallel: If True, generate chapters in parallel (faster but no context)
                  If False, generate sequentially with context (default: False, recommended)
        use_cached_transcript: If True, use cached transcript if available (default: True)
        use_cached_metadata: If True, use cached metadata if available (default: True)
        use_cached_booklet: If True, use cached booklet if available (default: True)
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
        >>> # Chapter-based with context (recommended for long videos)
        >>> result = transcript_to_booklet("https://youtube.com/watch?v=...")
        >>> 
        >>> # Regenerate only booklet (keep cached transcript/metadata)
        >>> result = transcript_to_booklet("https://youtube.com/watch?v=...", use_cached_booklet=False)
        >>> 
        >>> # Regenerate everything
        >>> result = transcript_to_booklet(
        ...     "https://youtube.com/watch?v=...",
        ...     use_cached_transcript=False,
        ...     use_cached_metadata=False,
        ...     use_cached_booklet=False
        ... )
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
    
    if use_cached_transcript:
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
    metadata = None
    if use_cached_metadata:
        metadata = cache.get_metadata(video_id)
        if metadata:
            logger.info("   ✅ Using cached metadata")
    
    if not metadata:
        # Fetch metadata from YouTube
        logger.info("   Fetching from YouTube...")
        try:
            metadata_result = get_video_metadata.func(video_id)
            if metadata_result.get('success'):
                metadata = metadata_result
                cache.save_metadata(video_id, metadata)
                logger.info(f"   ✅ Got metadata")
        except Exception as e:
            logger.warning(f"   ⚠️  Could not fetch metadata: {e}")
    
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
    
    if use_cached_booklet:
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
                parallel=parallel,
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
