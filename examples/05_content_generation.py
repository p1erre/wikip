"""
Example 5: Content Generation from Video

This example demonstrates how to use the content generation agent to create
high-quality posts or booklets from YouTube videos, organized by chapters.

The workflow:
1. Analyze a YouTube video (get metadata and transcript)
2. Use the content agent to generate structured content
3. The agent automatically organizes content by YouTube chapters
4. Output is a well-formatted markdown document

Run this example:
    python examples/05_content_generation.py
"""

import os
from dotenv import load_dotenv

from src.agents.video import analyze_video
from src.agents.content import generate_content


def main():
    """Main example function"""
    
    # Load environment variables
    load_dotenv()
    
    # Check if API key is set
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY not set in environment")
        print("Please create a .env file with your API key")
        return
    
    print("\n" + "="*70)
    print("📚 CONTENT GENERATION AGENT EXAMPLE")
    print("="*70 + "\n")
    
    # Example YouTube URL - replace with any video you want to analyze
    # This example uses a video that likely has chapters
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
    print(f"   Channel: {video_result['metadata'].get('channel')}")
    print(f"   Duration: {video_result['metadata'].get('duration')} seconds")
    
    # Check if we have transcript
    if not video_result.get('transcript') or not video_result['transcript'].get('success'):
        print("\n❌ No transcript available for this video")
        print("   Try a different video with captions/transcript")
        return
    
    print(f"   Transcript segments: {video_result['transcript'].get('num_segments')}")
    
    # Step 2: Generate content
    print("\n✍️  Step 2: Generating content from video...")
    print("-" * 70)
    print("This may take a minute as the AI analyzes and writes the content...\n")
    
    content_result = generate_content(
        video_id=video_result['video_id'],
        metadata=video_result['metadata'],
        transcript=video_result['transcript'],
        content_type="booklet"  # Options: 'post', 'booklet', 'article'
    )
    
    if not content_result.get('success'):
        print("❌ Failed to generate content")
        return
    
    print("✅ Content generated successfully!\n")
    
    # Step 3: Display the generated content
    print("="*70)
    print("📄 GENERATED CONTENT")
    print("="*70 + "\n")
    
    print(content_result['content'])
    
    print("\n" + "="*70)
    
    # Save to markdown file by default
    output_file = f"output_{video_result['video_id']}_booklet.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"# {video_result['metadata'].get('title')}\n\n")
        f.write(f"**Channel:** {video_result['metadata'].get('channel')}\n\n")
        f.write(f"**Original Video:** {youtube_url}\n\n")
        f.write("---\n\n")
        f.write(content_result['content'])
    
    print(f"\n💾 Content saved to markdown file: {output_file}")
    print("\n" + "="*70 + "\n")


def example_with_different_styles():
    """
    Example showing how to generate different content types
    """
    print("\n" + "="*70)
    print("🎨 DIFFERENT CONTENT STYLES")
    print("="*70 + "\n")
    
    # This is a more advanced example showing different content types
    youtube_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    # Analyze once
    video_result = analyze_video(youtube_url)
    
    if not video_result.get('video_id') or not video_result.get('transcript'):
        print("❌ Could not analyze video")
        return
    
    content_types = ['post', 'booklet', 'article']
    
    for content_type in content_types:
        print(f"\n📝 Generating {content_type.upper()}...")
        
        content_result = generate_content(
            video_id=video_result['video_id'],
            metadata=video_result['metadata'],
            transcript=video_result['transcript'],
            content_type=content_type
        )
        
        if content_result.get('success'):
            print(f"✅ {content_type.capitalize()} generated!")
            
            # Save each type
            output_file = f"output_{video_result['video_id']}_{content_type}.md"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(content_result['content'])
            print(f"   Saved to: {output_file}")


if __name__ == "__main__":
    # Run the main example
    main()
    
    # Uncomment to try different content styles
    # example_with_different_styles()
