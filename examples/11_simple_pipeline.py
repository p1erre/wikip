"""
Example: Simple video processing pipeline with caching

This example demonstrates the new simplified API that handles:
- YouTube URLs/IDs and local files
- Automatic caching of all processing steps
- One function call to process everything
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pipeline import process_video, get_cache_info, clear_video_cache


def main():
    """
    Simple pipeline example
    """
    print("\n" + "="*80)
    print("🚀 SIMPLE VIDEO PROCESSING PIPELINE")
    print("="*80)
    
    # Example 1: Process a local video file
    video_input = ".test_videos/r1qZpYAmqmg_12min.mp4"
    
    # Or use YouTube:
    # video_input = "https://youtube.com/watch?v=r1qZpYAmqmg"
    # video_input = "r1qZpYAmqmg"  # Just the ID works too!
    
    print(f"\n📹 Input: {video_input}\n")
    
    # Process video (with caching!)
    print("="*80)
    print("PROCESSING VIDEO")
    print("="*80)
    
    result = process_video(
        video_input,
        force_reprocess=False,  # Use cache if available
        skip_vision=False,      # Include vision analysis
        vision_provider='openrouter',
        vision_model='openai/gpt-4o'
    )
    
    # Display results
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    
    print(f"\n📊 Video ID: {result['video_id']}")
    print(f"📁 Video Type: {result['video_type']}")
    print(f"📄 Video Path: {result['video_path']}")
    
    print(f"\n🎬 Slides:")
    print(f"   Total: {result['slides']['num_unique_slides']}")
    print(f"   From cache: {'✅' if result['from_cache']['slides'] else '❌'}")
    
    if result['transcript']:
        print(f"\n📝 Transcript:")
        print(f"   Segments: {len(result['transcript']['segments'])}")
        print(f"   From cache: {'✅' if result['from_cache']['transcript'] else '❌'}")
    
    if result['vision_analysis']:
        print(f"\n🔍 Vision Analysis:")
        print(f"   Slides analyzed: {len(result['vision_analysis'])}")
        print(f"   From cache: {'✅' if result['from_cache']['vision_analysis'] else '❌'}")
    
    # Show first slide
    if result['vision_analysis']:
        print("\n" + "="*80)
        print("FIRST SLIDE EXAMPLE")
        print("="*80)
        
        slide = result['vision_analysis'][0]
        print(f"\n📊 Slide {slide['slide_number']}")
        print(f"   Time: {slide['start_time']:.1f}s - {slide['end_time']:.1f}s")
        
        analysis = slide.get('vision_analysis', {})
        print(f"   Type: {analysis.get('slide_type', 'N/A')}")
        print(f"   Topic: {analysis.get('main_topic', 'N/A')}")
        
        if analysis.get('key_visual_concepts'):
            print(f"   Visual concepts:")
            for concept in analysis['key_visual_concepts'][:3]:
                print(f"      • {concept}")
    
    # Show cache info
    print("\n" + "="*80)
    print("CACHE STATISTICS")
    print("="*80)
    
    cache_info = get_cache_info()
    print(f"\n📁 Cache directory: {cache_info['cache_dir']}")
    print(f"💾 Cache size: {cache_info['size_mb']:.2f} MB")
    print(f"📊 Cached videos: {cache_info['num_videos']}")
    
    # Run again to demonstrate caching
    print("\n" + "="*80)
    print("RUNNING AGAIN (SHOULD USE CACHE)")
    print("="*80)
    
    result2 = process_video(video_input)
    
    print(f"\n✅ All data loaded from cache:")
    print(f"   Slides: {'✅' if result2['from_cache']['slides'] else '❌'}")
    print(f"   Transcript: {'✅' if result2['from_cache']['transcript'] else '❌'}")
    print(f"   Vision: {'✅' if result2['from_cache']['vision_analysis'] else '❌'}")
    
    print("\n" + "="*80)
    print("✅ COMPLETE!")
    print("="*80)
    print("\nKey benefits:")
    print("  • Works with YouTube URLs, IDs, or local files")
    print("  • Automatic caching of all processing steps")
    print("  • Second run is instant (loads from cache)")
    print("  • Saves API costs (vision analysis cached)")
    print("\n" + "="*80 + "\n")
    
    return 0


if __name__ == "__main__":
    exit(main())
