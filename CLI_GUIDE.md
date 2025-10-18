# CLI Quick Reference

Simple command-line interface for the video-to-book pipeline.

## Installation

The CLI is ready to use! Just make sure you have:
- `uv` installed
- API keys in `.env` file

## Usage

You can use the CLI in two ways:

### Option 1: Direct (recommended)
```bash
uv run python -m src.cli <command> [options]
```

### Option 2: Wrapper script
```bash
./vtb <command> [options]
```

## Commands

### 1. Generate Booklet

Generate a comprehensive booklet from a YouTube video.

**Basic usage:**
```bash
./vtb generate "https://youtube.com/watch?v=VIDEO_ID"
```

**With options:**
```bash
# Use different model
./vtb generate VIDEO_URL --model gpt-4o-mini --provider openai

# Parallel mode (faster, no context)
./vtb generate VIDEO_URL --parallel

# Custom output file
./vtb generate VIDEO_URL -o my_booklet.md

# Preview the output
./vtb generate VIDEO_URL --preview

# Regenerate (ignore cache)
./vtb generate VIDEO_URL --no-cache

# Adjust temperature
./vtb generate VIDEO_URL --temperature 0.7

# Use Anthropic Claude
./vtb generate VIDEO_URL --provider anthropic --model claude-3-5-sonnet-20241022
```

**All options:**
- `-o, --output FILE` - Output file path (default: booklet_VIDEO_ID.md)
- `--model MODEL` - LLM model (default: gpt-4o)
- `--provider PROVIDER` - LLM provider: openai, anthropic, openrouter (default: openai)
- `--temperature TEMP` - Generation temperature 0.0-1.0 (default: 0.5)
- `--words N` - Target words per section (default: 2000)
- `--parallel` - Use parallel generation (faster but no context between chapters)
- `--no-chapters` - Single-pass generation instead of chapter-based
- `--no-cache` - Regenerate everything (ignore cache)
- `--preview` - Show preview of generated content

### 2. Process Video

Process video with slide extraction and optional vision analysis.

**Basic usage:**
```bash
./vtb process "https://youtube.com/watch?v=VIDEO_ID"
```

**With options:**
```bash
# Skip vision analysis (faster, cheaper)
./vtb process VIDEO_URL --no-vision

# Use different vision provider
./vtb process VIDEO_URL --vision-provider openai

# Force reprocessing
./vtb process VIDEO_URL --force
```

**All options:**
- `--no-vision` - Skip vision analysis (faster, cheaper)
- `--vision-provider PROVIDER` - Vision provider: google, openai, openrouter (default: google)
- `--vision-model MODEL` - Vision model (default: gemini-1.5-flash)
- `--force` - Force reprocessing (ignore cache)

### 3. Cache Info

Show information about cached videos.

```bash
./vtb cache-info
```

**Output:**
- Cache directory location
- Total number of cached videos
- Total cache size
- Details for each cached video (transcripts, slides, booklets)

### 4. Cache Clear

Clear cache for a specific video.

```bash
./vtb cache-clear VIDEO_ID
```

## Examples

### Quick Start
```bash
# Generate booklet (simplest)
./vtb generate "https://youtube.com/watch?v=Hm-ZIiwiN1o"
```

### Production Use
```bash
# High-quality booklet with Claude
./vtb generate VIDEO_URL \
  --provider anthropic \
  --model claude-3-5-sonnet-20241022 \
  --temperature 0.5 \
  -o output/booklet.md
```

### Fast Iteration
```bash
# Parallel mode for speed
./vtb generate VIDEO_URL --parallel

# Skip vision to save time
./vtb process VIDEO_URL --no-vision
```

### Cache Management
```bash
# Check what's cached
./vtb cache-info

# Clear specific video
./vtb cache-clear VIDEO_ID

# Regenerate booklet only (keep transcript)
./vtb generate VIDEO_URL --no-cache
```

## Tips

1. **First run**: Use default settings to see how it works
   ```bash
   ./vtb generate VIDEO_URL
   ```

2. **Iterate on content**: Keep cached transcript, regenerate booklet
   ```bash
   # First run caches transcript
   ./vtb generate VIDEO_URL
   
   # Try different temperature
   ./vtb generate VIDEO_URL --temperature 0.7 --no-cache
   ```

3. **Save costs**: Use cheaper models for testing
   ```bash
   ./vtb generate VIDEO_URL --model gpt-4o-mini
   ```

4. **Speed vs Quality**: 
   - Sequential (default): Better coherence, slower
   - Parallel (`--parallel`): Faster, less coherent

5. **Check cache**: See what's stored
   ```bash
   ./vtb cache-info
   ```

## Troubleshooting

**"No module named 'src'"**
- Make sure you're in the project directory
- Use `uv run python -m src.cli` instead of `./vtb`

**"API key not found"**
- Check your `.env` file
- Make sure the key is set: `OPENAI_API_KEY=sk-...`

**"No transcript available"**
- Video doesn't have captions
- Try a different video

**Process seems stuck**
- It's likely generating content (can take 5-10 minutes for long videos)
- Check terminal for progress logs
- Press Ctrl+C to cancel

## Help

Get help for any command:
```bash
./vtb --help
./vtb generate --help
./vtb process --help
```
