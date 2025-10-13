# Vision-Based Slide Analysis

Extract rich context from presentation slides using vision LLMs (Gemini or GPT-4V).

## Overview

The vision analysis module analyzes slide images to extract:
- All visible text (titles, bullets, labels, code)
- Visual elements (diagrams, charts, images, icons)
- Key concepts and relationships
- Technical details (formulas, equations, specifications)
- Alignment with speaker transcript

## Quick Start

### 1. Set Up API Key

Add to your `.env` file:

```bash
# For Gemini (recommended - cheapest)
GOOGLE_API_KEY=your_google_api_key_here

# Or for OpenAI
OPENAI_API_KEY=your_openai_api_key_here

# Configure which model to use
VISION_MODEL_PROVIDER=google  # or 'openai'
VISION_MODEL=gemini-1.5-flash  # or 'gemini-1.5-pro', 'gpt-4o'
```

Get a Gemini API key: https://makersuite.google.com/app/apikey

### 2. Install Dependencies

```bash
pip install google-generativeai
# or
uv pip install google-generativeai
```

### 3. Run Complete Workflow

```bash
python examples/10_slides_with_vision_analysis.py
```

## Usage

### Basic Analysis

```python
from src.agents.slides import extract_slides_robust
from src.vision import analyze_slides_with_vision

# Extract slides
slides_result = extract_slides_robust.func(
    video_path="video.mp4",
    output_dir="./slides"
)

# Analyze with vision LLM
enriched_slides = analyze_slides_with_vision(
    slides_result=slides_result,
    provider='google',  # Use Gemini
    model='gemini-1.5-flash',  # Cheapest option
    output_path="./enriched_slides.json"
)

# Access results
for slide in enriched_slides:
    print(f"Slide {slide['slide_number']}")
    print(f"  Title: {slide['vision_analysis']['title']}")
    print(f"  Concepts: {slide['vision_analysis']['key_concepts']}")
```

### With Transcript

```python
from src.tools.youtube_tools import get_youtube_transcript

# Get transcript
transcript_result = get_youtube_transcript("video_id")
transcript = transcript_result['transcript']

# Analyze slides with transcript context
enriched_slides = analyze_slides_with_vision(
    slides_result=slides_result,
    transcript=transcript,  # Adds speaker context
    provider='google',
    model='gemini-1.5-flash'
)

# Each slide now includes what the speaker was saying
for slide in enriched_slides:
    print(f"Speaker: {slide['transcript']}")
    print(f"Visuals: {slide['vision_analysis']}")
```

### Advanced: Custom Analysis

```python
from src.vision import SlideVisionAnalyzer

# Create analyzer
analyzer = SlideVisionAnalyzer(
    provider='google',
    model='gemini-1.5-flash'
)

# Analyze single slide
analysis = analyzer.analyze_slide(
    image_path="slide_001.jpg",
    transcript="The speaker said this during the slide...",
    timestamp_info={'start': 10.5, 'end': 25.3}
)

print(analysis)
# {
#   "title": "Introduction to Python",
#   "text_content": ["Python is a high-level language", "Easy to learn"],
#   "visual_elements": {
#     "diagrams": ["Python logo"],
#     "code_snippets": ["print('Hello World')"]
#   },
#   "key_concepts": ["Python", "Programming", "Syntax"],
#   ...
# }
```

## Model Comparison

### Gemini 1.5 Flash (Recommended) 🏆

**Pros:**
- **Ultra-cheap**: $0.00001875 per image (~$0.002 per 12-min video)
- Fast response times
- Good quality for most slides
- Can process video directly

**Cons:**
- Slightly less accurate than Pro models for complex diagrams

**Best for:**
- High-volume processing
- Budget-conscious projects
- Simple to moderate slide complexity

### Gemini 1.5 Pro

**Pros:**
- Better accuracy than Flash
- Still very affordable: $0.00315 per image (~$0.05 per video)
- Excellent for technical content
- Can process video directly

**Cons:**
- 168x more expensive than Flash (but still cheap!)

**Best for:**
- Complex technical diagrams
- Code-heavy presentations
- When accuracy is critical

### GPT-4o

**Pros:**
- Excellent accuracy
- Great for technical content
- Fast and reliable

**Cons:**
- Most expensive: ~$0.0065 per image (~$0.10 per video)
- Cannot process video directly

**Best for:**
- Maximum accuracy needed
- Already using OpenAI ecosystem
- Budget not a constraint

## Output Format

Each enriched slide contains:

```json
{
  "slide_number": 1,
  "cluster_id": 0,
  "image_path": "./slides/slide_001.jpg",
  "timestamp": 0.0,
  "duration": 61.44,
  "start_time": 0.0,
  "end_time": 61.44,
  "transcript": "Welcome to this presentation about...",
  "vision_analysis": {
    "title": "Introduction to Machine Learning",
    "text_content": [
      "What is Machine Learning?",
      "Types of ML: Supervised, Unsupervised, Reinforcement",
      "Applications in real world"
    ],
    "visual_elements": {
      "diagrams": ["ML workflow diagram showing data -> model -> predictions"],
      "charts": [],
      "code_snippets": [],
      "images": ["Brain icon representing AI"],
      "icons": ["Checkmark icons for bullet points"]
    },
    "key_concepts": [
      "Machine Learning",
      "Supervised Learning",
      "Unsupervised Learning",
      "Reinforcement Learning"
    ],
    "technical_details": "",
    "layout": "Title at top, 3 bullet points in center, brain icon on right",
    "speaker_alignment": "Speaker introduces ML concepts that match the bullet points shown"
  },
  "num_occurrences": 1,
  "num_builds": 0
}
```

## Cost Examples

### 12-Minute Video (16 slides)

| Model | Cost per Slide | Total Cost | Quality |
|-------|---------------|------------|---------|
| Gemini 1.5 Flash | $0.00001875 | **$0.0003** | Good |
| Gemini 1.5 Pro | $0.00315 | **$0.05** | Very Good |
| GPT-4o | $0.0065 | **$0.10** | Excellent |

### 100 Videos

| Model | Total Cost |
|-------|-----------|
| Gemini 1.5 Flash | **$0.03** |
| Gemini 1.5 Pro | **$5.00** |
| GPT-4o | **$10.00** |

## Use Cases

### 1. Enhanced Book Generation

```python
# Generate book chapter with slide context
enriched_slides = analyze_slides_with_vision(slides_result, transcript)

chapter_content = generate_chapter(
    slides=enriched_slides,
    style="educational"
)
```

### 2. Study Guide Creation

```python
# Extract key concepts from all slides
all_concepts = []
for slide in enriched_slides:
    all_concepts.extend(slide['vision_analysis']['key_concepts'])

study_guide = create_study_guide(concepts=all_concepts)
```

### 3. Code Example Extraction

```python
# Find all code snippets
code_examples = []
for slide in enriched_slides:
    snippets = slide['vision_analysis']['visual_elements'].get('code_snippets', [])
    code_examples.extend(snippets)
```

### 4. Quiz Generation

```python
# Generate quiz questions from slide content
quiz = generate_quiz(
    slides=enriched_slides,
    num_questions=10
)
```

## Best Practices

### 1. Start with Gemini Flash

Test your workflow with the cheapest model first:

```python
# Test with Flash
enriched_slides = analyze_slides_with_vision(
    slides_result=slides_result,
    provider='google',
    model='gemini-1.5-flash'
)

# If quality is insufficient, upgrade to Pro
```

### 2. Include Transcript When Available

Transcript provides crucial context:

```python
# Better results with transcript
enriched_slides = analyze_slides_with_vision(
    slides_result=slides_result,
    transcript=transcript,  # Adds speaker context
    provider='google'
)
```

### 3. Batch Processing

Process multiple videos efficiently:

```python
for video_path in video_list:
    slides = extract_slides_robust.func(video_path=video_path)
    enriched = analyze_slides_with_vision(slides, provider='google')
    save_results(enriched)
```

### 4. Error Handling

```python
try:
    enriched_slides = analyze_slides_with_vision(
        slides_result=slides_result,
        provider='google',
        model='gemini-1.5-flash'
    )
except Exception as e:
    print(f"Vision analysis failed: {e}")
    # Fallback to basic OCR or manual review
```

## Troubleshooting

### "GOOGLE_API_KEY not found"

Add to `.env`:
```bash
GOOGLE_API_KEY=your_api_key_here
```

Get key from: https://makersuite.google.com/app/apikey

### "Module 'google.generativeai' not found"

Install the package:
```bash
pip install google-generativeai
```

### Rate Limits

Gemini has generous rate limits, but if you hit them:

```python
import time

for slide in slides:
    analysis = analyzer.analyze_slide(slide['image_path'])
    time.sleep(0.1)  # Small delay between requests
```

### Poor Quality Results

Try upgrading the model:

```python
# Upgrade from Flash to Pro
enriched_slides = analyze_slides_with_vision(
    slides_result=slides_result,
    provider='google',
    model='gemini-1.5-pro'  # Better quality
)
```

## API Reference

### `analyze_slides_with_vision()`

```python
def analyze_slides_with_vision(
    slides_result: Dict[str, Any],
    transcript: Optional[Dict[str, Any]] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    output_path: Optional[str] = None
) -> List[Dict[str, Any]]
```

**Parameters:**
- `slides_result`: Result from `extract_slides_robust()`
- `transcript`: Optional transcript dict with 'segments'
- `provider`: 'google' or 'openai' (default from env)
- `model`: Model name (default from env)
- `output_path`: Optional path to save JSON

**Returns:**
- List of enriched slides with vision analysis

### `SlideVisionAnalyzer`

```python
class SlideVisionAnalyzer:
    def __init__(self, provider: str, model: str)
    def analyze_slide(self, image_path: str, transcript: str, timestamp_info: dict) -> dict
    def analyze_slides_batch(self, slides: list, transcript_segments: list) -> list
```

## Next Steps

1. **Get API Key**: https://makersuite.google.com/app/apikey
2. **Add to .env**: `GOOGLE_API_KEY=your_key`
3. **Run Example**: `python examples/10_slides_with_vision_analysis.py`
4. **Integrate**: Use enriched slides in your content generation pipeline

## Resources

- [Gemini API Documentation](https://ai.google.dev/docs)
- [Gemini Pricing](https://ai.google.dev/pricing)
- [Example Script](../examples/10_slides_with_vision_analysis.py)
- [Slide Extraction Guide](ROBUST_SLIDE_EXTRACTION.md)
