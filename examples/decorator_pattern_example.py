"""
Example: Using the Cache Decorator Pattern

This shows how the decorator pattern simplifies tool implementation.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.decorators import cached_metadata, cached_transcript, with_cache_control


# ============================================================================
# BEFORE: Manual cache handling (current approach)
# ============================================================================

def get_video_metadata_old(video_id: str, use_cache: bool = True) -> dict:
    """Old approach - cache logic mixed with business logic."""
    from src.utils.cache import get_cache
    
    # Cache logic clutters the function
    if use_cache:
        cache = get_cache()
        cached = cache.get_metadata(video_id)
        if cached:
            return cached
    
    # Business logic
    result = fetch_metadata_from_api(video_id)
    
    # More cache logic
    if use_cache:
        cache = get_cache()
        cache.save_metadata(video_id, result)
    
    return result


# ============================================================================
# AFTER: Clean separation with decorator (new approach)
# ============================================================================

@cached_metadata
def get_video_metadata_new(video_id: str) -> dict:
    """
    New approach - clean business logic only!
    
    Caching is handled by the decorator.
    """
    # Just implement the core logic
    return fetch_metadata_from_api(video_id)


@cached_transcript
def get_youtube_transcript_new(video_id: str) -> dict:
    """
    Get YouTube transcript with automatic caching.
    
    The decorator handles:
    - Cache checking
    - Source tracking
    - Cache saving
    """
    from youtube_transcript_api import YouTubeTranscriptApi
    
    # Just implement the core logic
    api = YouTubeTranscriptApi()
    transcript_data = api.fetch(video_id)
    
    # Format and return
    segments = [
        {
            "text": snippet.text,
            "start": snippet.start,
            "duration": snippet.duration,
            "end": snippet.start + snippet.duration
        }
        for snippet in transcript_data.snippets
    ]
    
    return {
        "success": True,
        "video_id": video_id,
        "num_segments": len(segments),
        "segments": segments,
        "total_duration": segments[-1]["end"] if segments else 0,
        "source": "youtube"  # Decorator uses this for multi-source caching
    }


# ============================================================================
# OPTIONAL: Add explicit cache control if needed
# ============================================================================

@with_cache_control
@cached_metadata
def get_video_metadata_with_control(video_id: str) -> dict:
    """
    Metadata with explicit cache control parameters.
    
    Usage:
        # Normal - uses cache
        get_video_metadata_with_control("abc123")
        
        # Force refresh
        get_video_metadata_with_control("abc123", force_refresh=True)
        
        # Bypass cache
        get_video_metadata_with_control("abc123", use_cache=False)
    """
    return fetch_metadata_from_api(video_id)


# ============================================================================
# HELPER (mock for example)
# ============================================================================

def fetch_metadata_from_api(video_id: str) -> dict:
    """Mock API call."""
    return {
        "success": True,
        "video_id": video_id,
        "title": "Example Video",
        "duration": 120
    }


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

if __name__ == "__main__":
    import os
    
    print("="*70)
    print("DECORATOR PATTERN EXAMPLE")
    print("="*70)
    print()
    
    # Example 1: Normal use (uses cache)
    print("1. Normal use (uses cache):")
    result = get_video_metadata_new("test123")
    print(f"   Result: {result['title']}")
    print()
    
    # Example 2: Force refresh via environment
    print("2. Force refresh:")
    os.environ['VIDEO_FORCE_REFRESH'] = 'true'
    result = get_video_metadata_new("test123")
    os.environ.pop('VIDEO_FORCE_REFRESH')
    print(f"   Result: {result['title']}")
    print()
    
    # Example 3: With explicit cache control
    print("3. With explicit cache control:")
    result = get_video_metadata_with_control("test123", force_refresh=True)
    print(f"   Result: {result['title']}")
    print()
    
    print("="*70)
    print("BENEFITS:")
    print("="*70)
    print("✅ Clean separation of concerns")
    print("✅ Tools focus on business logic only")
    print("✅ Consistent caching behavior")
    print("✅ Easy to test (mock the cache, not parameters)")
    print("✅ DRY - no repeated cache code")
    print("✅ Flexible - can add cache control when needed")
