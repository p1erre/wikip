# Slides Extraction Agent

Extract and analyze slides from presentation videos using computer vision and OCR.

## Features

- **Frame Extraction**: Extract frames from video at configurable intervals using ffmpeg
- **Slide Detection**: Detect unique slides by comparing frame similarity using OpenCV
- **OCR Text Extraction**: Extract text from slides using Tesseract OCR
- **Transcript Alignment**: Match slides to transcript segments by timestamp

## Prerequisites

### System Dependencies

**macOS:**
```bash
brew install ffmpeg tesseract
```

**Ubuntu/Debian:**
```bash
sudo apt-get install ffmpeg tesseract-ocr
```

**Windows:**
- Download ffmpeg from https://ffmpeg.org/download.html
- Download tesseract from https://github.com/UB-Mannheim/tesseract/wiki

### Python Dependencies

Already included in `pyproject.toml`:
- `opencv-python` - Computer vision for slide detection
- `scikit-image` - Image similarity metrics
- `pytesseract` - Python wrapper for Tesseract OCR
- `pillow` - Image processing

## Usage

### Basic Slide Extraction

```python
from src.agents.slides import extract_slides

# Extract slides from video
result = extract_slides(
    video_path="presentation.mp4",
    output_dir="./slides",
    fps=0.5,  # Extract 1 frame every 2 seconds
    threshold=0.85  # Similarity threshold (0-1)
)

print(f"Found {result['num_slides']} unique slides")
for slide in result['slides']:
    print(f"Slide {slide['slide_number']} at {slide['timestamp']}s")
```

### Extract Text from Slides

```python
from src.agents.slides import analyze_slide_content

# Analyze slide content with OCR
content = analyze_slide_content("slide_001.jpg")

print(f"Text: {content['text']}")
print(f"Confidence: {content['confidence']}%")
```

### Align Slides with Transcript

```python
from src.agents.video import analyze_video
from src.agents.slides import extract_slides, align_slides_with_transcript

# Get video transcript
video_result = analyze_video("https://youtube.com/watch?v=...")

# Extract slides
slides_result = extract_slides("video.mp4")

# Align slides with transcript
aligned = align_slides_with_transcript(
    slides=slides_result['slides'],
    transcript=video_result['transcript']
)

# Each slide now has matching transcript text
for slide in aligned['slides']:
    print(f"Slide {slide['slide_number']}: {slide['transcript'][:100]}...")
```

## Tools

### `extract_video_frames`
Extract frames from video at specified frame rate.

**Parameters:**
- `video_path` (str): Path to video file
- `output_dir` (str): Directory to save frames
- `fps` (float): Frames per second to extract (default: 0.5)

**Returns:**
```python
{
    "success": True,
    "num_frames": 150,
    "frames": ["frame_0001.jpg", "frame_0002.jpg", ...],
    "output_dir": "./frames"
}
```

### `detect_slide_changes`
Detect unique slides by comparing frame similarity.

**Parameters:**
- `frame_paths` (List[str]): List of frame image paths
- `threshold` (float): Similarity threshold 0-1 (default: 0.85)
- `output_dir` (str): Directory to save unique slides

**Returns:**
```python
{
    "success": True,
    "num_slides": 25,
    "slides": [
        {
            "slide_number": 1,
            "image_path": "slide_001.jpg",
            "timestamp": 0.0,
            "frame_index": 0
        },
        ...
    ]
}
```

### `extract_slides`
Complete workflow: extract frames and detect slides.

**Parameters:**
- `video_path` (str): Path to video file
- `output_dir` (str): Directory to save slides
- `fps` (float): Frames per second (default: 0.5)
- `threshold` (float): Similarity threshold (default: 0.85)

### `analyze_slide_content`
Extract text from slide using OCR.

**Parameters:**
- `image_path` (str): Path to slide image

**Returns:**
```python
{
    "success": True,
    "text": "Introduction to AI Agents\n- Autonomous systems\n- Goal-oriented",
    "confidence": 87.5,
    "num_words": 8
}
```

### `align_slides_with_transcript`
Match slides to transcript segments by timestamp.

**Parameters:**
- `slides` (list): List of slides with timestamps
- `transcript` (dict): Transcript with segments

**Returns:**
```python
{
    "success": True,
    "slides": [
        {
            "slide_number": 1,
            "timestamp": 0.0,
            "transcript": "Welcome to this presentation...",
            "num_segments": 5,
            "duration": 30.0
        },
        ...
    ]
}
```

## Configuration

### Frame Extraction Rate (fps)
- **0.5 fps** (default): 1 frame every 2 seconds - good balance
- **1.0 fps**: 1 frame per second - more accurate but slower
- **0.25 fps**: 1 frame every 4 seconds - faster but may miss slides

### Similarity Threshold
- **0.85** (default): Good for most presentations
- **0.90**: More strict - only major changes detected
- **0.80**: More sensitive - may detect minor changes

## Example

See `examples/08_extract_slides.py` for a complete example:

```bash
python examples/08_extract_slides.py
```

## Workflow

```
1. Video File
   ↓
2. extract_video_frames() → Extract frames at intervals
   ↓
3. detect_slide_changes() → Compare frames, find unique slides
   ↓
4. analyze_slide_content() → OCR text extraction
   ↓
5. align_slides_with_transcript() → Match to narration
   ↓
6. Enhanced Book Content (slides + transcript)
```

## Next Steps

After extracting slides, you can:

1. **Generate Enhanced Books**: Combine slide content with transcript
2. **Create Visual Summaries**: Include slide images in generated content
3. **Extract Code Examples**: Detect and extract code from slides
4. **Analyze Diagrams**: Use GPT-4 Vision for complex visuals (Option B/C)

## Limitations

- OCR accuracy depends on slide quality and text size
- May miss slides if they're shown briefly
- Cannot understand complex diagrams (use GPT-4 Vision for that)
- Requires ffmpeg and tesseract to be installed

## Troubleshooting

**"ffmpeg not found"**
```bash
# macOS
brew install ffmpeg

# Ubuntu
sudo apt-get install ffmpeg
```

**"pytesseract not found"**
```bash
# macOS
brew install tesseract

# Ubuntu
sudo apt-get install tesseract-ocr
```

**Low OCR confidence**
- Increase video quality
- Adjust frame extraction rate (higher fps)
- Try different similarity threshold
- Preprocess images (contrast, brightness)
