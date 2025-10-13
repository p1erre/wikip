# Slide Detection Algorithm - Detailed Explanation

## Overview

The algorithm detects unique slides from a video by comparing consecutive frames using **Structural Similarity Index (SSIM)**.

## Input

- **frame_paths**: List of extracted video frames (e.g., 360 frames from 12-minute video at 0.5 fps)
- **threshold**: Major change threshold (default: 0.85)
- **progressive_threshold**: Minor change threshold (default: 0.95)
- **detect_progressive**: Enable progressive slide detection (default: True)

## Key Variables

```python
prev_frame = None                    # Previous frame's grayscale image
current_slide_group = []             # Frames belonging to current slide
unique_slides = []                   # Final list of detected slides
slide_count = 0                      # Counter for slides
```

## Algorithm Steps

### Step 1: Initialize
```
For each frame in frame_paths:
    Read frame
    Convert to grayscale
```

### Step 2: Compare with Previous Frame

**Key Line (262):** `similarity = ssim(prev_frame, gray)`

This compares the **current frame** with the **immediately previous frame** (not the first frame of the group!).

**SSIM returns a value between 0 and 1:**
- 1.0 = Identical images
- 0.9-1.0 = Very similar (same slide, no change)
- 0.85-0.95 = Similar with minor differences (progressive content)
- < 0.85 = Different images (different slide)

### Step 3: Classify Change Type

```python
if prev_frame is None:
    is_major_change = True              # First frame always starts new slide
    
elif similarity < threshold (0.85):
    is_major_change = True              # Completely different slide
    
elif similarity < progressive_threshold (0.95):
    is_minor_change = True              # Progressive content (same slide)
    
else:
    # No change (similarity >= 0.95)
    # Frame is too similar, skip it
```

### Step 4: Handle Slide Grouping

**Case A: Major Change (Different Slide)**
```python
if is_major_change:
    1. Save current_slide_group as a complete slide
    2. Start new group with this frame
    3. Update prev_frame = current frame
```

**Case B: Minor Change (Progressive Content)**
```python
elif is_minor_change:
    1. Add frame to current_slide_group
    2. Update prev_frame = current frame
```

**Case C: No Change (Too Similar)**
```python
else:
    # Do nothing, skip this frame
    # prev_frame stays the same
```

## The Bug 🐛

### Problem: Comparing to Wrong Frame

**What we do (WRONG):**
```
Frame 30 → Frame 31 → ... → Frame 82 → Frame 83
         ↑                            ↑
         |                            |
    Compare to frame 29         Compare to frame 82
```

**What happens:**
1. Frame 30: New slide detected (compare to frame 29)
2. Frame 39: Progressive content (compare to frame 38, similar to 39)
3. Frame 83: Progressive content (compare to frame 82, similar to 83) ❌ BUG!

**The issue:**
- Frame 83 is compared to frame 82 (its immediate neighbor)
- Frame 82 and 83 are very similar (same slide state)
- So similarity = 0.93 (minor change)
- Frame 83 gets added to the group with frame 30
- **But frame 83 might be a COMPLETELY DIFFERENT SLIDE than frame 30!**

### Why This Happens

Between frame 30 and frame 83, there are **53 frames** (106 seconds).

The video might show:
- Frame 30: Slide A with title
- Frame 39: Slide A with title + bullet 1
- Frame 60-82: Slide B (completely different!)
- Frame 83: Slide B with more content

But we only compare:
- Frame 39 to frame 38 ✓ (both on Slide A)
- Frame 83 to frame 82 ✓ (both on Slide B)

We never compare frame 83 to frame 30, so we don't detect that they're different slides!

## The Fix 🔧

**What we should do:**

Compare each frame to the **first frame in the current group**, not the previous frame:

```python
# Instead of:
similarity = ssim(prev_frame, gray)

# Do:
if current_slide_group:
    first_frame_in_group = current_slide_group[0]['gray']
    similarity = ssim(first_frame_in_group, gray)
else:
    is_major_change = True  # First frame
```

This ensures:
- Frame 39 compared to frame 30 (first in group) ✓
- Frame 83 compared to frame 30 (first in group) ✓
- If frame 83 is different from frame 30, it starts a new group ✓

## Example Walkthrough

### Current Algorithm (Buggy)

```
Frame 0: "Intro slide"
  prev_frame = None
  → Major change (first frame)
  → Group: [0]

Frame 30: "Training - title"
  Compare to frame 29
  similarity = 0.82 < 0.85
  → Major change (different slide)
  → Save group [0] as slide_001
  → Group: [30]

Frame 39: "Training - title + bullet 1"
  Compare to frame 38
  similarity = 0.91 (0.85 < sim < 0.95)
  → Minor change (progressive)
  → Group: [30, 39]

Frame 83: "DIFFERENT SLIDE - Specializing"
  Compare to frame 82 ❌ WRONG!
  similarity = 0.93 (0.85 < sim < 0.95)
  → Minor change (progressive) ❌ WRONG!
  → Group: [30, 39, 83] ❌ BUG!
```

### Fixed Algorithm

```
Frame 0: "Intro slide"
  No group yet
  → Major change (first frame)
  → Group: [0]

Frame 30: "Training - title"
  Compare to frame 0 (first in group)
  similarity = 0.82 < 0.85
  → Major change (different slide)
  → Save group [0] as slide_001
  → Group: [30]

Frame 39: "Training - title + bullet 1"
  Compare to frame 30 (first in group) ✓
  similarity = 0.91 (0.85 < sim < 0.95)
  → Minor change (progressive)
  → Group: [30, 39]

Frame 83: "DIFFERENT SLIDE - Specializing"
  Compare to frame 30 (first in group) ✓
  similarity = 0.65 < 0.85 ✓
  → Major change (different slide) ✓
  → Save group [30, 39] as slide_002
  → Group: [83] ✓
```

## Summary

**Current behavior:**
- Compares each frame to its immediate predecessor
- Fails when there are gaps between extracted frames
- Groups unrelated slides together

**Fixed behavior:**
- Compares each frame to the first frame in the current group
- Correctly detects when content has changed too much
- Each group contains only frames from the same slide
