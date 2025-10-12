"""
Example 4: Complete Video Analysis Workflow

This example combines everything we've learned:
- Custom graph structure
- Agent with tools
- Streaming output
- Error handling
- Real-world workflow

This is a production-ready example showing best practices.

Learning objectives:
- How to combine agents and custom nodes
- How to handle errors gracefully
- How to provide good user feedback
- How to structure a real application
"""

import os
import sys
from pathlib import Path
from typing import TypedDict, Annotated

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from src.agents.video_agent import create_video_agent

load_dotenv()


# ============================================================================
# STATE DEFINITION
# ============================================================================

class CompleteWorkflowState(TypedDict):
    """
    Complete state for video analysis workflow.
    
    This state tracks everything we need throughout the workflow.
    """
    # Input
    youtube_url: str
    
    # Agent communication
    messages: Annotated[list[BaseMessage], add_messages]
    
    # Extracted data
    video_id: str | None
    metadata: dict | None
    transcript: dict | None
    
    # Workflow control
    current_step: str
    completed_steps: list[str]
    error: str | None
    
    # Output
    summary: str | None


# ============================================================================
# NODE FUNCTIONS
# ============================================================================

def validate_input_node(state: CompleteWorkflowState) -> CompleteWorkflowState:
    """
    Node 1: Validate input URL.
    
    This is a good practice - validate inputs before doing expensive operations.
    """
    url = state["youtube_url"]
    
    # Basic validation
    if not url:
        return {
            **state,
            "error": "No URL provided",
            "current_step": "error"
        }
    
    if "youtube.com" not in url and "youtu.be" not in url:
        return {
            **state,
            "error": "Invalid YouTube URL",
            "current_step": "error"
        }
    
    # URL is valid
    return {
        **state,
        "current_step": "input_validated",
        "completed_steps": state.get("completed_steps", []) + ["validate_input"]
    }


def agent_analysis_node(state: CompleteWorkflowState) -> CompleteWorkflowState:
    """
    Node 2: Run the agent to analyze the video.
    
    This node uses our ReAct agent to:
    - Extract video ID
    - Get metadata
    - Get transcript
    """
    # Create agent
    agent = create_video_agent()
    
    # Create message for agent
    message = HumanMessage(
        content=f"""Analyze this YouTube video: {state['youtube_url']}

Please:
1. Extract the video ID
2. Get the video metadata (title, duration, channel)
3. Try to get the transcript

Provide a brief summary of what you found."""
    )
    
    try:
        # Run agent
        result = agent.invoke({
            "messages": [message]
        })
        
        # Extract information from agent's tool calls
        # (In a real app, you'd parse the tool results more carefully)
        messages = result["messages"]
        
        # Get the agent's final response
        final_message = messages[-1].content if messages else "No response"
        
        return {
            **state,
            "messages": messages,
            "summary": final_message,
            "current_step": "analysis_complete",
            "completed_steps": state.get("completed_steps", []) + ["agent_analysis"]
        }
        
    except Exception as e:
        return {
            **state,
            "error": f"Agent analysis failed: {str(e)}",
            "current_step": "error"
        }


def generate_report_node(state: CompleteWorkflowState) -> CompleteWorkflowState:
    """
    Node 3: Generate final report.
    
    This node creates a formatted report from the analysis.
    """
    # Create a nice formatted report
    report_lines = [
        "="*70,
        "VIDEO ANALYSIS REPORT",
        "="*70,
        "",
        f"URL: {state['youtube_url']}",
        "",
    ]
    
    # Add agent's summary
    if state.get("summary"):
        report_lines.extend([
            "ANALYSIS:",
            "-"*70,
            state["summary"],
            "",
        ])
    
    # Add completed steps
    if state.get("completed_steps"):
        report_lines.extend([
            "COMPLETED STEPS:",
            "-"*70,
        ])
        for step in state["completed_steps"]:
            report_lines.append(f"  ✓ {step}")
        report_lines.append("")
    
    report_lines.append("="*70)
    
    report = "\n".join(report_lines)
    
    return {
        **state,
        "summary": report,
        "current_step": "report_generated",
        "completed_steps": state.get("completed_steps", []) + ["generate_report"]
    }


# ============================================================================
# ROUTING FUNCTIONS
# ============================================================================

def route_after_validation(state: CompleteWorkflowState) -> str:
    """Route after input validation."""
    if state.get("error"):
        return "error_handler"
    return "agent_analysis"


def route_after_analysis(state: CompleteWorkflowState) -> str:
    """Route after agent analysis."""
    if state.get("error"):
        return "error_handler"
    return "generate_report"


def error_handler_node(state: CompleteWorkflowState) -> CompleteWorkflowState:
    """Handle errors gracefully."""
    error_msg = state.get("error", "Unknown error")
    
    report = f"""
{"="*70}
ERROR REPORT
{"="*70}

An error occurred during video analysis:

{error_msg}

URL: {state['youtube_url']}
Step: {state.get('current_step', 'unknown')}

{"="*70}
"""
    
    return {
        **state,
        "summary": report,
        "current_step": "error_handled"
    }


# ============================================================================
# GRAPH CREATION
# ============================================================================

def create_complete_workflow() -> StateGraph:
    """
    Create the complete video analysis workflow.
    
    This workflow has:
    - Input validation
    - Agent-based analysis
    - Report generation
    - Error handling
    
    Returns:
        Compiled graph ready to run
    """
    workflow = StateGraph(CompleteWorkflowState)
    
    # Add nodes
    workflow.add_node("validate_input", validate_input_node)
    workflow.add_node("agent_analysis", agent_analysis_node)
    workflow.add_node("generate_report", generate_report_node)
    workflow.add_node("error_handler", error_handler_node)
    
    # Set entry point
    workflow.set_entry_point("validate_input")
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "validate_input",
        route_after_validation,
        {
            "agent_analysis": "agent_analysis",
            "error_handler": "error_handler"
        }
    )
    
    workflow.add_conditional_edges(
        "agent_analysis",
        route_after_analysis,
        {
            "generate_report": "generate_report",
            "error_handler": "error_handler"
        }
    )
    
    # Terminal edges
    workflow.add_edge("generate_report", END)
    workflow.add_edge("error_handler", END)
    
    return workflow.compile()


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main() -> None:
    """Run the complete workflow example."""
    
    print("\n" + "="*70)
    print("EXAMPLE 4: Complete Video Analysis Workflow")
    print("="*70 + "\n")
    
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY not found in environment")
        print("Please create a .env file with your OpenAI API key")
        return
    
    # Create workflow
    print("🏗️  Building workflow...")
    workflow = create_complete_workflow()
    print("✅ Workflow ready!\n")
    
    # Example URLs to try
    test_urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Valid video
        # "https://example.com/not-youtube",  # Invalid URL (uncomment to test error handling)
    ]
    
    for url in test_urls:
        print(f"🎥 Processing: {url}\n")
        print("-"*70 + "\n")
        
        # Initial state
        initial_state: CompleteWorkflowState = {
            "youtube_url": url,
            "messages": [],
            "video_id": None,
            "metadata": None,
            "transcript": None,
            "current_step": "start",
            "completed_steps": [],
            "error": None,
            "summary": None,
        }
        
        # Stream the workflow
        print("📊 Progress:\n")
        
        for i, state in enumerate(workflow.stream(initial_state), 1):
            node_name = list(state.keys())[0]
            node_state = state[node_name]
            
            current_step = node_state.get("current_step", "unknown")
            
            # Show progress
            if current_step == "input_validated":
                print(f"  {i}. ✅ Input validated")
            elif current_step == "analysis_complete":
                print(f"  {i}. ✅ Agent analysis complete")
            elif current_step == "report_generated":
                print(f"  {i}. ✅ Report generated")
            elif current_step == "error_handled":
                print(f"  {i}. ⚠️  Error handled")
            else:
                print(f"  {i}. 🔄 {current_step}")
        
        # Get final state
        final_state = node_state
        
        # Print report
        print("\n" + final_state.get("summary", "No summary available"))
        print()
    
    print("\n📚 Key Takeaways:")
    print("  1. Combined custom nodes with agent nodes")
    print("  2. Implemented proper error handling")
    print("  3. Validated inputs before expensive operations")
    print("  4. Generated formatted output")
    print("  5. Used streaming for real-time feedback")
    print("\nThis is a production-ready pattern you can use in real applications!")
    print()


if __name__ == "__main__":
    main()
