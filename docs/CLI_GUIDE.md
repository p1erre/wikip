# CLI Guide

This project provides two CLI interfaces for different use cases.

## Overview

```
video-to-book/
├── src/cli/
│   ├── runner.py      ✅ Current: Tool/Agent runner
│   └── interactive.py 🚧 Future: Claude-style chat
└── vtb                # Convenience wrapper
```

## Current: Runner CLI

**Purpose**: Test and run tools/agents independently

**Use Cases**:
- Testing individual tools during development
- Debugging agent workflows
- Scripting and automation
- Quick experiments

### Installation

No extra dependencies needed - uses Python stdlib!

### Usage

**Three ways to run**:

```bash
# 1. Using the wrapper script (easiest)
./vtb tools extract-id "https://youtube.com/watch?v=abc123"

# 2. Using Python module
python -m src.cli.runner tools extract-id "https://youtube.com/watch?v=abc123"

# 3. With uv
uv run python -m src.cli.runner tools extract-id "https://youtube.com/watch?v=abc123"
```

### Commands

#### Tools

Run individual YouTube tools:

**Extract Video ID**
```bash
./vtb tools extract-id "https://youtube.com/watch?v=dQw4w9WgXcQ"

# Output:
# ✅ Success!
#   video_id: dQw4w9WgXcQ
```

**Get Video Metadata**
```bash
./vtb tools get-metadata dQw4w9WgXcQ

# Output:
# ✅ Success!
#   video_id: dQw4w9WgXcQ
#   title: Rick Astley - Never Gonna Give You Up
#   duration: 212
#   channel: Rick Astley
#   ...
```

**Get Transcript**
```bash
./vtb tools get-transcript dQw4w9WgXcQ

# Output:
# ✅ Success!
#   num_segments: 45
#   total_duration: 212.0
#   segments: [...]
```

**Download Video/Audio**
```bash
# Download audio only (default)
./vtb tools download dQw4w9WgXcQ

# Download full video
./vtb tools download dQw4w9WgXcQ --video

# Custom output directory
./vtb tools download dQw4w9WgXcQ --output-dir ./my-downloads
```

#### Agents

Run complete agent workflows:

**Analyze Video**
```bash
./vtb agent analyze "https://youtube.com/watch?v=dQw4w9WgXcQ"

# With custom model
./vtb agent analyze "https://youtube.com/watch?v=abc" --model gpt-4

# Output:
# 🤖 Analyzing video: https://youtube.com/watch?v=dQw4w9WgXcQ
# (This may take a moment...)
#
# ======================================================================
# ANALYSIS COMPLETE
# ======================================================================
#
# Video: Rick Astley - Never Gonna Give You Up
# Duration: 3:32
# Transcript: Available (45 segments)
# ...
```

### JSON Output

Add `--json` flag for machine-readable output (great for scripting):

```bash
./vtb tools get-metadata dQw4w9WgXcQ --json

# Output:
# {
#   "success": true,
#   "video_id": "dQw4w9WgXcQ",
#   "title": "Rick Astley - Never Gonna Give You Up",
#   "duration": 212,
#   ...
# }
```

**Use in scripts**:
```bash
# Extract just the title
TITLE=$(./vtb tools get-metadata dQw4w9WgXcQ --json | jq -r '.title')
echo "Video title: $TITLE"

# Check if transcript exists
HAS_TRANSCRIPT=$(./vtb tools get-metadata dQw4w9WgXcQ --json | jq -r '.has_subtitles')
if [ "$HAS_TRANSCRIPT" = "true" ]; then
    ./vtb tools get-transcript dQw4w9WgXcQ --json > transcript.json
fi
```

### Help

Get help for any command:

```bash
# Main help
./vtb --help

# Tools help
./vtb tools --help

# Specific tool help
./vtb tools download --help

# Agent help
./vtb agent --help
```

### Exit Codes

The CLI follows standard Unix conventions:
- `0` = Success
- `1` = Error

```bash
# Use in scripts
if ./vtb tools extract-id "https://youtube.com/watch?v=abc"; then
    echo "Success!"
else
    echo "Failed!"
fi
```

## Future: Interactive CLI

**Purpose**: Conversational agent interaction (like Claude Code)

**Status**: 🚧 Planned for future release

### Planned Features

1. **Conversational Interface**
   - Natural language interaction
   - Multi-turn conversations
   - Context awareness

2. **Streaming Responses**
   - Real-time output as agent thinks
   - Progress indicators
   - Cancellable operations

3. **Rich Terminal UI**
   - Syntax highlighting
   - Formatted output
   - Interactive prompts

4. **Session Management**
   - Save/restore conversations
   - Command history
   - Auto-completion

5. **Advanced Operations**
   - File operations
   - Code execution
   - Multi-video analysis

### Preview

```bash
# Future usage
./vtb chat

# Or
python -m src.cli.interactive
```

**Example session** (planned):
```
╭─ Video-to-Book Interactive CLI ─────────────────────────────╮
│ Type 'help' for commands, 'exit' to quit                    │
╰──────────────────────────────────────────────────────────────╯

You: Analyze this video: https://youtube.com/watch?v=abc123

Agent: I'll analyze that video for you. Let me start by getting
       the metadata...
       
       ✓ Video ID extracted: abc123
       ✓ Metadata retrieved
       
       Title: "Introduction to LangGraph"
       Duration: 15:30
       Channel: AI Tutorials
       
       Would you like me to get the transcript as well?

You: Yes, and summarize the key points

Agent: Getting transcript...
       
       ✓ Transcript retrieved (45 segments)
       
       Analyzing content...
       
       Key Points:
       1. LangGraph is a framework for building agentic AI
       2. It uses a graph-based approach...
       [streaming output continues...]

You: Save this analysis to a file

Agent: ✓ Saved to analysis_abc123.md
       
       Would you like to analyze another video?
```

## Design Philosophy

### Why Two CLIs?

**Runner CLI** (Current):
- ✅ Simple, lightweight
- ✅ No dependencies beyond stdlib
- ✅ Perfect for testing and scripting
- ✅ Fast startup
- ✅ Predictable output

**Interactive CLI** (Future):
- 🎯 Rich user experience
- 🎯 Conversational interaction
- 🎯 Complex workflows
- 🎯 Exploration and learning
- 🎯 Requires additional dependencies

### Separation of Concerns

```python
# runner.py - Simple, direct
result = tool.invoke({"video_id": "abc"})
print(result)

# interactive.py - Rich, conversational
async for chunk in agent.stream(message):
    console.print(chunk, style="agent")
    await handle_user_input()
```

## Examples

### Example 1: Quick Test

```bash
# Test if a video has captions
./vtb tools get-metadata dQw4w9WgXcQ --json | jq '.has_subtitles'
```

### Example 2: Batch Processing

```bash
# Process multiple videos
for video_id in abc123 def456 ghi789; do
    echo "Processing $video_id..."
    ./vtb tools get-transcript $video_id --json > "transcript_${video_id}.json"
done
```

### Example 3: Pipeline

```bash
# Extract ID, get metadata, download if duration < 10 min
URL="https://youtube.com/watch?v=abc123"

# Extract ID
ID=$(./vtb tools extract-id "$URL" --json | jq -r '.video_id')

# Get duration
DURATION=$(./vtb tools get-metadata "$ID" --json | jq -r '.duration')

# Download if short
if [ "$DURATION" -lt 600 ]; then
    ./vtb tools download "$ID"
fi
```

### Example 4: Error Handling

```bash
# Robust script with error handling
if ! ./vtb tools get-transcript "$VIDEO_ID" --json > transcript.json 2>&1; then
    echo "No transcript available, downloading video to generate one..."
    ./vtb tools download "$VIDEO_ID"
fi
```

## Development

### Adding New Tools

To add a new tool to the CLI:

1. **Create the tool** in `src/tools/`
2. **Add command** in `src/cli/runner.py`:

```python
def cmd_my_new_tool(args: argparse.Namespace) -> int:
    """My new tool."""
    result = my_new_tool.invoke({"arg": args.value})
    print_result(result, args.json)
    return 0 if result.get("success") else 1

# In create_parser():
my_tool_parser = tools_subparsers.add_parser(
    "my-tool",
    help="Description of my tool"
)
my_tool_parser.add_argument("value", help="Input value")
my_tool_parser.set_defaults(func=cmd_my_new_tool)
```

3. **Test it**:
```bash
./vtb tools my-tool test-value
```

### Adding New Agents

Similar process for agents:

```python
def cmd_agent_my_workflow(args: argparse.Namespace) -> int:
    """My custom workflow."""
    # Implementation
    pass

# In create_parser():
my_agent_parser = agent_subparsers.add_parser(
    "my-workflow",
    help="Description"
)
my_agent_parser.set_defaults(func=cmd_agent_my_workflow)
```

## Troubleshooting

### "Module not found"

Make sure you're running from the project root:
```bash
cd /path/to/video-to-book
./vtb --help
```

### "Permission denied"

Make the script executable:
```bash
chmod +x vtb
```

### "API key not found"

For agent commands, set up your `.env`:
```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### Tool returns error

Use `--json` to see detailed error:
```bash
./vtb tools get-transcript abc123 --json
```

## Tips & Tricks

### 1. Alias for Convenience

Add to your `.bashrc` or `.zshrc`:
```bash
alias vtb='/path/to/video-to-book/vtb'
```

### 2. Combine with jq

```bash
# Get just the title
./vtb tools get-metadata abc --json | jq -r '.title'

# Count transcript segments
./vtb tools get-transcript abc --json | jq '.segments | length'

# Extract all timestamps
./vtb tools get-transcript abc --json | jq -r '.segments[].start'
```

### 3. Use in Makefiles

```makefile
.PHONY: analyze
analyze:
	./vtb agent analyze $(URL)

.PHONY: download
download:
	./vtb tools download $(VIDEO_ID) --output-dir ./videos
```

### 4. CI/CD Integration

```yaml
# GitHub Actions example
- name: Analyze video
  run: |
    ./vtb agent analyze "${{ env.VIDEO_URL }}" --json > analysis.json
    
- name: Upload analysis
  uses: actions/upload-artifact@v2
  with:
    name: analysis
    path: analysis.json
```

## Comparison

| Feature | Runner CLI | Interactive CLI |
|---------|-----------|-----------------|
| **Status** | ✅ Available | 🚧 Planned |
| **Purpose** | Testing/Scripting | Conversation |
| **Dependencies** | Minimal | Rich UI libs |
| **Output** | Text/JSON | Formatted/Streaming |
| **Use Case** | Automation | Exploration |
| **Startup** | Instant | Slower |
| **Learning Curve** | Low | Medium |

## Next Steps

1. **Try the runner CLI**:
   ```bash
   ./vtb tools extract-id "https://youtube.com/watch?v=dQw4w9WgXcQ"
   ```

2. **Explore all commands**:
   ```bash
   ./vtb --help
   ./vtb tools --help
   ./vtb agent --help
   ```

3. **Use in scripts**:
   - See examples above
   - Combine with jq for JSON processing
   - Use exit codes for error handling

4. **Stay tuned for interactive CLI**:
   - Watch for updates
   - Will be announced when ready
   - Feedback welcome!

---

**Questions?** Check the main [README.md](../README.md) or [INDEX.md](INDEX.md)
