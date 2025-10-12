# LangGraph Tutorial: Building a Video Analysis Agent

## Table of Contents
1. [What is LangGraph?](#what-is-langgraph)
2. [Core Concepts](#core-concepts)
3. [Building Our First Agent](#building-our-first-agent)
4. [The Video Agent](#the-video-agent)
5. [Tools and Function Calling](#tools-and-function-calling)
6. [State Management](#state-management)
7. [Creating the Graph](#creating-the-graph)
8. [Running and Testing](#running-and-testing)

---

## What is LangGraph?

**LangGraph** is a library for building stateful, multi-actor applications with LLMs. Think of it as a way to create workflows where:

- **Nodes** = Actions (agents, tools, or functions)
- **Edges** = Transitions (what happens next)
- **State** = Shared data that flows through the workflow

### Why LangGraph for Our Video Agent?

```
Traditional Approach:          LangGraph Approach:
┌─────────────────┐           ┌──────────────────┐
│ Call LLM        │           │   State Graph    │
│ Parse response  │           │  ┌────┐  ┌────┐  │
│ Call tool       │           │  │Node│→ │Node│  │
│ Call LLM again  │           │  └────┘  └────┘  │
│ ... manually    │           │  Auto-managed!   │
└─────────────────┘           └──────────────────┘
```

**Benefits:**
- ✅ Automatic state management
- ✅ Built-in retry logic
- ✅ Checkpointing (save/resume)
- ✅ Visual workflow representation
- ✅ Easy debugging

---

## Core Concepts

### 1. State

State is a typed dictionary that flows through your graph. All nodes can read and modify it.

```python
from typing import TypedDict

class VideoState(TypedDict):
    """State that flows through our workflow"""
    youtube_url: str          # Input
    video_title: str          # Filled by agent
    transcript: list[str]     # Filled by agent
    error: str | None         # Error handling
```

### 2. Nodes

Nodes are functions that receive state and return updated state.

```python
def download_video(state: VideoState) -> VideoState:
    """A node that downloads a video"""
    url = state["youtube_url"]
    # ... download logic ...
    state["video_title"] = "Downloaded Video"
    return state
```

### 3. Edges

Edges define the flow between nodes.

```python
# Simple edge: always go from A to B
graph.add_edge("download_video", "extract_transcript")

# Conditional edge: decide based on state
def should_retry(state: VideoState) -> str:
    return "retry" if state["error"] else "continue"

graph.add_conditional_edges("download_video", should_retry)
```

### 4. Graph

The graph combines nodes and edges into a workflow.

```python
from langgraph.graph import StateGraph

# Create graph
graph = StateGraph(VideoState)

# Add nodes
graph.add_node("download", download_video)
graph.add_node("transcribe", extract_transcript)

# Add edges
graph.add_edge("download", "transcribe")

# Compile
app = graph.compile()
```

---

## Building Our First Agent

Let's build a simple agent that decides what to do with a YouTube URL.

### Step 1: Define the State

```python
from typing import TypedDict, Literal

class SimpleVideoState(TypedDict):
    youtube_url: str
    action: Literal["download_video", "download_transcript", "generate_transcript"]
    reasoning: str
```

### Step 2: Create the Agent Node

```python
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

def video_decision_agent(state: SimpleVideoState) -> SimpleVideoState:
    """
    Agent that decides what to do with a YouTube URL.
    
    This is our first LangGraph node!
    """
    # Initialize LLM
    llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0)
    
    # Create prompt
    system_prompt = """You are a video analysis assistant. 
    Given a YouTube URL, decide the best action:
    - download_video: Download the full video file
    - download_transcript: Use YouTube's existing captions
    - generate_transcript: Download audio and generate transcript
    
    Respond with JSON: {"action": "...", "reasoning": "..."}
    """
    
    user_message = f"YouTube URL: {state['youtube_url']}"
    
    # Call LLM
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message)
    ])
    
    # Parse response (simplified - in production, use structured output)
    import json
    result = json.loads(response.content)
    
    # Update state
    state["action"] = result["action"]
    state["reasoning"] = result["reasoning"]
    
    return state
```

### Step 3: Create the Graph

```python
from langgraph.graph import StateGraph, END

# Create graph
graph = StateGraph(SimpleVideoState)

# Add our agent as a node
graph.add_node("decide", video_decision_agent)

# Set entry point
graph.set_entry_point("decide")

# Add edge to end
graph.add_edge("decide", END)

# Compile the graph
app = graph.compile()
```

### Step 4: Run It!

```python
# Run the agent
result = app.invoke({
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
})

print(f"Action: {result['action']}")
print(f"Reasoning: {result['reasoning']}")
```

**Output:**
```
Action: download_transcript
Reasoning: This video likely has existing captions, which is faster than generating
```

---

## The Video Agent

Now let's build our production video agent with **tools** (function calling).

### Architecture

```
┌─────────────────────────────────────────────┐
│           Video Analysis Agent              │
│                                             │
│  Decides what to do and calls tools:        │
│  ┌──────────────┐  ┌──────────────┐        │
│  │ YouTube Tool │  │ Whisper Tool │        │
│  │              │  │              │        │
│  │ - Download   │  │ - Transcribe │        │
│  │ - Get info   │  │ - Timestamps │        │
│  │ - Captions   │  │              │        │
│  └──────────────┘  └──────────────┘        │
└─────────────────────────────────────────────┘
```

### Step 1: Define Tools

Tools are functions the agent can call. LangGraph uses LangChain's tool system.

```python
from langchain_core.tools import tool
from pydantic import BaseModel, Field

class YouTubeDownloadInput(BaseModel):
    """Input for YouTube download tool"""
    video_id: str = Field(description="YouTube video ID")
    download_video: bool = Field(
        default=False, 
        description="Whether to download video file (vs just audio)"
    )

@tool(args_schema=YouTubeDownloadInput)
def download_youtube_video(video_id: str, download_video: bool = False) -> dict:
    """
    Download a YouTube video or audio.
    
    Returns metadata about the downloaded content.
    """
    import yt_dlp
    
    # Configure yt-dlp options
    ydl_opts = {
        'format': 'bestvideo+bestaudio' if download_video else 'bestaudio',
        'outtmpl': f'downloads/{video_id}.%(ext)s',
        'quiet': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)
            
            return {
                "success": True,
                "title": info.get("title"),
                "duration": info.get("duration"),
                "file_path": f"downloads/{video_id}.{info.get('ext')}",
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


class TranscriptInput(BaseModel):
    """Input for transcript download tool"""
    video_id: str = Field(description="YouTube video ID")

@tool(args_schema=TranscriptInput)
def get_youtube_transcript(video_id: str) -> dict:
    """
    Get the transcript/captions from a YouTube video.
    
    Returns the transcript segments with timestamps.
    """
    from youtube_transcript_api import YouTubeTranscriptApi
    
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        
        return {
            "success": True,
            "segments": [
                {
                    "text": segment["text"],
                    "start": segment["start"],
                    "duration": segment["duration"]
                }
                for segment in transcript
            ]
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
```

### Step 2: Create Agent with Tools

```python
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

# Initialize LLM
llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0)

# Create list of tools
tools = [download_youtube_video, get_youtube_transcript]

# Create ReAct agent (Reasoning + Acting)
# This is a pre-built LangGraph pattern!
video_agent = create_react_agent(
    llm,
    tools,
    state_modifier="""You are a video analysis assistant.
    
    Your job is to:
    1. Extract the video ID from the YouTube URL
    2. Try to get the transcript using get_youtube_transcript
    3. If that fails, download the audio using download_youtube_video
    
    Always explain your reasoning before calling tools.
    """
)
```

**What is ReAct?**
- **Re**asoning: Agent thinks about what to do
- **Act**ing: Agent calls tools
- Repeats until task is complete

### Step 3: Define State for Our Agent

```python
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class VideoAgentState(TypedDict):
    """State for our video agent workflow"""
    
    # Input
    youtube_url: str
    
    # Agent communication (managed by LangGraph)
    messages: Annotated[list[BaseMessage], add_messages]
    
    # Outputs
    video_metadata: dict | None
    transcript: list[dict] | None
    error: str | None
```

**Note:** `Annotated[list[BaseMessage], add_messages]` is special:
- `add_messages` is a reducer that appends new messages to the list
- This is how agents communicate in LangGraph

### Step 4: Create Wrapper Node

```python
def video_analysis_node(state: VideoAgentState) -> VideoAgentState:
    """
    Node that runs the video agent.
    
    This wraps our ReAct agent in a node that fits our state.
    """
    # Create initial message for the agent
    from langchain_core.messages import HumanMessage
    
    initial_message = HumanMessage(
        content=f"Analyze this YouTube video and get its transcript: {state['youtube_url']}"
    )
    
    # Run the agent
    result = video_agent.invoke({
        "messages": [initial_message]
    })
    
    # Extract results from agent's messages
    # The agent's tool calls and responses are in result["messages"]
    state["messages"] = result["messages"]
    
    # Parse the final result
    # (In production, you'd extract this from tool call results)
    # For now, we'll add a helper to parse the messages
    
    return state
```

---

## Tools and Function Calling

### How Tool Calling Works in LangGraph

```
1. Agent receives task
   ↓
2. Agent decides to call a tool
   ↓
3. LangGraph automatically calls the tool
   ↓
4. Tool result is added to messages
   ↓
5. Agent sees result and continues
   ↓
6. Repeat until task complete
```

### Example: Tool Call Flow

```python
# Agent's thought process (simplified):

# Turn 1: Agent thinks
"I need to get the transcript. I'll call get_youtube_transcript."

# Turn 2: Tool is called automatically
get_youtube_transcript(video_id="dQw4w9WgXcQ")
# Returns: {"success": True, "segments": [...]}

# Turn 3: Agent sees result
"Great! I got the transcript. Task complete."
```

### Creating Custom Tools

```python
from langchain_core.tools import tool

@tool
def extract_video_id(youtube_url: str) -> str:
    """Extract video ID from a YouTube URL."""
    import re
    
    # Pattern for YouTube URLs
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, youtube_url)
        if match:
            return match.group(1)
    
    raise ValueError(f"Could not extract video ID from: {youtube_url}")

# Now the agent can call this tool!
```

---

## State Management

### Understanding State Updates

LangGraph state is **immutable** - each node returns a new state.

```python
# ❌ Wrong: Modifying state directly
def bad_node(state: VideoState) -> VideoState:
    state["title"] = "New Title"  # This works but is not idiomatic
    return state

# ✅ Better: Return new state
def good_node(state: VideoState) -> VideoState:
    return {
        **state,
        "title": "New Title"
    }

# ✅ Best: Use Pydantic models
from pydantic import BaseModel

class VideoState(BaseModel):
    youtube_url: str
    title: str | None = None
    
    def with_title(self, title: str) -> "VideoState":
        return self.model_copy(update={"title": title})
```

### State Reducers

Reducers control how state updates are merged.

```python
from typing import Annotated
from operator import add

class State(TypedDict):
    # Normal field: replaced on update
    current_step: str
    
    # List with add reducer: appends new items
    completed_steps: Annotated[list[str], add]
    
    # Messages: special reducer that handles message deduplication
    messages: Annotated[list[BaseMessage], add_messages]

# Usage:
state1 = {"completed_steps": ["step1"]}
state2 = {"completed_steps": ["step2"]}
# After merge: {"completed_steps": ["step1", "step2"]}
```

---

## Creating the Graph

### Full Video Agent Graph

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph.message import add_messages

# 1. Define State
class VideoWorkflowState(TypedDict):
    youtube_url: str
    messages: Annotated[list[BaseMessage], add_messages]
    video_id: str | None
    transcript: list[dict] | None
    error: str | None
    current_step: str

# 2. Create Nodes
def extract_video_id_node(state: VideoWorkflowState) -> VideoWorkflowState:
    """Extract video ID from URL"""
    import re
    url = state["youtube_url"]
    match = re.search(r'(?:v=|/)([0-9A-Za-z_-]{11}).*', url)
    
    if match:
        return {
            **state,
            "video_id": match.group(1),
            "current_step": "video_id_extracted"
        }
    else:
        return {
            **state,
            "error": "Invalid YouTube URL",
            "current_step": "error"
        }

def get_transcript_node(state: VideoWorkflowState) -> VideoWorkflowState:
    """Try to get transcript from YouTube"""
    from youtube_transcript_api import YouTubeTranscriptApi
    
    try:
        transcript = YouTubeTranscriptApi.get_transcript(state["video_id"])
        return {
            **state,
            "transcript": transcript,
            "current_step": "transcript_retrieved"
        }
    except Exception as e:
        return {
            **state,
            "error": f"Could not get transcript: {str(e)}",
            "current_step": "transcript_failed"
        }

def download_and_transcribe_node(state: VideoWorkflowState) -> VideoWorkflowState:
    """Download video and generate transcript"""
    # This would use Whisper or similar
    # For now, simplified
    return {
        **state,
        "transcript": [{"text": "Generated transcript", "start": 0}],
        "current_step": "transcript_generated"
    }

# 3. Create Graph
workflow = StateGraph(VideoWorkflowState)

# 4. Add Nodes
workflow.add_node("extract_id", extract_video_id_node)
workflow.add_node("get_transcript", get_transcript_node)
workflow.add_node("generate_transcript", download_and_transcribe_node)

# 5. Add Edges
workflow.set_entry_point("extract_id")

# Conditional routing based on state
def route_after_extraction(state: VideoWorkflowState) -> str:
    """Decide where to go after extracting video ID"""
    if state.get("error"):
        return END
    return "get_transcript"

def route_after_transcript(state: VideoWorkflowState) -> str:
    """Decide what to do if transcript retrieval fails"""
    if state.get("transcript"):
        return END
    return "generate_transcript"

workflow.add_conditional_edges("extract_id", route_after_extraction)
workflow.add_conditional_edges("get_transcript", route_after_transcript)
workflow.add_edge("generate_transcript", END)

# 6. Compile
app = workflow.compile()
```

### Visualizing the Graph

```python
# LangGraph can generate a visual representation!
from IPython.display import Image, display

display(Image(app.get_graph().draw_mermaid_png()))
```

This generates:
```
┌─────────────┐
│ extract_id  │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ get_transcript  │
└──────┬──────────┘
       │
       ├─ Success ──→ END
       │
       └─ Fail ──→ ┌──────────────────────┐
                   │ generate_transcript  │
                   └──────────┬───────────┘
                              │
                              ▼
                             END
```

---

## Running and Testing

### Basic Execution

```python
# Run the workflow
result = app.invoke({
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "current_step": "start"
})

print(f"Video ID: {result['video_id']}")
print(f"Transcript segments: {len(result['transcript'])}")
print(f"Final step: {result['current_step']}")
```

### Streaming Results

```python
# Stream intermediate results
for state in app.stream({
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "current_step": "start"
}):
    print(f"Current step: {state['current_step']}")
```

### Checkpointing (Save & Resume)

```python
from langgraph.checkpoint.sqlite import SqliteSaver

# Create checkpointer
memory = SqliteSaver.from_conn_string(":memory:")

# Compile with checkpointing
app = workflow.compile(checkpointer=memory)

# Run with thread ID
config = {"configurable": {"thread_id": "video-123"}}
result = app.invoke(initial_state, config)

# Resume later with same thread ID
continued = app.invoke(None, config)  # Continues from last checkpoint
```

### Error Handling

```python
def safe_node(state: VideoWorkflowState) -> VideoWorkflowState:
    """Node with error handling"""
    try:
        # ... do work ...
        return {**state, "current_step": "success"}
    except Exception as e:
        return {
            **state,
            "error": str(e),
            "current_step": "error"
        }

# Add error routing
def route_on_error(state: VideoWorkflowState) -> str:
    if state.get("error"):
        return "error_handler"
    return "next_step"

workflow.add_conditional_edges("safe_node", route_on_error)
```

---

## Best Practices

### 1. Keep Nodes Small and Focused

```python
# ❌ Bad: One node does everything
def massive_node(state):
    # Download video
    # Extract frames
    # Generate transcript
    # Analyze content
    # ...
    pass

# ✅ Good: Each node has one job
def download_node(state): ...
def extract_frames_node(state): ...
def transcribe_node(state): ...
```

### 2. Use Type Hints

```python
# ✅ Always type your state and nodes
def my_node(state: MyState) -> MyState:
    ...
```

### 3. Make Nodes Idempotent

```python
# ✅ Node can be safely retried
def download_node(state: VideoState) -> VideoState:
    # Check if already downloaded
    if state.get("video_path"):
        return state
    
    # Download
    path = download_video(state["url"])
    return {**state, "video_path": path}
```

### 4. Add Logging

```python
import logging

def my_node(state: MyState) -> MyState:
    logging.info(f"Processing: {state['youtube_url']}")
    # ... work ...
    logging.info("Complete!")
    return state
```

### 5. Test Nodes Independently

```python
def test_extract_id_node():
    state = {
        "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    }
    result = extract_video_id_node(state)
    assert result["video_id"] == "dQw4w9WgXcQ"
```

---

## Next Steps

Now that you understand LangGraph basics, you can:

1. **Add More Agents:** Create frame extraction agent, text generation agent
2. **Add Human-in-the-Loop:** Require approval at key steps
3. **Implement Retries:** Use `retry` edges for failed operations
4. **Add Parallel Execution:** Process multiple videos simultaneously
5. **Build a UI:** Connect LangGraph to a web interface

Check out the implementation in `src/` to see these concepts in action!

---

## Quick Reference

```python
# Create graph
from langgraph.graph import StateGraph, END

graph = StateGraph(MyState)

# Add nodes
graph.add_node("name", function)

# Add edges
graph.add_edge("from", "to")  # Always go from→to
graph.add_conditional_edges("from", routing_function)  # Conditional

# Set entry
graph.set_entry_point("start_node")

# Compile
app = graph.compile()

# Run
result = app.invoke(initial_state)

# Stream
for state in app.stream(initial_state):
    print(state)
```

---

**Ready to build?** Check out `src/agents/video_agent.py` for the full implementation!
