"""
Decorators for common functionality.

Provides clean separation of concerns using decorator pattern.
"""

import functools
import logging
from typing import Any, Callable, Optional

from src.utils.cache import get_cache

logger = logging.getLogger(__name__)


def cached(
    cache_key_fn: Callable[..., str],
    cache_type: str,
    source_field: Optional[str] = None
):
    """
    Decorator to add caching to a function.
    
    This implements the Decorator Pattern to separate caching concerns
    from business logic.
    
    Args:
        cache_key_fn: Function to extract cache key from args
                     e.g., lambda video_id, **kwargs: video_id
        cache_type: Type of cache ('metadata', 'transcript', 'audio')
        source_field: Field in result dict that contains the source
                     (for multi-source caching like transcripts)
    
    Example:
        @cached(
            cache_key_fn=lambda video_id, **kwargs: video_id,
            cache_type='metadata'
        )
        def get_video_metadata(video_id: str) -> dict:
            # Just implement the core logic
            return fetch_metadata_from_api(video_id)
    
    Usage:
        # Normal use - uses cache
        result = get_video_metadata("abc123")
        
        # Force refresh - set environment variable
        os.environ['VIDEO_FORCE_REFRESH'] = 'true'
        result = get_video_metadata("abc123")
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import os
            
            # Extract cache key from arguments
            cache_key = cache_key_fn(*args, **kwargs)
            
            # Check environment flags
            bypass_cache = os.getenv('VIDEO_BYPASS_CACHE', 'false').lower() == 'true'
            force_refresh = os.getenv('VIDEO_FORCE_REFRESH', 'false').lower() == 'true'
            
            cache = get_cache()
            
            # Try to get from cache (unless bypassing or forcing refresh)
            if not bypass_cache and not force_refresh:
                cached_result = None
                
                if cache_type == 'metadata':
                    cached_result = cache.get_metadata(cache_key)
                elif cache_type == 'transcript':
                    # For transcripts, check if source is specified
                    source = kwargs.get('source')
                    cached_result = cache.get_transcript(cache_key, source=source)
                elif cache_type == 'audio':
                    cached_result = cache.get_audio_path(cache_key)
                
                if cached_result:
                    logger.info(f"Cache hit for {cache_type}: {cache_key}")
                    return cached_result
            
            # Cache miss or forced refresh - call the actual function
            logger.info(f"Cache miss for {cache_type}: {cache_key}, fetching...")
            result = func(*args, **kwargs)
            
            # Save to cache (unless bypassing)
            if not bypass_cache and result and result.get('success'):
                if cache_type == 'metadata':
                    cache.save_metadata(cache_key, result)
                elif cache_type == 'transcript':
                    # Extract source from result if available
                    source = result.get(source_field) if source_field else None
                    cache.save_transcript(cache_key, result, source=source)
                # Audio caching handled differently (file-based)
                
                logger.info(f"Saved to cache: {cache_type}/{cache_key}")
            
            return result
        
        return wrapper
    return decorator


def with_cache_control(func: Callable) -> Callable:
    """
    Decorator to add cache control parameters to a function.
    
    This adds standard cache control kwargs that can be used
    to override default caching behavior.
    
    Example:
        @with_cache_control
        def get_video_metadata(video_id: str) -> dict:
            return fetch_metadata(video_id)
    
    Usage:
        # Normal use
        result = get_video_metadata("abc123")
        
        # Force refresh
        result = get_video_metadata("abc123", force_refresh=True)
        
        # Bypass cache
        result = get_video_metadata("abc123", use_cache=False)
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        import os
        
        # Extract cache control parameters from kwargs
        use_cache = kwargs.pop('use_cache', True)
        force_refresh = kwargs.pop('force_refresh', False)
        
        # Set environment variables based on parameters
        if not use_cache:
            os.environ['VIDEO_BYPASS_CACHE'] = 'true'
        if force_refresh:
            os.environ['VIDEO_FORCE_REFRESH'] = 'true'
        
        try:
            # Call the function
            result = func(*args, **kwargs)
            return result
        finally:
            # Clean up environment variables
            os.environ.pop('VIDEO_BYPASS_CACHE', None)
            os.environ.pop('VIDEO_FORCE_REFRESH', None)
    
    return wrapper


# Convenience decorators for specific cache types
def cached_metadata(func: Callable) -> Callable:
    """Decorator for metadata caching."""
    return cached(
        cache_key_fn=lambda video_id, **kwargs: video_id,
        cache_type='metadata'
    )(func)


def cached_transcript(func: Callable) -> Callable:
    """Decorator for transcript caching with source tracking."""
    return cached(
        cache_key_fn=lambda video_id, **kwargs: video_id,
        cache_type='transcript',
        source_field='source'
    )(func)
