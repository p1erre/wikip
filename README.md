# Video-to-Book Pipeline

Convert YouTube videos into comprehensive educational booklets using AI.

## 🎯 Features

- **YouTube Processing**: Extract transcripts and metadata automatically
- **Slide Extraction**: Detect and extract unique slides from presentation videos
- **Vision Analysis**: Analyze slides with vision LLMs (Gemini, GPT-4V, OpenRouter)
- **Smart Chapter Generation**: Create chapters semantically or from video metadata
- **Context-Aware Content**: Sequential generation maintains consistency across chapters
- **Intelligent Caching**: Avoid reprocessing with granular cache control
- **Multiple LLM Providers**: OpenAI, Anthropic, OpenRouter support

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- API keys for your chosen LLM provider (OpenAI, Anthropic, or OpenRouter)
- FFmpeg (required for video processing)

### Installation

**Option 1: Using uv (Recommended - Fast!)**

```bash
# Install uv if you haven't already
# curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone or navigate to the project
cd video-to-book

# Install dependencies (uv creates venv automatically)
uv sync

# Set up environment variables
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

**Option 2: Using pip**

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# Set up environment variables
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### Quick Start - CLI

**Simplest way to use:**

```bash
# Generate booklet from YouTube video
./vtb generate "https://youtube.com/watch?v=VIDEO_ID"

# Or using uv directly
uv run python -m src.cli generate "https://youtube.com/watch?v=VIDEO_ID"
```

**More options:**

```bash
# Use different model
./vtb generate VIDEO_URL --model gpt-4o-mini

# Parallel mode (faster)
./vtb generate VIDEO_URL --parallel

# Process video with vision analysis
./vtb process VIDEO_URL

# Check cache
./vtb cache-info
```

See `docs/CLI_GUIDE.md` for complete CLI documentation.

### Python API

```python
from src.pipeline import transcript_to_booklet

# Generate a booklet from a YouTube video
result = transcript_to_booklet(
    input_source="https://www.youtube.com/watch?v=VIDEO_ID",
    model="gpt-4o",
    provider="openai",
    use_chapters=True,    # Chapter-based generation
    parallel=False,       # Sequential with context (recommended)
)

if result['success']:
    # Save the booklet
    with open('booklet.md', 'w') as f:
        f.write(result['booklet'])
    print(f"✅ Generated {result.get('num_sections')} sections")
```

See `examples/example_usage.py` for more Python examples.

## 📖 Usage Examples

### 1. Generate Booklet (Simple)

```python
from src.pipeline import transcript_to_booklet

result = transcript_to_booklet("https://www.youtube.com/watch?v=VIDEO_ID")
print(result['booklet'])
```

### 2. Process Video with Vision Analysis

```python
from src.pipeline import process_video_with_slides

result = process_video_with_slides(
    input_source="https://www.youtube.com/watch?v=VIDEO_ID",
    skip_vision=False,
    vision_provider="google",
    vision_model="gemini-1.5-flash"
)

print(f"Extracted {result['slides']['num_unique_slides']} slides")
print(f"Analyzed {len(result['vision_analysis'])} slides")
```

### 3. Cache Control

```python
# Regenerate only the booklet (keep cached transcript)
result = transcript_to_booklet(
    input_source="VIDEO_URL",
    use_cached_transcript=True,
    use_cached_booklet=False,  # Force regeneration
    temperature=0.7  # Try different temperature
)
```

### 4. Sequential vs Parallel Generation

```python
# Sequential (recommended) - maintains context between chapters
result = transcript_to_booklet(
    input_source="VIDEO_URL",
    parallel=False,  # Sequential with context
    use_chapters=True
)

# Parallel - faster but no context sharing
result = transcript_to_booklet(
    input_source="VIDEO_URL",
    parallel=True,  # 5x faster
    use_chapters=True
)
```

See `examples/example_usage.py` for complete examples.

## 🏗️ Project Structure

```
video-to-book/
├── README.md                    # This file
├── pyproject.toml              # Dependencies
├── .env.example                # Environment template
├── vtb                         # CLI wrapper script
├── examples/                   # Usage examples
│   ├── example_usage.py        # Python API examples
│   ├── generate_booklet.py     # Simple booklet generation
│   ├── ejemplo_pipeline.py     # Spanish examples
│   └── test_pipeline.py        # Import verification
├── docs/                       # Documentation
│   ├── CLI_GUIDE.md           # CLI documentation
│   ├── PIPELINE_EXPLICACION.md # Pipeline explanation
│   ├── CHANGELOG.md           # Change history
│   └── REFACTORING_SUMMARY.md # Refactoring notes
│
└── src/
    ├── pipeline.py             # Main API
    ├── processing/
    │   ├── content/            # Content generation
    │   │   ├── chapters.py     # Chapter-based generation
    │   │   └── generation.py   # Single-pass generation
    │   ├── slides/             # Slide extraction
    │   │   ├── extraction.py   # Slide detection
    │   │   └── segmentation.py # Deduplication
    │   ├── video/              # YouTube operations
    │   │   └── youtube.py      # Transcript/metadata
    │   └── vision/             # Vision analysis
    │       └── analyzer.py     # Vision LLM integration
    └── utils/
        ├── cache.py            # Caching system
        ├── decorators.py       # Cache decorators
        └── video_input.py      # Input normalization
```

## 🔑 API Reference

### Main Functions

#### `transcript_to_booklet()`
Generate educational booklet from YouTube video transcript.

**Parameters:**
- `input_source` (str): YouTube URL or video ID
- `model` (str): LLM model (default: "gpt-4o")
- `provider` (str): LLM provider ("openai", "anthropic", "openrouter")
- `temperature` (float): Generation temperature (default: 0.5)
- `use_chapters` (bool): Use chapter-based generation (default: True)
- `parallel` (bool): Parallel processing (default: False, sequential recommended)
- `words_per_section` (int): Target words per section (default: 2000)
- `use_cached_transcript` (bool): Use cached transcript (default: True)
- `use_cached_metadata` (bool): Use cached metadata (default: True)
- `use_cached_booklet` (bool): Use cached booklet (default: True)

**Returns:** Dict with `success`, `booklet`, `video_id`, `video_title`, etc.

#### `process_video_with_slides()`
Complete video processing with slide extraction and vision analysis.

**Parameters:**
- `input_source` (str): YouTube URL/ID or local video file
- `force_reprocess` (bool): Skip cache (default: False)
- `skip_vision` (bool): Skip vision analysis (default: False)
- `vision_provider` (str): Vision provider ("google", "openai", "openrouter")
- `vision_model` (str): Vision model name

**Returns:** Dict with `slides`, `transcript`, `vision_analysis`, etc.

## ⚙️ Configuration

### Environment Variables

Create a `.env` file with your API keys:

```bash
# Required for content generation
OPENAI_API_KEY=sk-...
# Or use Anthropic
ANTHROPIC_API_KEY=sk-ant-...
# Or use OpenRouter
OPENROUTER_API_KEY=sk-or-...

# Optional for vision analysis
GOOGLE_API_KEY=...  # For Gemini vision
```

### LLM Providers

**OpenAI** (default):
- Models: `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`
- Best for: General purpose, vision analysis

**Anthropic**:
- Models: `claude-3-5-sonnet-20241022`, `claude-3-opus-20240229`
- Best for: Long-form content, detailed analysis

**OpenRouter**:
- Access to multiple models through one API
- Best for: Flexibility, cost optimization

## 💡 Tips & Best Practices

### Content Generation

1. **Use Sequential Mode** for better coherence:
   ```python
   transcript_to_booklet(url, parallel=False)  # Maintains context
   ```

2. **Adjust Temperature** based on needs:
   - `0.3-0.5`: Factual, consistent (recommended)
   - `0.6-0.8`: More creative, varied

3. **Cache Control** for iterations:
   ```python
   # Keep transcript, regenerate booklet
   transcript_to_booklet(url, use_cached_booklet=False)
   ```

### Slide Extraction

1. **Use `extract_slides_robust`** for presentations
2. **Adjust FPS** based on video type:
   - Presentations: `fps_sample=2.0`
   - Fast-paced: `fps_sample=5.0`

### Vision Analysis

1. **Skip vision** if not needed (saves time/money):
   ```python
   process_video_with_slides(url, skip_vision=True)
   ```

2. **Use Gemini** for cost-effective vision analysis:
   ```python
   process_video_with_slides(url, vision_provider="google", vision_model="gemini-1.5-flash")
   ```

## 🐛 Troubleshooting

### Common Issues

**Import errors after refactoring:**
```bash
python test_pipeline.py  # Verify all imports work
```

**No transcript available:**
- Video may not have captions
- Try a different video or use Whisper for local transcription

**Vision analysis fails:**
- Check API key is set correctly
- Verify provider/model combination is valid

**Cache issues:**
```python
from src.pipeline import clear_video_cache
clear_video_cache("VIDEO_ID")  # Clear specific video
```

## 📝 Recent Changes

See `REFACTORING_SUMMARY.md` for details on the recent simplification.

**Key improvements:**
- ✅ Simplified from 90+ files to 17 core modules
- ✅ Removed unnecessary agent abstractions
- ✅ Direct processing pipeline API
- ✅ All functionality preserved

## 📄 License

MIT

## 🤝 Contributing

This is a learning/personal project. Feel free to fork and adapt for your needs!
