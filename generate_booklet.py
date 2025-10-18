#!/usr/bin/env python3
"""
Generate booklet from YouTube video
"""

from pathlib import Path
from src.pipeline import generate_booklet

# Video URL
video_url = "https://www.youtube.com/watch?v=Hm-ZIiwiN1o"

print("🚀 Starting booklet generation...")
print(f"Video: {video_url}")
print()

# Generate booklet with sequential context (recommended)
result = generate_booklet(
    input_source=video_url,
    model="gpt-4o",
    provider="openai",
    temperature=0.5,
    use_chapters=True,      # Chapter-based generation
    parallel=False,          # Sequential with context (recommended)
    words_per_section=2000,
)

if result['success']:
    print()
    print("=" * 80)
    print("✅ SUCCESS!")
    print("=" * 80)
    print(f"Video: {result['video_title']}")
    print(f"Video ID: {result['video_id']}")
    print(f"Sections: {result.get('num_sections', 'N/A')}")
    print(f"Length: {result['length']:,} characters")
    print(f"Model: {result['model']}")
    print(f"From cache: {result['from_cache']}")
    print()
    
    # Save to file
    output_file = Path(f"booklet_{result['video_id']}.md")
    output_file.write_text(result['booklet'])
    print(f"📄 Saved to: {output_file}")
    print()
    print("Preview (first 500 chars):")
    print("-" * 80)
    print(result['booklet'][:500])
    print("...")
else:
    print()
    print("=" * 80)
    print("❌ ERROR")
    print("=" * 80)
    print(f"Error: {result.get('error')}")
