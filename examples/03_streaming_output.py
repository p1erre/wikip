"""
Example 3: Streaming Output

This example shows how to stream results from a LangGraph workflow.
Instead of waiting for the entire workflow to complete, we see each step as it happens.

Learning objectives:
- How to use .stream() instead of .invoke()
- How to process intermediate results
- How to provide real-time feedback to users
"""

import os
import sys
from pathlib import Path
from typing import TypedDict

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

from src.tools.youtube_tools import (
    extract_video_id_from_url,
    get_video_metadata,
    get_youtube_transcript,
)

load_dotenv()


class VideoWorkflowState(TypedDict):
    """State for streaming workflow."""
    youtube_url: str
    video_id: str | None
    metadata: dict | None
    transcript: dict | None
    error: str | None
    current_step: str


def extract_id_node(state: VideoWorkflowState) -> VideoWorkflowState:
    """Extract video ID from URL."""
    result = extract_video_id_from_url.invoke({"youtube_url": state["youtube_url"]})
    
    if result["success"]:
        return {
            **state,
            "video_id": result["video_id"],
            "current_step": "id_extracted"
        }
    else:
        return {
            **state,
            "error": result.get("error"),
            "current_step": "error"
        }


def get_metadata_node(state: VideoWorkflowState) -> VideoWorkflowState:
    """Get video metadata."""
    result = get_video_metadata.invoke({"video_id": state["video_id"]})
    
    if result["success"]:
        return {
            **state,
            "metadata": result,
            "current_step": "metadata_fetched"
        }
    else:
        return {
            **state,
            "error": result.get("error"),
            "current_step": "error"
        }


def get_transcript_node(state: VideoWorkflowState) -> VideoWorkflowState:
    """Get video transcript."""
    result = get_youtube_transcript.invoke({"video_id": state["video_id"]})
    
    if result["success"]:
        return {
            **state,
            "transcript": result,
            "current_step": "transcript_fetched"
        }
    else:
        return {
            **state,
            "current_step": "transcript_unavailable"
        }


def create_streaming_workflow() -> StateGraph:
    """Create workflow for streaming example."""
    workflow = StateGraph(VideoWorkflowState)
    
    workflow.add_node("extract_id", extract_id_node)
    workflow.add_node("get_metadata", get_metadata_node)
    workflow.add_node("get_transcript", get_transcript_node)
    
    workflow.set_entry_point("extract_id")
    
    # Simple linear flow for this example
    workflow.add_edge("extract_id", "get_metadata")
    workflow.add_edge("get_metadata", "get_transcript")
    workflow.add_edge("get_transcript", END)
    
    return workflow.compile()


def print_progress_bar(step: int, total: int, description: str) -> None:
    """Print a nice progress bar."""
    bar_length = 40
    filled = int(bar_length * step / total)
    bar = "█" * filled + "░" * (bar_length - filled)
    percent = int(100 * step / total)
    print(f"\r  [{bar}] {percent}% - {description}", end="", flush=True)


def main() -> None:
    """Run the streaming example."""
    
    print("\n" + "="*70)
    print("EXAMPLE 3: Streaming Output")
    print("="*70 + "\n")
    
    print("This example shows real-time progress as the workflow executes.\n")
    
    # Create workflow
    workflow = create_streaming_workflow()
    
    # Example URL
    youtube_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    print(f"🎥 Processing: {youtube_url}\n")
    print("="*70 + "\n")
    
    # Initial state
    initial_state: VideoWorkflowState = {
        "youtube_url": youtube_url,
        "video_id": None,
        "metadata": None,
        "transcript": None,
        "error": None,
        "current_step": "start"
    }
    
    # Stream the workflow execution
    # .stream() yields state after each node execution
    step_count = 0
    total_steps = 3  # We have 3 nodes
    
    print("📊 Progress:\n")
    
    for state in workflow.stream(initial_state):
        step_count += 1
        
        # state is a dict with node name as key
        # Get the node name and its output state
        node_name = list(state.keys())[0]
        node_state = state[node_name]
        
        current_step = node_state.get("current_step", "unknown")
        
        # Update progress based on current step
        if current_step == "id_extracted":
            print_progress_bar(1, total_steps, "Extracted video ID")
            print(f"\n    ✅ Video ID: {node_state.get('video_id')}")
            
        elif current_step == "metadata_fetched":
            print_progress_bar(2, total_steps, "Fetched metadata")
            metadata = node_state.get('metadata', {})
            print(f"\n    ✅ Title: {metadata.get('title', 'Unknown')}")
            print(f"    ✅ Duration: {metadata.get('duration', 0)} seconds")
            
        elif current_step == "transcript_fetched":
            print_progress_bar(3, total_steps, "Fetched transcript")
            transcript = node_state.get('transcript', {})
            print(f"\n    ✅ Transcript: {transcript.get('num_segments', 0)} segments")
            
        elif current_step == "transcript_unavailable":
            print_progress_bar(3, total_steps, "Transcript unavailable")
            print(f"\n    ⚠️  No transcript available")
            
        elif current_step == "error":
            print(f"\n    ❌ Error: {node_state.get('error')}")
            break
    
    print("\n\n" + "="*70)
    print("COMPLETE!")
    print("="*70 + "\n")
    
    print("📚 Key Takeaways:")
    print("  1. .stream() yields state after each node")
    print("  2. We can show progress in real-time")
    print("  3. Great for long-running workflows")
    print("  4. Users see what's happening, not just a loading spinner")
    print()


if __name__ == "__main__":
    main()
