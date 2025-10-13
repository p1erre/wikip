# Simplified Workflow Summary

## What Changed

Refactored from an LLM-based agent to a **simple, deterministic workflow** for video analysis.

### Before (LLM Agent)
```python
# Complex LLM agent that decides what to do
agent = create_video_agent()
result = agent.invoke({"messages": [HumanMessage("Analyze video...")]})
# Unpredictable, requires API calls, harder to debug
```

### After (Simple Workflow)
```python
# Clear, step-by-step workflow
result = analyze_video_workflow("https://youtube.com/watch?v=abc")
# Predictable, deterministic, easy to understand
```

## New Structure

```
src/agents/video/
├── __init__.py          # Exports both workflow and agent
├── agent.py             # LLM agent (for advanced use cases)
├── workflow.py          # ✨ NEW: Simple deterministic workflow
└── tools.py             # All tools including new transcription tool
```

## New Workflow

**File**: `src/agents/video/workflow.py`

### Main Function: `analyze_video_workflow()`

```python
def analyze_video_workflow(
    youtube_url: str,
    force_download: bool = False,
    output_dir: str = "./downloads"
) -> dict[str, Any]:
    """
    Simple deterministic workflow:
    1. Extract video ID
    2. Get metadata
    3. Try YouTube transcript
    4. If no transcript, download audio
    5. Generate transcript with Whisper
    """
```

### Steps

1. **Extract Video ID**
   - Parse URL to get video ID
   - Handles multiple URL formats

2. **Get Metadata**
   - Title, duration, channel, views
   - Uses yt-dlp

3. **Try YouTube Transcript**
   - Attempts to get existing captions
   - Prefers manual over auto-generated

4. **Download Audio** (if needed)
   - Downloads audio only (faster, smaller)
   - Saves to `./downloads/`

5. **Generate Transcript** (if needed)
   - Uses Whisper to transcribe audio
   - Smart file size handling

## New Tool: `generate_transcript_from_audio`

**File**: `src/agents/video/tools.py`

### Smart Whisper Integration

```python
@tool
def generate_transcript_from_audio(video_id: str, audio_path: str = None):
    """
    Generate transcript using Whisper.
    
    - Files < 25MB: OpenAI Whisper API (fast, cloud)
    - Files >= 25MB: Local Whisper (slower, local)
    
    Automatically chooses the best option!
    """
```

### Why Two Approaches?

| Approach | File Size | Speed | Cost | Quality |
|----------|-----------|-------|------|---------|
| **Whisper API** | < 25MB | Fast | $0.006/min | Excellent |
| **Local Whisper** | Any size | Slower | Free | Excellent |

**Decision**: Use API when possible, fall back to local for large files.

## Usage Examples

### 1. Simple Transcript Extraction

```python
from src.agents.video import get_transcript

# Get transcript (tries YouTube first, then Whisper)
transcript = get_transcript("https://youtube.com/watch?v=abc")

for segment in transcript['segments']:
    print(f"[{segment['start']:.1f}s] {segment['text']}")
```

### 2. Full Video Analysis

```python
from src.agents.video import analyze_video_workflow

# Analyze video
result = analyze_video_workflow("https://youtube.com/watch?v=abc")

print(f"Title: {result['metadata']['title']}")
print(f"Duration: {result['metadata']['duration']}s")
print(f"Transcript segments: {result['transcript']['num_segments']}")
```

### 3. Force Download & Transcribe

```python
# Skip YouTube transcript, always use Whisper
result = analyze_video_workflow(
    "https://youtube.com/watch?v=abc",
    force_download=True  # Always download and transcribe
)
```

## Comparison: Workflow vs Agent

### Simple Workflow (Recommended)

**File**: `workflow.py`

**Pros**:
- ✅ Deterministic behavior
- ✅ No LLM API calls needed
- ✅ Fast and predictable
- ✅ Easy to understand
- ✅ Clear error messages
- ✅ No token costs

**Cons**:
- ❌ Fixed sequence of steps
- ❌ Can't adapt to unusual situations

**Use when**:
- You just want transcripts
- You want predictable behavior
- You're building a pipeline
- You want to minimize costs

### LLM Agent (Advanced)

**File**: `agent.py`

**Pros**:
- ✅ Can reason about problems
- ✅ Adapts to situations
- ✅ Can handle edge cases
- ✅ Natural language interface

**Cons**:
- ❌ Requires LLM API calls
- ❌ Unpredictable behavior
- ❌ Slower
- ❌ Costs tokens

**Use when**:
- You need reasoning
- You have complex requirements
- You want natural language interface
- Cost is not a concern

## Testing

### Test Script

**File**: `test_workflow.py`

```bash
# Run the test
uv run python test_workflow.py
```

### Test Results

Tested with: **The FDE Playbook for AI Startups with Bob McGrew**
- URL: `https://www.youtube.com/watch?v=Zyw-YA0k3xo`
- Duration: 50 minutes 42 seconds
- Audio size: 26.4MB

**Results**:
- ✅ Video ID extracted
- ✅ Metadata fetched
- ✅ Audio downloaded (26.4MB)
- ⚠️ Whisper API rejected (file too large)
- 🔄 Ready for local Whisper fallback

## Fixed Issues

### 1. YouTube Transcript API

**Problem**: `YouTubeTranscriptApi.get_transcript()` doesn't exist

**Fix**:
```python
# Before (broken)
transcript = YouTubeTranscriptApi.get_transcript(video_id)

# After (fixed)
api = YouTubeTranscriptApi()
transcript = api.fetch(video_id)
```

### 2. Whisper File Size Limit

**Problem**: Whisper API has 25MB limit

**Fix**: Smart fallback
```python
if file_size_mb < 25:
    # Use API (fast)
    use_whisper_api()
else:
    # Use local Whisper (slower but works)
    use_local_whisper()
```

## Dependencies

### Required
```toml
# Already in pyproject.toml
yt-dlp = "*"
openai = "*"
youtube-transcript-api = "*"
```

### Optional (for local Whisper)
```bash
# Install if you need to transcribe large files
pip install openai-whisper
# or
uv add openai-whisper
```

## API Documentation

### `analyze_video_workflow()`

```python
def analyze_video_workflow(
    youtube_url: str,
    force_download: bool = False,
    output_dir: str = "./downloads"
) -> dict[str, Any]:
    """
    Returns:
        {
            "youtube_url": str,
            "video_id": str,
            "metadata": dict,  # Title, duration, channel, etc.
            "transcript": dict,  # Segments with timestamps
            "audio_path": str | None,  # If downloaded
            "steps_completed": list[str],
            "errors": list[str]
        }
    """
```

### `get_transcript()`

```python
def get_transcript(
    youtube_url: str,
    prefer_youtube: bool = True,
    output_dir: str = "./downloads"
) -> dict[str, Any]:
    """
    Simplified interface - just get the transcript.
    
    Returns:
        {
            "success": bool,
            "video_id": str,
            "num_segments": int,
            "segments": list[dict],
            "total_duration": float,
            "source": "youtube" | "whisper_api" | "whisper_local"
        }
    """
```

## Migration Guide

### From Old Agent

```python
# Old way (LLM agent)
from src.agents.video import create_video_agent, analyze_video

agent = create_video_agent()
result = analyze_video(url)

# New way (simple workflow)
from src.agents.video import analyze_video_workflow

result = analyze_video_workflow(url)
```

### Backward Compatibility

The old `analyze_video()` function still works:

```python
from src.agents.video import analyze_video

# This now uses the workflow (not the LLM agent)
result = analyze_video(url)
```

## Future Enhancements

### 1. Chunking for Large Files

For files > 25MB, split into chunks:
```python
def chunk_audio(audio_path, chunk_size_mb=20):
    # Split audio into smaller chunks
    # Transcribe each chunk
    # Merge results
```

### 2. Multiple Languages

```python
result = analyze_video_workflow(
    url,
    language="es"  # Spanish
)
```

### 3. Custom Whisper Models

```python
result = analyze_video_workflow(
    url,
    whisper_model="large"  # Better accuracy, slower
)
```

### 4. Parallel Processing

```python
# Process multiple videos in parallel
results = await asyncio.gather(*[
    analyze_video_workflow(url) for url in urls
])
```

## Summary

### What We Built

1. ✅ **Simple workflow** - Deterministic, no LLM needed
2. ✅ **Whisper integration** - Smart API/local fallback
3. ✅ **Fixed YouTube API** - Updated to new API
4. ✅ **Clear interface** - Easy to use and understand
5. ✅ **Backward compatible** - Old code still works

### Benefits

- 🚀 **Faster** - No LLM reasoning overhead
- 💰 **Cheaper** - No token costs for basic operations
- 🎯 **Predictable** - Always does the same thing
- 🐛 **Debuggable** - Clear steps, easy to trace
- 📚 **Educational** - Shows how to build workflows

### When to Use What

| Task | Use |
|------|-----|
| Get transcript | `get_transcript()` |
| Full analysis | `analyze_video_workflow()` |
| Complex reasoning | `create_video_agent()` (LLM) |
| Natural language | `create_video_agent()` (LLM) |

Perfect foundation for video-to-book conversion! 🎉
