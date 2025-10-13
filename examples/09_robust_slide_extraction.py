"""
Example 9: Robust Slide Extraction with Progressive Reveal Detection

This example demonstrates the advanced slide extraction algorithm that:
1. Handles progressive reveals (builds) intelligently
2. Uses motion masking to ignore presenter movements
3. Performs global deduplication across the entire video
4. Supports perceptual hashing and SSIM verification

The algorithm supports two build policies:
- build_collapse: Treat all build steps as one logical slide (keep final frame)
- build_preserve: Emit a sub-slide for each build step

Prerequisites:
- pip install opencv-python pillow imagehash scikit-image numpy

Run this example:
    python examples/09_robust_slide_extraction.py
"""

import os
from pathlib import Path
from dotenv import load_dotenv

from src.agents.slides import extract_slides_robust


def main():
    """Main example function"""
    
    # Load environment variables
    load_dotenv()
    
    print("\n" + "="*70)
    print("🚀 ROBUST SLIDE EXTRACTION WITH BUILD DETECTION")
    print("="*70 + "\n")
    
    # For testing, use a local video file
    local_video_path = "./downloads/video.mp4"  # Update this path
    
    if not Path(local_video_path).exists():
        print(f"❌ Video file not found: {local_video_path}")
        print("Please provide a valid video path")
        return
    
    print(f"📹 Using video: {local_video_path}\n")
    
    # Example 1: Build Collapse (default)
    # This keeps the final fully revealed version of each slide
    print("=" * 70)
    print("Example 1: Build Collapse Policy")
    print("=" * 70)
    print("This policy treats all build steps as one logical slide.")
    print("Only the final fully revealed frame is saved.\n")
    
    result_collapse = extract_slides_robust.func(
        video_path=local_video_path,
        output_dir="./slides_robust/collapse",
        fps_sample=2.0,  # Sample 2 frames per second
        build_policy="build_collapse",
        presenter_roi=None,  # Set to (0.72, 0.72, 0.98, 0.98) if presenter in corner
        save_keyframes=True,
    )
    
    if result_collapse.get('success'):
        print(f"✅ Extraction complete!")
        print(f"   Unique slides: {result_collapse['num_unique_slides']}")
        print(f"   Total segments: {result_collapse['num_segments']}")
        print(f"   Output: {result_collapse['output_dir']}")
        print(f"   Metadata: {result_collapse['metadata_path']}\n")
        
        # Show details of first few slides
        if result_collapse['slides']:
            print("   First 3 slides:")
            for slide in result_collapse['slides'][:3]:
                print(f"   - Slide {slide['slide_number']}: "
                      f"t={slide['timestamp']:.1f}s, "
                      f"duration={slide['duration']:.1f}s, "
                      f"builds={slide['num_builds']}, "
                      f"occurrences={slide['num_occurrences']}")
    else:
        print(f"❌ Error: {result_collapse.get('error')}")
        return
    
    print("\n" + "=" * 70)
    print("Example 2: Build Preserve Policy")
    print("=" * 70)
    print("This policy creates sub-slides for each build step.")
    print("Each progressive reveal gets its own slide.\n")
    
    result_preserve = extract_slides_robust.func(
        video_path=local_video_path,
        output_dir="./slides_robust/preserve",
        fps_sample=2.0,
        build_policy="build_preserve",
        presenter_roi=None,
        save_keyframes=True,
    )
    
    if result_preserve.get('success'):
        print(f"✅ Extraction complete!")
        print(f"   Unique slides: {result_preserve['num_unique_slides']}")
        print(f"   Total segments: {result_preserve['num_segments']}")
        print(f"   Output: {result_preserve['output_dir']}")
        print(f"   Metadata: {result_preserve['metadata_path']}\n")
        
        # Compare with collapse policy
        print(f"   Comparison:")
        print(f"   - Collapse policy: {result_collapse['num_unique_slides']} slides")
        print(f"   - Preserve policy: {result_preserve['num_unique_slides']} slides")
        print(f"   - Difference: {result_preserve['num_unique_slides'] - result_collapse['num_unique_slides']} "
              f"additional sub-slides from builds")
    else:
        print(f"❌ Error: {result_preserve.get('error')}")
    
    print("\n" + "=" * 70)
    print("Example 3: With Presenter Masking")
    print("=" * 70)
    print("Mask the presenter region to avoid false slide changes.\n")
    
    # Example: Mask bottom-right corner where presenter might appear
    result_masked = extract_slides_robust.func(
        video_path=local_video_path,
        output_dir="./slides_robust/masked",
        fps_sample=2.0,
        build_policy="build_collapse",
        presenter_roi=(0.72, 0.72, 0.98, 0.98),  # Bottom-right 26% of frame
        save_keyframes=True,
    )
    
    if result_masked.get('success'):
        print(f"✅ Extraction complete with presenter masking!")
        print(f"   Unique slides: {result_masked['num_unique_slides']}")
        print(f"   Presenter ROI: (0.72, 0.72, 0.98, 0.98)")
        print(f"   Output: {result_masked['output_dir']}\n")
    else:
        print(f"❌ Error: {result_masked.get('error')}")
    
    print("\n" + "=" * 70)
    print("✅ All examples complete!")
    print("=" * 70)
    print("\nKey Features Demonstrated:")
    print("1. ✅ Progressive reveal detection (builds)")
    print("2. ✅ Motion masking for stable regions")
    print("3. ✅ Global deduplication across video")
    print("4. ✅ Perceptual hashing + SSIM verification")
    print("5. ✅ Two build policies (collapse vs preserve)")
    print("\nNext Steps:")
    print("1. Review extracted slides in output directories")
    print("2. Check slides_metadata.json for detailed information")
    print("3. Integrate with OCR and transcript alignment")
    print("4. Use slides for enhanced book content generation")
    print("=" * 70 + "\n")


def compare_algorithms():
    """
    Compare the robust algorithm with the basic algorithm
    """
    load_dotenv()
    
    video_path = "./downloads/video.mp4"
    
    if not Path(video_path).exists():
        print(f"❌ Video file not found: {video_path}")
        return
    
    print("\n" + "="*70)
    print("🔬 ALGORITHM COMPARISON")
    print("="*70 + "\n")
    
    # Import basic algorithm
    from src.agents.slides import extract_slides
    
    # Run basic algorithm
    print("Running basic algorithm...")
    basic_result = extract_slides.func(
        video_path=video_path,
        output_dir="./slides_comparison/basic",
        fps=0.5,
        threshold=0.85,
        detect_progressive=True
    )
    
    # Run robust algorithm
    print("Running robust algorithm...")
    robust_result = extract_slides_robust.func(
        video_path=video_path,
        output_dir="./slides_comparison/robust",
        fps_sample=2.0,
        build_policy="build_collapse",
    )
    
    # Compare results
    print("\n" + "="*70)
    print("COMPARISON RESULTS")
    print("="*70)
    
    if basic_result.get('success') and robust_result.get('success'):
        print(f"\nBasic Algorithm:")
        print(f"  - Slides detected: {basic_result['num_slides']}")
        print(f"  - Frames analyzed: {basic_result['num_frames']}")
        
        print(f"\nRobust Algorithm:")
        print(f"  - Unique slides: {robust_result['num_unique_slides']}")
        print(f"  - Total segments: {robust_result['num_segments']}")
        print(f"  - Clusters: {len(robust_result['clusters'])}")
        
        print(f"\nKey Differences:")
        print(f"  - Robust algorithm found {robust_result['num_unique_slides']} truly unique slides")
        print(f"  - Basic algorithm found {basic_result['num_slides']} slides (may include duplicates)")
        print(f"  - Deduplication removed {robust_result['num_segments'] - robust_result['num_unique_slides']} duplicate segments")
        
        print("\nAdvantages of Robust Algorithm:")
        print("  ✅ Better handling of progressive reveals")
        print("  ✅ Global deduplication across entire video")
        print("  ✅ Motion masking for presenter movements")
        print("  ✅ More accurate with perceptual hashing")
        print("  ✅ Configurable build policies")
    else:
        print("❌ One or both algorithms failed")
        if not basic_result.get('success'):
            print(f"Basic: {basic_result.get('error')}")
        if not robust_result.get('success'):
            print(f"Robust: {robust_result.get('error')}")
    
    print("="*70 + "\n")


def advanced_usage():
    """
    Demonstrate advanced usage with custom configuration
    """
    load_dotenv()
    
    video_path = "./downloads/video.mp4"
    
    if not Path(video_path).exists():
        print(f"❌ Video file not found: {video_path}")
        return
    
    print("\n" + "="*70)
    print("⚙️  ADVANCED CONFIGURATION")
    print("="*70 + "\n")
    
    # Direct usage of SlideDeduplicator for fine-grained control
    from src.agents.slides.slideseg import SlideDeduplicator
    import cv2
    import json
    
    print("Creating custom deduplicator with fine-tuned parameters...\n")
    
    dedup = SlideDeduplicator(
        fps_sample=2.0,
        build_policy="build_collapse",
        presenter_roi=(0.72, 0.72, 0.98, 0.98),
        # Custom thresholds
        ham_keep=8,          # More strict for "same" detection
        ham_new=20,          # More lenient for "new" detection
        ssim_keep=0.95,      # Higher similarity required
        ssim_build=0.98,     # Very strict for build detection
        confirm_k=4,         # Require 4 consecutive mismatches
        min_seg_secs=3.0,    # Minimum 3 seconds per segment
    )
    
    print("Processing video with custom configuration...")
    result = dedup.process_video(video_path)
    
    print(f"\n✅ Processing complete!")
    print(f"   Segments: {len(result['segments'])}")
    print(f"   Clusters: {len(result['clusters'])}")
    
    # Analyze build information
    total_builds = sum(len(seg.get('builds', [])) for seg in result['segments'])
    print(f"   Total build steps detected: {total_builds}")
    
    # Save detailed results
    output_dir = Path("./slides_robust/advanced")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save keyframes for unique slides
    for cid, cluster in enumerate(result["clusters"]):
        rep_idx = cluster["rep_idx"]
        segment = dedup.segments[rep_idx]
        
        slide_path = output_dir / f"slide_{cid+1:03d}.jpg"
        cv2.imwrite(str(slide_path), segment.keyframe)
    
    # Save detailed metadata
    metadata = {
        "config": {
            "fps_sample": dedup.cfg.fps_sample,
            "build_policy": dedup.cfg.build_policy,
            "ham_keep": dedup.cfg.ham_keep,
            "ham_new": dedup.cfg.ham_new,
            "ssim_keep": dedup.cfg.ssim_keep,
            "ssim_build": dedup.cfg.ssim_build,
            "confirm_k": dedup.cfg.confirm_k,
            "min_seg_secs": dedup.cfg.min_seg_secs,
        },
        "results": {
            "num_segments": len(result['segments']),
            "num_clusters": len(result['clusters']),
            "total_builds": total_builds,
        },
        "segments": result['segments'],
        "clusters": result['clusters'],
    }
    
    metadata_path = output_dir / "detailed_metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n   Saved to: {output_dir}")
    print(f"   Metadata: {metadata_path}")
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    # Run the main example
    main()
    
    # Uncomment to run comparison
    # compare_algorithms()
    
    # Uncomment to run advanced usage
    # advanced_usage()
