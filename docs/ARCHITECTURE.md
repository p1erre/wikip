# Architecture Overview

This document explains how the video-to-book system is structured using LangGraph.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INPUT                              │
│                    (YouTube URL)                                │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LANGGRAPH WORKFLOW                           │
│                                                                 │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐ │
│  │   Validate   │─────▶│    Agent     │─────▶│   Generate   │ │
│  │    Input     │      │   Analysis   │      │    Report    │ │
│  └──────────────┘      └──────────────┘      └──────────────┘ │
│         │                      │                      │        │
│         │                      │                      │        │
│         ▼                      ▼                      ▼        │
│    [State]                [State]                [State]       │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      VIDEO AGENT                                │
│                   (ReAct Pattern)                               │
│                                                                 │
│  Think ──▶ Act ──▶ Observe ──▶ Think ──▶ Act ──▶ ...          │
│    │        │         │                                        │
│    │        │         └─ Tool Results                          │
│    │        └─────────── Call Tools                            │
│    └────────────────────── LLM Reasoning                       │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                         TOOLS                                   │
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐                   │
│  │  Extract Video   │  │   Get Video      │                   │
│  │      ID          │  │   Metadata       │                   │
│  └──────────────────┘  └──────────────────┘                   │
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐                   │
│  │  Get YouTube     │  │   Download       │                   │
│  │  Transcript      │  │   Content        │                   │
│  └──────────────────┘  └──────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    EXTERNAL SERVICES                            │
│                                                                 │
│     YouTube API          yt-dlp          OpenAI API            │
└─────────────────────────────────────────────────────────────────┘
```

## Component Breakdown

### 1. LangGraph Workflow (Orchestration Layer)

**Purpose:** Manages the overall flow of the application

**Components:**
- **Nodes:** Individual processing steps (validate, analyze, report)
- **Edges:** Transitions between nodes
- **State:** Shared data structure that flows through the workflow

**Example:**
```python
workflow = StateGraph(VideoWorkflowState)
workflow.add_node("validate", validate_input_node)
workflow.add_node("analyze", agent_analysis_node)
workflow.add_edge("validate", "analyze")
```

### 2. Video Agent (Intelligence Layer)

**Purpose:** Makes decisions about what to do

**Pattern:** ReAct (Reasoning + Acting)
- **Reasoning:** LLM thinks about the task
- **Acting:** LLM calls tools to accomplish goals
- **Observation:** LLM sees tool results
- **Repeat:** Until task is complete

**Example Flow:**
```
User: "Analyze this video: youtube.com/watch?v=abc"
  ↓
Agent thinks: "I need to extract the video ID first"
  ↓
Agent acts: Calls extract_video_id_from_url("youtube.com/watch?v=abc")
  ↓
Agent observes: Got video_id = "abc"
  ↓
Agent thinks: "Now I'll get the metadata"
  ↓
Agent acts: Calls get_video_metadata("abc")
  ↓
... continues ...
```

### 3. Tools (Capability Layer)

**Purpose:** Provide specific capabilities to the agent

**Characteristics:**
- **Atomic:** Each tool does one thing well
- **Idempotent:** Safe to call multiple times
- **Validated:** Pydantic models ensure correct inputs

**Available Tools:**
1. `extract_video_id_from_url` - Parse YouTube URLs
2. `get_video_metadata` - Fetch video information
3. `get_youtube_transcript` - Get captions/subtitles
4. `download_youtube_content` - Download video/audio

### 4. State (Data Layer)

**Purpose:** Store and pass data between components

**Structure:**
```python
class VideoWorkflowState(TypedDict):
    # Input
    youtube_url: str
    
    # Processing
    video_id: str | None
    metadata: dict | None
    transcript: dict | None
    
    # Control
    current_step: str
    error: str | None
    
    # Output
    summary: str | None
```

**Key Concepts:**
- **Immutable:** State is not modified, new state is returned
- **Typed:** TypedDict provides type safety
- **Shared:** All nodes can read and update state

## Data Flow

### Example: Analyzing a Video

```
1. User Input
   youtube_url = "https://youtube.com/watch?v=abc123"
   
2. Validate Node
   ✓ Check URL format
   ✓ Update state: current_step = "validated"
   
3. Agent Node
   ├─ Agent receives state
   ├─ Agent calls extract_video_id_from_url
   │  └─ Returns: video_id = "abc123"
   ├─ Agent calls get_video_metadata
   │  └─ Returns: {title: "...", duration: 180, ...}
   ├─ Agent calls get_youtube_transcript
   │  └─ Returns: {segments: [...]}
   └─ Agent updates state with results
   
4. Report Node
   ├─ Read state (has all data)
   ├─ Format into readable report
   └─ Update state: summary = "..."
   
5. Output
   Return final state with complete analysis
```

## LangGraph Concepts in Practice

### Nodes

**Definition:** Functions that process state

**Example:**
```python
def my_node(state: MyState) -> MyState:
    # Do some work
    result = process(state["input"])
    
    # Return updated state
    return {
        **state,
        "output": result
    }
```

### Edges

**Types:**

1. **Simple Edge:** Always go from A to B
```python
graph.add_edge("node_a", "node_b")
```

2. **Conditional Edge:** Route based on state
```python
def router(state):
    if state["error"]:
        return "error_handler"
    return "next_step"

graph.add_conditional_edges("node_a", router)
```

### State Management

**Reducers:** Control how state updates are merged

```python
from typing import Annotated
from operator import add

class State(TypedDict):
    # Replaced on update
    current: str
    
    # Appended on update
    history: Annotated[list[str], add]
```

## ReAct Pattern Deep Dive

### What is ReAct?

**Re**asoning + **Act**ing: An agent pattern where the LLM alternates between thinking and doing.

### How It Works

```
┌─────────────────────────────────────────┐
│  1. THOUGHT                             │
│  "I need to get the video ID"           │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  2. ACTION                              │
│  Call: extract_video_id_from_url(...)   │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  3. OBSERVATION                         │
│  Result: {"video_id": "abc123"}         │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  4. THOUGHT                             │
│  "Great! Now I'll get metadata"         │
└─────────────────┬───────────────────────┘
                  │
                  ▼
                 ...
```

### Why ReAct?

- ✅ **Transparent:** We can see the agent's reasoning
- ✅ **Flexible:** Agent decides what to do dynamically
- ✅ **Robust:** Can handle unexpected situations
- ✅ **Debuggable:** Easy to see where things go wrong

## Error Handling

### Strategy

```
┌──────────────┐
│  Any Node    │
└──────┬───────┘
       │
       ├─ Success ──▶ Next Node
       │
       └─ Error ────▶ Error Handler ──▶ END
```

### Implementation

```python
def my_node(state):
    try:
        result = do_work()
        return {**state, "result": result}
    except Exception as e:
        return {**state, "error": str(e)}

def router(state):
    if state.get("error"):
        return "error_handler"
    return "next_node"
```

## Extending the System

### Adding a New Tool

1. **Create the tool function:**
```python
from langchain_core.tools import tool

@tool
def my_new_tool(input: str) -> dict:
    """Description of what the tool does."""
    result = do_something(input)
    return {"success": True, "result": result}
```

2. **Add to tools list:**
```python
YOUTUBE_TOOLS.append(my_new_tool)
```

3. **Agent automatically has access!**

### Adding a New Node

1. **Create node function:**
```python
def my_new_node(state: MyState) -> MyState:
    # Process state
    return {**state, "new_field": "value"}
```

2. **Add to graph:**
```python
graph.add_node("my_node", my_new_node)
graph.add_edge("previous_node", "my_node")
```

### Adding a New Agent

1. **Create agent:**
```python
from langgraph.prebuilt import create_react_agent

my_agent = create_react_agent(llm, tools, state_modifier="...")
```

2. **Wrap in node:**
```python
def my_agent_node(state):
    result = my_agent.invoke({"messages": [...]})
    return {**state, "agent_result": result}
```

3. **Add to workflow:**
```python
workflow.add_node("my_agent", my_agent_node)
```

## Best Practices

### 1. Keep Nodes Small
- Each node should do one thing
- Easy to test and debug
- Reusable across workflows

### 2. Use Type Hints
- TypedDict for state
- Pydantic for tool inputs
- Helps catch errors early

### 3. Handle Errors Gracefully
- Try/except in nodes
- Conditional routing for errors
- Informative error messages

### 4. Log Everything
- Log node entry/exit
- Log tool calls
- Log state changes

### 5. Test Independently
- Test tools separately
- Test nodes separately
- Test graph integration

## Performance Considerations

### Caching
- Cache video downloads
- Cache transcripts
- Cache metadata

### Parallel Execution
- LangGraph supports parallel nodes
- Use when nodes are independent

### Streaming
- Use `.stream()` for long workflows
- Provide real-time feedback
- Better user experience

## Summary

The architecture is built on three key principles:

1. **Separation of Concerns**
   - Workflow (LangGraph) handles orchestration
   - Agent handles decision-making
   - Tools handle specific tasks

2. **Type Safety**
   - TypedDict for state
   - Pydantic for validation
   - Catch errors at development time

3. **Composability**
   - Nodes are reusable
   - Tools are independent
   - Easy to extend and modify

This creates a system that is:
- ✅ Easy to understand
- ✅ Easy to test
- ✅ Easy to extend
- ✅ Production-ready
