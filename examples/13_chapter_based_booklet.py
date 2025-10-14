"""
Example 13: Chapter-Based Booklet Generation

Demonstrates the chapter-based approach for generating comprehensive booklets.
This is the RECOMMENDED approach for videos longer than 15-20 minutes.

Benefits:
- Much more detailed output (15k-30k+ words vs 2k-5k)
- Better structure with clear sections
- Each section gets focused attention
- Higher quality content

Run this example:
    python examples/13_chapter_based_booklet.py
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
    print("📚 CHAPTER-BASED BOOKLET GENERATION")
    print("="*80 + "\n")
    
    # Use the 47-minute video
    video_url = "https://www.youtube.com/watch?v=Zyw-YA0k3xo"
    
    print(f"🎥 Video URL: {video_url}\n")
    print("This pipeline will:")
    print("  1. Get transcript from YouTube (cached)")
    print("  2. Get video metadata for chapters (cached)")
    print("  3. Generate detailed booklet section-by-section")
    print("  4. Each section: ~2000 words of comprehensive content")
    print("\n" + "-"*80 + "\n")
    
    # Run the chapter-based pipeline
    print("⚠️  This will take several minutes as it generates each section...")
    print("    (But it will be cached for instant future access!)\n")
    
    result = generate_booklet(
        input_source=video_url,
        model="gpt-4o",
        provider="openai",
        use_chapters=True,          # Chapter-based (recommended)
        words_per_section=2000,     # Target words per section
        temperature=0.7,
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
    print(f"   Sections: {result.get('num_sections', 'N/A')}")
    print(f"   Length: {result['length']:,} characters (~{result['length']//5:,} words)")
    print(f"   From cache:")
    print(f"      Transcript: {'✅' if result['from_cache']['transcript'] else '❌'}")
    print(f"      Booklet: {'✅' if result['from_cache']['booklet'] else '❌'}")
    
    # Save to file
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / f"booklet_{result['video_id']}_chapters.md"
    
    output_file.write_text(result['booklet'])
    print(f"\n💾 Saved to: {output_file}")
    
    # Show preview
    print("\n" + "="*80)
    print("📄 BOOKLET PREVIEW (first 2000 characters)")
    print("="*80 + "\n")
    print(result['booklet'][:2000])
    print("\n...")
    
    # Show table of contents
    lines = result['booklet'].split('\n')
    toc_start = None
    toc_end = None
    for i, line in enumerate(lines):
        if '## Table of Contents' in line:
            toc_start = i
        elif toc_start and line.startswith('---'):
            toc_end = i
            break
    
    if toc_start and toc_end:
        print("\n" + "="*80)
        print("📑 TABLE OF CONTENTS")
        print("="*80 + "\n")
        print('\n'.join(lines[toc_start:toc_end]))
    
    print("\n" + "="*80)
    print("✅ COMPLETE!")
    print("="*80)
    print(f"\nFull booklet saved to: {output_file}")
    print(f"This comprehensive booklet covers the entire {result.get('num_sections', 'N/A')}-section video in detail!")
    
    return 0


if __name__ == "__main__":
    exit(main())
