"""
Example 2: Custom LangGraph Workflow

This example shows how to build a custom graph from scratch.
Instead of using the pre-built ReAct agent, we'll create our own nodes and edges.

Learning objectives:
- How to define custom state
- How to create nodes (functions that process state)
- How to add edges (transitions between nodes)
- How to use conditional routing
"""

import os
import sys
from pathlib import Path
from typing import TypedDict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

from src.tools.youtube_tools import (
    extract_video_id_from_url,
    get_video_metadata,
    get_youtube_transcript,
)

load_dotenv()


# Step 1: Define the State
# This is the data structure that flows through our graph
class VideoWorkflowState(TypedDict):
    """State for our custom video workflow."""
    youtube_url: str
    video_id: str | None
    metadata: dict | None
    transcript: dict | None
    error: str | None
    current_step: str


# Step 2: Create Node Functions
# Each node is a function that takes state and returns updated state

def extract_id_node(state: VideoWorkflowState) -> VideoWorkflowState:
    """
    Node 1: Extract video ID from URL.
    
    This is our first node in the workflow.
    It calls the extract_video_id_from_url tool.
    """
    print(f"\n🔍 Node: Extracting video ID from {state['youtube_url']}")
    
    # Call the tool directly (not through an agent)
    result = extract_video_id_from_url.invoke({"youtube_url": state["youtube_url"]})
    
    if result["success"]:
        print(f"✅ Extracted video ID: {result['video_id']}")
        return {
            **state,
            "video_id": result["video_id"],
            "current_step": "id_extracted"
        }
    else:
        print(f"❌ Failed to extract video ID: {result.get('error')}")
        return {
            **state,
            "error": result.get("error"),
            "current_step": "error"
        }


def get_metadata_node(state: VideoWorkflowState) -> VideoWorkflowState:
    """
    Node 2: Get video metadata.
    
    This node fetches information about the video.
    """
    print(f"\n📊 Node: Fetching metadata for video {state['video_id']}")
    
    result = get_video_metadata.invoke({"video_id": state["video_id"]})
    
    if result["success"]:
        print(f"✅ Got metadata: {result['title']}")
        return {
            **state,
            "metadata": result,
            "current_step": "metadata_fetched"
        }
    else:
        print(f"❌ Failed to get metadata: {result.get('error')}")
        return {
            **state,
            "error": result.get("error"),
            "current_step": "error"
        }


def get_transcript_node(state: VideoWorkflowState) -> VideoWorkflowState:
    """
    Node 3: Get video transcript.
    
    This node tries to fetch the transcript.
    """
    print(f"\n📝 Node: Fetching transcript for video {state['video_id']}")
    
    result = get_youtube_transcript.invoke({"video_id": state["video_id"]})
    
    if result["success"]:
        print(f"✅ Got transcript: {result['num_segments']} segments")
        return {
            **state,
            "transcript": result,
            "current_step": "transcript_fetched"
        }
    else:
        print(f"⚠️  No transcript available: {result.get('error')}")
        # Not a critical error - we can continue without transcript
        return {
            **state,
            "transcript": None,
            "current_step": "transcript_unavailable"
        }


# Step 3: Create Routing Functions
# These decide which node to go to next based on state

def route_after_id_extraction(state: VideoWorkflowState) -> str:
    """
    Decide where to go after extracting video ID.
    
    If there's an error, end the workflow.
    Otherwise, continue to metadata fetching.
    """
    if state.get("error"):
        print("\n🛑 Routing: Error detected, ending workflow")
        return END
    
    print("\n➡️  Routing: Going to metadata node")
    return "get_metadata"


def route_after_metadata(state: VideoWorkflowState) -> str:
    """
    Decide where to go after getting metadata.
    
    Always try to get transcript next.
    """
    if state.get("error"):
        return END
    
    print("\n➡️  Routing: Going to transcript node")
    return "get_transcript"


def route_after_transcript(state: VideoWorkflowState) -> str:
    """
    Decide where to go after getting transcript.
    
    We're done, so end the workflow.
    """
    print("\n➡️  Routing: Workflow complete, ending")
    return END


# Step 4: Build the Graph

def create_video_workflow() -> StateGraph:
    """
    Create the custom video analysis workflow.
    
    This builds a graph with three nodes:
    1. Extract video ID
    2. Get metadata
    3. Get transcript
    
    Returns:
        Compiled graph ready to run
    """
    print("\n🏗️  Building workflow graph...")
    
    # Create the graph with our state type
    workflow = StateGraph(VideoWorkflowState)
    
    # Add nodes
    workflow.add_node("extract_id", extract_id_node)
    workflow.add_node("get_metadata", get_metadata_node)
    workflow.add_node("get_transcript", get_transcript_node)
    
    # Set the entry point (where the workflow starts)
    workflow.set_entry_point("extract_id")
    
    # Add conditional edges (routing based on state)
    workflow.add_conditional_edges(
        "extract_id",
        route_after_id_extraction,
        # Map routing function outputs to node names
        {
            "get_metadata": "get_metadata",
            END: END
        }
    )
    
    workflow.add_conditional_edges(
        "get_metadata",
        route_after_metadata,
        {
            "get_transcript": "get_transcript",
            END: END
        }
    )
    
    workflow.add_conditional_edges(
        "get_transcript",
        route_after_transcript,
        {
            END: END
        }
    )
    
    # Compile the graph
    app = workflow.compile()
    
    print("✅ Workflow graph built!\n")
    
    return app


def main() -> None:
    """Run the custom graph example."""
    
    print("\n" + "="*70)
    print("EXAMPLE 2: Custom LangGraph Workflow")
    print("="*70)
    
    # Check for API key (not needed for this example, but good practice)
    if not os.getenv("OPENAI_API_KEY"):
        print("\n⚠️  Warning: OPENAI_API_KEY not found")
        print("This example doesn't use LLMs, so it will still work!")
    
    # Create the workflow
    workflow = create_video_workflow()
    
    # Example YouTube URL
    youtube_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    print(f"🎥 Processing video: {youtube_url}")
    print("\n" + "="*70)
    
    # Create initial state
    initial_state: VideoWorkflowState = {
        "youtube_url": youtube_url,
        "video_id": None,
        "metadata": None,
        "transcript": None,
        "error": None,
        "current_step": "start"
    }
    
    # Run the workflow
    # The graph will execute nodes in order based on our routing
    result = workflow.invoke(initial_state)
    
    # Display results
    print("\n" + "="*70)
    print("WORKFLOW RESULTS")
    print("="*70 + "\n")
    
    print(f"Final step: {result['current_step']}")
    
    if result.get("error"):
        print(f"\n❌ Error: {result['error']}")
    else:
        print(f"\n✅ Success!")
        
        if result.get("metadata"):
            print(f"\n📊 Metadata:")
            print(f"  Title: {result['metadata'].get('title')}")
            print(f"  Duration: {result['metadata'].get('duration')} seconds")
            print(f"  Channel: {result['metadata'].get('channel')}")
            print(f"  Has subtitles: {result['metadata'].get('has_subtitles')}")
        
        if result.get("transcript"):
            print(f"\n📝 Transcript:")
            print(f"  Segments: {result['transcript'].get('num_segments')}")
            print(f"  Total duration: {result['transcript'].get('total_duration')} seconds")
            
            # Show first few segments
            segments = result['transcript'].get('segments', [])
            if segments:
                print(f"\n  First 3 segments:")
                for i, seg in enumerate(segments[:3], 1):
                    print(f"    {i}. [{seg['start']:.1f}s] {seg['text'][:60]}...")
    
    print("\n" + "="*70)
    print("\n📚 Key Takeaways:")
    print("  1. We built a custom graph with explicit nodes and edges")
    print("  2. Each node is just a Python function")
    print("  3. Conditional routing lets us handle different scenarios")
    print("  4. State flows through the graph automatically")
    print("  5. No LLM needed - we called tools directly!")
    print()


if __name__ == "__main__":
    main()
