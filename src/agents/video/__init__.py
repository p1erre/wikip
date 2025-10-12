"""
Video Analysis Agent Module

This module provides a complete video analysis agent with its own tools.

Components:
- agent.py: The LangGraph agent implementation
- tools.py: YouTube-specific tools for the agent

Usage:
    from src.agents.video import create_video_agent, analyze_video
    from src.agents.video.tools import extract_video_id_from_url
    
    # Or import the whole module
    from src.agents import video
    agent = video.create_video_agent()
"""

# Import workflow functions (simple, deterministic)
from src.agents.video.workflow import (
    analyze_video_workflow,
    get_transcript,
    analyze_video,  # Backward compatible
)

# Import LLM agent (for advanced use cases)
from src.agents.video.agent import (
    create_video_agent,
    VideoAgentState,
)

# Import tools for direct use
from src.agents.video.tools import (
    extract_video_id_from_url,
    get_video_metadata,
    get_youtube_transcript,
    download_youtube_content,
    get_tools,
)

__all__ = [
    # Workflow (simple, recommended)
    "analyze_video_workflow",
    "get_transcript",
    "analyze_video",  # Backward compatible
    # LLM Agent (advanced)
    "create_video_agent",
    "VideoAgentState",
    # Tools
    "extract_video_id_from_url",
    "get_video_metadata",
    "get_youtube_transcript",
    "download_youtube_content",
    "generate_transcript_from_audio",
    "get_tools",
]
