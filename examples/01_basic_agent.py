"""
Example 1: Basic Video Agent

This example demonstrates the simplest way to use the video agent.
It shows how LangGraph handles tool calling automatically.

Learning objectives:
- How to create and run a LangGraph agent
- How the ReAct pattern works (Reasoning + Acting)
- How to interpret agent results
"""

import os
import sys
from pathlib import Path

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from src.agents.video import create_video_agent

# Load environment variables from .env file
load_dotenv()


def main() -> None:
    """Run the basic video agent example."""
    
    print("\n" + "="*70)
    print("EXAMPLE 1: Basic Video Agent")
    print("="*70 + "\n")
    
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY not found in environment")
        print("Please create a .env file with your OpenAI API key")
        return
    
    # Create the agent
    print("📦 Creating video agent...")
    agent = create_video_agent(model="gpt-4-turbo-preview")
    print("✅ Agent created!\n")
    
    # Example YouTube URL
    youtube_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    print(f"🎥 Analyzing video: {youtube_url}\n")
    print("-" * 70)
    
    # Create a message for the agent
    # This is what the user would type
    message = HumanMessage(
        content=f"Please analyze this YouTube video: {youtube_url}. "
                f"Get the metadata and transcript if available."
    )
    
    # Run the agent
    # The agent will:
    # 1. Read the message
    # 2. Decide what tools to call
    # 3. Call the tools
    # 4. Process the results
    # 5. Respond to the user
    print("🤖 Agent is working...\n")
    
    result = agent.invoke({
        "messages": [message]
    })
    
    print("-" * 70)
    print("\n📊 RESULTS\n")
    
    # The result contains all messages in the conversation
    # This includes:
    # - The user's message
    # - The agent's thoughts
    # - Tool calls
    # - Tool results
    # - The agent's final response
    
    messages = result["messages"]
    
    print(f"Total messages in conversation: {len(messages)}\n")
    
    # Let's look at each message
    for i, msg in enumerate(messages, 1):
        print(f"\nMessage {i}:")
        print(f"  Type: {type(msg).__name__}")
        
        # Different message types have different attributes
        if hasattr(msg, "content"):
            content = msg.content
            # Truncate long content
            if isinstance(content, str) and len(content) > 200:
                content = content[:200] + "..."
            print(f"  Content: {content}")
        
        if hasattr(msg, "name"):
            print(f"  Tool: {msg.name}")
    
    # The last message is usually the agent's final response
    final_response = messages[-1]
    
    print("\n" + "="*70)
    print("AGENT'S FINAL RESPONSE")
    print("="*70 + "\n")
    print(final_response.content)
    print("\n" + "="*70 + "\n")
    
    # Key takeaways
    print("📚 Key Takeaways:")
    print("  1. The agent automatically decided which tools to call")
    print("  2. LangGraph handled all the tool calling for us")
    print("  3. The conversation history is preserved in messages")
    print("  4. We can see the agent's reasoning process")
    print()


if __name__ == "__main__":
    main()
