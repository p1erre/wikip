#!/usr/bin/env python3
"""
Example usage of the video-to-book pipeline

This demonstrates the main functionality after refactoring.
"""

from pathlib import Path
from src.pipeline import transcript_to_booklet, process_video_with_slides, get_cache_info


def example_1_generate_booklet():
    """Generate a booklet from a YouTube video."""
    print("=" * 80)
    print("EXAMPLE 1: Generate Booklet from YouTube Video")
    print("=" * 80)
    
    # YouTube video URL or ID
    video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    # Generate booklet with sequential context (recommended)
    result = transcript_to_booklet(
        input_source=video_url,
        model="gpt-4o",
        provider="openai",
        temperature=0.5,
        use_chapters=True,      # Chapter-based generation
        parallel=False,          # Sequential with context
        words_per_section=2000,
    )
    
    if result['success']:
        print(f"\n✅ Success!")
        print(f"Video: {result['video_title']}")
        print(f"Sections: {result.get('num_sections', 'N/A')}")
        print(f"Length: {result['length']} characters")
        print(f"From cache: {result['from_cache']}")
        
        # Save to file
        output_file = Path("booklet.md")
        output_file.write_text(result['booklet'])
        print(f"\n📄 Saved to: {output_file}")
    else:
        print(f"\n❌ Error: {result.get('error')}")


def example_2_process_video_with_vision():
    """Process video with slide extraction and vision analysis."""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Process Video with Vision Analysis")
    print("=" * 80)
    
    video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    # Process video (slides + transcript + vision)
    result = process_video_with_slides(
        input_source=video_url,
        skip_vision=False,           # Include vision analysis
        vision_provider="google",    # Use Google Gemini
        vision_model="gemini-1.5-flash",
        force_reprocess=False,       # Use cache if available
    )
    
    print(f"\n✅ Processing complete!")
    print(f"Video ID: {result['video_id']}")
    print(f"Slides: {result['slides']['num_unique_slides']} unique slides")
    print(f"Transcript: {len(result['transcript']['segments'])} segments")
    print(f"Vision analysis: {len(result['vision_analysis'])} slides analyzed")
    print(f"From cache: {result['from_cache']}")


def example_3_cache_control():
    """Demonstrate cache control."""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Cache Control")
    print("=" * 80)
    
    video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    # First run - everything cached
    print("\n1. Using all cached data:")
    result = transcript_to_booklet(
        input_source=video_url,
        use_cached_transcript=True,
        use_cached_metadata=True,
        use_cached_booklet=True,
    )
    print(f"From cache: {result['from_cache']}")
    
    # Second run - regenerate only booklet
    print("\n2. Regenerating booklet only:")
    result = transcript_to_booklet(
        input_source=video_url,
        use_cached_transcript=True,   # Keep transcript
        use_cached_metadata=True,     # Keep metadata
        use_cached_booklet=False,     # Regenerate booklet
        temperature=0.7,              # Try different temperature
    )
    print(f"From cache: {result['from_cache']}")
    
    # Third run - regenerate everything
    print("\n3. Regenerating everything:")
    result = transcript_to_booklet(
        input_source=video_url,
        use_cached_transcript=False,
        use_cached_metadata=False,
        use_cached_booklet=False,
    )
    print(f"From cache: {result['from_cache']}")


def example_4_parallel_vs_sequential():
    """Compare parallel vs sequential generation."""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Parallel vs Sequential Generation")
    print("=" * 80)
    
    video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    # Parallel mode - faster but no context
    print("\n1. Parallel mode (faster, no context):")
    result_parallel = transcript_to_booklet(
        input_source=video_url,
        parallel=True,
        use_cached_booklet=False,
    )
    print(f"✅ Generated {result_parallel.get('num_sections')} sections")
    
    # Sequential mode - slower but with context
    print("\n2. Sequential mode (slower, with context):")
    result_sequential = transcript_to_booklet(
        input_source=video_url,
        parallel=False,
        use_cached_booklet=False,
    )
    print(f"✅ Generated {result_sequential.get('num_sections')} sections")
    
    print("\nRecommendation: Use sequential mode for better coherence")


def example_5_cache_info():
    """Get cache information."""
    print("\n" + "=" * 80)
    print("EXAMPLE 5: Cache Information")
    print("=" * 80)
    
    info = get_cache_info()
    
    print(f"\nCache directory: {info['cache_dir']}")
    print(f"Total videos cached: {info['num_videos']}")
    print(f"Total size: {info['total_size_mb']:.2f} MB")
    
    if info['videos']:
        print("\nCached videos:")
        for video_id, video_info in list(info['videos'].items())[:5]:
            print(f"  - {video_id}: {video_info['size_mb']:.2f} MB")


if __name__ == "__main__":
    import sys
    
    print("Video-to-Book Pipeline Examples")
    print("=" * 80)
    print("\nAvailable examples:")
    print("1. Generate booklet from YouTube video")
    print("2. Process video with vision analysis")
    print("3. Cache control demonstration")
    print("4. Parallel vs sequential generation")
    print("5. Cache information")
    print("\nNote: These are examples. Uncomment the function you want to run.")
    print("=" * 80)
    
    # Uncomment the example you want to run:
    # example_1_generate_booklet()
    # example_2_process_video_with_vision()
    # example_3_cache_control()
    # example_4_parallel_vs_sequential()
    # example_5_cache_info()
    
    print("\n💡 Tip: Edit this file and uncomment an example to run it.")
