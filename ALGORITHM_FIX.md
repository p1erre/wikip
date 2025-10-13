# Algorithm Fix: Original Color Frames

## Issue Identified

The original implementation was saving **processed grayscale masked images** instead of the original color frames from the video.

### What Was Happening
- Algorithm received original BGR color frames from video
- Converted to grayscale for comparison (correct for algorithm)
- Applied motion masking (correct for algorithm)
- **BUT**: Saved the processed grayscale image as the final slide ❌

### What Should Happen
- Algorithm receives original BGR color frames
- Converts to grayscale for comparison ✅
- Applies motion masking for comparison ✅
- **Saves the original color frame** as the final slide ✅

## Fix Applied

### Changes Made

1. **Updated `Segment` dataclass** to store both versions:
   ```python
   @dataclass
   class Segment:
       keyframe: np.ndarray  # Processed grayscale for comparison
       keyframe_original: np.ndarray  # Original color frame ← NEW
   ```

2. **Updated all methods** to track original frames:
   - `_start_segment()`: Now accepts `original_frame` parameter
   - `_end_segment()`: Stores both processed and original frames
   - `_record_build()`: Updates both versions during builds
   - `_step()`: Passes original frame through pipeline

3. **Updated wrapper tool** to save original frames:
   ```python
   # Before: cv2.imwrite(str(slide_path), segment.keyframe)
   # After:
   cv2.imwrite(str(slide_path), segment.keyframe_original)
   ```

## Results Comparison

### Before Fix (Processed Grayscale)
```
-rw-r--r--  67K slide_001.jpg  # Grayscale, 1024px wide
-rw-r--r--  101K slide_002.jpg
-rw-r--r--  70K slide_003.jpg
```

### After Fix (Original Color)
```
-rw-r--r--  183K slide_001.jpg  # Color RGB, 1920x1080
-rw-r--r--  185K slide_002.jpg
-rw-r--r--  185K slide_003.jpg
```

**File size increased ~2.5x** due to:
- Color (3 channels vs 1)
- Full resolution (1920x1080 vs 1024px wide)
- No masking artifacts

## Technical Details

### Image Properties

**Before (Processed):**
- Format: Grayscale (1 channel)
- Resolution: 1024px wide (resized for processing)
- Artifacts: Motion masking applied (gray regions)
- File type: JPEG, components 1

**After (Original):**
- Format: Color RGB (3 channels)
- Resolution: 1920x1080 (original video resolution)
- Quality: Pristine original frames
- File type: JPEG, components 3

### Algorithm Still Works Correctly

The comparison logic remains unchanged:
- Still uses grayscale for perceptual hashing ✅
- Still applies motion masking for comparison ✅
- Still uses SSIM on processed images ✅
- Still detects builds with edge-delta ✅

**Only the output changes** - now saves original color frames.

## Verification

```bash
# Check image properties
file test_slides_robust/collapse/slide_001.jpg
# Output: JPEG image data, ..., 1920x1080, components 3
#                                           ^^^^^^^^^^^
#                                           Color RGB!

# Compare file sizes
ls -lh test_slides_robust/collapse/*.jpg
# Shows 150-290KB files (vs 25-115KB before)
```

## Impact

### ✅ Benefits
1. **Full color slides** - Much better for viewing and OCR
2. **Full resolution** - 1920x1080 instead of 1024px
3. **No artifacts** - Clean original frames without masking
4. **Better quality** - Suitable for presentations and books

### ⚠️ Considerations
1. **Larger files** - ~2.5x bigger (but still reasonable)
2. **Same accuracy** - Detection quality unchanged
3. **Same speed** - Processing time unchanged

## Usage

No changes needed to your code! The fix is transparent:

```python
from src.agents.slides import extract_slides_robust

# Same API, now returns original color frames
result = extract_slides_robust.func(
    video_path="video.mp4",
    output_dir="./slides"
)

# Slides are now full-color, full-resolution originals
for slide in result['slides']:
    print(f"Slide {slide['slide_number']}: {slide['image_path']}")
    # These are now pristine color frames!
```

## Summary

The algorithm now correctly:
1. ✅ Uses processed grayscale for comparison (fast & accurate)
2. ✅ Applies motion masking for comparison (ignores presenter)
3. ✅ Detects builds with edge-delta (progressive reveals)
4. ✅ **Saves original color frames** (high quality output)

This gives you the best of both worlds: efficient processing with high-quality output!
