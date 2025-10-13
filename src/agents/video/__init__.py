"""
Video Analysis Agent Module

This module provides a LangGraph agent for video analysis.

Components:
- agent.py: The LangGraph agent implementation
- tools.py: YouTube-specific tools decorated with @tool for the agent

For simple processing without an agent, use src.processing.video instead.

Usage:
    # Use the LangGraph agent (advanced)
    from src.agents.video import create_video_agent
    agent = create_video_agent()
    
    # Or use simple processing (recommended)
    from src.processing.video import analyze_video_workflow
    result = analyze_video_workflow(youtube_url)
"""

# Import LLM agent
from src.agents.video.agent import (
    create_video_agent,
    VideoAgentState,
)

# Import tools for the agent
from src.agents.video.tools import (
    get_tools,
)

# Re-export processing functions for backward compatibility
from src.processing.video import (
    extract_video_id_from_url,
    get_video_metadata,
    get_youtube_transcript,
    download_youtube_content,
    generate_transcript_from_audio,
    analyze_video_workflow,
    get_transcript,
    analyze_video,
)

__all__ = [
    # LLM Agent
    "create_video_agent",
    "VideoAgentState",
    "get_tools",
    # Processing functions (re-exported for backward compatibility)
    "extract_video_id_from_url",
    "get_video_metadata",
    "get_youtube_transcript",
    "download_youtube_content",
    "generate_transcript_from_audio",
    "analyze_video_workflow",
    "get_transcript",
    "analyze_video",
]
