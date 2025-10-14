"""
Show the exact prompt being sent to the LLM for booklet generation
"""
import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.processing.content.generation import format_transcript_for_llm, _build_booklet_prompt


def main():
    # Load cached transcript
    transcript_file = Path(".cache/videos/Zyw-YA0k3xo/transcript_youtube.json")
    
    if not transcript_file.exists():
        print("❌ No cached transcript found. Run the pipeline first.")
        return 1
    
    print("\n" + "="*80)
    print("📝 BOOKLET GENERATION PROMPT")
    print("="*80 + "\n")
    
    # Load transcript
    with open(transcript_file) as f:
        transcript = json.load(f)
    
    # Format transcript
    formatted_transcript = format_transcript_for_llm(transcript)
    
    print(f"📊 Transcript Stats:")
    print(f"   Segments: {len(transcript.get('segments', []))}")
    print(f"   Raw text length: {sum(len(s.get('text', '')) for s in transcript.get('segments', []))} chars")
    print(f"   Formatted length: {len(formatted_transcript):,} chars")
    print(f"   Estimated tokens: ~{len(formatted_transcript) // 4:,}")
    
    # Build prompt
    video_title = "Forward Deployed Engineer Model in AI"
    video_url = "https://youtube.com/watch?v=Zyw-YA0k3xo"
    
    prompt = _build_booklet_prompt(
        transcript_text=formatted_transcript,
        video_title=video_title,
        video_url=video_url
    )
    
    print(f"\n📏 Full Prompt Stats:")
    print(f"   Total length: {len(prompt):,} chars")
    print(f"   Estimated tokens: ~{len(prompt) // 4:,}")
    
    # Show first part of prompt
    print("\n" + "="*80)
    print("📄 PROMPT PREVIEW (first 2000 chars)")
    print("="*80 + "\n")
    print(prompt[:2000])
    print("\n... [middle section with full transcript] ...")
    
    # Show last part of prompt
    print("\n" + "="*80)
    print("📄 PROMPT END (last 500 chars)")
    print("="*80 + "\n")
    print(prompt[-500:])
    
    # Option to save full prompt
    print("\n" + "="*80)
    save = input("\n💾 Save full prompt to file? (y/n): ").lower().strip()
    
    if save == 'y':
        output_file = Path("tmp/full_prompt.txt")
        output_file.write_text(prompt)
        print(f"✅ Saved to: {output_file}")
        print(f"   Size: {len(prompt):,} chars")
    
    return 0


if __name__ == "__main__":
    exit(main())
