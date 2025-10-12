#!/usr/bin/env python3
"""
Test the simplified video workflow.

This demonstrates the new deterministic workflow approach.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from src.agents.video import analyze_video_workflow, get_transcript

load_dotenv()


def main():
    # Test URL from user's request
    test_url = "https://www.youtube.com/watch?v=Zyw-YA0k3xo&t=2s"
    
    print("\n" + "="*70)
    print("TESTING SIMPLIFIED VIDEO WORKFLOW")
    print("="*70 + "\n")
    
    print(f"URL: {test_url}\n")
    
    # Run the workflow (will try YouTube transcript first)
    print("Running workflow...\n")
    result = analyze_video_workflow(test_url, force_download=False)
    
    # Display results
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70 + "\n")
    
    print(f"Video ID: {result['video_id']}")
    print(f"Steps completed: {', '.join(result['steps_completed'])}")
    
    if result['errors']:
        print(f"\nErrors encountered:")
        for error in result['errors']:
            print(f"  - {error}")
    
    if result['metadata']:
        print(f"\n📹 Metadata:")
        print(f"  Title: {result['metadata'].get('title')}")
        print(f"  Duration: {result['metadata'].get('duration')} seconds")
        print(f"  Channel: {result['metadata'].get('channel')}")
        print(f"  Views: {result['metadata'].get('view_count'):,}")
    
    if result['transcript']:
        print(f"\n📝 Transcript:")
        print(f"  Segments: {result['transcript'].get('num_segments')}")
        print(f"  Duration: {result['transcript'].get('total_duration'):.1f} seconds")
        print(f"  Source: {result['transcript'].get('source', 'youtube')}")
        
        # Show first 3 segments
        if result['transcript'].get('segments'):
            print(f"\n  First 3 segments:")
            for i, seg in enumerate(result['transcript']['segments'][:3], 1):
                print(f"    {i}. [{seg['start']:.1f}s] {seg['text'][:80]}...")
    
    if result['audio_path']:
        print(f"\n🎵 Audio downloaded: {result['audio_path']}")
    
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    main()
