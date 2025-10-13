"""
Show the output structure of extract_slides_robust
"""
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from src.agents.slides import extract_slides_robust

def main():
    print("\n" + "="*80)
    print("📊 EXTRACT_SLIDES_ROBUST OUTPUT STRUCTURE")
    print("="*80)
    
    # Use existing test video
    video_path = ".test_videos/r1qZpYAmqmg_12min.mp4"
    output_dir = "./demo_slides_output"
    
    print(f"\n📹 Video: {video_path}")
    print(f"📁 Output: {output_dir}\n")
    
    # Extract slides
    result = extract_slides_robust.func(
        video_path=video_path,
        output_dir=output_dir,
        fps_sample=2.0,
        build_policy="build_collapse",
        save_keyframes=True,
    )
    
    print("\n" + "="*80)
    print("📦 RETURN VALUE (result)")
    print("="*80)
    print(json.dumps({
        k: v for k, v in result.items() if k != 'slides'
    }, indent=2))
    
    print("\n" + "="*80)
    print("📋 SLIDES ARRAY (result['slides'])")
    print("="*80)
    print(f"\nTotal slides: {len(result['slides'])}\n")
    
    # Show first 3 slides in detail
    for i, slide in enumerate(result['slides'][:3], 1):
        print(f"--- Slide {i} ---")
        print(json.dumps(slide, indent=2))
        print()
    
    if len(result['slides']) > 3:
        print(f"... and {len(result['slides']) - 3} more slides\n")
    
    print("="*80)
    print("📊 SUMMARY TABLE")
    print("="*80)
    print(f"\n{'Slide':<8} {'Time':<15} {'Duration':<10} {'Occurs':<8} {'Builds':<8} {'Image'}")
    print("-" * 80)
    
    for slide in result['slides']:
        start = slide['timestamp']
        end = start + slide['duration']
        time_str = f"{start:.1f}s-{end:.1f}s"
        img_name = Path(slide['image_path']).name
        
        print(f"{slide['slide_number']:<8} {time_str:<15} {slide['duration']:<10.1f} "
              f"{slide['num_occurrences']:<8} {slide['num_builds']:<8} {img_name}")
    
    print("\n" + "="*80)
    print("🎯 KEY FIELDS EXPLANATION")
    print("="*80)
    print("""
result = {
    'success': True,                    # Whether extraction succeeded
    'num_unique_slides': 16,            # Total unique slides found
    'num_segments': 16,                 # Total segments (before deduplication)
    'output_dir': './demo_slides_output', # Where slides were saved
    'metadata_path': '...metadata.json', # Path to metadata file
    'slides': [                         # Array of slide objects
        {
            'slide_number': 1,          # Sequential slide number
            'cluster_id': 0,            # Cluster ID (for deduplication)
            'image_path': 'slide_001.jpg', # Path to saved image
            'timestamp': 0.0,           # Start time in seconds
            'duration': 61.44,          # Duration in seconds
            'num_occurrences': 1,       # How many times this slide appears
            'occurrences': [            # List of all occurrences
                {
                    'segment_idx': 0,   # Segment index
                    'start': 0.0,       # Start time
                    'end': 61.44        # End time
                }
            ],
            'num_builds': 0,            # Number of progressive reveals
            'builds': []                # List of build steps (if any)
        },
        # ... more slides
    ]
}
""")
    
    print("="*80)
    print("✅ COMPLETE!")
    print("="*80)
    print(f"\nSlides saved to: {result['output_dir']}")
    print(f"Metadata saved to: {result['metadata_path']}")
    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    main()
