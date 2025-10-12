"""
Example 6: Create Chapter-Organized Markdown

This example demonstrates how to use the create_chapter_markdown tool to
generate a markdown document organized by YouTube chapters with full transcript content.

The tool:
1. Takes video metadata (with chapters) and transcript (with timestamps)
2. Matches transcript segments to chapters using timestamps
3. Creates a markdown document with each chapter containing its full transcript

Run this example:
    python examples/06_chapter_markdown.py
"""

import os
from dotenv import load_dotenv

from src.agents.video import analyze_video
from src.agents.content import create_chapter_markdown


def main():
    """Main example function"""
    
    # Load environment variables
    load_dotenv()
    
    print("\n" + "="*70)
    print("📝 CHAPTER MARKDOWN GENERATOR")
    print("="*70 + "\n")
    
    # Example YouTube URL - use a video with chapters for best results
    youtube_url = "https://www.youtube.com/watch?v=Zyw-YA0k3xo&t=2s"
    
    print(f"🎥 Video URL: {youtube_url}\n")
    
    # Step 1: Analyze the video
    print("📊 Step 1: Analyzing video (getting metadata and transcript)...")
    print("-" * 70)
    
    video_result = analyze_video(youtube_url)
    
    if not video_result.get('video_id'):
        print("❌ Failed to analyze video")
        return
    
    print(f"✅ Video analyzed successfully!")
    print(f"   Title: {video_result['metadata'].get('title')}")
    print(f"   Duration: {video_result['metadata'].get('duration')} seconds")
    
    # Check if we have transcript
    if not video_result.get('transcript') or not video_result['transcript'].get('success'):
        print("\n❌ No transcript available for this video")
        return
    
    print(f"   Transcript segments: {video_result['transcript'].get('num_segments')}")
    
    # Check for chapters
    has_chapters = 'chapters' in video_result['metadata'] and video_result['metadata']['chapters']
    if has_chapters:
        num_chapters = len(video_result['metadata']['chapters'])
        print(f"   Chapters: {num_chapters} found ✨")
    else:
        print(f"   Chapters: None (will use full video as one chapter)")
    
    # Step 2: Create chapter markdown
    print("\n📝 Step 2: Creating chapter-organized markdown...")
    print("-" * 70)
    
    # Call the tool directly
    markdown_result = create_chapter_markdown.func(
        video_id=video_result['video_id'],
        metadata=video_result['metadata'],
        transcript=video_result['transcript']
    )
    
    if not markdown_result.get('success'):
        print("❌ Failed to create chapter markdown")
        return
    
    print("✅ Chapter markdown created successfully!\n")
    print(f"   Chapters processed: {markdown_result['num_chapters']}")
    print(f"   Total length: {markdown_result['total_length']} characters")
    
    # Step 3: Save to file
    output_file = f"transcript_{video_result['video_id']}_chapters.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(markdown_result['markdown'])
    
    print(f"\n💾 Saved to: {output_file}")
    
    # Show preview
    print("\n" + "="*70)
    print("📄 PREVIEW (first 1000 characters)")
    print("="*70 + "\n")
    print(markdown_result['markdown'][:1000] + "...")
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    main()
