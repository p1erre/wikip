"""
Example 8: Extract Slides from Presentation Video

This example demonstrates how to extract slides from a presentation video using:
1. Frame extraction (ffmpeg)
2. Slide change detection (OpenCV)
3. OCR text extraction (Tesseract)
4. Slide-transcript alignment

Prerequisites:
- ffmpeg installed: brew install ffmpeg (Mac) or apt-get install ffmpeg (Linux)
- tesseract installed: brew install tesseract (Mac) or apt-get install tesseract-ocr (Linux)

Run this example:
    python examples/08_extract_slides.py
"""

import os
from pathlib import Path
from dotenv import load_dotenv

from src.agents.video import analyze_video, download_youtube_content
from src.agents.slides import (
    extract_slides,
    analyze_slide_content,
    align_slides_with_transcript,
)


def main():
    """Main example function"""
    
    # Load environment variables
    load_dotenv()
    
    print("\n" + "="*70)
    print("📊 SLIDE EXTRACTION FROM PRESENTATION VIDEO")
    print("="*70 + "\n")
    
    # Example: Use a presentation video URL
    # Replace with any presentation video you want to analyze
    youtube_url = "https://www.youtube.com/watch?v=EXAMPLE"  # Replace with actual URL
    
    # For testing, you can also use a local video file
    use_local_video = True
    local_video_path = "./downloads/video.mp4"  # Update this path
    
    if use_local_video and Path(local_video_path).exists():
        print(f"📹 Using local video: {local_video_path}\n")
        video_path = local_video_path
        video_id = "local_video"
    else:
        print(f"🎥 Video URL: {youtube_url}\n")
        
        # Step 1: Download video
        print("📥 Step 1: Downloading video...")
        print("-" * 70)
        
        video_result = analyze_video(youtube_url)
        
        if not video_result.get('video_id'):
            print("❌ Failed to analyze video")
            return
        
        video_id = video_result['video_id']
        
        # Download the video file
        download_result = download_youtube_content.func(
            video_id=video_id,
            download_video=True,
            output_dir="./downloads"
        )
        
        if not download_result.get('success'):
            print("❌ Failed to download video")
            return
        
        video_path = download_result['file_path']
        print(f"✅ Video downloaded: {video_path}\n")
    
    # Step 2: Extract slides
    print("🖼️  Step 2: Extracting slides from video...")
    print("-" * 70)
    print("This may take a few minutes depending on video length...")
    
    slides_result = extract_slides.func(
        video_path=video_path,
        output_dir=f"./slides/{video_id}",
        fps=0.5,  # Extract 1 frame every 2 seconds
        threshold=0.85  # Similarity threshold for slide detection
    )
    
    if not slides_result.get('success'):
        print(f"❌ Failed to extract slides: {slides_result.get('error')}")
        return
    
    print(f"✅ Extracted {slides_result['num_slides']} unique slides")
    print(f"   Total frames analyzed: {slides_result['num_frames']}")
    print(f"   Output directory: {slides_result['output_dir']}\n")
    
    # Step 3: Analyze slide content with OCR
    print("📝 Step 3: Extracting text from slides using OCR...")
    print("-" * 70)
    
    slides_with_text = []
    for slide in slides_result['slides'][:5]:  # Analyze first 5 slides as example
        print(f"   Analyzing slide {slide['slide_number']}...")
        
        content_result = analyze_slide_content.func(slide['image_path'])
        
        if content_result.get('success'):
            slide_with_content = {
                **slide,
                'text': content_result['text'],
                'confidence': content_result['confidence'],
            }
            slides_with_text.append(slide_with_content)
            
            # Show preview
            text_preview = content_result['text'][:100].replace('\n', ' ')
            print(f"      Text: {text_preview}...")
            print(f"      Confidence: {content_result['confidence']:.1f}%")
    
    print(f"\n✅ Analyzed {len(slides_with_text)} slides\n")
    
    # Step 4: Align slides with transcript (if available)
    if not use_local_video:
        print("🔗 Step 4: Aligning slides with transcript...")
        print("-" * 70)
        
        # Get transcript
        transcript = video_result.get('transcript')
        
        if transcript and transcript.get('success'):
            aligned_result = align_slides_with_transcript.func(
                slides=slides_result['slides'],
                transcript=transcript
            )
            
            if aligned_result.get('success'):
                print(f"✅ Aligned {aligned_result['num_slides']} slides with transcript\n")
                
                # Show example of aligned slide
                if aligned_result['slides']:
                    example_slide = aligned_result['slides'][0]
                    print("   Example aligned slide:")
                    print(f"   Slide {example_slide['slide_number']} at {example_slide['timestamp']}s")
                    print(f"   Duration: {example_slide.get('duration', 'N/A')}s")
                    print(f"   Transcript segments: {example_slide['num_segments']}")
                    transcript_preview = example_slide['transcript'][:150]
                    print(f"   Transcript: {transcript_preview}...")
            else:
                print(f"❌ Failed to align slides: {aligned_result.get('error')}")
        else:
            print("⚠️  No transcript available for alignment")
    
    print("\n" + "="*70)
    print("✅ Slide extraction complete!")
    print("="*70)
    print(f"\nSlides saved to: {slides_result['output_dir']}")
    print(f"Total slides: {slides_result['num_slides']}")
    print("\nNext steps:")
    print("1. Review extracted slides in the output directory")
    print("2. Use slides + transcript to generate enhanced book content")
    print("="*70 + "\n")


def quick_test_with_local_video():
    """
    Quick test with a local video file (no download needed)
    """
    load_dotenv()
    
    video_path = "./test_video.mp4"  # Update this path
    
    if not Path(video_path).exists():
        print(f"❌ Video file not found: {video_path}")
        print("Please provide a valid video path")
        return
    
    print(f"📹 Extracting slides from: {video_path}\n")
    
    # Extract slides
    result = extract_slides.func(
        video_path=video_path,
        output_dir="./test_slides",
        fps=0.5,
        threshold=0.85
    )
    
    if result.get('success'):
        print(f"✅ Found {result['num_slides']} slides")
        print(f"   Saved to: {result['output_dir']}")
        
        # Analyze first slide
        if result['slides']:
            first_slide = result['slides'][0]
            content = analyze_slide_content.func(first_slide['image_path'])
            if content.get('success'):
                print(f"\nFirst slide text:\n{content['text']}")
    else:
        print(f"❌ Error: {result.get('error')}")


if __name__ == "__main__":
    # Run the main example
    main()
    
    # Or run quick test with local video
    # quick_test_with_local_video()
