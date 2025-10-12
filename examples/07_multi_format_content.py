"""
Example 7: Generate Multiple Content Formats

This example demonstrates how to generate different content types from a video:
- Booklet (comprehensive guide)
- Blog post
- LinkedIn post
- Twitter thread
- Summary

The workflow:
1. Analyze video and get transcript
2. Create chapter-organized markdown
3. Generate different content formats using LLM

Run this example:
    python examples/07_multi_format_content.py
"""

import os
from dotenv import load_dotenv

from src.agents.video import analyze_video
from src.agents.content import create_chapter_markdown, generate_content_from_chapters


def main():
    """Main example function"""
    
    # Load environment variables
    load_dotenv()
    
    print("\n" + "="*70)
    print("🎨 MULTI-FORMAT CONTENT GENERATOR")
    print("="*70 + "\n")
    
    # Example YouTube URL
    youtube_url = "https://www.youtube.com/watch?v=Zyw-YA0k3xo&t=2s"
    
    print(f"🎥 Video URL: {youtube_url}\n")
    
    # Step 1: Analyze the video
    print("📊 Step 1: Analyzing video...")
    print("-" * 70)
    
    video_result = analyze_video(youtube_url)
    
    if not video_result.get('video_id'):
        print("❌ Failed to analyze video")
        return
    
    print(f"✅ Video analyzed!")
    print(f"   Title: {video_result['metadata'].get('title')}")
    
    # Check if we have transcript
    if not video_result.get('transcript') or not video_result['transcript'].get('success'):
        print("\n❌ No transcript available")
        return
    
    # Step 2: Create chapter markdown
    print("\n📝 Step 2: Creating chapter-organized markdown...")
    print("-" * 70)
    
    markdown_result = create_chapter_markdown.func(
        video_id=video_result['video_id'],
        metadata=video_result['metadata'],
        transcript=video_result['transcript']
    )
    
    if not markdown_result.get('success'):
        print("❌ Failed to create chapter markdown")
        return
    
    print(f"✅ Chapter markdown created!")
    print(f"   Chapters: {markdown_result['num_chapters']}")
    
    # Step 3: Generate different content formats
    print("\n✍️  Step 3: Generating content in multiple formats...")
    print("-" * 70)
    
    content_types = ['booklet', 'blog', 'linkedin', 'twitter', 'summary']
    
    for content_type in content_types:
        print(f"\n📄 Generating {content_type}...")
        
        content_result = generate_content_from_chapters(
            chapter_markdown=markdown_result['markdown'],
            video_title=video_result['metadata'].get('title'),
            content_type=content_type,
            model="gpt-4-turbo-preview"  # or "gpt-3.5-turbo" for faster/cheaper
        )
        
        if content_result.get('success'):
            # Save to file
            output_file = f"output_{video_result['video_id']}_{content_type}.md"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"# {video_result['metadata'].get('title')}\n\n")
                f.write(f"**Format:** {content_type.capitalize()}\n\n")
                f.write(f"**Channel:** {video_result['metadata'].get('channel')}\n\n")
                f.write(f"**Original Video:** {youtube_url}\n\n")
                f.write("---\n\n")
                f.write(content_result['content'])
            
            print(f"   ✅ Saved to: {output_file}")
            
            # Show preview
            preview_length = 200
            preview = content_result['content'][:preview_length]
            print(f"   Preview: {preview}...")
        else:
            print(f"   ❌ Failed to generate {content_type}")
    
    print("\n" + "="*70)
    print("✅ All content formats generated successfully!")
    print("="*70 + "\n")


def generate_single_format():
    """
    Example: Generate just one format (faster for testing)
    """
    load_dotenv()
    
    youtube_url = "https://www.youtube.com/watch?v=Zyw-YA0k3xo&t=2s"
    
    # Analyze video
    video_result = analyze_video(youtube_url)
    
    # Create chapter markdown
    markdown_result = create_chapter_markdown.func(
        video_id=video_result['video_id'],
        metadata=video_result['metadata'],
        transcript=video_result['transcript']
    )
    
    # Generate LinkedIn post
    content_result = generate_content_from_chapters(
        chapter_markdown=markdown_result['markdown'],
        video_title=video_result['metadata'].get('title'),
        content_type='linkedin'  # Change to: booklet, blog, twitter, summary
    )
    
    print(content_result['content'])


if __name__ == "__main__":
    # Run the main example (generates all formats)
    main()
    
    # Or run single format for testing
    # generate_single_format()
