"""
Example 12: Simple Booklet Generation Pipeline

The simplest possible workflow:
1. Get YouTube transcript
2. Generate booklet from transcript
3. Save to file

No slides, no vision analysis - just transcript → booklet.

Run this example:
    python examples/12_simple_booklet_generation.py
"""

import sys
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pipeline import generate_booklet


def main():
    """Main example function"""
    
    # Load environment variables
    load_dotenv()
    
    print("\n" + "="*80)
    print("📚 SIMPLE BOOKLET GENERATION PIPELINE")
    print("="*80 + "\n")
    
    # Use the video from the request
    video_url = "https://www.youtube.com/watch?v=Zyw-YA0k3xo"
    
    print(f"🎥 Video URL: {video_url}\n")
    print("This pipeline will:")
    print("  1. Get transcript from YouTube (cached)")
    print("  2. Generate booklet using LLM (cached)")
    print("  3. Save to markdown file")
    print("\n" + "-"*80 + "\n")
    
    # Run the pipeline
    result = generate_booklet(
        input_source=video_url,
        model="gpt-4o",           # or "gpt-4o-mini" for faster/cheaper
        provider="openai",         # or "anthropic", "openrouter"
        temperature=0.7,           # creative writing
    )
    
    # Check result
    if not result.get('success'):
        print(f"❌ Failed: {result.get('error')}")
        return 1
    
    print("✅ Booklet generated successfully!\n")
    print(f"📊 Statistics:")
    print(f"   Video ID: {result['video_id']}")
    print(f"   Title: {result['video_title']}")
    print(f"   Model: {result['model']}")
    print(f"   Length: {result['length']:,} characters")
    print(f"   From cache:")
    print(f"      Transcript: {'✅' if result['from_cache']['transcript'] else '❌'}")
    print(f"      Booklet: {'✅' if result['from_cache']['booklet'] else '❌'}")
    
    # Save to file
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / f"booklet_{result['video_id']}.md"
    
    output_file.write_text(result['booklet'])
    print(f"\n💾 Saved to: {output_file}")
    
    # Show preview
    print("\n" + "="*80)
    print("📄 BOOKLET PREVIEW (first 1000 characters)")
    print("="*80 + "\n")
    print(result['booklet'][:1000])
    print("\n...")
    print("\n" + "="*80)
    
    # Run again to demonstrate caching
    print("\n🔄 Running again to demonstrate caching...")
    print("-"*80 + "\n")
    
    result2 = generate_booklet(video_url)
    
    print(f"\n✅ Second run complete!")
    print(f"   From cache:")
    print(f"      Transcript: {'✅' if result2['from_cache']['transcript'] else '❌'}")
    print(f"      Booklet: {'✅' if result2['from_cache']['booklet'] else '❌'}")
    print("\n   ⚡ Much faster because everything was cached!")
    
    print("\n" + "="*80 + "\n")
    
    return 0


if __name__ == "__main__":
    exit(main())
