# Video-to-Book: LangGraph Tutorial Project

A hands-on tutorial for learning **LangGraph** by building a real-world video analysis agent.

## 🎯 What You'll Learn

This project teaches you LangGraph through a practical example: analyzing YouTube videos with AI agents.

### Core Concepts Covered

- ✅ **LangGraph Basics**: Nodes, edges, and state management
- ✅ **ReAct Pattern**: How agents reason and act
- ✅ **Tool Calling**: Giving agents capabilities
- ✅ **Custom Workflows**: Building graphs from scratch
- ✅ **Streaming**: Real-time progress updates
- ✅ **Best Practices**: Production-ready patterns

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- OpenAI API key (for the agent examples)
- FFmpeg (optional, for video processing)

### Installation

```bash
# Clone or navigate to the project
cd video-to-book

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### Run Your First Example

```bash
# Example 1: Basic agent with tools
python examples/01_basic_agent.py

# Example 2: Custom graph workflow
python examples/02_custom_graph.py

# Example 3: Streaming output
python examples/03_streaming_output.py
```

## 📚 Learning Path

### 1. Start with the Tutorial

Read **[LANGGRAPH_TUTORIAL.md](docs/LANGGRAPH_TUTORIAL.md)** - A comprehensive guide covering:
- What is LangGraph and why use it
- Core concepts (state, nodes, edges, graphs)
- Building your first agent
- Tools and function calling
- Creating custom workflows

### 2. Explore the Examples

Work through the examples in order:

#### **Example 1: Basic Agent** (`examples/01_basic_agent.py`)
- Uses pre-built ReAct agent
- Shows automatic tool calling
- Demonstrates message flow

#### **Example 2: Custom Graph** (`examples/02_custom_graph.py`)
- Build a graph from scratch
- Define custom nodes
- Implement conditional routing
- No LLM required!

#### **Example 3: Streaming** (`examples/03_streaming_output.py`)
- Real-time progress updates
- Stream intermediate results
- Better user experience

### 3. Study the Implementation

Dive into the source code:

```
src/
├── tools/
│   └── youtube_tools.py    # Tools agents can use
└── agents/
    └── video_agent.py      # Agent implementation
```

### 4. Experiment and Extend

Try modifying the code:
- Add new tools
- Change the workflow
- Implement error handling
- Add more agents

## 🏗️ Project Structure

```
video-to-book/
├── README.md               # This file
├── requirements.txt        # Dependencies
├── .env.example           # Environment template
│
├── docs/                   # Documentation
│   ├── LANGGRAPH_TUTORIAL.md   # Comprehensive tutorial
│   ├── DESIGN.md               # Framework comparison
│   ├── ARCHITECTURE.md         # System architecture
│   ├── QUICK_START.md          # 5-minute guide
│   ├── PROJECT_SUMMARY.md      # Overview
│   └── INDEX.md                # Navigation guide
│
├── src/
│   ├── tools/
│   │   └── youtube_tools.py    # YouTube interaction tools
│   └── agents/
│       └── video_agent.py      # Video analysis agent
│
└── examples/
    ├── 01_basic_agent.py       # Simple agent example
    ├── 02_custom_graph.py      # Custom workflow
    ├── 03_streaming_output.py  # Streaming results
    └── 04_complete_workflow.py # Production pattern
```

## 🛠️ Available Tools

The video agent has access to these tools:

### `extract_video_id_from_url`
Extract video ID from any YouTube URL format.

```python
result = extract_video_id_from_url("https://youtube.com/watch?v=abc123")
# Returns: {"success": True, "video_id": "abc123"}
```

### `get_video_metadata`
Get video information without downloading.

```python
metadata = get_video_metadata("abc123")
# Returns: title, duration, channel, description, etc.
```

### `get_youtube_transcript`
Fetch existing captions/transcript.

```python
transcript = get_youtube_transcript("abc123")
# Returns: segments with text and timestamps
```

### `download_youtube_content`
Download video or audio files.

```python
result = download_youtube_content("abc123", download_video=False)
# Downloads audio only
```

## 🎓 Understanding the Video Agent

### How It Works

```
User Request
    ↓
Agent receives message
    ↓
Agent decides: "I need to extract the video ID"
    ↓
Calls extract_video_id_from_url tool
    ↓
Gets result: {"video_id": "abc123"}
    ↓
Agent decides: "Now I'll get metadata"
    ↓
Calls get_video_metadata tool
    ↓
Gets result: {title, duration, ...}
    ↓
Agent decides: "Let me get the transcript"
    ↓
Calls get_youtube_transcript tool
    ↓
Gets result: {segments: [...]}
    ↓
Agent responds to user with summary
```

### The ReAct Pattern

**Re**asoning + **Act**ing:

1. **Thought**: "I need to get the video ID first"
2. **Action**: Call `extract_video_id_from_url`
3. **Observation**: Got video ID "abc123"
4. **Thought**: "Now I can get metadata"
5. **Action**: Call `get_video_metadata`
6. ... continues until task complete

## 📖 Code Examples

### Using the Agent

```python
from src.agents.video_agent import create_video_agent
from langchain_core.messages import HumanMessage

# Create agent
agent = create_video_agent()

# Send request
result = agent.invoke({
    "messages": [
        HumanMessage(content="Analyze https://youtube.com/watch?v=abc123")
    ]
})

# Get response
print(result["messages"][-1].content)
```

### Building a Custom Graph

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict

# Define state
class MyState(TypedDict):
    input: str
    output: str

# Create nodes
def process_node(state: MyState) -> MyState:
    return {**state, "output": state["input"].upper()}

# Build graph
graph = StateGraph(MyState)
graph.add_node("process", process_node)
graph.set_entry_point("process")
graph.add_edge("process", END)

# Run
app = graph.compile()
result = app.invoke({"input": "hello"})
print(result["output"])  # "HELLO"
```

## 🔧 Configuration

Edit `.env` file:

```bash
# Required: OpenAI API key
OPENAI_API_KEY=sk-...

# Optional: Anthropic for Claude models
ANTHROPIC_API_KEY=sk-ant-...

# Model selection
LLM_PROVIDER=openai
OPENAI_MODEL=gpt-4-turbo-preview
```

## 🧪 Testing

```bash
# Run all examples
python examples/01_basic_agent.py
python examples/02_custom_graph.py
python examples/03_streaming_output.py

# Or run the agent directly
python -m src.agents.video_agent
```

## 💡 Tips for Learning

1. **Start Simple**: Run example 1 first, understand what happens
2. **Read the Code**: The code is heavily commented for learning
3. **Experiment**: Change prompts, add print statements, break things!
4. **Check Logs**: The agent logs its decisions
5. **Use the Tutorial**: Refer to docs/LANGGRAPH_TUTORIAL.md for concepts

## 🐛 Troubleshooting

### "OPENAI_API_KEY not found"
- Create a `.env` file from `.env.example`
- Add your API key: `OPENAI_API_KEY=sk-...`

### "No module named 'yt_dlp'"
- Install dependencies: `pip install -r requirements.txt`

### "Could not get transcript"
- Not all videos have captions
- This is expected behavior, not an error
- The agent will suggest downloading instead

### "FFmpeg not found"
- Only needed for video downloads
- Install: `brew install ffmpeg` (Mac) or see [ffmpeg.org](https://ffmpeg.org)

## 📚 Additional Resources

- **[LangGraph Documentation](https://langchain-ai.github.io/langgraph/)**: Official docs
- **[LANGGRAPH_TUTORIAL.md](docs/LANGGRAPH_TUTORIAL.md)**: Our comprehensive tutorial
- **[DESIGN.md](docs/DESIGN.md)**: Framework comparison and architecture decisions
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)**: System architecture deep dive
- **[INDEX.md](docs/INDEX.md)**: Complete documentation guide

## 🎯 Next Steps

After completing this tutorial, you can:

1. **Add More Agents**: Frame extraction, text generation
2. **Implement Checkpointing**: Save and resume workflows
3. **Add Human-in-the-Loop**: Require approval at key steps
4. **Build a UI**: Create a web interface
5. **Deploy**: Put your agent in production

## 🤝 Contributing

This is a learning project! Feel free to:
- Add more examples
- Improve documentation
- Fix bugs
- Share your extensions

## 📝 License

MIT License - use this for learning and projects!

---

**Ready to learn LangGraph?** Start with [QUICK_START.md](docs/QUICK_START.md) or dive into [LANGGRAPH_TUTORIAL.md](docs/LANGGRAPH_TUTORIAL.md)!
