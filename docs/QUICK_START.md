# Quick Start Guide

Get up and running with the LangGraph video agent in 5 minutes!

## Setup (2 minutes)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up API key
cp .env.example .env
# Edit .env and add: OPENAI_API_KEY=sk-your-key-here

# 3. Test installation
python -c "import langgraph; print('✅ LangGraph installed!')"
```

## Run Your First Agent (1 minute)

```bash
python examples/01_basic_agent.py
```

This will:
- Create a video analysis agent
- Analyze a YouTube video
- Show you how the agent thinks and acts

## What Just Happened?

The agent:
1. **Extracted** the video ID from the URL
2. **Fetched** video metadata (title, duration, etc.)
3. **Retrieved** the transcript if available
4. **Summarized** everything for you

All automatically using the **ReAct pattern** (Reasoning + Acting)!

## Try Other Examples

```bash
# Custom graph without LLM
python examples/02_custom_graph.py

# Streaming output
python examples/03_streaming_output.py

# Complete workflow
python examples/04_complete_workflow.py
```

## Next Steps

1. **Read the tutorial**: [LANGGRAPH_TUTORIAL.md](LANGGRAPH_TUTORIAL.md)
2. **Explore the code**: Start with `src/tools/youtube_tools.py`
3. **Modify examples**: Change prompts, add features
4. **Build your own**: Create new agents and workflows

## Common Issues

**"OPENAI_API_KEY not found"**
- Make sure you created `.env` file
- Check the key is formatted: `OPENAI_API_KEY=sk-...`

**"No module named 'langgraph'"**
- Run: `pip install -r requirements.txt`

**"Could not get transcript"**
- This is normal! Not all videos have captions
- The agent will tell you this

## Quick Reference

### Create an Agent
```python
from src.agents.video_agent import create_video_agent

agent = create_video_agent()
```

### Run the Agent
```python
from langchain_core.messages import HumanMessage

result = agent.invoke({
    "messages": [HumanMessage(content="Analyze VIDEO_URL")]
})
```

### Build a Custom Graph
```python
from langgraph.graph import StateGraph, END

graph = StateGraph(MyState)
graph.add_node("my_node", my_function)
graph.set_entry_point("my_node")
graph.add_edge("my_node", END)
app = graph.compile()
```

### Use Tools Directly
```python
from src.tools.youtube_tools import get_video_metadata

result = get_video_metadata.invoke({"video_id": "abc123"})
```

## Learning Path

1. ✅ Run examples (you are here!)
2. 📖 Read [LANGGRAPH_TUTORIAL.md](LANGGRAPH_TUTORIAL.md)
3. 🔍 Study the code in `src/`
4. 🛠️ Modify and experiment
5. 🚀 Build your own agents

---

**Questions?** Check the full [README.md](README.md) or [LANGGRAPH_TUTORIAL.md](LANGGRAPH_TUTORIAL.md)
