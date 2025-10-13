"""
Test script for robust slide extraction
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.agents.slides import extract_slides_robust

def main():
    video_path = ".test_videos/r1qZpYAmqmg_12min.mp4"
    
    print("\n" + "="*70)
    print("🚀 TESTING ROBUST SLIDE EXTRACTION")
    print("="*70)
    print(f"\n📹 Video: {video_path}\n")
    
    # Test 1: Build Collapse (default)
    print("=" * 70)
    print("Test 1: Build Collapse Policy")
    print("=" * 70)
    print("Extracting slides with build_collapse policy...")
    print("This keeps the final fully revealed version of each slide.\n")
    
    result = extract_slides_robust.func(
        video_path=video_path,
        output_dir="./test_slides_robust/collapse",
        fps_sample=2.0,
        build_policy="build_collapse",
        save_keyframes=True,
    )
    
    if result.get('success'):
        print(f"\n✅ Extraction complete!")
        print(f"   Unique slides: {result['num_unique_slides']}")
        print(f"   Total segments: {result['num_segments']}")
        print(f"   Output: {result['output_dir']}")
        print(f"   Metadata: {result['metadata_path']}")
        
        # Show slide details
        if result['slides']:
            print(f"\n📊 Slide Details:")
            for slide in result['slides'][:5]:  # Show first 5
                print(f"   Slide {slide['slide_number']:2d}: "
                      f"t={slide['timestamp']:6.1f}s, "
                      f"dur={slide['duration']:5.1f}s, "
                      f"builds={slide['num_builds']}, "
                      f"occurs={slide['num_occurrences']}x")
            
            if len(result['slides']) > 5:
                print(f"   ... and {len(result['slides']) - 5} more slides")
        
        # Show cluster information
        print(f"\n🔄 Deduplication Results:")
        print(f"   Total segments found: {result['num_segments']}")
        print(f"   Unique slides (clusters): {result['num_unique_slides']}")
        print(f"   Duplicates removed: {result['num_segments'] - result['num_unique_slides']}")
        
        # Show slides with multiple occurrences
        multi_occur = [s for s in result['slides'] if s['num_occurrences'] > 1]
        if multi_occur:
            print(f"\n📍 Slides appearing multiple times:")
            for slide in multi_occur:
                print(f"   Slide {slide['slide_number']}: appears {slide['num_occurrences']}x")
                for occ in slide['occurrences']:
                    print(f"      - at {occ['start']:.1f}s - {occ['end']:.1f}s")
        
        # Show slides with builds
        with_builds = [s for s in result['slides'] if s['num_builds'] > 0]
        if with_builds:
            print(f"\n🎯 Slides with progressive reveals (builds):")
            for slide in with_builds[:3]:  # Show first 3
                print(f"   Slide {slide['slide_number']}: {slide['num_builds']} build steps")
                for i, build in enumerate(slide['builds'], 1):
                    print(f"      Step {i}: t={build['t']:.1f}s, "
                          f"added={build['add_ratio']:.2%}, "
                          f"removed={build['rem_ratio']:.2%}")
        
        print("\n" + "="*70)
        print("✅ Test Complete!")
        print("="*70)
        print(f"\nResults saved to: {result['output_dir']}")
        print(f"Check slides_metadata.json for complete details")
        print("="*70 + "\n")
        
    else:
        print(f"\n❌ Error: {result.get('error')}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
