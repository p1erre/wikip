# Robust Slide Extraction Algorithm

## Overview

The robust slide extraction algorithm provides production-ready slide detection with advanced features for handling progressive reveals ("builds"), motion masking, and global deduplication. This algorithm significantly improves upon basic frame comparison methods.

## Key Features

### 1. **Progressive Reveal Detection (Builds)**
Intelligently detects when content is being revealed incrementally on the same slide (e.g., bullet points appearing one by one).

**Two Build Policies:**
- **`build_collapse`** (default): Treats all build steps as one logical slide, keeping only the final fully revealed frame
- **`build_preserve`**: Creates sub-slides for each build step (e.g., slide_10.1, slide_10.2, ...)

### 2. **Motion Masking**
Automatically masks regions with high temporal variance (e.g., presenter movements) to prevent false slide changes.

**Features:**
- Temporal stability analysis using rolling buffer
- Optional manual ROI masking for known presenter positions
- Configurable sensitivity thresholds

### 3. **Perceptual Hashing + SSIM**
Uses a two-stage comparison approach:
- **Fast path**: Perceptual hashing (pHash) for quick similarity checks
- **Verification**: SSIM (Structural Similarity Index) for borderline cases
- **Build detection**: Edge-delta analysis for progressive reveals

### 4. **Global Deduplication**
Identifies and clusters duplicate slides across the entire video (e.g., title slide appearing multiple times).

### 5. **Hysteresis & Minimum Duration**
Prevents false positives from transitions and animations:
- Requires K consecutive mismatches before cutting
- Enforces minimum segment duration

## Installation

```bash
# Install required dependencies
pip install opencv-python pillow imagehash scikit-image numpy

# Or update your environment
pip install -r requirements.txt
```

## Usage

### Basic Usage

```python
from src.agents.slides import extract_slides_robust

# Extract slides with default settings
result = extract_slides_robust.func(
    video_path="presentation.mp4",
    output_dir="./slides",
    fps_sample=2.0,
    build_policy="build_collapse",
)

print(f"Found {result['num_unique_slides']} unique slides")
print(f"Total segments: {result['num_segments']}")
```

### With Presenter Masking

```python
# Mask bottom-right corner where presenter appears
result = extract_slides_robust.func(
    video_path="presentation.mp4",
    output_dir="./slides",
    fps_sample=2.0,
    build_policy="build_collapse",
    presenter_roi=(0.72, 0.72, 0.98, 0.98),  # (x1, y1, x2, y2) in [0,1]
)
```

### Build Preserve Mode

```python
# Create sub-slides for each build step
result = extract_slides_robust.func(
    video_path="presentation.mp4",
    output_dir="./slides",
    fps_sample=2.0,
    build_policy="build_preserve",
)

# Each progressive reveal gets its own slide
for slide in result['slides']:
    print(f"Slide {slide['slide_number']}: {slide['num_builds']} builds")
```

### Advanced Configuration

```python
from src.agents.slides.slideseg import SlideDeduplicator

# Fine-grained control over detection parameters
dedup = SlideDeduplicator(
    fps_sample=2.0,
    build_policy="build_collapse",
    presenter_roi=(0.72, 0.72, 0.98, 0.98),
    
    # Hashing thresholds
    ham_keep=10,        # Keep if Hamming distance <= 10
    ham_new=18,         # New slide if Hamming distance >= 18
    
    # SSIM thresholds
    ssim_keep=0.93,     # Keep if SSIM >= 0.93
    ssim_build=0.98,    # Build if SSIM >= 0.98
    
    # Build detection
    build_add_ratio_max=0.15,    # Max 15% new content for build
    build_remove_ratio_max=0.03, # Max 3% removed content for build
    
    # Hysteresis
    confirm_k=3,        # Require 3 consecutive mismatches
    min_seg_secs=2.0,   # Minimum 2 seconds per segment
    
    # Global deduplication
    cluster_merge_ham=10,      # Merge if Hamming <= 10
    cluster_verify_ssim=0.92,  # Verify with SSIM >= 0.92
)

result = dedup.process_video("presentation.mp4")
```

## Configuration Parameters

### Sampling & Preprocessing
- **`target_width`** (default: 1024): Resize width for processing
- **`fps_sample`** (default: 2.0): Frames per second to sample

### Masking
- **`presenter_roi`**: Optional tuple (x1, y1, x2, y2) in [0,1] to mask presenter
- **`motion_buffer_len`** (default: 7): Frames to buffer for motion detection
- **`motion_std_thresh`** (default: 4.0): Std deviation threshold for stability

### Hashing Thresholds
- **`phash_size`** (default: 8): Hash size (8→64bit, 16→256bit)
- **`ham_keep`** (default: 10): Keep if Hamming distance ≤ this
- **`ham_new`** (default: 18): New slide if Hamming distance ≥ this

### SSIM Thresholds
- **`ssim_keep`** (default: 0.93): Keep if SSIM ≥ this
- **`ssim_build`** (default: 0.98): Build detection if SSIM ≥ this

### Build Detection
- **`build_policy`**: "build_collapse" or "build_preserve"
- **`build_add_ratio_max`** (default: 0.15): Max ratio of added content
- **`build_remove_ratio_max`** (default: 0.03): Max ratio of removed content

### Hysteresis
- **`confirm_k`** (default: 3): Consecutive mismatches before cutting
- **`min_seg_secs`** (default: 2.0): Minimum segment duration in seconds

### Global Deduplication
- **`cluster_merge_ham`** (default: 10): Merge clusters if Hamming ≤ this
- **`cluster_verify_ssim`** (default: 0.92): Verify with SSIM (None to skip)

## Output Format

### Result Dictionary

```python
{
    "success": True,
    "video_path": "presentation.mp4",
    "num_unique_slides": 15,
    "num_segments": 18,
    "slides": [...],
    "clusters": [...],
    "segments": [...],
    "output_dir": "./slides",
    "metadata_path": "./slides/slides_metadata.json"
}
```

### Slide Information

```python
{
    "slide_number": 1,
    "cluster_id": 0,
    "image_path": "./slides/slide_001.jpg",
    "timestamp": 5.2,
    "duration": 12.5,
    "num_occurrences": 2,  # Appears twice in video
    "occurrences": [
        {"segment_idx": 0, "start": 5.2, "end": 17.7},
        {"segment_idx": 15, "start": 245.1, "end": 250.3}
    ],
    "num_builds": 3,  # 3 progressive reveals
    "builds": [
        {"t": 8.5, "add_ratio": 0.12, "rem_ratio": 0.01},
        {"t": 11.2, "add_ratio": 0.08, "rem_ratio": 0.00},
        {"t": 14.8, "add_ratio": 0.10, "rem_ratio": 0.02}
    ]
}
```

### Metadata JSON

Saved to `{output_dir}/slides_metadata.json`:

```json
{
  "video_path": "presentation.mp4",
  "build_policy": "build_collapse",
  "fps_sample": 2.0,
  "num_unique_slides": 15,
  "num_segments": 18,
  "slides": [...]
}
```

## Algorithm Details

### How Progressive Reveals Are Detected

1. **High SSIM Check**: Requires SSIM ≥ 0.98 (very similar)
2. **Edge Delta Analysis**: 
   - Computes edge maps using Canny edge detection
   - Calculates ratio of added edges (new content)
   - Calculates ratio of removed edges (disappeared content)
3. **Build Criteria**:
   - Added content ≤ 15% of total edges
   - Removed content ≤ 3% of total edges

### Decision Flow

```
Frame → Preprocess → Apply Mask → Compute pHash
                                        ↓
                            Compare with current slide
                                        ↓
                    ┌───────────────────┼───────────────────┐
                    ↓                   ↓                   ↓
            Ham ≤ H1 (10)      H1 < Ham < H2        Ham ≥ H2 (18)
                    ↓                   ↓                   ↓
                Keep Same        Verify with SSIM      Likely New
                                        ↓
                            ┌───────────┴───────────┐
                            ↓                       ↓
                    SSIM ≥ 0.93              SSIM < 0.93
                            ↓                       ↓
                    Check Build             Pending Fail++
                            ↓
                    ┌───────┴───────┐
                    ↓               ↓
            Is Build Step      Not Build
                    ↓               ↓
            Record Build      Keep Same
```

### Global Deduplication

After processing all frames:

1. **Cluster Formation**: Group segments with similar pHash (Hamming ≤ 10)
2. **SSIM Verification**: Optionally verify with SSIM ≥ 0.92
3. **Representative Selection**: First occurrence becomes cluster representative
4. **Cluster ID Assignment**: All segments get their cluster ID

## Comparison with Basic Algorithm

| Feature | Basic Algorithm | Robust Algorithm |
|---------|----------------|------------------|
| Progressive Reveals | Simple threshold | Edge-delta analysis |
| Deduplication | None | Global clustering |
| Motion Handling | None | Temporal masking |
| Similarity Metric | SSIM only | pHash + SSIM |
| False Positives | Higher | Lower (hysteresis) |
| Configuration | Limited | Highly configurable |
| Performance | Slower (SSIM all) | Faster (pHash first) |

## Tuning Recommendations

### For Text-Heavy Slides
```python
dedup = SlideDeduplicator(
    phash_size=16,      # 256-bit hash for more precision
    ham_keep=8,         # Stricter "same" detection
    ssim_keep=0.95,     # Higher similarity required
    build_add_ratio_max=0.10,  # Less tolerant of changes
)
```

### For Image-Heavy Slides
```python
dedup = SlideDeduplicator(
    phash_size=8,       # 64-bit hash sufficient
    ham_keep=12,        # More lenient
    ssim_keep=0.90,     # Lower similarity OK
    build_add_ratio_max=0.20,  # More tolerant of changes
)
```

### For Videos with Animations
```python
dedup = SlideDeduplicator(
    confirm_k=5,        # Require more consecutive mismatches
    min_seg_secs=3.0,   # Longer minimum duration
    motion_std_thresh=6.0,  # More aggressive motion masking
)
```

## Examples

See `examples/09_robust_slide_extraction.py` for complete examples:

```bash
# Run the main example
python examples/09_robust_slide_extraction.py

# The example demonstrates:
# 1. Build collapse policy
# 2. Build preserve policy
# 3. Presenter masking
# 4. Algorithm comparison
# 5. Advanced configuration
```

## Integration with Existing Tools

The robust algorithm integrates seamlessly with existing tools:

```python
from src.agents.slides import extract_slides_robust, analyze_slide_content, align_slides_with_transcript

# 1. Extract slides
slides_result = extract_slides_robust.func(
    video_path="video.mp4",
    output_dir="./slides"
)

# 2. Analyze with OCR
for slide in slides_result['slides']:
    content = analyze_slide_content.func(slide['image_path'])
    print(f"Slide {slide['slide_number']}: {content['text'][:100]}")

# 3. Align with transcript
from src.agents.video import get_youtube_transcript

transcript = get_youtube_transcript.func(video_id="...")
aligned = align_slides_with_transcript.func(
    slides=slides_result['slides'],
    transcript=transcript
)
```

## Troubleshooting

### Too Many Slides Detected
- Increase `ham_keep` (e.g., 12-15)
- Increase `ssim_keep` (e.g., 0.95)
- Increase `confirm_k` (e.g., 4-5)
- Increase `min_seg_secs` (e.g., 3.0)

### Too Few Slides Detected
- Decrease `ham_keep` (e.g., 8)
- Decrease `ssim_keep` (e.g., 0.90)
- Decrease `confirm_k` (e.g., 2)
- Decrease `min_seg_secs` (e.g., 1.5)

### Builds Not Detected
- Increase `build_add_ratio_max` (e.g., 0.20)
- Decrease `ssim_build` (e.g., 0.96)

### Too Many False Builds
- Decrease `build_add_ratio_max` (e.g., 0.10)
- Increase `ssim_build` (e.g., 0.99)

### Presenter Causing False Changes
- Set `presenter_roi` to mask presenter region
- Increase `motion_std_thresh` (e.g., 6.0)
- Increase `motion_buffer_len` (e.g., 10)

## Performance Considerations

- **Sampling Rate**: Higher `fps_sample` = more accurate but slower
- **Hash Size**: Larger `phash_size` = more precise but slower hashing
- **SSIM Width**: Smaller `ssim_short_w` = faster SSIM but less accurate
- **Motion Buffer**: Larger buffer = better motion detection but more memory

Typical performance: ~2-5x real-time on modern hardware (i.e., 10-minute video processes in 2-5 minutes).

## Future Extensions

Potential enhancements (not yet implemented):

1. **YOLO/Face Detection**: Auto-detect and mask presenter region
2. **OCR Integration**: Require monotone token growth for build confirmation
3. **Parallel Processing**: Process multiple videos concurrently
4. **GPU Acceleration**: Use CUDA for faster SSIM computation
5. **Adaptive Thresholds**: Learn optimal thresholds from video characteristics

## References

- **Perceptual Hashing**: [imagehash library](https://github.com/JohannesBuchner/imagehash)
- **SSIM**: Wang et al., "Image Quality Assessment: From Error Visibility to Structural Similarity"
- **Edge Detection**: Canny, "A Computational Approach to Edge Detection"

## License

MIT License - See project root for details.
