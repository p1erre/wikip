# Pipeline Module Separation

## Overview

Refactored the monolithic `src/pipeline.py` (520 lines) into three specialized modules for better organization and maintainability.

## New Structure

```
src/
├── pipeline.py              # Main API (60 lines) - backward compatible wrapper
├── slides_pipeline.py       # Slide processing (200 lines)
└── transcript_pipeline.py   # Transcript processing (300 lines)
```

## Modules

### 1. `src/pipeline.py` - Main API

**Purpose:** Thin wrapper that maintains backward compatibility

**Contents:**
- Imports from specialized modules
- Utility functions: `clear_video_cache()`, `get_cache_info()`
- `__all__` export list

**Size:** ~60 lines (was 520 lines)

```python
from src.slides_pipeline import process_video_with_slides
from src.transcript_pipeline import transcript_to_booklet
```

### 2. `src/slides_pipeline.py` - Slide Processing

**Purpose:** Process videos with slides/presentations

**Function:** `process_video_with_slides()`

**What it does:**
1. Downloads video file (full video, not just audio)
2. Extracts slides with deduplication
3. Fetches YouTube transcript (if available)
4. Analyzes slides with vision LLM (optional)
5. Caches all results

**Size:** ~200 lines

**Key Features:**
- Specialized for presentation videos
- Requires actual video file for slide extraction
- Vision analysis optional (can skip for speed/cost)

### 3. `src/transcript_pipeline.py` - Transcript Processing

**Purpose:** Generate booklets from transcripts only

**Function:** `transcript_to_booklet()`

**What it does:**
1. Fetches YouTube transcript
2. Gets video metadata (title, chapters)
3. Generates booklet using LLM
4. Supports chapter-based or single-pass generation
5. Caches all results

**Size:** ~300 lines

**Key Features:**
- No slide processing
- No vision analysis
- Only needs transcript data
- Chapter-based generation with context awareness

## Benefits

### 1. Single Responsibility
Each module has one clear purpose:
- `slides_pipeline.py` → Process videos with slides
- `transcript_pipeline.py` → Generate booklets from transcripts

### 2. Easier Navigation
- Smaller files (~200-300 lines vs 520 lines)
- Clear separation of concerns
- Easier to find specific functionality

### 3. Better Maintainability
- Changes to slide processing don't affect transcript processing
- Easier to test individual pipelines
- Clearer dependencies for each pipeline

### 4. Scalability
- Easy to add new pipelines without bloating existing files
- Each pipeline can evolve independently
- Clear pattern for future additions

### 5. Backward Compatibility
- All existing imports still work
- `from src.pipeline import process_video_with_slides` works as before
- No breaking changes for users

## Migration

**No migration needed!** All existing code continues to work:

```python
# This still works exactly as before
from src.pipeline import process_video_with_slides, transcript_to_booklet

# Or import directly from specialized modules
from src.slides_pipeline import process_video_with_slides
from src.transcript_pipeline import transcript_to_booklet
```

## Testing

All imports verified with `examples/test_pipeline.py`:
```bash
uv run python examples/test_pipeline.py
# ✅ All imports successful!
```

## Future Improvements

With this structure, we can easily:

1. **Add new pipelines** without cluttering existing code
2. **Optimize individual pipelines** independently
3. **Add pipeline-specific features** without affecting others
4. **Create pipeline variants** (e.g., `slides_pipeline_fast.py`)
5. **Better testing** - test each pipeline in isolation

## Example: Iterating on Slides Pipeline

Now that slides processing is isolated, we can:

```python
# src/slides_pipeline.py

def process_video_with_slides(
    input_source: str,
    # ... existing params ...
    
    # NEW: Add slide-specific parameters
    fps_sample: float = 2.0,
    similarity_threshold: float = 0.95,
    min_slide_duration: float = 1.0,
):
    # Iterate and improve slide extraction
    # without touching transcript pipeline
    ...
```

This makes it much easier to experiment and improve individual pipelines!
