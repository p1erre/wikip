#!/usr/bin/env python3
"""
Simple CLI runner for testing tools and agents.

This is a lightweight CLI for:
- Running individual tools with arguments
- Testing agent workflows
- Debugging and development
- Scripting and automation

Design Philosophy:
- Minimal dependencies (stdlib + argparse)
- JSON output option for scripting
- Clear, simple interface
- No fancy UI (that's for interactive.py)

Usage:
    python -m src.cli.runner tools extract-id <url>
    python -m src.cli.runner tools get-metadata <video_id>
    python -m src.cli.runner agent analyze <url>

For junior developers:
- This uses argparse (Python's built-in CLI library)
- Each tool/agent is a subcommand
- --json flag makes output machine-readable
- Exit codes: 0 = success, 1 = error
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.tools.youtube_tools import (
    extract_video_id_from_url,
    get_video_metadata,
    get_youtube_transcript,
    download_youtube_content,
)


def print_result(result: dict[str, Any], as_json: bool = False) -> None:
    """
    Print result in human-readable or JSON format.
    
    Args:
        result: Dictionary to print
        as_json: If True, print as JSON. Otherwise, pretty-print.
    """
    if as_json:
        print(json.dumps(result, indent=2, default=str))
    else:
        # Human-readable output
        if result.get("success"):
            print("✅ Success!")
            for key, value in result.items():
                if key != "success":
                    if isinstance(value, (list, dict)):
                        print(f"\n{key}:")
                        print(json.dumps(value, indent=2, default=str))
                    else:
                        print(f"  {key}: {value}")
        else:
            print("❌ Error!")
            print(f"  {result.get('error', 'Unknown error')}")
            if "suggestion" in result:
                print(f"  💡 {result['suggestion']}")


# ============================================================================
# TOOL COMMANDS
# ============================================================================

def cmd_extract_id(args: argparse.Namespace) -> int:
    """Extract video ID from YouTube URL."""
    result = extract_video_id_from_url.invoke({"youtube_url": args.url})
    print_result(result, args.json)
    return 0 if result.get("success") else 1


def cmd_get_metadata(args: argparse.Namespace) -> int:
    """Get video metadata."""
    result = get_video_metadata.invoke({"video_id": args.video_id})
    print_result(result, args.json)
    return 0 if result.get("success") else 1


def cmd_get_transcript(args: argparse.Namespace) -> int:
    """Get video transcript."""
    result = get_youtube_transcript.invoke({"video_id": args.video_id})
    print_result(result, args.json)
    return 0 if result.get("success") else 1


def cmd_download(args: argparse.Namespace) -> int:
    """Download video or audio."""
    result = download_youtube_content.invoke({
        "video_id": args.video_id,
        "download_video": args.video,
        "output_dir": args.output_dir,
    })
    print_result(result, args.json)
    return 0 if result.get("success") else 1


# ============================================================================
# AGENT COMMANDS
# ============================================================================

def cmd_agent_analyze(args: argparse.Namespace) -> int:
    """
    Run the video analysis agent.
    
    Note: This requires API keys to be set in .env
    """
    try:
        from src.agents.video_agent import analyze_video
        
        print(f"🤖 Analyzing video: {args.url}")
        print("(This may take a moment...)\n")
        
        result = analyze_video(args.url, model=args.model)
        
        if args.json:
            # JSON output
            output = {
                "success": True,
                "youtube_url": result["youtube_url"],
                "video_id": result.get("video_id"),
                "metadata": result.get("metadata"),
                "transcript": result.get("transcript"),
                "summary": result.get("summary"),
            }
            print(json.dumps(output, indent=2, default=str))
        else:
            # Human-readable output
            print("="*70)
            print("ANALYSIS COMPLETE")
            print("="*70)
            print(f"\n{result.get('summary', 'No summary available')}\n")
        
        return 0
        
    except Exception as e:
        error_result = {
            "success": False,
            "error": str(e),
            "suggestion": "Make sure your .env file has OPENAI_API_KEY or ANTHROPIC_API_KEY set"
        }
        print_result(error_result, args.json)
        return 1


# ============================================================================
# MAIN CLI SETUP
# ============================================================================

def create_parser() -> argparse.ArgumentParser:
    """
    Create the argument parser with all subcommands.
    
    This uses argparse's subparser feature to create a hierarchy:
    - Main command (runner.py)
      - tools (subcommand group)
        - extract-id (specific tool)
        - get-metadata (specific tool)
        - etc.
      - agent (subcommand group)
        - analyze (specific agent)
    """
    parser = argparse.ArgumentParser(
        description="Video-to-Book CLI - Run tools and agents independently",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract video ID from URL
  python -m src.cli.runner tools extract-id "https://youtube.com/watch?v=abc123"
  
  # Get metadata as JSON (for scripting)
  python -m src.cli.runner tools get-metadata abc123 --json
  
  # Get transcript
  python -m src.cli.runner tools get-transcript abc123
  
  # Download audio only
  python -m src.cli.runner tools download abc123
  
  # Download video
  python -m src.cli.runner tools download abc123 --video
  
  # Run full agent analysis
  python -m src.cli.runner agent analyze "https://youtube.com/watch?v=abc123"

For the interactive Claude-style CLI (future):
  python -m src.cli.interactive
        """
    )
    
    # Create subparsers for main command groups
    subparsers = parser.add_subparsers(
        title="commands",
        description="Available command groups",
        dest="command",
        required=True
    )
    
    # ========================================================================
    # TOOLS SUBCOMMAND GROUP
    # ========================================================================
    
    tools_parser = subparsers.add_parser(
        "tools",
        help="Run individual tools",
        description="Run YouTube tools independently for testing"
    )
    
    tools_subparsers = tools_parser.add_subparsers(
        title="tools",
        description="Available tools",
        dest="tool",
        required=True
    )
    
    # Tool: extract-id
    extract_id_parser = tools_subparsers.add_parser(
        "extract-id",
        help="Extract video ID from YouTube URL"
    )
    extract_id_parser.add_argument("url", help="YouTube URL")
    extract_id_parser.add_argument("--json", action="store_true", help="Output as JSON")
    extract_id_parser.set_defaults(func=cmd_extract_id)
    
    # Tool: get-metadata
    metadata_parser = tools_subparsers.add_parser(
        "get-metadata",
        help="Get video metadata"
    )
    metadata_parser.add_argument("video_id", help="YouTube video ID")
    metadata_parser.add_argument("--json", action="store_true", help="Output as JSON")
    metadata_parser.set_defaults(func=cmd_get_metadata)
    
    # Tool: get-transcript
    transcript_parser = tools_subparsers.add_parser(
        "get-transcript",
        help="Get video transcript/captions"
    )
    transcript_parser.add_argument("video_id", help="YouTube video ID")
    transcript_parser.add_argument("--json", action="store_true", help="Output as JSON")
    transcript_parser.set_defaults(func=cmd_get_transcript)
    
    # Tool: download
    download_parser = tools_subparsers.add_parser(
        "download",
        help="Download video or audio"
    )
    download_parser.add_argument("video_id", help="YouTube video ID")
    download_parser.add_argument(
        "--video",
        action="store_true",
        help="Download video (default: audio only)"
    )
    download_parser.add_argument(
        "--output-dir",
        default="./downloads",
        help="Output directory (default: ./downloads)"
    )
    download_parser.add_argument("--json", action="store_true", help="Output as JSON")
    download_parser.set_defaults(func=cmd_download)
    
    # ========================================================================
    # AGENT SUBCOMMAND GROUP
    # ========================================================================
    
    agent_parser = subparsers.add_parser(
        "agent",
        help="Run AI agents",
        description="Run complete agent workflows"
    )
    
    agent_subparsers = agent_parser.add_subparsers(
        title="agents",
        description="Available agents",
        dest="agent_cmd",
        required=True
    )
    
    # Agent: analyze
    analyze_parser = agent_subparsers.add_parser(
        "analyze",
        help="Analyze a YouTube video with AI agent"
    )
    analyze_parser.add_argument("url", help="YouTube URL to analyze")
    analyze_parser.add_argument(
        "--model",
        default="gpt-4-turbo-preview",
        help="LLM model to use (default: gpt-4-turbo-preview)"
    )
    analyze_parser.add_argument("--json", action="store_true", help="Output as JSON")
    analyze_parser.set_defaults(func=cmd_agent_analyze)
    
    return parser


def main() -> int:
    """
    Main entry point for the CLI.
    
    Returns:
        Exit code (0 = success, 1 = error)
    """
    parser = create_parser()
    args = parser.parse_args()
    
    # Call the appropriate function based on the subcommand
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
