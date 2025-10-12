#!/usr/bin/env python3
"""
Cache management CLI

Simple commands to inspect and manage the video cache.
"""

import argparse
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.cache import get_cache


def cmd_info(args):
    """Show cache information."""
    cache = get_cache(args.cache_dir)
    info = cache.get_cache_info()
    
    print("\n" + "="*60)
    print("CACHE INFORMATION")
    print("="*60 + "\n")
    
    print(f"Cache directory: {info['cache_dir']}")
    print(f"\nTotal size: {info['size_mb']['total']:.2f} MB")
    print(f"  - Metadata: {info['size_mb']['metadata']:.2f} MB")
    print(f"  - Transcripts: {info['size_mb']['transcripts']:.2f} MB")
    print(f"  - Audio: {info['size_mb']['audio']:.2f} MB")
    
    print(f"\nCached videos:")
    print(f"  - Metadata: {info['cached_videos']['metadata']} videos")
    print(f"  - Transcripts: {info['cached_videos']['transcripts']} videos")
    print(f"  - Audio files: {info['cached_videos']['audio']} files")
    
    print()
    return 0


def cmd_list(args):
    """List cached videos."""
    cache = get_cache(args.cache_dir)
    
    # Get all cached video IDs
    metadata_files = list(cache.metadata_dir.glob("*.json"))
    
    if not metadata_files:
        print("No cached videos found.")
        return 0
    
    print("\n" + "="*60)
    print(f"CACHED VIDEOS ({len(metadata_files)})")
    print("="*60 + "\n")
    
    for metadata_file in sorted(metadata_files):
        video_id = metadata_file.stem
        
        # Load metadata
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        # Check what's cached
        transcript_sources = cache.get_available_transcripts(video_id)
        has_audio = cache.get_audio_path(video_id) is not None
        
        print(f"📹 {video_id}")
        print(f"   Title: {metadata.get('title', 'Unknown')}")
        print(f"   Duration: {metadata.get('duration', 0)} seconds")
        print(f"   Cached: metadata", end="")
        if transcript_sources:
            print(f", transcript ({', '.join(transcript_sources)})", end="")
        if has_audio:
            print(", audio", end="")
        print("\n")
    
    return 0


def cmd_clear(args):
    """Clear cache."""
    cache = get_cache(args.cache_dir)
    
    if args.video_id:
        # Clear specific video
        print(f"Clearing cache for video: {args.video_id}")
        cache.clear_video(args.video_id)
        print("✅ Done!")
    else:
        # Clear all
        if not args.force:
            response = input("Are you sure you want to clear the entire cache? (yes/no): ")
            if response.lower() != "yes":
                print("Cancelled.")
                return 1
        
        print("Clearing entire cache...")
        cache.clear_all()
        print("✅ Done!")
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Manage video cache",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show cache info
  python -m src.cli.cache_manager info
  
  # List cached videos
  python -m src.cli.cache_manager list
  
  # Clear specific video
  python -m src.cli.cache_manager clear --video-id abc123
  
  # Clear entire cache
  python -m src.cli.cache_manager clear --force
        """
    )
    
    parser.add_argument(
        "--cache-dir",
        default=".cache",
        help="Cache directory (default: .cache)"
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Info command
    info_parser = subparsers.add_parser("info", help="Show cache information")
    info_parser.set_defaults(func=cmd_info)
    
    # List command
    list_parser = subparsers.add_parser("list", help="List cached videos")
    list_parser.set_defaults(func=cmd_list)
    
    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Clear cache")
    clear_parser.add_argument("--video-id", help="Clear specific video")
    clear_parser.add_argument("--force", action="store_true", help="Don't ask for confirmation")
    clear_parser.set_defaults(func=cmd_clear)
    
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
