# Refactoring Summary: Simplified Chapter Creation

## What Changed

### Before: 3 Separate Functions
```python
# Confusing - which one to use?
auto_create_chapters()        # Time-based with titles
create_semantic_chapters()    # Semantic detection
create_hybrid_chapters()      # Combines both
```

### After: 1 Unified Function
```python
# Simple - one function, multiple strategies
create_chapters(transcript, strategy="auto")
```

---

## New API

### Main Function: `create_chapters()`

```python
from src.processing.content import create_chapters

# Recommended: Auto strategy (semantic with fallback)
chapters = create_chapters(transcript)

# Force time-based only
chapters = create_chapters(transcript, strategy="time-based")

# Force semantic only (may fail)
chapters = create_chapters(transcript, strategy="semantic")
```

**Strategies:**
- **`auto`** (default): Tries semantic, falls back to time-based with titles
- **`semantic`**: Only semantic detection (may raise exception)
- **`time-based`**: Fixed intervals with generated titles

---

## Key Improvements

### 1. ✅ Simplified API
- **Before**: 3 functions, confusing which to use
- **After**: 1 function with strategy parameter

### 2. ✅ Comprehensive Logging
All prompts now log:
```
📊 Prompt stats (semantic chapter detection):
   Characters: 68,725
   Estimated tokens: ~17,181
```

**Tracks:**
- Character count
- Estimated token count
- Warnings for large prompts

### 3. ✅ Automatic Fallback
```python
# Tries semantic first
chapters = create_chapters(transcript)
# If semantic fails → automatically falls back to time-based
# Always returns valid chapters
```

### 4. ✅ Better Chapter Titles

**Before:**
- Section 1
- Section 2
- Section 3

**After:**
- Introduction to Forward Deployed Engineers
- Origins and Evolution at Palantir  
- The Echo and Delta Team Structure

---

## Implementation Details

### Prompt Tracking

Every LLM call now logs:
```python
log_prompt_stats(prompt, context="semantic chapter detection")

# Output:
#    📊 Prompt stats (semantic chapter detection):
#       Characters: 68,725
#       Estimated tokens: ~17,181
#       ℹ️  Large prompt (but within GPT-4o limits)
```

### Token Estimation

```python
def estimate_tokens(text: str) -> int:
    """
    Rough approximation: 1 token ≈ 4 characters
    Conservative estimate for English text
    """
    return len(text) // 4
```

**Warnings:**
- `> 100k tokens`: ⚠️  Very large prompt! May hit token limits
- `> 50k tokens`: ℹ️  Large prompt (but within GPT-4o limits)

---

## Migration Guide

### Old Code (Still Works)
```python
from src.processing.content import auto_create_chapters

chapters = auto_create_chapters(transcript, generate_titles=True)
```

### New Code (Recommended)
```python
from src.processing.content import create_chapters

chapters = create_chapters(transcript, strategy="auto")
```

**Note:** `auto_create_chapters()` is deprecated but still works for backward compatibility.

---

## Files Changed

### Modified:
- `src/processing/content/chapters.py`
  - Added `create_chapters()` - main API
  - Added `log_prompt_stats()` - prompt tracking
  - Added `estimate_tokens()` - token estimation
  - Refactored into private helpers: `_create_semantic_chapters()`, `_create_time_based_chapters()`
  - Deprecated `auto_create_chapters()` (kept for compatibility)

- `src/processing/content/__init__.py`
  - Exports `create_chapters` as main API
  - Marks `auto_create_chapters` as deprecated

- `src/pipeline.py`
  - Uses `create_chapters(strategy="auto")` for intelligent chapter creation

### Deleted:
- `src/processing/content/semantic_chapters.py` (merged into chapters.py)

---

## Benefits

1. **Simpler API**: One function instead of three
2. **Better logging**: Track prompt size and token usage
3. **Smarter defaults**: Auto strategy works for all cases
4. **Backward compatible**: Old code still works
5. **More maintainable**: Less code duplication

---

## Example Output

```
Creating chapters (strategy: auto)...
Trying semantic chapter detection...
   📊 Prompt stats (semantic chapter detection):
      Characters: 68,725
      Estimated tokens: ~17,181
      ℹ️  Large prompt (but within GPT-4o limits)
Detected 7 semantic chapters
   1. Introduction and Background (0-4 min)
   2. The FDE Model at Palantir (4-12 min)
   3. Echo and Delta Teams (12-18 min)
   4. Applying FDE to AI Startups (18-28 min)
   5. Challenges and Best Practices (28-35 min)
   6. Pricing and Business Model (35-42 min)
   7. Future of FDE in AI (42-47 min)
✅ Using 7 semantic chapters
```

---

## Cost Impact

**Before:** No tracking

**After:** Full visibility
- See exact prompt sizes
- Estimate token usage
- Predict costs before calling LLM

**Example:**
- Semantic detection: ~17k tokens (~$0.01-0.02)
- Title generation: ~2k tokens (~$0.001)
- Section generation: ~5-10k tokens each (~$0.01-0.02 per section)

---

## Next Steps

1. ✅ Simplified chapter creation
2. ✅ Added comprehensive logging
3. ✅ Integrated into pipeline
4. ⏳ Test on various videos
5. ⏳ Collect metrics on semantic vs time-based success rates
