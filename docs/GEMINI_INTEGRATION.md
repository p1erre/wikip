# Gemini Vision Integration - Quick Reference

## Setup (2 minutes)

### 1. Get API Key
Visit: https://makersuite.google.com/app/apikey

### 2. Add to .env
```bash
GOOGLE_API_KEY=your_api_key_here
VISION_MODEL_PROVIDER=google
VISION_MODEL=gemini-1.5-flash
```

### 3. Install Package
```bash
pip install google-generativeai
```

## Usage

### Complete Workflow
```python
from src.agents.slides import extract_slides_robust
from src.agents.slides import analyze_slides_with_vision
from src.tools.youtube_tools import get_youtube_transcript

# 1. Extract slides
slides = extract_slides_robust.func(
    video_path="video.mp4",
    output_dir="./slides"
)

# 2. Get transcript (optional)
transcript = get_youtube_transcript("video_id")['transcript']

# 3. Analyze with Gemini
enriched = analyze_slides_with_vision(
    slides_result=slides,
    transcript=transcript,
    provider='google',
    model='gemini-1.5-flash'
)

# 4. Use enriched data
for slide in enriched:
    print(slide['vision_analysis']['title'])
    print(slide['vision_analysis']['key_concepts'])
```

## Pricing (Ultra-Cheap!)

| Model | Per Slide | 16 Slides | 100 Videos |
|-------|-----------|-----------|------------|
| **gemini-1.5-flash** | $0.00002 | $0.0003 | **$0.03** |
| gemini-1.5-pro | $0.00315 | $0.05 | $5.00 |
| gpt-4o | $0.0065 | $0.10 | $10.00 |

**Recommendation: Start with gemini-1.5-flash** (practically free!)

## What You Get

Each slide includes:
- **Timestamps**: Start/end times in video
- **Transcript**: What speaker said during slide
- **Vision Analysis**:
  - Title and all text content
  - Visual elements (diagrams, charts, code)
  - Key concepts
  - Technical details
  - Layout description
  - Alignment with speaker

## Example Output

```json
{
  "slide_number": 1,
  "start_time": 0.0,
  "end_time": 61.44,
  "transcript": "Welcome everyone...",
  "vision_analysis": {
    "title": "Introduction to Python",
    "text_content": ["Python is easy", "Great for beginners"],
    "visual_elements": {
      "code_snippets": ["print('Hello')"],
      "diagrams": ["Python logo"]
    },
    "key_concepts": ["Python", "Programming"],
    "speaker_alignment": "Speaker introduces concepts shown on slide"
  }
}
```

## Run Example

```bash
python examples/10_slides_with_vision_analysis.py
```

## Next Steps

1. ✅ Get Gemini API key
2. ✅ Add to .env
3. ✅ Run example script
4. ✅ Integrate into your content pipeline

Full documentation: [VISION_ANALYSIS.md](VISION_ANALYSIS.md)
