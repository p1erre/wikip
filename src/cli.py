#!/usr/bin/env python3
"""
Simple CLI for video-to-book pipeline

Usage:
    uv run python -m src.cli generate <video_url> [options]
    uv run python -m src.cli process <video_url> [options]
    uv run python -m src.cli cache-info
    uv run python -m src.cli cache-clear <video_id>
"""

import sys
import argparse
from pathlib import Path
from typing import Optional

from src.pipeline import transcript_to_booklet, process_video_with_slides, get_cache_info, clear_video_cache


def cmd_generate(args):
    """Generate booklet from YouTube video."""
    print("🚀 Generating booklet...")
    print(f"Video: {args.video_url}")
    print(f"Model: {args.provider}/{args.model}")
    print(f"Mode: {'Sequential' if not args.parallel else 'Parallel'}")
    print()
    
    result = transcript_to_booklet(
        input_source=args.video_url,
        model=args.model,
        provider=args.provider,
        temperature=args.temperature,
        use_chapters=not args.no_chapters,
        parallel=args.parallel,
        words_per_section=args.words,
        use_cached_transcript=not args.no_cache,
        use_cached_metadata=not args.no_cache,
        use_cached_booklet=not args.no_cache,
    )
    
    if result['success']:
        print()
        print("=" * 80)
        print("✅ SUCCESS!")
        print("=" * 80)
        print(f"Video: {result['video_title']}")
        print(f"Video ID: {result['video_id']}")
        print(f"Sections: {result.get('num_sections', 'N/A')}")
        print(f"Length: {result['length']:,} characters")
        print(f"From cache: {result['from_cache']}")
        print()
        
        # Determine output file
        if args.output:
            output_file = Path(args.output)
        else:
            output_file = Path(f"booklet_{result['video_id']}.md")
        
        output_file.write_text(result['booklet'])
        print(f"📄 Saved to: {output_file.absolute()}")
        
        if args.preview:
            print()
            print("Preview (first 500 chars):")
            print("-" * 80)
            print(result['booklet'][:500])
            print("...")
        
        return 0
    else:
        print()
        print("=" * 80)
        print("❌ ERROR")
        print("=" * 80)
        print(f"Error: {result.get('error')}")
        return 1


def cmd_process(args):
    """Process video with slides and vision analysis."""
    print("🚀 Processing video...")
    print(f"Video: {args.video_url}")
    print(f"Vision: {'Enabled' if not args.no_vision else 'Disabled'}")
    if not args.no_vision:
        print(f"Vision provider: {args.vision_provider}/{args.vision_model}")
    print()
    
    result = process_video_with_slides(
        input_source=args.video_url,
        force_reprocess=args.force,
        skip_vision=args.no_vision,
        vision_provider=args.vision_provider if not args.no_vision else None,
        vision_model=args.vision_model if not args.no_vision else None,
    )
    
    print()
    print("=" * 80)
    print("✅ PROCESSING COMPLETE")
    print("=" * 80)
    print(f"Video ID: {result['video_id']}")
    print(f"Video type: {result['video_type']}")
    
    if result.get('slides'):
        print(f"Slides: {result['slides']['num_unique_slides']} unique slides")
    
    if result.get('transcript'):
        print(f"Transcript: {len(result['transcript']['segments'])} segments")
    
    if result.get('vision_analysis'):
        print(f"Vision analysis: {len(result['vision_analysis'])} slides analyzed")
    
    print(f"From cache: {result['from_cache']}")
    print(f"Cache dir: {result['cache_dir']}")
    
    return 0


def cmd_cache_info(args):
    """Show cache information."""
    info = get_cache_info()
    
    print("=" * 80)
    print("📦 CACHE INFORMATION")
    print("=" * 80)
    print(f"Cache directory: {info['cache_dir']}")
    print(f"Total videos: {info['num_videos']}")
    print(f"Total size: {info['total_size_mb']:.2f} MB")
    print()
    
    if info['videos']:
        print("Cached videos:")
        print("-" * 80)
        for video_id, video_info in info['videos'].items():
            print(f"  {video_id}")
            print(f"    Size: {video_info['size_mb']:.2f} MB")
            if video_info.get('has_transcript'):
                print(f"    ✓ Transcript")
            if video_info.get('has_slides'):
                print(f"    ✓ Slides")
            if video_info.get('has_vision'):
                print(f"    ✓ Vision analysis")
            if video_info.get('booklets'):
                print(f"    ✓ Booklets: {', '.join(video_info['booklets'])}")
            print()
    else:
        print("No cached videos.")
    
    return 0


def cmd_cache_clear(args):
    """Clear cache for a video."""
    print(f"🗑️  Clearing cache for: {args.video_id}")
    clear_video_cache(args.video_id)
    print("✅ Cache cleared!")
    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Video-to-Book Pipeline CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate booklet from YouTube video
  uv run python -m src.cli generate "https://youtube.com/watch?v=VIDEO_ID"
  
  # Generate with custom model
  uv run python -m src.cli generate VIDEO_URL --model gpt-4o-mini --provider openai
  
  # Generate in parallel mode (faster)
  uv run python -m src.cli generate VIDEO_URL --parallel
  
  # Process video with vision analysis
  uv run python -m src.cli process VIDEO_URL
  
  # Process without vision (faster, cheaper)
  uv run python -m src.cli process VIDEO_URL --no-vision
  
  # Show cache info
  uv run python -m src.cli cache-info
  
  # Clear cache for a video
  uv run python -m src.cli cache-clear VIDEO_ID
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # ========================================================================
    # GENERATE command
    # ========================================================================
    generate_parser = subparsers.add_parser(
        'generate',
        help='Generate booklet from YouTube video'
    )
    generate_parser.add_argument(
        'video_url',
        help='YouTube URL or video ID'
    )
    generate_parser.add_argument(
        '-o', '--output',
        help='Output file path (default: booklet_VIDEO_ID.md)'
    )
    generate_parser.add_argument(
        '--model',
        default='gpt-4o',
        help='LLM model (default: gpt-4o)'
    )
    generate_parser.add_argument(
        '--provider',
        default='openai',
        choices=['openai', 'anthropic', 'openrouter'],
        help='LLM provider (default: openai)'
    )
    generate_parser.add_argument(
        '--temperature',
        type=float,
        default=0.5,
        help='Generation temperature (default: 0.5)'
    )
    generate_parser.add_argument(
        '--words',
        type=int,
        default=2000,
        help='Target words per section (default: 2000)'
    )
    generate_parser.add_argument(
        '--parallel',
        action='store_true',
        help='Use parallel generation (faster but no context)'
    )
    generate_parser.add_argument(
        '--no-chapters',
        action='store_true',
        help='Use single-pass generation instead of chapters'
    )
    generate_parser.add_argument(
        '--no-cache',
        action='store_true',
        help='Disable cache (regenerate everything)'
    )
    generate_parser.add_argument(
        '--preview',
        action='store_true',
        help='Show preview of generated content'
    )
    generate_parser.set_defaults(func=cmd_generate)
    
    # ========================================================================
    # PROCESS command
    # ========================================================================
    process_parser = subparsers.add_parser(
        'process',
        help='Process video with slides and vision analysis'
    )
    process_parser.add_argument(
        'video_url',
        help='YouTube URL or video ID'
    )
    process_parser.add_argument(
        '--no-vision',
        action='store_true',
        help='Skip vision analysis (faster, cheaper)'
    )
    process_parser.add_argument(
        '--vision-provider',
        default='google',
        choices=['google', 'openai', 'openrouter'],
        help='Vision provider (default: google)'
    )
    process_parser.add_argument(
        '--vision-model',
        default='gemini-1.5-flash',
        help='Vision model (default: gemini-1.5-flash)'
    )
    process_parser.add_argument(
        '--force',
        action='store_true',
        help='Force reprocessing (ignore cache)'
    )
    process_parser.set_defaults(func=cmd_process)
    
    # ========================================================================
    # CACHE-INFO command
    # ========================================================================
    cache_info_parser = subparsers.add_parser(
        'cache-info',
        help='Show cache information'
    )
    cache_info_parser.set_defaults(func=cmd_cache_info)
    
    # ========================================================================
    # CACHE-CLEAR command
    # ========================================================================
    cache_clear_parser = subparsers.add_parser(
        'cache-clear',
        help='Clear cache for a video'
    )
    cache_clear_parser.add_argument(
        'video_id',
        help='Video ID to clear from cache'
    )
    cache_clear_parser.set_defaults(func=cmd_cache_clear)
    
    # Parse and execute
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        return 130
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
