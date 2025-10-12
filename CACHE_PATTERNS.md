# Cache Patterns Comparison

## Problem

How to add caching to tools without cluttering the business logic?

## Current Approach (Manual)

```python
def get_video_metadata(video_id: str, use_cache: bool = True) -> dict:
    """Get metadata with manual cache handling."""
    
    # ❌ Cache logic mixed with business logic
    if use_cache:
        cache = get_cache()
        cached = cache.get_metadata(video_id)
        if cached:
            return cached
    
    # ✅ Business logic
    import yt_dlp
    ydl_opts = {'quiet': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"https://youtube.com/watch?v={video_id}", download=False)
        result = {
            "success": True,
            "video_id": video_id,
            "title": info.get("title"),
            # ...
        }
    
    # ❌ More cache logic
    if use_cache:
        cache = get_cache()
        cache.save_metadata(video_id, result)
    
    return result
```

**Problems**:
- ❌ Cache logic clutters the function
- ❌ Repeated in every tool
- ❌ Hard to change caching strategy
- ❌ Violates Single Responsibility Principle

## Solution: Decorator Pattern ✨

### Basic Decorator

```python
from src.utils.decorators import cached_metadata

@cached_metadata
def get_video_metadata(video_id: str) -> dict:
    """Get metadata - caching handled by decorator!"""
    
    # ✅ Only business logic - clean and focused
    import yt_dlp
    ydl_opts = {'quiet': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"https://youtube.com/watch?v={video_id}", download=False)
        return {
            "success": True,
            "video_id": video_id,
            "title": info.get("title"),
            # ...
        }
```

**Benefits**:
- ✅ Clean separation of concerns
- ✅ No repeated cache code
- ✅ Easy to test
- ✅ Follows Single Responsibility Principle
- ✅ Consistent behavior across all tools

### With Cache Control (Optional)

```python
from src.utils.decorators import cached_metadata, with_cache_control

@with_cache_control
@cached_metadata
def get_video_metadata(video_id: str) -> dict:
    """Metadata with explicit cache control."""
    # Business logic only
    return fetch_metadata(video_id)

# Usage:
result = get_video_metadata("abc123")  # Uses cache
result = get_video_metadata("abc123", force_refresh=True)  # Force refresh
result = get_video_metadata("abc123", use_cache=False)  # Bypass cache
```

## Cache Control Methods

### Method 1: Environment Variables (Recommended)

```python
import os

# Force refresh for all calls
os.environ['VIDEO_FORCE_REFRESH'] = 'true'
result = get_video_metadata("abc123")
os.environ.pop('VIDEO_FORCE_REFRESH')

# Bypass cache
os.environ['VIDEO_BYPASS_CACHE'] = 'true'
result = get_video_metadata("abc123")
os.environ.pop('VIDEO_BYPASS_CACHE')
```

**Best for**: CLI flags, global settings

### Method 2: Function Parameters

```python
@with_cache_control
@cached_metadata
def get_video_metadata(video_id: str) -> dict:
    return fetch_metadata(video_id)

# Usage
result = get_video_metadata("abc123", force_refresh=True)
```

**Best for**: Programmatic control, specific calls

### Method 3: CLI Flags

```bash
# Normal use
./vtb tools get-metadata abc123

# Force refresh
./vtb tools get-metadata abc123 --refresh-cache

# Bypass cache
./vtb tools get-metadata abc123 --no-cache
```

**Best for**: End users, command-line usage

## Implementation

### 1. Create Decorators

```python
# src/utils/decorators.py

def cached(cache_key_fn, cache_type, source_field=None):
    """Generic caching decorator."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Extract cache key
            cache_key = cache_key_fn(*args, **kwargs)
            
            # Check environment flags
            bypass = os.getenv('VIDEO_BYPASS_CACHE') == 'true'
            refresh = os.getenv('VIDEO_FORCE_REFRESH') == 'true'
            
            # Try cache (unless bypassing/refreshing)
            if not bypass and not refresh:
                cached = get_from_cache(cache_key, cache_type)
                if cached:
                    return cached
            
            # Call function
            result = func(*args, **kwargs)
            
            # Save to cache (unless bypassing)
            if not bypass:
                save_to_cache(cache_key, result, cache_type)
            
            return result
        return wrapper
    return decorator

# Convenience decorators
cached_metadata = cached(
    cache_key_fn=lambda video_id, **kw: video_id,
    cache_type='metadata'
)

cached_transcript = cached(
    cache_key_fn=lambda video_id, **kw: video_id,
    cache_type='transcript',
    source_field='source'
)
```

### 2. Apply to Tools

```python
# src/agents/video/tools.py

from src.utils.decorators import cached_metadata, cached_transcript

@tool(args_schema=VideoIDInput)
@cached_metadata
def get_video_metadata(video_id: str) -> dict:
    """Get metadata - clean business logic only!"""
    import yt_dlp
    # ... just the core logic
    return result

@tool(args_schema=VideoIDInput)
@cached_transcript
def get_youtube_transcript(video_id: str) -> dict:
    """Get transcript - caching handled automatically!"""
    from youtube_transcript_api import YouTubeTranscriptApi
    # ... just the core logic
    return result
```

### 3. Add CLI Flags

```python
# src/cli/runner.py

parser.add_argument('--no-cache', action='store_true')
parser.add_argument('--refresh-cache', action='store_true')

def cmd_get_metadata(args):
    if args.no_cache:
        os.environ['VIDEO_BYPASS_CACHE'] = 'true'
    if args.refresh_cache:
        os.environ['VIDEO_FORCE_REFRESH'] = 'true'
    
    result = get_video_metadata.invoke({"video_id": args.video_id})
    
    # Cleanup
    os.environ.pop('VIDEO_BYPASS_CACHE', None)
    os.environ.pop('VIDEO_FORCE_REFRESH', None)
```

## Comparison

| Aspect | Manual | Decorator |
|--------|--------|-----------|
| **Code clarity** | ❌ Cluttered | ✅ Clean |
| **DRY** | ❌ Repeated | ✅ Reusable |
| **Testing** | ❌ Complex | ✅ Simple |
| **Consistency** | ❌ Varies | ✅ Uniform |
| **Flexibility** | ⚠️ Medium | ✅ High |
| **Maintenance** | ❌ Hard | ✅ Easy |

## Migration Path

### Step 1: Add Decorators (Non-Breaking)

```python
# Keep old signature, add decorator
@cached_metadata
def get_video_metadata(video_id: str, use_cache: bool = True) -> dict:
    # Decorator handles caching, parameter ignored
    return fetch_metadata(video_id)
```

### Step 2: Deprecate Parameters

```python
@cached_metadata
def get_video_metadata(video_id: str, use_cache: bool = None) -> dict:
    if use_cache is not None:
        warnings.warn("use_cache parameter is deprecated", DeprecationWarning)
    return fetch_metadata(video_id)
```

### Step 3: Remove Parameters

```python
@cached_metadata
def get_video_metadata(video_id: str) -> dict:
    return fetch_metadata(video_id)
```

## Recommendation

**Use the Decorator Pattern** because:

1. ✅ **Clean Code** - Tools focus on business logic
2. ✅ **DRY** - No repeated cache code
3. ✅ **Flexible** - Easy to add cache control when needed
4. ✅ **Testable** - Mock the cache, not parameters
5. ✅ **Maintainable** - Change caching strategy in one place
6. ✅ **Consistent** - All tools behave the same way

This follows SOLID principles and makes the codebase more maintainable! 🎯
