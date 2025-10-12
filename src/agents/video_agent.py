"""
Video Analysis Agent using LangGraph

This module implements a LangGraph-based agent that analyzes YouTube videos.
The agent can:
1. Extract video ID from URL
2. Get video metadata
3. Retrieve or generate transcripts

For junior developers:
- This demonstrates the ReAct pattern (Reasoning + Acting)
- The agent thinks about what to do, then calls tools
- LangGraph manages the conversation and tool calling automatically
"""

import logging
from typing import Any, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from src.tools.youtube_tools import get_tools

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VideoAgentState(TypedDict):
    """
    State for the video analysis agent.
    
    This is the data structure that flows through the agent's workflow.
    
    Attributes:
        youtube_url: Input YouTube URL to analyze
        messages: Conversation history between user and agent
        video_id: Extracted video ID (filled by agent)
        metadata: Video metadata (filled by agent)
        transcript: Video transcript segments (filled by agent)
        error: Error message if something went wrong
    """
    youtube_url: str
    messages: list[BaseMessage]
    video_id: str | None
    metadata: dict[str, Any] | None
    transcript: list[dict[str, Any]] | None
    error: str | None


# System prompt that defines the agent's behavior
VIDEO_AGENT_SYSTEM_PROMPT = """You are a video analysis assistant specialized in processing YouTube videos.

Your capabilities:
1. Extract video IDs from YouTube URLs
2. Fetch video metadata (title, duration, description, etc.)
3. Retrieve transcripts/captions when available
4. Download videos or audio when needed

Your workflow:
1. First, extract the video ID from the provided URL using extract_video_id_from_url
2. Then, get the video metadata using get_video_metadata
3. Try to get the transcript using get_youtube_transcript
4. If transcript is not available, inform the user and suggest downloading

Important guidelines:
- Always explain what you're doing before calling a tool
- If a tool fails, explain why and suggest alternatives
- Be concise but informative in your responses
- Focus on getting accurate information

Remember: You have access to tools. Use them!
"""


def create_video_agent(
    model: str = "gpt-4-turbo-preview",
    temperature: float = 0,
) -> Any:
    """
    Create a video analysis agent using LangGraph's ReAct pattern.
    
    The ReAct pattern means:
    - Re: Reasoning - Agent thinks about what to do
    - Act: Acting - Agent calls tools to accomplish tasks
    
    This is a pre-built pattern from LangGraph that handles:
    - Tool calling
    - Error handling
    - Conversation management
    
    Args:
        model: OpenAI model to use (default: gpt-4-turbo-preview)
        temperature: LLM temperature (0 = deterministic, 1 = creative)
        
    Returns:
        Compiled LangGraph agent ready to use
        
    Example:
        >>> agent = create_video_agent()
        >>> result = agent.invoke({
        ...     "messages": [HumanMessage(content="Analyze https://youtube.com/watch?v=abc")]
        ... })
        >>> print(result["messages"][-1].content)
    """
    logger.info(f"Creating video agent with model: {model}")
    
    # Initialize the LLM
    llm = ChatOpenAI(model=model, temperature=temperature)
    
    # Get all YouTube tools
    tools = get_tools()
    
    # Create the ReAct agent
    # This is a pre-built LangGraph pattern that:
    # 1. Receives a message
    # 2. Decides what tool to call (if any)
    # 3. Calls the tool
    # 4. Processes the result
    # 5. Repeats until task is complete
    agent = create_react_agent(
        llm,
        tools,
        state_modifier=VIDEO_AGENT_SYSTEM_PROMPT
    )
    
    logger.info("Video agent created successfully")
    return agent


def analyze_video(youtube_url: str, model: str = "gpt-4-turbo-preview") -> dict[str, Any]:
    """
    High-level function to analyze a YouTube video.
    
    This is a convenience function that:
    1. Creates the agent
    2. Sends the analysis request
    3. Returns the results
    
    Args:
        youtube_url: YouTube URL to analyze
        model: OpenAI model to use
        
    Returns:
        Dictionary with analysis results
        
    Example:
        >>> result = analyze_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        >>> print(result["summary"])
        Video: Rick Astley - Never Gonna Give You Up
        Duration: 3:33
        Transcript: Available (45 segments)
    """
    logger.info(f"Starting video analysis for: {youtube_url}")
    
    # Create the agent
    agent = create_video_agent(model=model)
    
    # Create the initial message
    initial_message = HumanMessage(
        content=f"""Please analyze this YouTube video: {youtube_url}

Follow these steps:
1. Extract the video ID
2. Get the video metadata (title, duration, etc.)
3. Try to get the transcript
4. Provide a summary of what you found

Be thorough and explain each step."""
    )
    
    # Run the agent
    result = agent.invoke({
        "messages": [initial_message]
    })
    
    # Extract information from the conversation
    messages = result["messages"]
    
    # The last message should be the agent's final response
    final_response = messages[-1].content if messages else "No response"
    
    # Parse tool call results from the conversation
    # Tool calls and results are stored in the messages
    video_id = None
    metadata = None
    transcript = None
    
    for message in messages:
        # Check if this is a tool message (result of a tool call)
        if hasattr(message, "name"):
            if message.name == "get_video_metadata" and hasattr(message, "content"):
                try:
                    import json
                    metadata = json.loads(message.content) if isinstance(message.content, str) else message.content
                except:
                    pass
            elif message.name == "get_youtube_transcript" and hasattr(message, "content"):
                try:
                    import json
                    transcript = json.loads(message.content) if isinstance(message.content, str) else message.content
                except:
                    pass
            elif message.name == "extract_video_id_from_url" and hasattr(message, "content"):
                try:
                    import json
                    data = json.loads(message.content) if isinstance(message.content, str) else message.content
                    if isinstance(data, dict):
                        video_id = data.get("video_id")
                except:
                    pass
    
    logger.info("Video analysis complete")
    
    return {
        "youtube_url": youtube_url,
        "video_id": video_id,
        "metadata": metadata,
        "transcript": transcript,
        "summary": final_response,
        "messages": messages,
    }


# Example usage
if __name__ == "__main__":
    """
    Example of how to use the video agent.
    
    Run this file directly to see the agent in action:
    $ python -m src.agents.video_agent
    """
    import os
    from dotenv import load_dotenv
    
    # Load environment variables
    load_dotenv()
    
    # Check if API key is set
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set in environment")
        print("Please create a .env file with your API key")
        exit(1)
    
    # Example YouTube URL
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    print(f"\n{'='*60}")
    print("VIDEO AGENT EXAMPLE")
    print(f"{'='*60}\n")
    print(f"Analyzing: {test_url}\n")
    
    # Analyze the video
    result = analyze_video(test_url)
    
    # Print results
    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}\n")
    print(f"Video ID: {result['video_id']}")
    
    if result['metadata']:
        print(f"\nMetadata:")
        print(f"  Title: {result['metadata'].get('title')}")
        print(f"  Duration: {result['metadata'].get('duration')} seconds")
        print(f"  Channel: {result['metadata'].get('channel')}")
    
    if result['transcript']:
        print(f"\nTranscript:")
        print(f"  Segments: {result['transcript'].get('num_segments')}")
        print(f"  Duration: {result['transcript'].get('total_duration')} seconds")
    
    print(f"\nAgent Summary:")
    print(f"{result['summary']}")
    
    print(f"\n{'='*60}\n")
