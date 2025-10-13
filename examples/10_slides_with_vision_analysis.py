"""
Example: Extract slides and analyze with Gemini Vision

This example demonstrates:
1. Extracting slides from video with robust algorithm
2. Analyzing slides with Gemini 1.5 Flash (ultra-cheap vision LLM)
3. Combining slide visuals with transcript
4. Generating enriched content for book creation
"""
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.slides import extract_slides_robust
from src.vision import analyze_slides_with_vision
from src.tools.youtube_tools import get_youtube_transcript


def main():
    """
    Complete workflow: Video -> Slides -> Vision Analysis -> Enriched Content
    """
    # Configuration
    video_path = ".test_videos/r1qZpYAmqmg_12min.mp4"
    video_id = "r1qZpYAmqmg"  # For transcript
    output_dir = "./output/slides_with_vision"
    
    print("\n" + "="*80)
    print("🎬 COMPLETE SLIDE ANALYSIS WORKFLOW")
    print("="*80)
    print(f"\n📹 Video: {video_path}")
    print(f"📁 Output: {output_dir}\n")
    
    # Step 1: Extract slides
    print("="*80)
    print("STEP 1: Extract Slides with Robust Algorithm")
    print("="*80)
    
    slides_result = extract_slides_robust.func(
        video_path=video_path,
        output_dir=f"{output_dir}/slides",
        fps_sample=2.0,
        build_policy="build_collapse",
        save_keyframes=True,
    )
    
    if not slides_result.get('success'):
        print(f"❌ Error extracting slides: {slides_result.get('error')}")
        return 1
    
    print(f"\n✅ Extracted {slides_result['num_unique_slides']} unique slides")
    print(f"   Saved to: {slides_result['output_dir']}")
    
    # Step 2: Get transcript
    print("\n" + "="*80)
    print("STEP 2: Fetch YouTube Transcript")
    print("="*80)
    
    try:
        transcript_result = get_youtube_transcript(video_id)
        if transcript_result.get('success'):
            transcript = transcript_result['transcript']
            print(f"✅ Got transcript with {len(transcript['segments'])} segments")
        else:
            print("⚠️  No transcript available, continuing without it")
            transcript = None
    except Exception as e:
        print(f"⚠️  Could not fetch transcript: {e}")
        transcript = None
    
    # Step 3: Analyze slides with Gemini Vision
    print("\n" + "="*80)
    print("STEP 3: Analyze Slides with Gemini 1.5 Flash")
    print("="*80)
    print("Using ultra-cheap vision LLM (~$0.002 per video!)\n")
    
    enriched_slides = analyze_slides_with_vision(
        slides_result=slides_result,
        transcript=transcript,
        provider='google',  # Use Gemini
        model='gemini-1.5-flash',  # Cheapest option
        output_path=f"{output_dir}/enriched_slides.json"
    )
    
    print(f"\n✅ Analyzed {len(enriched_slides)} slides with vision LLM")
    
    # Step 4: Display results
    print("\n" + "="*80)
    print("STEP 4: Results Summary")
    print("="*80)
    
    for i, slide in enumerate(enriched_slides[:3], 1):  # Show first 3
        print(f"\n📊 Slide {slide['slide_number']}")
        print(f"   Time: {slide['start_time']:.1f}s - {slide['end_time']:.1f}s")
        print(f"   Duration: {slide['duration']:.1f}s")
        
        analysis = slide.get('vision_analysis', {})
        
        if 'title' in analysis:
            print(f"   Title: {analysis['title']}")
        
        if 'text_content' in analysis and analysis['text_content']:
            print(f"   Content: {len(analysis['text_content'])} bullet points")
            for bullet in analysis['text_content'][:2]:
                print(f"      • {bullet}")
        
        if 'key_concepts' in analysis and analysis['key_concepts']:
            print(f"   Concepts: {', '.join(analysis['key_concepts'][:3])}")
        
        if slide.get('transcript'):
            transcript_preview = slide['transcript'][:100] + "..." if len(slide['transcript']) > 100 else slide['transcript']
            print(f"   Speaker: \"{transcript_preview}\"")
    
    if len(enriched_slides) > 3:
        print(f"\n   ... and {len(enriched_slides) - 3} more slides")
    
    # Step 5: Generate sample content
    print("\n" + "="*80)
    print("STEP 5: Sample Content Generation")
    print("="*80)
    
    print("\nYou can now use this enriched data to:")
    print("  1. Generate book chapters with slide context")
    print("  2. Create study guides with visual references")
    print("  3. Build interactive tutorials")
    print("  4. Extract code examples and diagrams")
    print("  5. Generate quizzes based on slide content")
    
    # Show cost estimate
    print("\n" + "="*80)
    print("💰 Cost Estimate")
    print("="*80)
    print(f"   Slides analyzed: {len(enriched_slides)}")
    print(f"   Model: Gemini 1.5 Flash")
    print(f"   Cost per image: $0.00001875")
    print(f"   Total cost: ${len(enriched_slides) * 0.00001875:.6f}")
    print("   (Practically free! 🎉)")
    
    # Final summary
    print("\n" + "="*80)
    print("✅ WORKFLOW COMPLETE!")
    print("="*80)
    print(f"\nOutput files:")
    print(f"  📁 Slides: {slides_result['output_dir']}")
    print(f"  📄 Metadata: {slides_result['metadata_path']}")
    print(f"  🔍 Vision Analysis: {output_dir}/enriched_slides.json")
    print("\n" + "="*80 + "\n")
    
    return 0


if __name__ == "__main__":
    exit(main())
